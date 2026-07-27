import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Self

from minilucene.errors import WriterAlreadyOpenError
from minilucene.index.memory import RamIndexBuilder
from minilucene.reader import IndexReader
from minilucene.storage.image import SegmentImage
from minilucene.storage.live_docs import LiveDocsStore
from minilucene.storage.manifest import (
    Manifest,
    ManifestStore,
    SegmentCommit,
)
from minilucene.storage.segment_store import (
    SegmentDescriptor,
    SegmentStore,
)

if TYPE_CHECKING:
    from minilucene.index.directory import Index


@dataclass(frozen=True, slots=True)
class FlushPolicy:
    max_documents: int = 1_000
    max_postings: int = 100_000

    def __post_init__(self) -> None:
        if self.max_documents <= 0 or self.max_postings <= 0:
            raise ValueError("flush thresholds must be positive")


class IndexWriter:
    def __init__(
        self,
        index: "Index",
        *,
        flush_policy: FlushPolicy | None = None,
    ) -> None:
        self.index = index
        self.flush_policy = flush_policy or FlushPolicy()
        self._lock_path = Path(index.path) / ".writer.lock"
        self._closed = False
        try:
            descriptor = os.open(
                self._lock_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
        except FileExistsError as error:
            raise WriterAlreadyOpenError(
                f"writer already open for index: {index.path}"
            ) from error
        try:
            payload = json.dumps(
                {"pid": os.getpid()}, separators=(",", ":")
            ).encode("utf-8")
            os.write(descriptor, payload)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        manifest = index.manifest()
        self._segment_store = SegmentStore(index.path)
        self._manifest_store = ManifestStore(index.path)
        self._live_docs_store = LiveDocsStore(index.path)
        self._buffer = RamIndexBuilder(index.schema)
        self._buffer_live_docs: set[int] = set()
        self._segment_generations = list(manifest.segment_generations)
        self._next_segment_generation = (
            manifest.next_segment_generation
        )
        self._live_docs: dict[int, frozenset[int]] = {}
        self._live_docs_metadata: dict[
            int, tuple[int, str] | None
        ] = {}
        for segment_commit in manifest.segments:
            image = self._segment_store.open(
                segment_commit.segment_generation,
                index.schema.fingerprint,
            )
            if segment_commit.live_docs_generation is None:
                mask = frozenset(range(image.max_doc))
                metadata = None
            else:
                mask = self._live_docs_store.read(
                    segment_generation=segment_commit.segment_generation,
                    live_docs_generation=(
                        segment_commit.live_docs_generation
                    ),
                    expected_checksum=(
                        segment_commit.live_docs_checksum or ""
                    ),
                    max_doc=image.max_doc,
                )
                metadata = (
                    segment_commit.live_docs_generation,
                    segment_commit.live_docs_checksum or "",
                )
            self._live_docs[segment_commit.segment_generation] = mask
            self._live_docs_metadata[
                segment_commit.segment_generation
            ] = metadata
        self._dirty_live_docs: set[int] = set()

    @property
    def segment_generations(self) -> tuple[int, ...]:
        return tuple(self._segment_generations)

    @property
    def buffered_document_count(self) -> int:
        return self._buffer.document_count

    @property
    def buffered_posting_count(self) -> int:
        return self._buffer.posting_count

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("writer is closed")

    def add_document(self, **values: object) -> int:
        self._ensure_open()
        prepared = self._buffer.prepare_document(values)
        if self.buffered_document_count and (
            self.buffered_document_count
            >= self.flush_policy.max_documents
            or self.buffered_posting_count
            >= self.flush_policy.max_postings
        ):
            self.flush()
        doc_id = self._buffer.add_prepared(prepared)
        self._buffer_live_docs.add(doc_id)
        return doc_id

    def flush(self) -> SegmentDescriptor | None:
        self._ensure_open()
        if self.buffered_document_count == 0:
            return None
        compacted = RamIndexBuilder(self.index.schema)
        for doc_id in sorted(self._buffer_live_docs):
            compacted.add_document(dict(self._buffer.documents[doc_id]))
        if compacted.document_count == 0:
            self._buffer = RamIndexBuilder(self.index.schema)
            self._buffer_live_docs = set()
            return None
        generation = self._next_segment_generation
        while self._segment_store.generation_exists(generation):
            generation += 1
        image = SegmentImage.from_memory_segment(
            generation=generation,
            schema_fingerprint=self.index.schema.fingerprint,
            segment=compacted.freeze(generation=0),
        )
        descriptor = self._segment_store.publish(image)
        self._segment_generations.append(generation)
        self._live_docs[generation] = frozenset(range(image.max_doc))
        self._live_docs_metadata[generation] = None
        self._next_segment_generation = generation + 1
        self._buffer = RamIndexBuilder(self.index.schema)
        self._buffer_live_docs = set()
        return descriptor

    def refresh(self) -> IndexReader:
        self._ensure_open()
        self.flush()
        segments = tuple(
            self._segment_store.open(
                generation, self.index.schema.fingerprint
            )
            for generation in self._segment_generations
        )
        live_docs = tuple(
            self._live_docs[generation]
            for generation in self._segment_generations
        )
        return IndexReader(
            self.index.schema,
            segments,
            live_docs,
            commit_generation=None,
        )

    def delete_by_term(self, field: str, term: str) -> int:
        self._ensure_open()
        if field not in self.index.schema:
            raise ValueError(f"unknown field: {field}")
        if not self.index.schema[field].indexed:
            raise ValueError(f"field is not indexed: {field}")
        if not isinstance(term, str) or not term:
            raise ValueError("delete term must be a non-empty string")

        derived_masks = dict(self._live_docs)
        changed_generations: set[int] = set()
        deleted = 0
        for generation in self._segment_generations:
            image = self._segment_store.open(
                generation, self.index.schema.fingerprint
            )
            matches = {
                posting.doc_id
                for posting in image.postings.get(field, {}).get(term, ())
            }
            current = derived_masks[generation]
            removed = current & matches
            if removed:
                derived_masks[generation] = current - removed
                changed_generations.add(generation)
                deleted += len(removed)

        buffered_matches = (
            self._buffer.matching_doc_ids(field, term)
            & self._buffer_live_docs
        )
        next_buffer_live_docs = self._buffer_live_docs - buffered_matches
        deleted += len(buffered_matches)

        self._live_docs = derived_masks
        self._dirty_live_docs.update(changed_generations)
        self._buffer_live_docs = next_buffer_live_docs
        return deleted

    def commit(self) -> Manifest:
        self._ensure_open()
        self.flush()
        for generation in self._segment_generations:
            self._segment_store.open(
                generation, self.index.schema.fingerprint
            )
        current = self.index.manifest()
        pending_metadata = dict(self._live_docs_metadata)
        segment_commits: list[SegmentCommit] = []
        for generation in self._segment_generations:
            image = self._segment_store.open(
                generation, self.index.schema.fingerprint
            )
            live_docs = self._live_docs[generation]
            metadata = pending_metadata[generation]
            if live_docs != frozenset(range(image.max_doc)):
                if generation in self._dirty_live_docs:
                    live_generation = (
                        metadata[0] + 1 if metadata is not None else 1
                    )
                    while self._live_docs_store.generation_exists(
                        generation, live_generation
                    ):
                        live_generation += 1
                    descriptor = self._live_docs_store.publish(
                        segment_generation=generation,
                        live_docs_generation=live_generation,
                        max_doc=image.max_doc,
                        live_docs=live_docs,
                    )
                    metadata = (
                        descriptor.live_docs_generation,
                        descriptor.checksum,
                    )
                    pending_metadata[generation] = metadata
                if metadata is None:
                    raise RuntimeError(
                        "deleted segment lacks live-doc metadata"
                    )
                segment_commits.append(
                    SegmentCommit(
                        segment_generation=generation,
                        live_docs_generation=metadata[0],
                        live_docs_checksum=metadata[1],
                    )
                )
            else:
                segment_commits.append(
                    SegmentCommit(segment_generation=generation)
                )

        manifest = Manifest.next_from(
            current,
            segments=tuple(segment_commits),
            next_segment_generation=self._next_segment_generation,
        )
        self._manifest_store.write_atomic(manifest)
        self._live_docs_metadata = pending_metadata
        self._dirty_live_docs.clear()
        return manifest

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._lock_path.unlink()
        except FileNotFoundError:
            pass

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

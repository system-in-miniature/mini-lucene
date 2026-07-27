import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Self

from minilucene.errors import WriterAlreadyOpenError
from minilucene.index.memory import RamIndexBuilder
from minilucene.storage.image import SegmentImage
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
        self._buffer = RamIndexBuilder(index.schema)
        self._segment_generations = list(manifest.segment_generations)
        self._next_segment_generation = (
            manifest.next_segment_generation
        )

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
        return self._buffer.add_prepared(prepared)

    def flush(self) -> SegmentDescriptor | None:
        self._ensure_open()
        if self.buffered_document_count == 0:
            return None
        generation = self._next_segment_generation
        image = SegmentImage.from_memory_segment(
            generation=generation,
            schema_fingerprint=self.index.schema.fingerprint,
            segment=self._buffer.freeze(generation=0),
        )
        descriptor = self._segment_store.publish(image)
        self._segment_generations.append(generation)
        self._next_segment_generation += 1
        self._buffer = RamIndexBuilder(self.index.schema)
        return descriptor

    def commit(self) -> Manifest:
        self._ensure_open()
        self.flush()
        for generation in self._segment_generations:
            self._segment_store.open(
                generation, self.index.schema.fingerprint
            )
        current = self.index.manifest()
        manifest = Manifest.next_from(
            current,
            segments=tuple(
                SegmentCommit(segment_generation=generation)
                for generation in self._segment_generations
            ),
            next_segment_generation=self._next_segment_generation,
        )
        self._manifest_store.write_atomic(manifest)
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

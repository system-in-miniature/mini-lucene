from collections.abc import Mapping
from typing import Self

from minilucene.errors import AlreadyClosedError
from minilucene.index.postings import Posting
from minilucene.query.model import Query
from minilucene.schema import Schema
from minilucene.search.collector import TopDocs
from minilucene.search.reader import ReaderView
from minilucene.search.searcher import IndexSearcher
from minilucene.snapshot import ReaderSnapshot, SegmentSnapshot
from minilucene.storage.image import SegmentImage


class IndexReader(ReaderView):
    def __init__(
        self,
        schema: Schema,
        segments: tuple[SegmentImage, ...],
        live_docs: tuple[frozenset[int], ...] | None = None,
        *,
        commit_generation: int | None = None,
    ) -> None:
        super().__init__(  # type: ignore[arg-type]
            schema,
            segments,
            live_docs,
        )
        masks = (
            live_docs
            if live_docs is not None
            else tuple(
                frozenset(range(segment.max_doc))
                for segment in segments
            )
        )
        self.snapshot = ReaderSnapshot(
            schema_fingerprint=schema.fingerprint,
            segments=tuple(
                SegmentSnapshot(
                    generation=segment.generation,
                    image=segment,
                    live_docs=mask,
                )
                for segment, mask in zip(
                    segments, masks, strict=True
                )
            ),
            corpus_stats=self.corpus_stats,
            commit_generation=commit_generation,
        )
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise AlreadyClosedError("reader is closed")

    def search(self, query: Query, *, top_k: int = 10) -> TopDocs:
        self._ensure_open()
        return IndexSearcher(self).search(query, top_k=top_k)

    def document(self, doc_id: int) -> Mapping[str, str]:
        self._ensure_open()
        return super().stored_fields(doc_id)

    def stored_fields(self, doc_id: int) -> Mapping[str, str]:
        self._ensure_open()
        return super().stored_fields(doc_id)

    def postings(self, field: str, term: str) -> tuple[Posting, ...]:
        self._ensure_open()
        return super().postings(field, term)

    def field_length(self, field: str, doc_id: int) -> int:
        self._ensure_open()
        return super().field_length(field, doc_id)

    def close(self) -> None:
        self._closed = True

    def __enter__(self) -> Self:
        self._ensure_open()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

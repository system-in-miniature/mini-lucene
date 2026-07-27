from collections.abc import Mapping
from dataclasses import dataclass

from minilucene.index.postings import MemorySegment, Posting
from minilucene.query.match import match_query
from minilucene.query.model import Query
from minilucene.schema import Schema
from minilucene.search.stats import CorpusStats, freeze_corpus_stats


@dataclass(frozen=True, slots=True)
class DocAddress:
    segment_generation: int
    local_doc_id: int


class ReaderView:
    def __init__(
        self,
        schema: Schema,
        segments: tuple[MemorySegment, ...],
        live_docs: tuple[frozenset[int], ...] | None = None,
        *,
        max_prefix_expansions: int = 1_024,
    ) -> None:
        self.schema = schema
        self.segments = segments
        self.max_prefix_expansions = max_prefix_expansions
        if live_docs is None:
            live_docs = tuple(
                frozenset(range(segment.max_doc)) for segment in segments
            )
        if len(live_docs) != len(segments):
            raise ValueError("live-doc masks must match segments")
        for segment, mask in zip(segments, live_docs, strict=True):
            if any(doc_id < 0 or doc_id >= segment.max_doc for doc_id in mask):
                raise ValueError("live-doc ID outside segment")
        self._live_docs = live_docs
        bases: list[int] = []
        next_base = 0
        for segment in segments:
            bases.append(next_base)
            next_base += segment.max_doc
        self._bases = tuple(bases)
        self.max_doc = next_base
        self.live_doc_ids = frozenset(
            base + local_doc_id
            for base, mask in zip(self._bases, live_docs, strict=True)
            for local_doc_id in mask
        )
        self.corpus_stats = self._build_corpus_stats()

    @property
    def num_live_docs(self) -> int:
        return len(self.live_doc_ids)

    def _resolve(self, doc_id: int) -> tuple[int, MemorySegment, int]:
        if doc_id < 0 or doc_id >= self.max_doc:
            raise IndexError(f"document ID outside reader: {doc_id}")
        for index in range(len(self.segments) - 1, -1, -1):
            base = self._bases[index]
            if doc_id >= base:
                return index, self.segments[index], doc_id - base
        raise IndexError(f"document ID outside reader: {doc_id}")

    def address(self, doc_id: int) -> DocAddress:
        _, segment, local_doc_id = self._resolve(doc_id)
        return DocAddress(segment.generation, local_doc_id)

    def postings(self, field: str, term: str) -> tuple[Posting, ...]:
        result: list[Posting] = []
        for base, segment, live in zip(
            self._bases, self.segments, self._live_docs, strict=True
        ):
            for posting in segment.postings.get(field, {}).get(term, ()):
                if posting.doc_id in live:
                    result.append(
                        Posting(
                            doc_id=base + posting.doc_id,
                            term_frequency=posting.term_frequency,
                            positions=posting.positions,
                        )
                    )
        return tuple(result)

    def terms_with_prefix(
        self, field: str, prefix: str
    ) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    term
                    for segment in self.segments
                    for term in segment.postings.get(field, {})
                    if term.startswith(prefix)
                }
            )
        )

    def has_phrase(
        self,
        field: str,
        terms: tuple[str, ...],
        query_positions: tuple[int, ...],
        doc_id: int,
    ) -> bool:
        segment_index, segment, local_doc_id = self._resolve(doc_id)
        if local_doc_id not in self._live_docs[segment_index]:
            return False
        term_positions: list[set[int]] = []
        for term in terms:
            posting = next(
                (
                    item
                    for item in segment.postings.get(field, {}).get(term, ())
                    if item.doc_id == local_doc_id
                ),
                None,
            )
            if posting is None:
                return False
            term_positions.append(set(posting.positions))
        return any(
            all(
                start + query_position in positions
                for query_position, positions in zip(
                    query_positions, term_positions, strict=True
                )
            )
            for start in term_positions[0]
        )

    def stored_fields(self, doc_id: int) -> Mapping[str, str]:
        index, segment, local_doc_id = self._resolve(doc_id)
        if local_doc_id not in self._live_docs[index]:
            raise KeyError(f"document is deleted: {doc_id}")
        return segment.stored_documents[local_doc_id]

    def field_length(self, field: str, doc_id: int) -> int:
        index, segment, local_doc_id = self._resolve(doc_id)
        if local_doc_id not in self._live_docs[index]:
            raise KeyError(f"document is deleted: {doc_id}")
        return segment.field_lengths.get(
            field, (0,) * segment.max_doc
        )[local_doc_id]

    def match(self, query: Query) -> set[int]:
        return match_query(self, query)

    def _build_corpus_stats(self) -> CorpusStats:
        doc_frequencies: dict[tuple[str, str], int] = {}
        for segment, live in zip(
            self.segments, self._live_docs, strict=True
        ):
            for field, terms in segment.postings.items():
                for term, postings in terms.items():
                    frequency = sum(
                        posting.doc_id in live for posting in postings
                    )
                    key = (field, term)
                    doc_frequencies[key] = (
                        doc_frequencies.get(key, 0) + frequency
                    )

        length_sums: dict[str, int] = {}
        length_counts: dict[str, int] = {}
        for segment, live in zip(
            self.segments, self._live_docs, strict=True
        ):
            for field, lengths in segment.field_lengths.items():
                for local_doc_id in live:
                    length = lengths[local_doc_id]
                    if length > 0:
                        length_sums[field] = length_sums.get(field, 0) + length
                        length_counts[field] = length_counts.get(field, 0) + 1
        averages = {
            field: length_sums[field] / count
            for field, count in length_counts.items()
        }
        return freeze_corpus_stats(
            live_doc_count=len(self.live_doc_ids),
            doc_frequencies=doc_frequencies,
            average_field_lengths=averages,
        )

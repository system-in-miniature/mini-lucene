from collections.abc import Mapping
from dataclasses import dataclass
from itertools import pairwise
from types import MappingProxyType

from minilucene.index.postings import MemorySegment, Posting


def _freeze_string_mapping(
    values: Mapping[str, str],
) -> Mapping[str, str]:
    return MappingProxyType(dict(sorted(values.items())))


@dataclass(frozen=True, slots=True)
class SegmentImage:
    generation: int
    schema_fingerprint: str
    stored_documents: Mapping[int, Mapping[str, str]]
    postings: Mapping[str, Mapping[str, tuple[Posting, ...]]]
    field_lengths: Mapping[str, tuple[int, ...]]

    def __post_init__(self) -> None:
        if self.generation <= 0:
            raise ValueError("segment generation must be positive")
        if not self.schema_fingerprint:
            raise ValueError("schema fingerprint must be non-empty")

        stored = {
            doc_id: _freeze_string_mapping(document)
            for doc_id, document in sorted(self.stored_documents.items())
        }
        if tuple(stored) != tuple(range(len(stored))):
            raise ValueError("stored document IDs must be dense")
        max_doc = len(stored)

        frozen_postings: dict[
            str, Mapping[str, tuple[Posting, ...]]
        ] = {}
        for field, terms in sorted(self.postings.items()):
            frozen_terms: dict[str, tuple[Posting, ...]] = {}
            for term, term_postings in sorted(terms.items()):
                term_postings = tuple(term_postings)
                doc_ids = tuple(
                    posting.doc_id for posting in term_postings
                )
                if any(
                    right <= left for left, right in pairwise(doc_ids)
                ):
                    raise ValueError(
                        "posting doc IDs must be strictly increasing"
                    )
                for posting in term_postings:
                    if not 0 <= posting.doc_id < max_doc:
                        raise ValueError("posting doc ID outside segment")
                    if posting.term_frequency <= 0:
                        raise ValueError("term frequency must be positive")
                    if posting.positions:
                        if posting.term_frequency != len(posting.positions):
                            raise ValueError(
                                "term frequency must equal position count"
                            )
                        if any(
                            right <= left
                            for left, right in pairwise(posting.positions)
                        ):
                            raise ValueError(
                                "positions must be strictly increasing"
                            )
                frozen_terms[term] = term_postings
            frozen_postings[field] = MappingProxyType(frozen_terms)

        lengths: dict[str, tuple[int, ...]] = {}
        for field, values in sorted(self.field_lengths.items()):
            values = tuple(values)
            if len(values) != max_doc or any(value < 0 for value in values):
                raise ValueError(
                    "field lengths must match documents and be non-negative"
                )
            lengths[field] = values

        object.__setattr__(
            self, "stored_documents", MappingProxyType(stored)
        )
        object.__setattr__(
            self, "postings", MappingProxyType(frozen_postings)
        )
        object.__setattr__(
            self, "field_lengths", MappingProxyType(lengths)
        )

    @property
    def max_doc(self) -> int:
        return len(self.stored_documents)

    @classmethod
    def from_memory_segment(
        cls,
        *,
        generation: int,
        schema_fingerprint: str,
        segment: MemorySegment,
    ) -> "SegmentImage":
        return cls(
            generation=generation,
            schema_fingerprint=schema_fingerprint,
            stored_documents={
                doc_id: document
                for doc_id, document in enumerate(
                    segment.stored_documents
                )
            },
            postings=segment.postings,
            field_lengths=segment.field_lengths,
        )

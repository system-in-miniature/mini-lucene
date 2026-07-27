from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Posting:
    doc_id: int
    term_frequency: int
    positions: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class MemorySegment:
    generation: int
    max_doc: int
    postings: Mapping[str, Mapping[str, tuple[Posting, ...]]]
    stored_documents: tuple[Mapping[str, str], ...]
    field_lengths: Mapping[str, tuple[int, ...]]

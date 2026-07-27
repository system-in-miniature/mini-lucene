from dataclasses import dataclass

from minilucene.search.stats import CorpusStats
from minilucene.storage.image import SegmentImage


@dataclass(frozen=True, slots=True)
class SegmentSnapshot:
    generation: int
    image: SegmentImage
    live_docs: frozenset[int]


@dataclass(frozen=True, slots=True)
class ReaderSnapshot:
    schema_fingerprint: str
    segments: tuple[SegmentSnapshot, ...]
    corpus_stats: CorpusStats
    commit_generation: int | None

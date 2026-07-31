import heapq
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class SearchHit:
    score: float
    segment_generation: int
    local_doc_id: int
    stored_fields: Mapping[str, str]
    highlights: Mapping[str, str] = field(
        default_factory=lambda: MappingProxyType({})
    )


@dataclass(frozen=True, slots=True)
class TopDocs:
    total_hits: int
    hits: tuple[SearchHit, ...]


@dataclass(frozen=True, slots=True)
class CollectedDoc:
    """Lightweight first-phase winner retained before stored-field fetch."""

    doc_id: int
    score: float
    segment_generation: int
    local_doc_id: int
    stored_fields: Mapping[str, str] | None = None
    highlights: Mapping[str, str] | None = None


class TopKCollector:
    def __init__(self, top_k: int) -> None:
        if not isinstance(top_k, int) or top_k < 0:
            raise ValueError("top_k must be a non-negative integer")
        self.top_k = top_k
        self.total_hits = 0
        self.max_retained = 0
        self._heap: list[
            tuple[tuple[float, int, int], CollectedDoc]
        ] = []

    def collect(
        self,
        score: float,
        segment_generation: int,
        local_doc_id: int,
        stored_fields: Mapping[str, str] | None = None,
        highlights: Mapping[str, str] | None = None,
        *,
        doc_id: int | None = None,
    ) -> None:
        if not math.isfinite(score):
            raise ValueError("collected score must be finite")
        self.total_hits += 1
        if self.top_k == 0:
            return
        candidate = CollectedDoc(
            doc_id=local_doc_id if doc_id is None else doc_id,
            score=score,
            segment_generation=segment_generation,
            local_doc_id=local_doc_id,
            stored_fields=(
                None
                if stored_fields is None
                else MappingProxyType(dict(stored_fields))
            ),
            highlights=(
                None
                if highlights is None
                else MappingProxyType(dict(highlights))
            ),
        )
        key = (score, -segment_generation, -local_doc_id)
        item = (key, candidate)
        if len(self._heap) < self.top_k:
            heapq.heappush(self._heap, item)
        elif key > self._heap[0][0]:
            heapq.heapreplace(self._heap, item)
        self.max_retained = max(self.max_retained, len(self._heap))

    def top_candidates(self) -> tuple[CollectedDoc, ...]:
        return tuple(
            sorted(
                (candidate for _, candidate in self._heap),
                key=lambda candidate: (
                    -candidate.score,
                    candidate.segment_generation,
                    candidate.local_doc_id,
                ),
            )
        )

    def top_docs(self) -> TopDocs:
        hits = tuple(
            SearchHit(
                score=candidate.score,
                segment_generation=candidate.segment_generation,
                local_doc_id=candidate.local_doc_id,
                stored_fields=(
                    candidate.stored_fields or MappingProxyType({})
                ),
                highlights=(
                    candidate.highlights or MappingProxyType({})
                ),
            )
            for candidate in self.top_candidates()
        )
        return TopDocs(total_hits=self.total_hits, hits=hits)

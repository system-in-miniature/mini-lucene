import heapq
import math
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class SearchHit:
    score: float
    segment_generation: int
    local_doc_id: int
    stored_fields: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class TopDocs:
    total_hits: int
    hits: tuple[SearchHit, ...]


class TopKCollector:
    def __init__(self, top_k: int) -> None:
        if not isinstance(top_k, int) or top_k < 0:
            raise ValueError("top_k must be a non-negative integer")
        self.top_k = top_k
        self.total_hits = 0
        self.max_retained = 0
        self._heap: list[
            tuple[tuple[float, int, int], SearchHit]
        ] = []

    def collect(
        self,
        score: float,
        segment_generation: int,
        local_doc_id: int,
        stored_fields: Mapping[str, str] | None = None,
    ) -> None:
        if not math.isfinite(score):
            raise ValueError("collected score must be finite")
        self.total_hits += 1
        if self.top_k == 0:
            return
        hit = SearchHit(
            score=score,
            segment_generation=segment_generation,
            local_doc_id=local_doc_id,
            stored_fields=MappingProxyType(dict(stored_fields or {})),
        )
        key = (score, -segment_generation, -local_doc_id)
        item = (key, hit)
        if len(self._heap) < self.top_k:
            heapq.heappush(self._heap, item)
        elif key > self._heap[0][0]:
            heapq.heapreplace(self._heap, item)
        self.max_retained = max(self.max_retained, len(self._heap))

    def top_docs(self) -> TopDocs:
        hits = tuple(
            sorted(
                (hit for _, hit in self._heap),
                key=lambda hit: (
                    -hit.score,
                    hit.segment_generation,
                    hit.local_doc_id,
                ),
            )
        )
        return TopDocs(total_hits=self.total_hits, hits=hits)

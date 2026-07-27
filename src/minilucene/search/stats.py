from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class CorpusStats:
    live_doc_count: int
    doc_frequencies: Mapping[tuple[str, str], int]
    average_field_lengths: Mapping[str, float]

    def doc_frequency(self, field: str, term: str) -> int:
        return self.doc_frequencies.get((field, term), 0)

    def average_length(self, field: str) -> float:
        return self.average_field_lengths.get(field, 0.0)


def freeze_corpus_stats(
    *,
    live_doc_count: int,
    doc_frequencies: dict[tuple[str, str], int],
    average_field_lengths: dict[str, float],
) -> CorpusStats:
    return CorpusStats(
        live_doc_count=live_doc_count,
        doc_frequencies=MappingProxyType(dict(doc_frequencies)),
        average_field_lengths=MappingProxyType(
            dict(average_field_lengths)
        ),
    )

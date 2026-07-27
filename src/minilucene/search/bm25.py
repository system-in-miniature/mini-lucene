import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BM25:
    k1: float = 1.2
    b: float = 0.75

    def __post_init__(self) -> None:
        if not math.isfinite(self.k1) or self.k1 <= 0:
            raise ValueError("BM25 k1 must be finite and positive")
        if not math.isfinite(self.b) or not 0.0 <= self.b <= 1.0:
            raise ValueError("BM25 b must be finite and between zero and one")

    def term_score(
        self,
        *,
        tf: int,
        df: int,
        n: int,
        dl: int,
        avgdl: float,
    ) -> float:
        if tf <= 0 or df <= 0 or n <= 0:
            return 0.0
        idf = math.log(1.0 + (n - df + 0.5) / (df + 0.5))
        normalized_length = dl / avgdl if avgdl else 0.0
        norm = 1.0 - self.b + self.b * normalized_length
        return (
            idf
            * (tf * (self.k1 + 1.0))
            / (tf + self.k1 * norm)
        )

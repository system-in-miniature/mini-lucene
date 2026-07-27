import math
from collections.abc import Hashable, Mapping, Sequence
from collections.abc import Set as AbstractSet
from numbers import Real


def _validate_k(k: int) -> None:
    if not isinstance(k, int) or isinstance(k, bool) or k < 0:
        raise ValueError("k must be a non-negative integer")


def _validate_ranked[T: Hashable](ranked: Sequence[T]) -> None:
    if len(set(ranked)) != len(ranked):
        raise ValueError("ranked IDs contain a duplicate")


def precision_at_k[T: Hashable](
    ranked: Sequence[T], relevant: AbstractSet[T], k: int
) -> float:
    _validate_k(k)
    _validate_ranked(ranked)
    if k == 0:
        return 0.0
    return sum(item in relevant for item in ranked[:k]) / k


def recall_at_k[T: Hashable](
    ranked: Sequence[T], relevant: AbstractSet[T], k: int
) -> float:
    _validate_k(k)
    _validate_ranked(ranked)
    if not relevant:
        return 0.0
    return sum(item in relevant for item in ranked[:k]) / len(relevant)


def mean_reciprocal_rank[T: Hashable](
    rankings: Sequence[Sequence[T]],
    relevant_sets: Sequence[AbstractSet[T]],
) -> float:
    if len(rankings) != len(relevant_sets):
        raise ValueError(
            "rankings and relevance sets must have the same number"
        )
    for ranked in rankings:
        _validate_ranked(ranked)
    if not rankings:
        return 0.0
    reciprocal_sum = 0.0
    for ranked, relevant in zip(
        rankings, relevant_sets, strict=True
    ):
        reciprocal_sum += next(
            (
                1.0 / rank
                for rank, item in enumerate(ranked, start=1)
                if item in relevant
            ),
            0.0,
        )
    return reciprocal_sum / len(rankings)


def _validate_grades[T: Hashable](
    relevance: Mapping[T, Real],
) -> None:
    for grade in relevance.values():
        if (
            not isinstance(grade, Real)
            or isinstance(grade, bool)
            or not math.isfinite(float(grade))
            or grade < 0
        ):
            raise ValueError(
                "relevance grades must be finite and non-negative"
            )


def _dcg(grades: Sequence[Real]) -> float:
    return sum(
        (2.0 ** float(grade) - 1.0) / math.log2(rank + 1)
        for rank, grade in enumerate(grades, start=1)
    )


def ndcg_at_k[T: Hashable](
    ranked: Sequence[T], relevance: Mapping[T, Real], k: int
) -> float:
    _validate_k(k)
    _validate_ranked(ranked)
    _validate_grades(relevance)
    if k == 0:
        return 0.0
    actual = _dcg(
        tuple(relevance.get(item, 0.0) for item in ranked[:k])
    )
    ideal = _dcg(
        tuple(sorted(relevance.values(), reverse=True)[:k])
    )
    return 0.0 if ideal == 0.0 else actual / ideal

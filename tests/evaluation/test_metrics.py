import math

import pytest

from minilucene.evaluation import (
    mean_reciprocal_rank,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)


def test_binary_metrics():
    ranked = ("d1", "d2", "d3")
    relevant = {"d2", "d3", "d4"}
    assert precision_at_k(ranked, relevant, 2) == 0.5
    assert recall_at_k(ranked, relevant, 2) == pytest.approx(1 / 3)
    assert mean_reciprocal_rank([ranked], [relevant]) == 0.5


def test_ndcg_uses_graded_relevance():
    assert ndcg_at_k(("b", "a"), {"a": 3, "b": 1}, 2) < 1.0
    assert ndcg_at_k(("a", "b"), {"a": 3, "b": 1}, 2) == 1.0


def test_zero_k_and_empty_relevance_are_defined():
    assert precision_at_k(("d1",), {"d1"}, 0) == 0.0
    assert recall_at_k(("d1",), set(), 10) == 0.0
    assert ndcg_at_k(("d1",), {}, 10) == 0.0
    assert mean_reciprocal_rank([], []) == 0.0


def test_mrr_averages_queries_including_misses():
    assert mean_reciprocal_rank(
        [("a", "b"), ("c",), ("d", "e")],
        [{"b"}, {"missing"}, {"d"}],
    ) == pytest.approx((0.5 + 0.0 + 1.0) / 3)


@pytest.mark.parametrize(
    "operation",
    [
        lambda: precision_at_k(("d1", "d1"), {"d1"}, 2),
        lambda: recall_at_k(("d1", "d1"), {"d1"}, 2),
        lambda: ndcg_at_k(("d1", "d1"), {"d1": 1}, 2),
        lambda: mean_reciprocal_rank(
            [("d1", "d1")], [{"d1"}]
        ),
    ],
)
def test_duplicate_ranked_ids_are_rejected(operation):
    with pytest.raises(ValueError, match="duplicate"):
        operation()


@pytest.mark.parametrize("k", [-1, 1.5, True])
def test_invalid_k_is_rejected(k):
    with pytest.raises(ValueError, match="non-negative integer"):
        precision_at_k(("d1",), {"d1"}, k)


@pytest.mark.parametrize("grade", [-1, math.inf, math.nan])
def test_ndcg_rejects_invalid_grades(grade):
    with pytest.raises(ValueError, match="finite and non-negative"):
        ndcg_at_k(("d1",), {"d1": grade}, 1)


def test_mrr_requires_one_relevance_set_per_query():
    with pytest.raises(ValueError, match="same number"):
        mean_reciprocal_rank([("a",)], [])

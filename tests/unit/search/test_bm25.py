import pytest

from minilucene.search.bm25 import BM25


def test_bm25_tf_saturates():
    bm25 = BM25(k1=1.2, b=0.75)
    one = bm25.term_score(tf=1, df=1, n=10, dl=10, avgdl=10)
    ten = bm25.term_score(tf=10, df=1, n=10, dl=10, avgdl=10)
    hundred = bm25.term_score(tf=100, df=1, n=10, dl=10, avgdl=10)
    assert ten > one
    assert hundred - ten < ten - one


def test_bm25_longer_document_is_normalized_down():
    bm25 = BM25()
    short = bm25.term_score(tf=2, df=2, n=10, dl=5, avgdl=10)
    long = bm25.term_score(tf=2, df=2, n=10, dl=20, avgdl=10)
    assert short > long


@pytest.mark.parametrize(
    ("k1", "b"),
    [(0.0, 0.75), (-1.0, 0.75), (1.2, -0.1), (1.2, 1.1)],
)
def test_bm25_rejects_invalid_parameters(k1, b):
    with pytest.raises(ValueError):
        BM25(k1=k1, b=b)


def test_bm25_returns_zero_for_non_match():
    assert BM25().term_score(tf=0, df=1, n=10, dl=1, avgdl=1) == 0.0

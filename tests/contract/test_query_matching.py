import pytest

from minilucene.query import (
    BooleanClause,
    BooleanQuery,
    MatchAllQuery,
    Occur,
    PhraseQuery,
    PrefixQuery,
    QueryError,
    TermQuery,
)
from tests.helpers.corpus import build_memory_reader


def test_phrase_requires_consecutive_positions():
    reader = build_memory_reader(
        ("distributed system", "distributed applications improve the system")
    )
    assert reader.match(PhraseQuery("body", ("distributed", "system"))) == {0}


def test_phrase_preserves_analyzed_stopword_gap():
    reader = build_memory_reader(
        ("distributed system", "distributed the system")
    )
    query = PhraseQuery(
        "body",
        ("distributed", "system"),
        positions=(0, 2),
    )
    assert reader.match(query) == {1}


def test_boolean_and_prefix_have_frozen_set_semantics():
    reader = build_memory_reader(
        ("kafka replicas", "rabbit replicas", "kafka")
    )
    query = BooleanQuery(
        (
            BooleanClause(Occur.MUST, PrefixQuery("body", "kaf")),
            BooleanClause(Occur.MUST, TermQuery("body", "replicas")),
            BooleanClause(Occur.MUST_NOT, TermQuery("body", "rabbit")),
        )
    )
    assert reader.match(query) == {0}


def test_should_is_required_without_must_and_optional_with_must():
    reader = build_memory_reader(("kafka", "kafka replicas", "replicas"))
    only_should = BooleanQuery(
        (
            BooleanClause(Occur.SHOULD, TermQuery("body", "kafka")),
            BooleanClause(Occur.SHOULD, TermQuery("body", "replicas")),
        )
    )
    with_must = BooleanQuery(
        (
            BooleanClause(Occur.MUST, TermQuery("body", "kafka")),
            BooleanClause(Occur.SHOULD, TermQuery("body", "replicas")),
        )
    )
    assert reader.match(only_should) == {0, 1, 2}
    assert reader.match(with_must) == {0, 1}


def test_only_must_not_matches_nothing():
    reader = build_memory_reader(("kafka", "rabbit"))
    query = BooleanQuery(
        (BooleanClause(Occur.MUST_NOT, TermQuery("body", "kafka")),)
    )
    assert reader.match(query) == set()
    assert reader.match(MatchAllQuery()) == {0, 1}


def test_prefix_expansion_limit_fails_explicitly():
    reader = build_memory_reader(("alpha alpine amber",))
    reader.max_prefix_expansions = 1
    with pytest.raises(QueryError, match="prefix expansion limit"):
        reader.match(PrefixQuery("body", "al"))


@pytest.mark.parametrize(
    "factory",
    [
        lambda: TermQuery("", "term"),
        lambda: PhraseQuery("body", ()),
        lambda: PhraseQuery("body", ("a", "b"), positions=(0,)),
        lambda: PhraseQuery("body", ("a", "b"), positions=(0, 0)),
        lambda: PhraseQuery("body", ("a",), slop=1),
        lambda: PrefixQuery("body", ""),
        lambda: BooleanQuery(()),
    ],
)
def test_invalid_query_values_are_rejected(factory):
    with pytest.raises(QueryError):
        factory()

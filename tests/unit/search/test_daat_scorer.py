import random

import pytest

from minilucene.index.memory import RamIndexBuilder
from minilucene.query import (
    BooleanClause,
    BooleanQuery,
    MatchAllQuery,
    Occur,
    PhraseQuery,
    PrefixQuery,
    Query,
    TermQuery,
)
from minilucene.schema import Schema, TextField
from minilucene.search.reader import ReaderView
from minilucene.search.scorer import iter_scored_docs, score_query

VOCABULARY = ("alpha", "beta", "gamma", "delta", "epsilon", "zeta")
CORPUS_COUNT = 24
QUERIES_PER_CORPUS = 40


def build_reader(documents: tuple[str, ...]) -> ReaderView:
    schema = Schema(body=TextField(stored=True))
    builder = RamIndexBuilder(schema)
    for document in documents:
        builder.add_document({"body": document})
    return ReaderView(schema, (builder.freeze(generation=1),))


def random_query(rng: random.Random, depth: int = 0) -> Query:
    if depth >= 3 or rng.random() < 0.38:
        return TermQuery("body", rng.choice(VOCABULARY))
    clause_count = rng.randint(1, 4)
    clauses = []
    for _ in range(clause_count):
        occur = rng.choice((Occur.MUST, Occur.SHOULD, Occur.MUST_NOT))
        clauses.append(
            BooleanClause(occur, random_query(rng, depth + 1))
        )
    return BooleanQuery(tuple(clauses))


def assert_stream_matches_oracle(reader: ReaderView, query: Query) -> None:
    oracle = score_query(reader, query)
    actual = dict(iter_scored_docs(reader, query))
    assert actual.keys() == oracle.keys()
    assert actual == pytest.approx(oracle)


def test_daat_matches_set_oracle_for_seeded_random_corpora_and_queries():
    rng = random.Random(0xDAA7)
    for _ in range(CORPUS_COUNT):
        documents = tuple(
            " ".join(
                rng.choice(VOCABULARY)
                for _ in range(rng.randint(0, 10))
            )
            for _ in range(rng.randint(0, 12))
        )
        reader = build_reader(documents)
        for _ in range(QUERIES_PER_CORPUS):
            assert_stream_matches_oracle(reader, random_query(rng))


@pytest.mark.parametrize(
    "query",
    [
        TermQuery("body", "missing"),
        MatchAllQuery(),
        BooleanQuery(
            (
                BooleanClause(
                    Occur.MUST_NOT, TermQuery("body", "alpha")
                ),
            )
        ),
        BooleanQuery(
            (
                BooleanClause(Occur.MUST, TermQuery("body", "alpha")),
                BooleanClause(
                    Occur.SHOULD, TermQuery("body", "beta")
                ),
                BooleanClause(
                    Occur.MUST_NOT, TermQuery("body", "gamma")
                ),
            )
        ),
    ],
)
def test_daat_fixed_boolean_edges_match_oracle(query: Query):
    reader = build_reader(
        ("alpha", "alpha beta", "alpha gamma", "beta", "")
    )
    assert_stream_matches_oracle(reader, query)


def test_daat_matches_oracle_across_segments_and_live_doc_masks():
    schema = Schema(body=TextField(stored=True))
    segments = []
    for generation, documents in enumerate(
        (
            ("alpha beta", "alpha gamma", "beta"),
            ("alpha alpha", "alpha beta gamma", "delta"),
        ),
        start=1,
    ):
        builder = RamIndexBuilder(schema)
        for document in documents:
            builder.add_document({"body": document})
        segments.append(builder.freeze(generation=generation))
    reader = ReaderView(
        schema,
        tuple(segments),
        (frozenset({0, 2}), frozenset({0, 1, 2})),
    )
    query = BooleanQuery(
        (
            BooleanClause(Occur.MUST, TermQuery("body", "alpha")),
            BooleanClause(Occur.SHOULD, TermQuery("body", "beta")),
            BooleanClause(
                Occur.MUST_NOT, TermQuery("body", "gamma")
            ),
        )
    )
    assert_stream_matches_oracle(reader, query)


def test_boolean_score_addition_preserves_original_clause_order_exactly():
    class UnitSimilarity:
        def term_score(self, **_kwargs):
            return 1.0

    schema = Schema(
        small_a=TextField(stored=True),
        small_b=TextField(stored=True),
        huge=TextField(stored=True, boost=1e16),
    )
    builder = RamIndexBuilder(schema)
    builder.add_document(
        {"small_a": "a", "small_b": "", "huge": "required"}
    )
    builder.add_document(
        {"small_a": "a", "small_b": "b", "huge": "required"}
    )
    reader = ReaderView(schema, (builder.freeze(generation=1),))
    query = BooleanQuery(
        (
            BooleanClause(
                Occur.SHOULD, TermQuery("small_a", "a")
            ),
            BooleanClause(
                Occur.SHOULD, TermQuery("small_b", "b")
            ),
            BooleanClause(
                Occur.MUST, TermQuery("huge", "required")
            ),
        )
    )

    oracle = score_query(reader, query, UnitSimilarity())
    actual = dict(iter_scored_docs(reader, query, UnitSimilarity()))

    assert actual == oracle
    assert oracle[1] > oracle[0]


@pytest.mark.parametrize(
    "query",
    [
        PhraseQuery("body", ("alpha", "beta")),
        PrefixQuery("body", "al"),
        BooleanQuery(
            (
                BooleanClause(
                    Occur.MUST,
                    PhraseQuery("body", ("alpha", "beta")),
                ),
                BooleanClause(
                    Occur.SHOULD, TermQuery("body", "gamma")
                ),
            )
        ),
    ],
)
def test_unmigrated_leaf_falls_back_for_the_entire_tree(query: Query):
    reader = build_reader(("alpha beta", "alpha x beta", "gamma"))
    assert_stream_matches_oracle(reader, query)

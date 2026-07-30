import pytest

from minilucene import KeywordField, Schema, StoredField, TextField
from minilucene.query import (
    BooleanClause,
    BooleanQuery,
    Occur,
    PhraseQuery,
    PrefixQuery,
    TermQuery,
)
from minilucene.query_parser import QuerySyntaxError, parse_query


@pytest.fixture
def schema():
    return Schema(
        id=KeywordField(stored=True),
        title=TextField(stored=True),
        body=TextField(stored=True),
        raw=StoredField(),
    )


def test_and_binds_tighter_than_or(schema):
    assert parse_query("a OR b AND c", schema, "body") == BooleanQuery(
        (
            BooleanClause(Occur.SHOULD, TermQuery("body", "a")),
            BooleanClause(
                Occur.SHOULD,
                BooleanQuery(
                    (
                        BooleanClause(Occur.MUST, TermQuery("body", "b")),
                        BooleanClause(Occur.MUST, TermQuery("body", "c")),
                    )
                ),
            ),
        )
    )


def test_fielded_phrase_is_analyzed_with_positions(schema):
    assert parse_query(
        'body:"distributed the system"', schema, "body"
    ) == PhraseQuery(
        "body", ("distributed", "system"), positions=(0, 2)
    )


def test_single_token_phrase_is_a_term_query(schema):
    assert parse_query('id:"doc-1"', schema, "body") == TermQuery(
        "id", "doc-1"
    )


def test_fielded_prefix_is_analyzed(schema):
    assert parse_query("title:KAF*", schema, "body") == PrefixQuery(
        "title", "kaf"
    )


def test_parentheses_unary_and_implicit_or(schema):
    assert parse_query("title:(Kafka rabbit) AND -body:slow", schema, "body") == (
        BooleanQuery(
            (
                BooleanClause(
                    Occur.MUST,
                    BooleanQuery(
                        (
                            BooleanClause(
                                Occur.SHOULD,
                                TermQuery("title", "kafka"),
                            ),
                            BooleanClause(
                                Occur.SHOULD,
                                TermQuery("title", "rabbit"),
                            ),
                        )
                    ),
                ),
                BooleanClause(
                    Occur.MUST_NOT, TermQuery("body", "slow")
                ),
            )
        )
    )


def test_only_negative_query_remains_explicit(schema):
    assert parse_query("NOT kafka", schema, "body") == BooleanQuery(
        (BooleanClause(Occur.MUST_NOT, TermQuery("body", "kafka")),)
    )


def test_leading_minus_remains_not(schema):
    assert parse_query("-term", schema, "body") == BooleanQuery(
        (BooleanClause(Occur.MUST_NOT, TermQuery("body", "term")),)
    )


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("unknown:value", "unknown field"),
        ("raw:value", "not indexed"),
        ('body:""', "no searchable terms"),
        ("body:!!!", "no searchable terms"),
        ("(kafka", "expected"),
        ("kafka AND", "expected"),
    ],
)
def test_invalid_queries_report_source_offsets(schema, source, message):
    with pytest.raises(QuerySyntaxError, match=message) as error:
        parse_query(source, schema, "body")
    assert 0 <= error.value.offset <= len(source)


def test_invalid_default_field_fails_at_start(schema):
    with pytest.raises(QuerySyntaxError, match="default field"):
        parse_query("kafka", schema, "missing")

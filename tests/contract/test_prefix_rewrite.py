import pytest

from minilucene.errors import TooManyTermsError
from minilucene.index.memory import RamIndexBuilder
from minilucene.query import (
    BooleanClause,
    BooleanQuery,
    MatchAllQuery,
    Occur,
    PrefixQuery,
    TermQuery,
)
from minilucene.schema import Schema, TextField
from minilucene.search.reader import ReaderView


@pytest.fixture
def reader():
    schema = Schema(body=TextField(stored=True))
    builder = RamIndexBuilder(schema)
    builder.add_document(
        {
            "body": (
                "application banana apple app apricot application"
            )
        }
    )
    return ReaderView(schema, (builder.freeze(generation=1),))


def test_prefix_expands_sorted_terms_without_scanning_stored_docs(reader):
    assert reader.rewrite(
        PrefixQuery("body", "app"), max_terms=3
    ) == BooleanQuery(
        (
            BooleanClause(
                Occur.SHOULD, TermQuery("body", "app")
            ),
            BooleanClause(
                Occur.SHOULD, TermQuery("body", "apple")
            ),
            BooleanClause(
                Occur.SHOULD, TermQuery("body", "application")
            ),
        )
    )


def test_prefix_expansion_fails_instead_of_truncating(reader):
    with pytest.raises(TooManyTermsError) as error:
        reader.rewrite(PrefixQuery("body", "a"), max_terms=2)
    assert error.value.limit == 2
    assert error.value.field == "body"
    assert error.value.prefix == "a"


def test_prefix_rewrite_is_recursive_and_zero_terms_match_nothing(reader):
    query = BooleanQuery(
        (
            BooleanClause(
                Occur.MUST, PrefixQuery("body", "ban")
            ),
            BooleanClause(
                Occur.MUST_NOT, PrefixQuery("body", "missing")
            ),
        )
    )
    assert reader.rewrite(query, max_terms=3) == BooleanQuery(
        (
            BooleanClause(
                Occur.MUST, TermQuery("body", "banana")
            ),
            BooleanClause(
                Occur.MUST_NOT,
                BooleanQuery(
                    (
                        BooleanClause(
                            Occur.MUST_NOT, MatchAllQuery()
                        ),
                    )
                ),
            ),
        )
    )


@pytest.mark.parametrize("limit", [0, -1, 1.5])
def test_prefix_rewrite_rejects_invalid_limits(reader, limit):
    with pytest.raises(ValueError, match="positive integer"):
        reader.rewrite(PrefixQuery("body", "app"), max_terms=limit)

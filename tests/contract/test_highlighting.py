import pytest

from minilucene import KeywordField, Schema, TextField
from minilucene.index.memory import RamIndexBuilder
from minilucene.query import TermQuery
from minilucene.search.reader import ReaderView
from minilucene.search.searcher import IndexSearcher


@pytest.fixture
def searcher():
    schema = Schema(
        id=KeywordField(stored=True),
        author=KeywordField(stored=True),
        title=TextField(stored=True),
        body=TextField(stored=True),
        hidden=TextField(stored=False),
    )
    builder = RamIndexBuilder(schema)
    builder.add_document(
        {
            "id": "1",
            "author": "jonah",
            "title": "Replication",
            "body": "Kafka & follower replicas. <script>",
            "hidden": "private",
        }
    )
    builder.add_document(
        {
            "id": "2",
            "author": "sam",
            "title": "Positions",
            "body": "Distributed the system",
            "hidden": "private",
        }
    )
    return IndexSearcher(
        ReaderView(schema, (builder.freeze(generation=1),))
    )


def test_highlight_uses_original_offsets_and_escapes_text(searcher):
    result = searcher.search_text(
        '"follower replicas"',
        default_field="body",
        top_k=1,
        highlight_fields=("body",),
    )
    assert result.hits[0].highlights["body"] == (
        "Kafka &amp; <em>follower replicas</em>. &lt;script&gt;"
    )


def test_highlight_matches_lowercase_query_with_original_case(searcher):
    result = searcher.search_text(
        "KAFKA",
        default_field="body",
        top_k=1,
        highlight_fields=("body",),
    )
    assert result.hits[0].highlights["body"].startswith(
        "<em>Kafka</em> &amp;"
    )


def test_overlapping_term_and_phrase_offsets_are_merged():
    schema = Schema(body=TextField(stored=True))
    builder = RamIndexBuilder(schema)
    builder.add_document({"body": "Kafka follower replicas"})
    searcher = IndexSearcher(
        ReaderView(schema, (builder.freeze(generation=1),))
    )
    result = searcher.search_text(
        'kafka OR "kafka follower"',
        default_field="body",
        top_k=1,
        highlight_fields=("body",),
    )
    assert result.hits[0].highlights["body"] == (
        "<em>Kafka follower</em> replicas"
    )


def test_phrase_gap_highlights_the_original_gap_text(searcher):
    result = searcher.search_text(
        '"distributed the system"',
        default_field="body",
        top_k=1,
        highlight_fields=("body",),
    )
    assert result.hits[0].highlights["body"] == (
        "<em>Distributed the system</em>"
    )


def test_requested_field_without_a_match_is_still_safely_escaped(searcher):
    result = searcher.search_text(
        "title:replication",
        default_field="body",
        top_k=1,
        highlight_fields=("body",),
    )
    assert result.hits[0].highlights["body"] == (
        "Kafka &amp; follower replicas. &lt;script&gt;"
    )


@pytest.mark.parametrize("field", ["author", "hidden"])
def test_nonstored_or_keyword_field_cannot_be_highlighted(searcher, field):
    with pytest.raises(ValueError, match="stored TextField"):
        searcher.search(
            TermQuery("author", "jonah"),
            top_k=1,
            highlight_fields=(field,),
        )


def test_rewritten_prefix_terms_are_highlighted(searcher):
    result = searcher.search_text(
        "foll*",
        default_field="body",
        top_k=1,
        highlight_fields=("body",),
    )
    assert "<em>follower</em>" in result.hits[0].highlights["body"]

from minilucene.query import (
    BooleanClause,
    BooleanQuery,
    Occur,
    PhraseQuery,
    TermQuery,
)
from tests.helpers.corpus import search_memory


def test_title_boost_changes_ranking():
    hits = search_memory(
        documents=(
            {"title": "kafka", "body": "nothing"},
            {"title": "nothing", "body": "kafka kafka"},
        ),
        query=BooleanQuery(
            (
                BooleanClause(
                    Occur.SHOULD, TermQuery("title", "kafka")
                ),
                BooleanClause(Occur.SHOULD, TermQuery("body", "kafka")),
            )
        ),
        title_boost=3.0,
    )
    assert hits[0].stored_fields["id"] == "0"


def test_phrase_scores_only_documents_that_match_positions():
    hits = search_memory(
        documents=(
            {"title": "", "body": "follower replicas"},
            {"title": "", "body": "follower distant replicas"},
        ),
        query=PhraseQuery("body", ("follower", "replicas")),
    )
    assert [hit.stored_fields["id"] for hit in hits] == ["0"]


def test_must_not_filters_without_contributing_score():
    positive = TermQuery("body", "kafka")
    filtered = BooleanQuery(
        (
            BooleanClause(Occur.MUST, positive),
            BooleanClause(
                Occur.MUST_NOT, TermQuery("body", "excluded")
            ),
        )
    )
    documents = (
        {"title": "", "body": "kafka"},
        {"title": "", "body": "kafka excluded"},
    )
    positive_hits = search_memory(documents=documents, query=positive)
    filtered_hits = search_memory(documents=documents, query=filtered)
    assert len(filtered_hits) == 1
    assert filtered_hits[0].score == positive_hits[0].score

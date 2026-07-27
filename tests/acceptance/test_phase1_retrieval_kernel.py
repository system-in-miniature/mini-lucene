from minilucene import KeywordField, MemoryIndex, Schema, TextField
from minilucene.query import (
    BooleanClause,
    BooleanQuery,
    Occur,
    PhraseQuery,
    TermQuery,
)


def test_fielded_phrase_bm25_topk_and_stored_fields_close_one_loop():
    index = MemoryIndex(
        Schema(
            id=KeywordField(stored=True),
            title=TextField(stored=True, boost=2.0),
            body=TextField(stored=True),
        )
    )
    index.add_document(
        id="1",
        title="Kafka",
        body="follower replicas",
    )
    index.add_document(
        id="2",
        title="Queues",
        body="follower processes coordinate distant replicas",
    )
    query = BooleanQuery(
        (
            BooleanClause(
                Occur.MUST, TermQuery("title", "kafka")
            ),
            BooleanClause(
                Occur.MUST,
                PhraseQuery("body", ("follower", "replicas")),
            ),
        )
    )
    result = index.search(query, top_k=1)
    assert result.total_hits == 1
    assert result.hits[0].stored_fields["id"] == "1"
    assert result.hits[0].score > 0

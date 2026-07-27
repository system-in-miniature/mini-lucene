import pytest

from minilucene import Index, KeywordField, MemoryIndex, Schema, TextField
from minilucene.query import (
    BooleanClause,
    BooleanQuery,
    Occur,
    PhraseQuery,
    PrefixQuery,
    TermQuery,
)


def test_disk_search_matches_in_memory_oracle_after_reopen(tmp_path):
    schema = Schema(
        id=KeywordField(stored=True),
        title=TextField(stored=True, boost=2.0),
        body=TextField(stored=True),
    )
    documents = (
        {
            "id": "1",
            "title": "Kafka",
            "body": "follower replicas",
        },
        {
            "id": "2",
            "title": "Rabbit",
            "body": "message replicas",
        },
        {
            "id": "3",
            "title": "Kafka internals",
            "body": "follower distant replicas",
        },
    )
    memory = MemoryIndex(schema)
    disk = Index.create(tmp_path, schema)
    with disk.writer() as writer:
        for position, document in enumerate(documents):
            memory.add_document(**document)
            writer.add_document(**document)
            if position == 0:
                writer.flush()
        writer.commit()

    reader = Index.open(tmp_path).open_reader()
    queries = (
        TermQuery("title", "kafka"),
        PhraseQuery("body", ("follower", "replicas")),
        PrefixQuery("title", "kaf"),
        BooleanQuery(
            (
                BooleanClause(
                    Occur.MUST, TermQuery("title", "kafka")
                ),
                BooleanClause(
                    Occur.MUST_NOT, TermQuery("body", "distant")
                ),
            )
        ),
    )
    for query in queries:
        expected = memory.search(query, top_k=10)
        actual = reader.search(query, top_k=10)
        assert actual.total_hits == expected.total_hits
        assert [
            hit.stored_fields["id"] for hit in actual.hits
        ] == [hit.stored_fields["id"] for hit in expected.hits]
        assert [hit.score for hit in actual.hits] == pytest.approx(
            [hit.score for hit in expected.hits]
        )

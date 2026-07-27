import pytest

from minilucene import Index, KeywordField, MemoryIndex, Schema, TextField
from minilucene.query import PhraseQuery, TermQuery


def test_restart_reads_only_committed_checksummed_segments(tmp_path):
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
    )
    memory = MemoryIndex(schema)
    index = Index.create(tmp_path, schema)
    with index.writer() as writer:
        for document in documents:
            memory.add_document(**document)
            writer.add_document(**document)
            writer.flush()
        manifest = writer.commit()

    assert manifest.segment_generations == (1, 2)
    reopened = Index.open(tmp_path)
    assert reopened.schema.fingerprint == schema.fingerprint
    reader = reopened.open_reader()

    for query in (
        TermQuery("body", "replicas"),
        PhraseQuery("body", ("follower", "replicas")),
    ):
        expected = memory.search(query, top_k=10)
        actual = reader.search(query, top_k=10)
        assert actual.total_hits == expected.total_hits
        assert [
            hit.stored_fields["id"] for hit in actual.hits
        ] == [hit.stored_fields["id"] for hit in expected.hits]
        assert [hit.score for hit in actual.hits] == pytest.approx(
            [hit.score for hit in expected.hits]
        )

    with reopened.writer() as writer:
        writer.add_document(id="3", title="Orphan", body="not committed")
        writer.flush()
    crashed_view = Index.open(tmp_path).open_reader()
    assert (
        crashed_view.search(
            TermQuery("body", "not"),
            top_k=10,
        ).total_hits
        == 0
    )
    assert crashed_view.max_doc == 2

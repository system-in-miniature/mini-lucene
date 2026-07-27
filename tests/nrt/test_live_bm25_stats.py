import pytest

from minilucene import Index, KeywordField, MemoryIndex, Schema, TextField
from minilucene.query import TermQuery


def test_deleted_documents_do_not_change_global_multisegment_bm25(tmp_path):
    schema = Schema(
        id=KeywordField(stored=True),
        body=TextField(stored=True),
    )
    live_documents = (
        {"id": "1", "body": "kafka kafka"},
        {"id": "3", "body": "kafka replicas"},
    )
    oracle = MemoryIndex(schema)
    for document in live_documents:
        oracle.add_document(**document)

    index = Index.create(tmp_path, schema)
    with index.writer() as writer:
        writer.add_document(**live_documents[0])
        writer.flush()
        writer.add_document(
            id="2",
            body=("kafka " * 50) + "deleted noise",
        )
        writer.flush()
        writer.add_document(**live_documents[1])
        writer.commit()
    with index.writer() as writer:
        writer.delete_by_term("id", "2")
        reader = writer.refresh()

    stats = reader.corpus_stats
    assert stats.live_doc_count == 2
    assert stats.doc_frequency("body", "kafka") == 2
    assert stats.average_length("body") == 2.0

    query = TermQuery("body", "kafka")
    expected = oracle.search(query, top_k=10)
    actual = reader.search(query, top_k=10)
    assert [hit.stored_fields["id"] for hit in actual.hits] == [
        hit.stored_fields["id"] for hit in expected.hits
    ]
    assert [hit.score for hit in actual.hits] == pytest.approx(
        [hit.score for hit in expected.hits]
    )

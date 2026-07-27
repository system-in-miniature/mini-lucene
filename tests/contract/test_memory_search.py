from minilucene import MemoryIndex, Schema, TextField
from minilucene.query import MatchAllQuery, TermQuery


def test_public_memory_index_returns_stored_fields():
    index = MemoryIndex(Schema(body=TextField(stored=True)))
    index.add_document(body="kafka replicas")
    result = index.search(TermQuery("body", "kafka"), top_k=10)
    assert result.total_hits == 1
    assert result.hits[0].stored_fields == {"body": "kafka replicas"}


def test_public_memory_index_uses_bounded_topk_and_deterministic_order():
    index = MemoryIndex(Schema(body=TextField(stored=True)))
    index.add_document(body="same")
    index.add_document(body="same")
    index.add_document(body="same")
    result = index.search(TermQuery("body", "same"), top_k=2)
    assert result.total_hits == 3
    assert [hit.local_doc_id for hit in result.hits] == [0, 1]


def test_match_all_can_report_total_without_returning_hits():
    index = MemoryIndex(Schema(body=TextField(stored=True)))
    index.add_document(body="one")
    index.add_document(body="two")
    result = index.search(MatchAllQuery(), top_k=0)
    assert result.total_hits == 2
    assert result.hits == ()

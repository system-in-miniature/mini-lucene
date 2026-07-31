from minilucene.index.memory import RamIndexBuilder
from minilucene.query import TermQuery
from minilucene.schema import Schema, TextField
from minilucene.search.reader import ReaderView
from minilucene.search.searcher import IndexSearcher


class CountingReader(ReaderView):
    def __init__(self, schema, segments):
        super().__init__(schema, segments)
        self.fetched_doc_ids: list[int] = []

    def stored_fields(self, doc_id):
        self.fetched_doc_ids.append(doc_id)
        return super().stored_fields(doc_id)


def test_search_fetches_stored_fields_only_for_final_top_k():
    schema = Schema(body=TextField(stored=True))
    builder = RamIndexBuilder(schema)
    for frequency in range(1, 11):
        builder.add_document({"body": " ".join(["term"] * frequency)})
    reader = CountingReader(schema, (builder.freeze(generation=1),))

    results = IndexSearcher(reader).search(
        TermQuery("body", "term"),
        top_k=3,
        highlight_fields=("body",),
    )

    assert results.total_hits == 10
    assert len(results.hits) == 3
    assert len(reader.fetched_doc_ids) == 3
    assert all(hit.highlights["body"] for hit in results.hits)
    with pytest.raises(TypeError):
        results.hits[0].highlights["body"] = "changed"


def test_top_k_zero_counts_without_fetching_stored_fields():
    schema = Schema(body=TextField(stored=True))
    builder = RamIndexBuilder(schema)
    for _ in range(4):
        builder.add_document({"body": "term"})
    reader = CountingReader(schema, (builder.freeze(generation=1),))

    results = IndexSearcher(reader).search(
        TermQuery("body", "term"), top_k=0
    )

    assert results.total_hits == 4
    assert results.hits == ()
    assert reader.fetched_doc_ids == []
import pytest

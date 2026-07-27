from pathlib import Path

import pytest

from minilucene import Index, KeywordField, MemoryIndex, Schema, TextField
from minilucene.query import (
    BooleanClause,
    BooleanQuery,
    Occur,
    PhraseQuery,
    TermQuery,
)
from minilucene.query_parser import parse_query
from tests.support.reference_corpus import load_reference_corpus

FIXTURES = Path(__file__).parents[1] / "fixtures"


@pytest.fixture
def reference():
    return load_reference_corpus(FIXTURES)


@pytest.fixture
def schema():
    return Schema(
        id=KeywordField(stored=True),
        title=TextField(stored=True, boost=2.0),
        body=TextField(stored=True),
        author=KeywordField(stored=True),
    )


def _ids(top_docs):
    return tuple(hit.stored_fields["id"] for hit in top_docs.hits)


def _snapshot(reader, queries):
    snapshot = {}
    for query in queries:
        results = reader.search(
            parse_query(
                query.text, reader.schema, query.default_field
            ),
            top_k=10,
        )
        snapshot[query.id] = (
            _ids(results),
            tuple(hit.score for hit in results.hits),
        )
    return snapshot


def test_fixture_ids_and_references_are_closed(reference):
    document_ids = {document["id"] for document in reference.documents}
    query_ids = {query.id for query in reference.queries}
    assert len(document_ids) == len(reference.documents)
    assert len(query_ids) == len(reference.queries)
    assert set(reference.qrels) == query_ids
    assert all(
        set(grades) <= document_ids
        for grades in reference.qrels.values()
    )


def test_title_boost_changes_order_relative_to_equal_body_matches():
    schema = Schema(
        id=KeywordField(stored=True),
        title=TextField(stored=True, boost=3.0),
        body=TextField(stored=True),
    )
    index = MemoryIndex(schema)
    index.add_document(id="title", title="kafka", body="neutral")
    index.add_document(id="body", title="neutral", body="kafka")
    query = BooleanQuery(
        (
            BooleanClause(
                Occur.SHOULD, TermQuery("title", "kafka")
            ),
            BooleanClause(
                Occur.SHOULD, TermQuery("body", "kafka")
            ),
        )
    )
    assert _ids(index.search(query, top_k=2)) == ("title", "body")


def test_bm25_term_frequency_saturates_instead_of_growing_linearly():
    schema = Schema(
        id=KeywordField(stored=True),
        body=TextField(stored=True),
    )
    index = MemoryIndex(schema)
    index.add_document(id="five", body="kafka " * 5)
    index.add_document(id="hundred", body="kafka " * 100)
    results = index.search(TermQuery("body", "kafka"), top_k=2)
    scores = {
        hit.stored_fields["id"]: hit.score for hit in results.hits
    }
    assert scores["hundred"] / scores["five"] < 2.0


def test_phrase_recall_is_narrower_than_boolean_conjunction():
    schema = Schema(
        id=KeywordField(stored=True),
        body=TextField(stored=True),
    )
    index = MemoryIndex(schema)
    index.add_document(id="adjacent", body="distributed system")
    index.add_document(
        id="separated",
        body="distributed applications improve system",
    )
    phrase = index.search(
        PhraseQuery("body", ("distributed", "system")), top_k=10
    )
    conjunction = index.search(
        BooleanQuery(
            (
                BooleanClause(
                    Occur.MUST,
                    TermQuery("body", "distributed"),
                ),
                BooleanClause(
                    Occur.MUST, TermQuery("body", "system")
                ),
            )
        ),
        top_k=10,
    )
    assert _ids(phrase) == ("adjacent",)
    assert set(_ids(conjunction)) == {"adjacent", "separated"}


def test_deleted_documents_affect_neither_hits_nor_statistics(tmp_path):
    schema = Schema(
        id=KeywordField(stored=True),
        title=TextField(stored=True),
        body=TextField(stored=True),
        author=KeywordField(stored=True),
    )
    index = Index.create(tmp_path, schema)
    with index.writer() as writer:
        writer.add_document(
            id="live",
            title="live",
            body="kafka replicas",
            author="a",
        )
        writer.flush()
        writer.add_document(
            id="deleted",
            title="noise",
            body="kafka " * 100,
            author="b",
        )
        writer.commit()
    with index.writer() as writer:
        assert writer.delete_by_term("id", "deleted") == 1
        reader = writer.refresh()
    try:
        assert reader.corpus_stats.live_doc_count == 1
        assert reader.corpus_stats.doc_frequency("body", "kafka") == 1
        assert reader.corpus_stats.average_length("body") == 2.0
        assert _ids(reader.search(TermQuery("body", "kafka"))) == (
            "live",
        )
    finally:
        reader.close()
        index.close()


def test_rankings_survive_commit_reopen_and_merge(
    tmp_path, reference, schema
):
    index = Index.create(tmp_path, schema)
    with index.writer() as writer:
        for position, document in enumerate(reference.documents):
            writer.add_document(**document)
            if position == 1:
                writer.flush()
        writer.commit()

    committed = Index.open(tmp_path)
    reader_before = committed.open_reader()
    expected = _snapshot(reader_before, reference.queries)
    reader_before.close()

    with committed.writer() as writer:
        assert len(writer.segment_generations) == 2
        writer.merge(writer.segment_generations)
        writer.commit()
    reader_after = Index.open(tmp_path).open_reader()
    actual = _snapshot(reader_after, reference.queries)
    reader_after.close()
    committed.close()
    index.close()

    assert actual.keys() == expected.keys()
    for query_id in expected:
        assert actual[query_id][0] == expected[query_id][0]
        assert actual[query_id][1] == pytest.approx(
            expected[query_id][1]
        )

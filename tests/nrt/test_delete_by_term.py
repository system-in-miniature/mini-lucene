from minilucene import Index, KeywordField, Schema, TextField
from minilucene.query import TermQuery


def build_index(tmp_path):
    return Index.create(
        tmp_path,
        Schema(
            id=KeywordField(stored=True),
            body=TextField(stored=True),
        ),
    )


def test_delete_matches_buffered_and_flushed_documents(tmp_path):
    index = build_index(tmp_path)
    with index.writer() as writer:
        writer.add_document(id="same", body="first")
        writer.flush()
        writer.add_document(id="same", body="second")
        assert writer.delete_by_term("id", "same") == 2
        reader = writer.refresh()
        assert reader.num_live_docs == 0
        assert reader.search(TermQuery("body", "first"), top_k=10).total_hits == 0
        assert reader.search(TermQuery("body", "second"), top_k=10).total_hits == 0


def test_old_reader_keeps_deleted_document_and_new_stats_exclude_it(tmp_path):
    index = build_index(tmp_path)
    with index.writer() as writer:
        writer.add_document(id="1", body="rare")
        writer.add_document(id="2", body="common")
        writer.commit()
    old = index.open_reader()
    with index.writer() as writer:
        assert writer.delete_by_term("id", "1") == 1
        new = writer.refresh()
    assert old.search(TermQuery("body", "rare"), top_k=10).total_hits == 1
    assert new.search(TermQuery("body", "rare"), top_k=10).total_hits == 0
    assert new.corpus_stats.live_doc_count == 1


def test_repeated_delete_counts_only_newly_deleted_documents(tmp_path):
    index = build_index(tmp_path)
    with index.writer() as writer:
        writer.add_document(id="1", body="value")
        writer.flush()
        assert writer.delete_by_term("id", "1") == 1
        assert writer.delete_by_term("id", "1") == 0


def test_committed_delete_survives_reopen_and_references_live_docs(tmp_path):
    index = build_index(tmp_path)
    with index.writer() as writer:
        writer.add_document(id="1", body="remove")
        writer.add_document(id="2", body="keep")
        writer.commit()
    with index.writer() as writer:
        writer.delete_by_term("id", "1")
        manifest = writer.commit()

    segment_commit = manifest.segments[0]
    assert segment_commit.live_docs_generation == 1
    assert segment_commit.live_docs_checksum
    reopened = Index.open(tmp_path).open_reader()
    assert reopened.num_live_docs == 1
    assert reopened.search(TermQuery("body", "remove"), top_k=10).total_hits == 0
    assert reopened.search(TermQuery("body", "keep"), top_k=10).total_hits == 1

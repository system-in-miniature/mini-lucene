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


def test_refresh_sees_flushed_uncommitted_documents(tmp_path):
    index = build_index(tmp_path)
    committed = index.open_reader()
    with index.writer() as writer:
        writer.add_document(id="1", body="visible")
        nrt = writer.refresh()
        assert nrt.search(TermQuery("body", "visible"), top_k=10).total_hits == 1
        assert nrt.snapshot.commit_generation is None
        assert committed.max_doc == 0
        assert index.open_reader().max_doc == 0


def test_uncommitted_refresh_state_disappears_after_process_reopen(tmp_path):
    index = build_index(tmp_path)
    with index.writer() as writer:
        writer.add_document(id="1", body="ephemeral")
        assert writer.refresh().max_doc == 1
    reopened = Index.open(tmp_path)
    assert reopened.open_reader().max_doc == 0


def test_old_nrt_reader_stays_unchanged_after_later_refresh(tmp_path):
    index = build_index(tmp_path)
    with index.writer() as writer:
        writer.add_document(id="1", body="first")
        first = writer.refresh()
        writer.add_document(id="2", body="second")
        second = writer.refresh()
        assert first.max_doc == 1
        assert second.max_doc == 2
        assert first.search(TermQuery("body", "second"), top_k=10).total_hits == 0


def test_new_writer_skips_generation_of_prior_orphan(tmp_path):
    index = build_index(tmp_path)
    with index.writer() as writer:
        writer.add_document(id="1", body="orphan")
        assert writer.refresh().snapshot.segments[0].generation == 1
    with index.writer() as writer:
        writer.add_document(id="2", body="next")
        reader = writer.refresh()
        assert reader.snapshot.segments[0].generation == 2

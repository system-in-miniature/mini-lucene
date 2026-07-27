import pytest

from minilucene import Index, KeywordField, Schema, TextField
from minilucene.errors import AlreadyClosedError
from minilucene.query import TermQuery


def build_index(tmp_path):
    return Index.create(
        tmp_path,
        Schema(
            id=KeywordField(stored=True),
            body=TextField(stored=True),
        ),
    )


def test_reader_snapshot_never_changes_after_later_commit(tmp_path):
    index = build_index(tmp_path)
    with index.writer() as writer:
        writer.add_document(id="1", body="old")
        writer.commit()
    old_reader = index.open_reader()
    with index.writer() as writer:
        writer.add_document(id="2", body="new")
        writer.commit()
    assert old_reader.max_doc == 1
    assert index.open_reader().max_doc == 2
    assert old_reader.search(TermQuery("body", "new"), top_k=10).total_hits == 0


def test_reader_close_is_idempotent_and_operations_fail(tmp_path):
    index = build_index(tmp_path)
    with index.writer() as writer:
        writer.add_document(id="1", body="value")
        writer.commit()
    reader = index.open_reader()
    reader.close()
    reader.close()
    with pytest.raises(AlreadyClosedError):
        reader.document(0)
    with pytest.raises(AlreadyClosedError):
        reader.search(TermQuery("body", "value"), top_k=10)


def test_closing_one_reader_does_not_invalidate_another(tmp_path):
    index = build_index(tmp_path)
    first = index.open_reader()
    second = index.open_reader()
    first.close()
    assert second.max_doc == 0
    assert second.search(TermQuery("body", "anything"), top_k=10).total_hits == 0


def test_reader_exposes_frozen_snapshot_metadata(tmp_path):
    index = build_index(tmp_path)
    reader = index.open_reader()
    assert reader.snapshot.schema_fingerprint == index.schema.fingerprint
    assert reader.snapshot.commit_generation == 0
    assert reader.snapshot.segments == ()

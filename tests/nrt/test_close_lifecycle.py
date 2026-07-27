import pytest

from minilucene import Index, Schema, TextField
from minilucene.errors import AlreadyClosedError
from minilucene.query import TermQuery


def build_index(tmp_path):
    return Index.create(
        tmp_path,
        Schema(body=TextField(stored=True)),
    )


def test_writer_close_stops_admission_and_releases_owner_and_lock(tmp_path):
    index = build_index(tmp_path)
    writer = index.writer()
    writer.add_document(body="unpublished")
    writer.flush()
    writer.close()
    writer.close()

    assert not (tmp_path / ".writer.lock").exists()
    assert index.lifecycle_diagnostics().writer_owner is None
    with pytest.raises(AlreadyClosedError):
        writer.add_document(body="late")
    with pytest.raises(AlreadyClosedError):
        writer.refresh()
    with pytest.raises(AlreadyClosedError):
        writer.commit()


def test_index_close_reports_external_reader_without_invalidating_it(tmp_path):
    index = build_index(tmp_path)
    with index.writer() as writer:
        writer.add_document(body="still readable")
        writer.commit()
    reader = index.open_reader()
    diagnostics = index.close()
    assert len(diagnostics.reader_owners) == 1
    assert (
        reader.search(
            TermQuery("body", "readable"),
            top_k=10,
        ).total_hits
        == 1
    )
    reader.close()
    assert index.lifecycle_diagnostics().reader_owners == ()


def test_closed_index_rejects_new_writer_and_reader(tmp_path):
    index = build_index(tmp_path)
    index.close()
    index.close()
    with pytest.raises(AlreadyClosedError):
        index.writer()
    with pytest.raises(AlreadyClosedError):
        index.open_reader()


def test_index_context_closes_only_index_admission(tmp_path):
    with build_index(tmp_path) as index:
        reader = index.open_reader()
    assert reader.search(TermQuery("body", "none"), top_k=10).total_hits == 0
    reader.close()

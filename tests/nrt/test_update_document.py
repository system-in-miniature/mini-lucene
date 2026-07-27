import pytest

from minilucene import Index, KeywordField, Schema, TextField
from minilucene.query import TermQuery
from minilucene.schema import SchemaError


def build_index(tmp_path):
    return Index.create(
        tmp_path,
        Schema(
            id=KeywordField(stored=True),
            body=TextField(stored=True),
        ),
    )


def test_update_deletes_all_matches_then_adds_one_replacement(tmp_path):
    index = build_index(tmp_path)
    with index.writer() as writer:
        writer.add_document(id="1", body="old one")
        writer.add_document(id="1", body="old two")
        writer.commit()
        deleted = writer.update_document(
            field="id",
            term="1",
            id="1",
            body="replacement",
        )
        assert deleted == 2
        reader = writer.refresh()
    assert reader.search(TermQuery("body", "old"), top_k=10).total_hits == 0
    assert (
        reader.search(
            TermQuery("body", "replacement"),
            top_k=10,
        ).total_hits
        == 1
    )


def test_invalid_replacement_leaves_delete_state_unchanged(tmp_path):
    index = build_index(tmp_path)
    with index.writer() as writer:
        writer.add_document(id="1", body="old")
        writer.commit()
        with pytest.raises(SchemaError):
            writer.update_document(
                field="id",
                term="1",
                id="1",
                body=7,
            )
        assert (
            writer.refresh().search(
                TermQuery("body", "old"),
                top_k=10,
            ).total_hits
            == 1
        )


def test_update_replaces_buffered_document_without_intermediate_visibility(
    tmp_path,
):
    index = build_index(tmp_path)
    with index.writer() as writer:
        writer.add_document(id="1", body="buffered old")
        assert (
            writer.update_document(
                field="id",
                term="1",
                id="1",
                body="buffered new",
            )
            == 1
        )
        reader = writer.refresh()
    assert reader.search(TermQuery("body", "old"), top_k=10).total_hits == 0
    assert reader.search(TermQuery("body", "new"), top_k=10).total_hits == 1


def test_committed_update_survives_reopen(tmp_path):
    index = build_index(tmp_path)
    with index.writer() as writer:
        writer.add_document(id="1", body="before")
        writer.commit()
    with index.writer() as writer:
        writer.update_document(
            field="id",
            term="1",
            id="1",
            body="after",
        )
        writer.commit()
    reader = Index.open(tmp_path).open_reader()
    assert reader.search(TermQuery("body", "before"), top_k=10).total_hits == 0
    assert reader.search(TermQuery("body", "after"), top_k=10).total_hits == 1

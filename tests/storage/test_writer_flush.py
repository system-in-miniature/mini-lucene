import pytest

from minilucene import Index, KeywordField, Schema, TextField
from minilucene.schema import SchemaError
from minilucene.writer import FlushPolicy


def build_index(tmp_path):
    return Index.create(
        tmp_path,
        Schema(
            id=KeywordField(stored=True),
            body=TextField(stored=True),
        ),
    )


def test_flush_creates_segment_but_does_not_change_manifest(tmp_path):
    index = build_index(tmp_path)
    with index.writer() as writer:
        writer.add_document(id="1", body="alpha")
        segment = writer.flush()
        assert segment.generation == 1
        assert writer.segment_generations == (1,)
        assert index.manifest().segments == ()


def test_document_threshold_flushes_before_next_add(tmp_path):
    index = build_index(tmp_path)
    with index.writer(
        flush_policy=FlushPolicy(max_documents=1, max_postings=100)
    ) as writer:
        writer.add_document(id="1", body="alpha")
        writer.add_document(id="2", body="beta")
        assert writer.segment_generations == (1,)
        assert writer.buffered_document_count == 1


def test_invalid_document_does_not_trigger_threshold_flush(tmp_path):
    index = build_index(tmp_path)
    with index.writer(
        flush_policy=FlushPolicy(max_documents=1, max_postings=100)
    ) as writer:
        writer.add_document(id="1", body="alpha")
        with pytest.raises(SchemaError):
            writer.add_document(id="2", unknown="invalid")
        assert writer.segment_generations == ()
        assert writer.buffered_document_count == 1


def test_empty_flush_is_a_noop(tmp_path):
    index = build_index(tmp_path)
    with index.writer() as writer:
        assert writer.flush() is None
        assert writer.segment_generations == ()


def test_posting_threshold_flushes_before_next_add(tmp_path):
    index = build_index(tmp_path)
    with index.writer(
        flush_policy=FlushPolicy(max_documents=100, max_postings=2)
    ) as writer:
        writer.add_document(id="1", body="alpha")
        assert writer.buffered_posting_count == 2
        writer.add_document(id="2", body="beta")
        assert writer.segment_generations == (1,)
        assert writer.buffered_document_count == 1

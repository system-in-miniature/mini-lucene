import pytest

from minilucene.index.memory import RamIndexBuilder
from minilucene.schema import KeywordField, Schema, TextField
from minilucene.storage.image import SegmentImage


def test_segment_image_rejects_non_dense_documents():
    with pytest.raises(ValueError, match="dense"):
        SegmentImage(
            generation=1,
            schema_fingerprint="abc",
            stored_documents={1: {"id": "late"}},
            postings={},
            field_lengths={},
        )


def test_segment_image_from_ram_segment_is_deeply_immutable():
    schema = Schema(
        id=KeywordField(stored=True),
        body=TextField(stored=True),
    )
    builder = RamIndexBuilder(schema)
    builder.add_document({"id": "1", "body": "search search"})
    image = SegmentImage.from_memory_segment(
        generation=7,
        schema_fingerprint=schema.fingerprint,
        segment=builder.freeze(generation=0),
    )
    assert image.max_doc == 1
    assert image.postings["body"]["search"][0].positions == (0, 1)
    with pytest.raises(TypeError):
        image.stored_documents[0] = {"id": "changed"}
    with pytest.raises(TypeError):
        image.stored_documents[0]["id"] = "changed"


def test_segment_image_rejects_nonmonotonic_posting_ids():
    from minilucene.index.postings import Posting

    with pytest.raises(ValueError, match="strictly increasing"):
        SegmentImage(
            generation=1,
            schema_fingerprint="abc",
            stored_documents={0: {}, 1: {}},
            postings={
                "body": {
                    "term": (
                        Posting(1, 1, (0,)),
                        Posting(0, 1, (0,)),
                    )
                }
            },
            field_lengths={"body": (1, 1)},
        )


def test_segment_image_rejects_wrong_field_length_count():
    with pytest.raises(ValueError, match="field lengths"):
        SegmentImage(
            generation=1,
            schema_fingerprint="abc",
            stored_documents={0: {}},
            postings={},
            field_lengths={"body": ()},
        )

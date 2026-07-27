import pytest

from minilucene.index.memory import RamIndexBuilder
from minilucene.schema import KeywordField, Schema, StoredField, TextField
from minilucene.storage.codec import SegmentDataCodec
from minilucene.storage.image import SegmentImage


def build_image():
    schema = Schema(
        id=KeywordField(stored=True),
        body=TextField(stored=True),
        note=StoredField(),
    )
    builder = RamIndexBuilder(schema)
    builder.add_document(
        {"id": "文档-1", "body": "Kafka kafka", "note": "α"}
    )
    builder.add_document(
        {"id": "doc-2", "body": "replicas", "note": "β"}
    )
    return SegmentImage.from_memory_segment(
        generation=4,
        schema_fingerprint=schema.fingerprint,
        segment=builder.freeze(generation=0),
    )


def test_segment_data_codec_is_deterministic():
    image = build_image()
    first = SegmentDataCodec.encode(image)
    second = SegmentDataCodec.encode(image)
    assert first == second
    assert set(first) == {
        "terms.bin",
        "postings.bin",
        "stored.bin",
        "norms.bin",
    }


def test_segment_data_codec_round_trips():
    image = build_image()
    files = SegmentDataCodec.encode(image)
    decoded = SegmentDataCodec.decode(
        generation=image.generation,
        schema_fingerprint=image.schema_fingerprint,
        files=files,
    )
    assert decoded == image


@pytest.mark.parametrize(
    "filename",
    ["terms.bin", "postings.bin", "stored.bin", "norms.bin"],
)
def test_segment_data_codec_rejects_trailing_bytes(filename):
    image = build_image()
    files = SegmentDataCodec.encode(image)
    files[filename] += b"\x00"
    with pytest.raises(ValueError):
        SegmentDataCodec.decode(
            generation=image.generation,
            schema_fingerprint=image.schema_fingerprint,
            files=files,
        )


def test_segment_data_codec_rejects_missing_file():
    image = build_image()
    files = SegmentDataCodec.encode(image)
    del files["norms.bin"]
    with pytest.raises(ValueError, match="exactly"):
        SegmentDataCodec.decode(
            generation=image.generation,
            schema_fingerprint=image.schema_fingerprint,
            files=files,
        )


def test_segment_data_codec_rejects_invalid_utf8_term_dictionary():
    image = build_image()
    files = SegmentDataCodec.encode(image)
    files["terms.bin"] = files["terms.bin"].replace(b"body", b"\xffody", 1)
    with pytest.raises(ValueError, match="UTF-8"):
        SegmentDataCodec.decode(
            generation=image.generation,
            schema_fingerprint=image.schema_fingerprint,
            files=files,
        )


def test_segment_data_codec_rejects_malformed_stored_json():
    image = build_image()
    files = SegmentDataCodec.encode(image)
    files["stored.bin"] = files["stored.bin"].replace(b'"body"', b'"bodx"', 1)
    files["stored.bin"] = files["stored.bin"].replace(b"{", b"[", 1)
    with pytest.raises(ValueError, match="stored JSON"):
        SegmentDataCodec.decode(
            generation=image.generation,
            schema_fingerprint=image.schema_fingerprint,
            files=files,
        )

# Stage 10 · Educational segment codec

### Goal

Build educational segment codec and explain its boundary from an executable counterexample, runtime state, and the critical statement.

??? note "Deliverable files"
    - `src/minilucene/storage/codec.py`
    - `tests/unit/storage/test_segment_codec.py`

### The problem at this point

A logical image is not durable until every table has an explicit binary layout and cross-file consistency checks.

### Test contract

#### See the failure first

Codec tests corrupt lengths, term order, doc deltas, positions, and trailing bytes across the four segment files.

??? note "File diff: tests/unit/storage/test_segment_codec.py"
    ```diff
    diff --git a/tests/unit/storage/test_segment_codec.py b/tests/unit/storage/test_segment_codec.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..2ca6f7a449fda5e4f422a6da8a0c8029a86f64d4
    --- /dev/null
    +++ b/tests/unit/storage/test_segment_codec.py
    @@ -0,0 +1,103 @@
    +import pytest
    +
    +from minilucene.index.memory import RamIndexBuilder
    +from minilucene.schema import KeywordField, Schema, StoredField, TextField
    +from minilucene.storage.codec import SegmentDataCodec
    +from minilucene.storage.image import SegmentImage
    +
    +
    +def build_image():
    +    schema = Schema(
    +        id=KeywordField(stored=True),
    +        body=TextField(stored=True),
    +        note=StoredField(),
    +    )
    +    builder = RamIndexBuilder(schema)
    +    builder.add_document(
    +        {"id": "文档-1", "body": "Kafka kafka", "note": "α"}
    +    )
    +    builder.add_document(
    +        {"id": "doc-2", "body": "replicas", "note": "β"}
    +    )
    +    return SegmentImage.from_memory_segment(
    +        generation=4,
    +        schema_fingerprint=schema.fingerprint,
    +        segment=builder.freeze(generation=0),
    +    )
    +
    +
    +def test_segment_data_codec_is_deterministic():
    +    image = build_image()
    +    first = SegmentDataCodec.encode(image)
    +    second = SegmentDataCodec.encode(image)
    +    assert first == second
    +    assert set(first) == {
    +        "terms.bin",
    +        "postings.bin",
    +        "stored.bin",
    +        "norms.bin",
    +    }
    +
    +
    +def test_segment_data_codec_round_trips():
    +    image = build_image()
    +    files = SegmentDataCodec.encode(image)
    +    decoded = SegmentDataCodec.decode(
    +        generation=image.generation,
    +        schema_fingerprint=image.schema_fingerprint,
    +        files=files,
    +    )
    +    assert decoded == image
    +
    +
    +@pytest.mark.parametrize(
    +    "filename",
    +    ["terms.bin", "postings.bin", "stored.bin", "norms.bin"],
    +)
    +def test_segment_data_codec_rejects_trailing_bytes(filename):
    +    image = build_image()
    +    files = SegmentDataCodec.encode(image)
    +    files[filename] += b"\x00"
    +    with pytest.raises(ValueError):
    +        SegmentDataCodec.decode(
    +            generation=image.generation,
    +            schema_fingerprint=image.schema_fingerprint,
    +            files=files,
    +        )
    +
    +
    +def test_segment_data_codec_rejects_missing_file():
    +    image = build_image()
    +    files = SegmentDataCodec.encode(image)
    +    del files["norms.bin"]
    +    with pytest.raises(ValueError, match="exactly"):
    +        SegmentDataCodec.decode(
    +            generation=image.generation,
    +            schema_fingerprint=image.schema_fingerprint,
    +            files=files,
    +        )
    +
    +
    +def test_segment_data_codec_rejects_invalid_utf8_term_dictionary():
    +    image = build_image()
    +    files = SegmentDataCodec.encode(image)
    +    files["terms.bin"] = files["terms.bin"].replace(b"body", b"\xffody", 1)
    +    with pytest.raises(ValueError, match="UTF-8"):
    +        SegmentDataCodec.decode(
    +            generation=image.generation,
    +            schema_fingerprint=image.schema_fingerprint,
    +            files=files,
    +        )
    +
    +
    +def test_segment_data_codec_rejects_malformed_stored_json():
    +    image = build_image()
    +    files = SegmentDataCodec.encode(image)
    +    files["stored.bin"] = files["stored.bin"].replace(b'"body"', b'"bodx"', 1)
    +    files["stored.bin"] = files["stored.bin"].replace(b"{", b"[", 1)
    +    with pytest.raises(ValueError, match="stored JSON"):
    +        SegmentDataCodec.decode(
    +            generation=image.generation,
    +            schema_fingerprint=image.schema_fingerprint,
    +            files=files,
    +        )
    ```

**What this test locks**

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

**How it constructs the counterexample**

Codec tests corrupt lengths, term order, doc deltas, positions, and trailing bytes across the four segment files.

**Key test statement**

```python
assert first == second
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

**What a failure means**

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

The codec splits terms, postings, stored fields, and norms into bounded canonical frames while preserving one shared document space.

### Why this mechanism is necessary

A logical image is not durable until every table has an explicit binary layout and cross-file consistency checks. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

Encode orders tables and delta-encodes monotonic IDs; decode validates headers, counts, bounds, ordering, and full input consumption.

### Mechanism blocks

#### Educational segment codec mechanism

Encode orders tables and delta-encodes monotonic IDs; decode validates headers, counts, bounds, ordering, and full input consumption.

??? note "File diff: src/minilucene/storage/codec.py"
    ```diff
    diff --git a/src/minilucene/storage/codec.py b/src/minilucene/storage/codec.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..2285dda6532220b4c97f50734575780623d55405
    --- /dev/null
    +++ b/src/minilucene/storage/codec.py
    @@ -0,0 +1,260 @@
    +import json
    +from collections.abc import Mapping
    +
    +from minilucene.index.postings import Posting
    +from minilucene.storage.image import SegmentImage
    +from minilucene.storage.varint import (
    +    decode_delta_sequence,
    +    decode_uvarint,
    +    encode_delta_sequence,
    +    encode_uvarint,
    +)
    +
    +_DATA_FILES = frozenset(
    +    {"terms.bin", "postings.bin", "stored.bin", "norms.bin"}
    +)
    +
    +
    +def _encode_bytes(value: bytes) -> bytes:
    +    return encode_uvarint(len(value)) + value
    +
    +
    +def _decode_bytes(
    +    data: bytes, offset: int, *, label: str
    +) -> tuple[bytes, int]:
    +    length, offset = decode_uvarint(data, offset)
    +    end = offset + length
    +    if end > len(data):
    +        raise ValueError(f"{label} frame outside input")
    +    return data[offset:end], end
    +
    +
    +def _decode_text(
    +    data: bytes, offset: int, *, label: str
    +) -> tuple[str, int]:
    +    encoded, offset = _decode_bytes(data, offset, label=label)
    +    try:
    +        return encoded.decode("utf-8", errors="strict"), offset
    +    except UnicodeDecodeError as error:
    +        raise ValueError(f"{label} must be strict UTF-8") from error
    +
    +
    +def _encode_posting_list(postings: tuple[Posting, ...]) -> bytes:
    +    encoded = bytearray(encode_uvarint(len(postings)))
    +    previous_doc_id = 0
    +    for index, posting in enumerate(postings):
    +        doc_delta = (
    +            posting.doc_id
    +            if index == 0
    +            else posting.doc_id - previous_doc_id
    +        )
    +        encoded.extend(encode_uvarint(doc_delta))
    +        encoded.extend(encode_uvarint(posting.term_frequency))
    +        encoded.extend(encode_uvarint(len(posting.positions)))
    +        encoded.extend(encode_delta_sequence(posting.positions))
    +        previous_doc_id = posting.doc_id
    +    return bytes(encoded)
    +
    +
    +def _decode_posting_list(data: bytes) -> tuple[Posting, ...]:
    +    count, offset = decode_uvarint(data, 0)
    +    postings: list[Posting] = []
    +    previous_doc_id = 0
    +    for index in range(count):
    +        delta, offset = decode_uvarint(data, offset)
    +        if index and delta == 0:
    +            raise ValueError("posting doc IDs must be strictly increasing")
    +        doc_id = delta if index == 0 else previous_doc_id + delta
    +        term_frequency, offset = decode_uvarint(data, offset)
    +        position_count, offset = decode_uvarint(data, offset)
    +        positions, offset = decode_delta_sequence(
    +            data, offset, position_count
    +        )
    +        postings.append(
    +            Posting(
    +                doc_id=doc_id,
    +                term_frequency=term_frequency,
    +                positions=positions,
    +            )
    +        )
    +        previous_doc_id = doc_id
    +    if offset != len(data):
    +        raise ValueError("trailing bytes in posting list")
    +    return tuple(postings)
    +
    +
    +class SegmentDataCodec:
    +    @staticmethod
    +    def encode(image: SegmentImage) -> dict[str, bytes]:
    +        postings_data = bytearray()
    +        term_entries: list[tuple[str, str, int, int]] = []
    +        for field, terms in image.postings.items():
    +            for term, postings in terms.items():
    +                encoded = _encode_posting_list(postings)
    +                offset = len(postings_data)
    +                postings_data.extend(encoded)
    +                term_entries.append((field, term, offset, len(encoded)))
    +
    +        terms_data = bytearray(encode_uvarint(len(term_entries)))
    +        for field, term, offset, length in term_entries:
    +            terms_data.extend(_encode_bytes(field.encode("utf-8")))
    +            terms_data.extend(_encode_bytes(term.encode("utf-8")))
    +            terms_data.extend(encode_uvarint(offset))
    +            terms_data.extend(encode_uvarint(length))
    +
    +        stored_data = bytearray(encode_uvarint(image.max_doc))
    +        for doc_id in range(image.max_doc):
    +            encoded = json.dumps(
    +                dict(image.stored_documents[doc_id]),
    +                sort_keys=True,
    +                ensure_ascii=False,
    +                separators=(",", ":"),
    +            ).encode("utf-8")
    +            stored_data.extend(_encode_bytes(encoded))
    +
    +        norms_data = bytearray(
    +            encode_uvarint(len(image.field_lengths))
    +        )
    +        for field, lengths in image.field_lengths.items():
    +            norms_data.extend(_encode_bytes(field.encode("utf-8")))
    +            norms_data.extend(encode_uvarint(len(lengths)))
    +            for length in lengths:
    +                norms_data.extend(encode_uvarint(length))
    +
    +        return {
    +            "terms.bin": bytes(terms_data),
    +            "postings.bin": bytes(postings_data),
    +            "stored.bin": bytes(stored_data),
    +            "norms.bin": bytes(norms_data),
    +        }
    +
    +    @staticmethod
    +    def decode(
    +        *,
    +        generation: int,
    +        schema_fingerprint: str,
    +        files: Mapping[str, bytes],
    +    ) -> SegmentImage:
    +        if set(files) != _DATA_FILES:
    +            raise ValueError(
    +                "segment data requires exactly terms, postings, stored, "
    +                "and norms files"
    +            )
    +        if any(not isinstance(value, bytes) for value in files.values()):
    +            raise ValueError("segment file values must be bytes")
    +
    +        term_entries = SegmentDataCodec._decode_terms(files["terms.bin"])
    +        postings = SegmentDataCodec._decode_postings(
    +            term_entries, files["postings.bin"]
    +        )
    +        stored_documents = SegmentDataCodec._decode_stored(
    +            files["stored.bin"]
    +        )
    +        field_lengths = SegmentDataCodec._decode_norms(
    +            files["norms.bin"]
    +        )
    +        return SegmentImage(
    +            generation=generation,
    +            schema_fingerprint=schema_fingerprint,
    +            stored_documents=stored_documents,
    +            postings=postings,
    +            field_lengths=field_lengths,
    +        )
    +
    +    @staticmethod
    +    def _decode_terms(
    +        data: bytes,
    +    ) -> tuple[tuple[str, str, int, int], ...]:
    +        count, offset = decode_uvarint(data, 0)
    +        entries: list[tuple[str, str, int, int]] = []
    +        previous_key: tuple[str, str] | None = None
    +        expected_postings_offset = 0
    +        for _ in range(count):
    +            field, offset = _decode_text(
    +                data, offset, label="term field"
    +            )
    +            term, offset = _decode_text(
    +                data, offset, label="term value"
    +            )
    +            postings_offset, offset = decode_uvarint(data, offset)
    +            postings_length, offset = decode_uvarint(data, offset)
    +            key = (field, term)
    +            if previous_key is not None and key <= previous_key:
    +                raise ValueError("term dictionary must be strictly sorted")
    +            if postings_offset != expected_postings_offset:
    +                raise ValueError(
    +                    "posting offsets must be contiguous and ordered"
    +                )
    +            entries.append(
    +                (field, term, postings_offset, postings_length)
    +            )
    +            previous_key = key
    +            expected_postings_offset += postings_length
    +        if offset != len(data):
    +            raise ValueError("trailing bytes in term dictionary")
    +        return tuple(entries)
    +
    +    @staticmethod
    +    def _decode_postings(
    +        entries: tuple[tuple[str, str, int, int], ...],
    +        data: bytes,
    +    ) -> dict[str, dict[str, tuple[Posting, ...]]]:
    +        postings: dict[str, dict[str, tuple[Posting, ...]]] = {}
    +        expected_end = 0
    +        for field, term, offset, length in entries:
    +            end = offset + length
    +            if end > len(data):
    +                raise ValueError("posting slice outside postings file")
    +            postings.setdefault(field, {})[term] = _decode_posting_list(
    +                data[offset:end]
    +            )
    +            expected_end = end
    +        if expected_end != len(data):
    +            raise ValueError("trailing bytes in postings file")
    +        return postings
    +
    +    @staticmethod
    +    def _decode_stored(
    +        data: bytes,
    +    ) -> dict[int, dict[str, str]]:
    +        count, offset = decode_uvarint(data, 0)
    +        documents: dict[int, dict[str, str]] = {}
    +        for doc_id in range(count):
    +            encoded, offset = _decode_bytes(
    +                data, offset, label="stored document"
    +            )
    +            try:
    +                value = json.loads(encoded.decode("utf-8", errors="strict"))
    +            except (UnicodeDecodeError, json.JSONDecodeError) as error:
    +                raise ValueError("invalid stored JSON") from error
    +            if not isinstance(value, dict) or any(
    +                not isinstance(key, str) or not isinstance(item, str)
    +                for key, item in value.items()
    +            ):
    +                raise ValueError("stored JSON must map strings to strings")
    +            documents[doc_id] = value
    +        if offset != len(data):
    +            raise ValueError("trailing bytes in stored fields")
    +        return documents
    +
    +    @staticmethod
    +    def _decode_norms(data: bytes) -> dict[str, tuple[int, ...]]:
    +        count, offset = decode_uvarint(data, 0)
    +        norms: dict[str, tuple[int, ...]] = {}
    +        previous_field: str | None = None
    +        for _ in range(count):
    +            field, offset = _decode_text(
    +                data, offset, label="norm field"
    +            )
    +            if previous_field is not None and field <= previous_field:
    +                raise ValueError("norm fields must be strictly sorted")
    +            length_count, offset = decode_uvarint(data, offset)
    +            lengths: list[int] = []
    +            for _ in range(length_count):
    +                length, offset = decode_uvarint(data, offset)
    +                lengths.append(length)
    +            norms[field] = tuple(lengths)
    +            previous_field = field
    +        if offset != len(data):
    +            raise ValueError("trailing bytes in norms file")
    +        return norms
    ```

**What it is and why it appears**

The codec splits terms, postings, stored fields, and norms into bounded canonical frames while preserving one shared document space.

**Runtime role**

Encode orders tables and delta-encodes monotonic IDs; decode validates headers, counts, bounds, ordering, and full input consumption.

**Statement understanding**

Rejecting trailing or non-canonical bytes makes one logical image map to one accepted representation, simplifying integrity evidence.

### Verification evidence

Run `uv run pytest -q $(cat journey/stages/10-segment-codec/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Rejecting trailing or non-canonical bytes makes one logical image map to one accepted representation, simplifying integrity evidence.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 4](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/04-codec.md)

[Complete reference patch / 完整参考补丁](https://github.com/system-in-miniature/mini-lucene/blob/main/journey/stages/10-segment-codec/stage.patch)

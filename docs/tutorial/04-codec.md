# Chapter 4: The Disk Codec

Persistence is not “pickle the RAM object.” A useful index format needs explicit
framing, deterministic ordering, integrity metadata, and readers that reject
ambiguous input. MiniLucene's educational codec stores one immutable segment in
four data files plus metadata. It is intentionally unrelated to Apache Lucene's
file format, but it teaches the same systems habit: bytes must have one
validated interpretation or fail closed.

## Learning objectives

By the end of this chapter, you can:

1. encode and decode unsigned variable-length integers;
2. explain delta encoding for increasing document IDs and positions;
3. assign roles to `terms.bin`, `postings.bin`, `stored.bin`, and `norms.bin`;
4. trace SHA-256 and exact-framing validation when a segment opens; and
5. distinguish integrity detection from crash-atomic publication.

## Mechanism: small integers and explicit frames

`src/minilucene/storage/varint.py` implements unsigned LEB128-style integers.
`encode_uvarint` emits seven payload bits per byte and sets the high continuation
bit while more bits remain. Values below 128 need one byte; 128 becomes
hexadecimal `80 01`; 300 becomes `ac 02`. Because Python's `bool` is a subclass
of `int`, the current type/range check accepts it: `False` encodes as `00` and
`True` as `01`. This is a Python-specific consequence of the implementation,
not a separate Boolean wire type. Other values must be integers in the
unsigned 64-bit range.

`decode_uvarint` reads at most ten bytes, reports the next offset, rejects an
unterminated value, and rejects overflow in the tenth byte. Returning the next
offset lets larger decoders consume a sequence without slicing each value.

`encode_delta_sequence` compresses a strictly increasing tuple. It stores the
first absolute value and each later difference. `(3, 10, 11)` becomes deltas
`(3, 7, 1)`, each one byte here. Strict increase matters: zero deltas would
permit duplicate IDs or positions and create an ambiguous semantic structure.
`decode_delta_sequence` reconstructs values while checking count, order, and
uint64 overflow.

The higher-level implementation is
`src/minilucene/storage/codec.py`. `SegmentDataCodec.encode` returns exactly
four byte strings:

- `terms.bin` is the sorted term dictionary. Each entry stores framed UTF-8
  field and term strings plus an offset and length into `postings.bin`.
- `postings.bin` concatenates posting-list frames. A frame stores posting
  count, delta-coded document IDs, term frequency, position count, and
  delta-coded positions.
- `stored.bin` stores a document count followed by length-framed canonical JSON
  objects, one per local document ID.
- `norms.bin` stores sorted field names and a varint field length for every
  document.

The term dictionary and postings file are deliberately separate. A term lookup
finds a contiguous byte slice, then `_decode_posting_list` interprets just that
slice. Every variable-length string or JSON record has a length prefix through
`_encode_bytes`.

### Canonical layout is a validation tool

`SegmentDataCodec.decode` begins by requiring the file-name set to equal the
four expected names. A missing file is not treated as empty, and an unknown
file is not silently ignored. This protects format-version semantics: newer or
incompatible components cannot be opened under an older interpretation.

`_decode_terms` requires `(field, term)` keys to be strictly sorted. It also
requires posting slices to form a gap-free, ordered partition beginning at
offset zero. `_decode_postings` checks that every slice is within the file and
that the final slice consumes every postings byte. `_decode_posting_list`
requires strictly increasing document IDs and consumes its frame exactly.
The stored and norms decoders similarly reject invalid UTF-8, wrong JSON types,
unsorted fields, truncation, and trailing bytes.

These rules reject “a valid prefix plus hidden garbage.” That is fail-closed
behavior: a corrupt segment is unavailable rather than interpreted as a
plausible different index.

### Metadata and SHA-256

`SegmentStore.publish` in `src/minilucene/storage/segment_store.py` encodes the
four files into a temporary segment directory. For every file it writes bytes,
fsyncs the file, and records length and SHA-256 in `segment.json`. Metadata also
contains magic, format version, codec name, generation, schema fingerprint, and
`max_doc`. It fsyncs metadata and the temporary directory, renames the directory
to its final generation name, then fsyncs the parent segments directory.

`SegmentStore.open` performs the reverse. `_read_metadata` requires strict UTF-8
JSON. `_validate_metadata` checks magic, format, codec, generation, schema
fingerprint, document count, and the exact file metadata set.
`_read_and_validate_files` checks each length and digest before
`SegmentDataCodec.decode` parses bytes. Expected low-level failures become
`CorruptIndexError` with segment context.

SHA-256 detects accidental or adversarial byte changes under this local
integrity model; it does not authenticate a trusted writer because no secret or
signature is involved. An attacker who can rewrite both data and metadata can
compute new hashes. Nor does a digest alone make a multi-file commit atomic.
Segment publication and manifest publication are separate protocols; Chapter 5
introduces that distinction and Chapter 7 covers commit atomicity in depth.

### Four files, not four independent truths

The data files must agree. Posting document IDs must be below `max_doc`; norm
arrays must cover the document space; stored document count defines the same
space. `SegmentImage.__post_init__` in
`src/minilucene/storage/image.py` validates the decoded cross-file image,
including schema fingerprint and posting constraints. The metadata's `max_doc`
is checked again against the decoded image in `SegmentStore.open`.

The payoff is a strong open contract: callers receive a coherent immutable
`SegmentImage` or an exception. Query code does not need to carry “maybe
corrupt” branches through every lookup.

### Corruption, compatibility, and recovery are different questions

A corruption check asks whether bytes satisfy the format and recorded digest.
A compatibility check asks whether this reader understands the declared magic,
version, and codec. A recovery protocol asks which complete generation to use
after a crash. MiniLucene answers at different layers:
`SegmentDataCodec.decode` validates canonical structures,
`SegmentStore.open` validates identity and hashes, and the manifest chooses
published generations.

A checksummed segment can still be incompatible. A valid and compatible segment
can still be an uncommitted orphan. Conversely, a manifest that names a missing
or corrupt segment cannot be partially opened: the path fails rather than
silently dropping data.

The codec is eager. `SegmentStore.open` reads and verifies every file and builds
the complete `SegmentImage`. This makes ownership and errors simple but scales
with segment size at open time. Production formats commonly use random access,
memory mapping, block indexes, lazy decoding, and caches. Those techniques move
validation and I/O boundaries and add resource lifetimes this project avoids.

Canonical serialization remains useful without production compression. It
gives stable fixtures, repeatable hashes, and one representation per logical
image. Future layout changes should use a new codec/version rather than making
the old decoder guess.

## Compared with Apache Lucene

Apache Lucene uses versioned codecs and many specialized files and data
structures: segment info, field infos, stored fields, term dictionaries,
postings, norms, doc values, points, live docs, and compound-file options.
Production codecs use packed integers, block compression, skip data, FST-based
term indexes, and compatibility machinery. Lucene's `CodecUtil` headers,
footers, checksums, and segment metadata participate in validation.

MiniLucene's four-file `educational-v1` format has none of that compatibility
or performance engineering. It is not readable by Lucene, and MiniLucene
cannot read a Lucene index. It uses JSON for stored fields, SHA-256 per data
file, eager full-file reads, and simple varints. There is no compound file,
memory mapping, block cache, compression, or pluggable codec API. See
[segment format](../segment-format.md), the
[Lucene mapping](../lucene-mapping.md), and the persistence/corruption rows in
the [behavior matrix](../behavior-matrix.md).

## Hands-on experiment: inspect primitive encodings

```bash
export UV_CACHE_DIR=/tmp/minilucene-uv-cache
uv run --offline python - <<'PY'
from minilucene.storage.varint import (
    decode_uvarint, encode_delta_sequence, encode_uvarint,
)
from minilucene.storage.codec import SegmentDataCodec

for value in (1, 127, 128, 300):
    encoded = encode_uvarint(value)
    print(value, encoded.hex(), decode_uvarint(encoded, 0))
print("bools", encode_uvarint(False).hex(), encode_uvarint(True).hex())

print("deltas", encode_delta_sequence((3, 10, 11)).hex())

try:
    SegmentDataCodec.decode(
        generation=1,
        schema_fingerprint="x",
        files={"terms.bin": b""},
    )
except ValueError as error:
    print(type(error).__name__, str(error))
PY
```

Measured output:

```text
1 01 (1, 1)
127 7f (127, 1)
128 8001 (128, 2)
300 ac02 (300, 2)
bools 00 01
deltas 030701
ValueError segment data requires exactly terms, postings, stored, and norms files
```

The tuple returned by decoding is `(value, next_offset)`. The delta sequence is
the bytes for 3, 7, and 1. The incomplete file map fails before any bytes are
interpreted.

Run the codec and corruption checks:

```bash
uv run --offline pytest -q tests/unit/storage/test_varint.py \
  tests/unit/storage/test_segment_codec.py \
  tests/storage/test_segment_store.py
```

Measured result:

```text
27 passed in 0.28s
```

## Exercises

1. **Understanding:** Why must the decoder reject trailing bytes even if the
   preceding frame is valid?

    ??? note "Reference answer"
        Otherwise one byte sequence could have multiple interpretations: a
        valid value plus ignored data, or a newer structure. Exact consumption
        gives one canonical interpretation and exposes corruption.

2. **Understanding:** What does SHA-256 prove here, and what does it not prove?

    ??? note "Reference answer"
        It detects bytes that differ from the digest in metadata. It does not
        authenticate who wrote the index and does not by itself make a
        multi-file publication crash-atomic.

3. **Hands-on:** Add `16384` to the varint loop. Acceptance: the encoded hex is
   `808001` and decoding reports next offset 3.

    ??? note "Reference answer"
        Seven payload bits per byte require three bytes:
        `print(encode_uvarint(16384).hex())` prints `808001`.

4. **Hands-on:** Call `encode_delta_sequence((3, 3))` and capture the failure.
   Acceptance: it raises `ValueError` with the strictly-increasing message.

    ??? note "Reference answer"
        Wrap the call in `try/except ValueError`. Duplicate absolute values
        create a zero delta and violate the posting/position ordering contract.

## Summary

MiniLucene's codec converts an immutable logical image into four canonically
framed files. Varints and deltas make ordered integers compact; sorted,
gap-free layouts and exact consumption make malformed bytes unambiguous;
metadata hashes detect changes before parsing. The next chapter explains why a
valid segment can still be invisible: persistence bytes, reader visibility, and
restart durability are three different boundaries.

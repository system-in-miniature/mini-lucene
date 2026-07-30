> **Language**: English | [简体中文](zh/segment-format.md)

# MiniLucene V1 Segment Data Format

MiniLucene segments are deterministic educational files. They are not Apache
Lucene files and carry no compatibility promise beyond the format version
recorded by MiniLucene's own segment metadata.

All strings are strict UTF-8. All integers are unsigned 64-bit varints. A byte
string frame is:

```text
byte_length:uvarint
bytes[byte_length]
```

Document IDs are dense, zero-based, and local to one immutable segment.

## `terms.bin`

```text
term_count:uvarint
repeat term_count:
    field:utf8_frame
    term:utf8_frame
    postings_offset:uvarint
    postings_length:uvarint
```

Entries sort strictly by `(field, term)`. Offsets are contiguous and point into
`postings.bin`; gaps, overlap, out-of-range slices, duplicate terms, and
trailing bytes are corruption.

## `postings.bin`

Each term points to one complete posting-list frame:

```text
posting_count:uvarint
repeat posting_count:
    doc_id_delta:uvarint
    term_frequency:uvarint
    position_count:uvarint
    position_deltas[position_count]:uvarint
```

The first document and position values are absolute. Later values are positive
deltas, so decoded IDs and positions must strictly increase. Keyword fields
have positive term frequency and zero stored positions.

## `stored.bin`

```text
document_count:uvarint
repeat document_count:
    canonical_json:utf8_frame
```

Each JSON object maps field names to Unicode strings. Encoding uses sorted keys,
no insignificant whitespace, and literal Unicode:

```python
json.dumps(
    value,
    sort_keys=True,
    ensure_ascii=False,
    separators=(",", ":"),
)
```

Frame order is local document-ID order.

## `norms.bin`

```text
field_count:uvarint
repeat field_count:
    field:utf8_frame
    document_length_count:uvarint
    document_lengths[document_length_count]:uvarint
```

Fields sort strictly. Every indexed field has exactly one analyzed token length
per segment document.

## Integrity boundary

These four files do not publish themselves. `segment.json`, written and synced
after the data files, records format magic/version, generation, schema
fingerprint, byte length, SHA-256 checksum, and codec identifier for every
file. The committed manifest is a later and separate publication boundary.

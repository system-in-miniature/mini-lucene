# Phase 2: Immutable Storage and Commit Acceptance

## Accepted persistence loop

```text
RamIndexBuilder
→ immutable SegmentImage
→ deterministic term/posting/stored/norm codecs
→ checksummed temporary segment directory
→ atomic segment rename
→ writer segment set
→ atomic manifest replacement
→ fresh committed IndexReader
```

`manifest.json` is the only recoverable root. A complete segment directory that
is not referenced by the manifest is an orphan and remains invisible after
reopen.

## Frozen storage behavior

- Segment generations are positive and document IDs are dense and local.
- Unsigned varints are uint64-bounded; document IDs and positions use positive
  deltas after their first value.
- Terms sort by field and term; their offsets cover `postings.bin`
  contiguously.
- Stored fields are length-framed canonical UTF-8 JSON.
- Norms carry one analyzed field length per local document.
- `segment.json` records magic, version, codec, schema fingerprint, lengths,
  and SHA-256 checksums.
- Segment data files are synced before `segment.json`; metadata is synced
  before the segment directory is atomically renamed.
- Schema JSON is persisted separately and verified against its SHA-256
  fingerprint and the committed manifest.
- Only one `IndexWriter` lock may exist per index path.
- Flush publishes an immutable segment to the writer state but does not modify
  the manifest.
- Commit flushes, reopens and validates every referenced segment, then replaces
  the manifest atomically.
- A manifest replacement failure leaves the previous commit authoritative.
- `Index.open_reader()` loads exactly the ordered manifest references and
  computes global reader statistics.
- Disk results and scores match the one-segment in-memory oracle.

## Failure evidence

Executable tests cover:

- failure during a data-file write before directory rename;
- corrupted file length or checksum;
- schema mismatch;
- malformed manifest and unknown versions;
- complete orphan segments;
- manifest replacement failure;
- fresh reopen after successful commit.

The segment byte layout is documented in
[`segment-format.md`](segment-format.md).

## Accepted commands

Executed on 2026-07-27:

```text
uv run pytest tests/acceptance/test_phase2_storage_commit.py -q
1 passed

uv run ruff check src tests tools
All checks passed

uv run pytest -q
108 passed

uv run python -m compileall -q src tests tools
exit 0

git diff --check
exit 0
```

## Deferred by phase boundary

Phase 2 has no NRT refresh, live-doc files, delete, update, merge, reference
owned cleanup, query-string parser, highlighting, network adapter, distributed
coordination, or vector retrieval.

# MiniLucene Immutable Storage and Commit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Execute inline and complete tasks in order.

**Goal:** Persist Phase 1 segments with deterministic codecs, publish commits atomically through one manifest, and reopen committed indexes with search results equivalent to the in-memory oracle.

**Architecture:** A frozen `SegmentImage` crosses the RAM/disk boundary. `SegmentCodec` writes immutable, checksummed segment directories. `ManifestStore` is the only recoverable root. `IndexWriter` owns the RAM buffer and generation counters; `Index.open_reader()` consumes only the committed manifest.

**Tech Stack:** Python 3.12 standard library (`pathlib`, `json`, `hashlib`, `os`, `struct`), pytest, Ruff, uv.

---

### Task 1: Freeze `SegmentImage` as the storage boundary

**Files:**
- Create: `src/minilucene/storage/__init__.py`
- Create: `src/minilucene/storage/image.py`
- Create: `tests/unit/storage/test_segment_image.py`

- [x] **Step 1: Write the failing invariant tests**

```python
import pytest

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


def test_segment_image_is_immutable(ram_segment):
    image = SegmentImage.from_ram_segment(7, "schema", ram_segment)
    with pytest.raises(TypeError):
        image.stored_documents[0] = {"id": "changed"}
```

- [x] **Step 2: Run RED**

```bash
uv run pytest tests/unit/storage/test_segment_image.py -q
```

Expected: import failure because `storage.image` does not exist.

- [x] **Step 3: Implement the frozen image**

Use immutable tuples and `MappingProxyType`. Validate generation is positive,
document IDs are exactly `range(max_doc)`, posting doc IDs are increasing and
in range, positions are increasing, and every field-length vector has
`max_doc` entries.

Public constructor:

```python
@dataclass(frozen=True)
class SegmentImage:
    generation: int
    schema_fingerprint: str
    stored_documents: Mapping[int, Mapping[str, str]]
    postings: Mapping[str, Mapping[str, tuple[Posting, ...]]]
    field_lengths: Mapping[str, tuple[int, ...]]

    @property
    def max_doc(self) -> int: ...

    @classmethod
    def from_ram_segment(
        cls, generation: int, schema_fingerprint: str, segment: MemorySegment
    ) -> "SegmentImage": ...
```

- [x] **Step 4: Run GREEN and regression**

```bash
uv run pytest tests/unit/storage/test_segment_image.py tests/unit/index -q
```

- [x] **Step 5: Commit**

```bash
git add src/minilucene/storage tests/unit/storage/test_segment_image.py
git commit -m "feat: freeze immutable segment images"
```

### Task 2: Implement unsigned varints and delta sequences

**Files:**
- Create: `src/minilucene/storage/varint.py`
- Create: `tests/unit/storage/test_varint.py`

- [x] **Step 1: Write table and malformed-input tests**

```python
import pytest

from minilucene.storage.varint import (
    decode_delta_sequence,
    decode_uvarint,
    encode_delta_sequence,
    encode_uvarint,
)


@pytest.mark.parametrize("value", [0, 1, 127, 128, 16_384, 2**63 - 1])
def test_uvarint_round_trip(value):
    encoded = encode_uvarint(value)
    assert decode_uvarint(encoded, 0) == (value, len(encoded))


def test_delta_sequence_requires_strict_increase():
    with pytest.raises(ValueError, match="increasing"):
        encode_delta_sequence((2, 2))


def test_unterminated_varint_is_rejected():
    with pytest.raises(ValueError, match="unterminated"):
        decode_uvarint(b"\x80", 0)
```

- [x] **Step 2: Run RED**

```bash
uv run pytest tests/unit/storage/test_varint.py -q
```

- [x] **Step 3: Implement bounded decoding**

`decode_uvarint` accepts at most ten bytes and rejects overflow, negative
offsets, out-of-bounds offsets, and unterminated input. Delta decoding accepts
an explicit element count and rejects zero deltas after the first element.

- [x] **Step 4: Run GREEN**

```bash
uv run pytest tests/unit/storage/test_varint.py -q
```

- [x] **Step 5: Commit**

```bash
git add src/minilucene/storage/varint.py tests/unit/storage/test_varint.py
git commit -m "feat: add bounded varint codecs"
```

### Task 3: Encode terms, postings, stored fields, and norms

**Files:**
- Create: `src/minilucene/storage/codec.py`
- Create: `tests/unit/storage/test_segment_codec.py`
- Create: `docs/segment-format.md`

- [x] **Step 1: Write byte-stability and round-trip tests**

```python
from minilucene.storage.codec import SegmentDataCodec


def test_segment_data_codec_is_deterministic(segment_image):
    first = SegmentDataCodec.encode(segment_image)
    second = SegmentDataCodec.encode(segment_image)
    assert first == second
    assert set(first) == {
        "terms.bin",
        "postings.bin",
        "stored.bin",
        "norms.bin",
    }


def test_segment_data_codec_round_trips(segment_image):
    files = SegmentDataCodec.encode(segment_image)
    decoded = SegmentDataCodec.decode(
        generation=segment_image.generation,
        schema_fingerprint=segment_image.schema_fingerprint,
        files=files,
    )
    assert decoded == segment_image
```

Add corruption cases for invalid UTF-8, offsets outside `postings.bin`,
non-monotonic doc IDs, non-monotonic positions, malformed JSON frames, trailing
bytes, and field-length count mismatches.

- [x] **Step 2: Run RED**

```bash
uv run pytest tests/unit/storage/test_segment_codec.py -q
```

- [x] **Step 3: Implement the documented codec**

Encoding contracts:

```text
terms.bin:
  term_count
  repeated(field_utf8, term_utf8, postings_offset, postings_length)

postings.bin:
  posting_count
  repeated(doc_delta, tf, position_count, position_deltas)

stored.bin:
  doc_count
  repeated(json_byte_length, canonical_json_bytes)

norms.bin:
  field_count
  repeated(field_utf8, length_count, document_lengths)
```

Every integer and byte-string length uses unsigned varints. Terms sort by
`(field UTF-8 bytes, term UTF-8 bytes)`. JSON uses
`sort_keys=True, ensure_ascii=False, separators=(",", ":")`.

- [x] **Step 4: Document the exact format**

`docs/segment-format.md` records magic/version ownership, every frame, sorting
rules, validation rules, and that compatibility with Apache Lucene is absent.

- [x] **Step 5: Run GREEN and deterministic check**

```bash
uv run pytest tests/unit/storage/test_segment_codec.py -q
uv run ruff check src/minilucene/storage tests/unit/storage
```

- [x] **Step 6: Commit**

```bash
git add src/minilucene/storage/codec.py tests/unit/storage/test_segment_codec.py docs/segment-format.md
git commit -m "feat: encode educational segment data"
```

### Task 4: Publish checksummed immutable segment directories

**Files:**
- Create: `src/minilucene/storage/filesystem.py`
- Create: `src/minilucene/storage/segment_store.py`
- Create: `tests/storage/test_segment_store.py`

- [x] **Step 1: Write publication and cleanup tests**

```python
from pathlib import Path

import pytest

from minilucene.storage.segment_store import SegmentStore


def test_segment_store_writes_metadata_last(tmp_path, segment_image, recording_fs):
    store = SegmentStore(tmp_path, fs=recording_fs)
    descriptor = store.publish(segment_image)
    assert recording_fs.file_syncs[-1].name == "segment.json"
    assert descriptor.path == Path("segments/seg_000001")
    assert not list((tmp_path / "segments").glob(".tmp-*"))


def test_failed_publish_never_creates_final_directory(
    tmp_path, segment_image, failing_fs
):
    store = SegmentStore(tmp_path, fs=failing_fs.fail_on_write("postings.bin"))
    with pytest.raises(OSError):
        store.publish(segment_image)
    assert not (tmp_path / "segments" / "seg_000001").exists()
```

- [x] **Step 2: Run RED**

```bash
uv run pytest tests/storage/test_segment_store.py -q
```

- [x] **Step 3: Implement injected filesystem operations**

`FileSystemOps` wraps mkdir, write, fsync-file, fsync-directory, replace, read,
remove-tree, and list-directory. `SegmentStore.publish` uses a UUID temp
directory, writes four data files, fsyncs them, writes `segment.json` last with
magic/version/generation/schema fingerprint/length/SHA-256 entries, fsyncs,
renames atomically, and fsyncs `segments/`.

- [x] **Step 4: Implement strict open**

`SegmentStore.open(generation, expected_schema_fingerprint)` validates metadata
before decoding. Unknown version, wrong schema, missing file, wrong length,
wrong checksum, or invalid codec data raises `CorruptIndexError` without
returning a partial image.

- [x] **Step 5: Run GREEN**

```bash
uv run pytest tests/storage/test_segment_store.py -q
```

- [x] **Step 6: Commit**

```bash
git add src/minilucene/storage/filesystem.py src/minilucene/storage/segment_store.py tests/storage/test_segment_store.py
git commit -m "feat: publish checksummed immutable segments"
```

### Task 5: Make the manifest the only committed root

**Files:**
- Create: `src/minilucene/storage/manifest.py`
- Create: `tests/storage/test_manifest_store.py`

- [x] **Step 1: Write atomic-root tests**

```python
import pytest

from minilucene.storage.manifest import Manifest, ManifestStore


def test_open_ignores_complete_orphan_segment(tmp_path, published_segment):
    store = ManifestStore(tmp_path)
    store.create(schema_fingerprint="schema")
    manifest = store.read()
    assert manifest.segment_generations == ()


def test_replace_failure_preserves_old_manifest(tmp_path, failing_fs):
    store = ManifestStore(tmp_path)
    store.create(schema_fingerprint="schema")
    old = store.read()
    broken = Manifest.next_from(old, segment_generations=(1,))
    with pytest.raises(OSError):
        store.write_atomic(broken, fs=failing_fs.fail_on_replace())
    assert store.read() == old
```

- [x] **Step 2: Run RED**

```bash
uv run pytest tests/storage/test_manifest_store.py -q
```

- [x] **Step 3: Implement immutable manifest values**

Manifest fields:

```python
@dataclass(frozen=True)
class SegmentCommit:
    segment_generation: int
    live_docs_generation: int | None
    live_docs_checksum: str | None


@dataclass(frozen=True)
class Manifest:
    format_version: int
    schema_fingerprint: str
    commit_generation: int
    segments: tuple[SegmentCommit, ...]
    next_segment_generation: int
    next_commit_generation: int
```

Create writes persisted schema plus generation-zero manifest. Update writes
canonical JSON to `manifest.tmp`, fsyncs, replaces `manifest.json`, and fsyncs
the index directory. Startup removes neither orphans nor temp files; it ignores
anything not referenced by the manifest.

- [x] **Step 4: Run GREEN**

```bash
uv run pytest tests/storage/test_manifest_store.py -q
```

- [x] **Step 5: Commit**

```bash
git add src/minilucene/storage/manifest.py tests/storage/test_manifest_store.py
git commit -m "feat: make manifest the committed index root"
```

### Task 6: Add index creation, schema persistence, and writer exclusion

**Files:**
- Create: `src/minilucene/index.py`
- Create: `src/minilucene/writer.py`
- Create: `src/minilucene/errors.py`
- Modify: `src/minilucene/__init__.py`
- Create: `tests/contract/test_index_lifecycle.py`

- [x] **Step 1: Write public lifecycle tests**

```python
import pytest

from minilucene import Index, KeywordField, Schema, TextField
from minilucene.errors import SchemaMismatchError, WriterAlreadyOpenError


def test_create_open_and_schema_fingerprint(tmp_path):
    schema = Schema(id=KeywordField(stored=True), body=TextField(stored=True))
    index = Index.create(tmp_path, schema)
    assert Index.open(tmp_path).schema == schema


def test_open_rejects_supplied_different_schema(tmp_path, schema):
    Index.create(tmp_path, schema)
    with pytest.raises(SchemaMismatchError):
        Index.open(tmp_path, Schema(body=TextField(stored=True)))


def test_only_one_writer_can_be_open(tmp_path, schema):
    index = Index.create(tmp_path, schema)
    first = index.writer()
    with pytest.raises(WriterAlreadyOpenError):
        index.writer()
    first.close()
    index.writer().close()
```

- [x] **Step 2: Run RED**

```bash
uv run pytest tests/contract/test_index_lifecycle.py -q
```

- [x] **Step 3: Implement lifecycle ownership**

`Index.create` refuses non-empty initialized paths, persists schema, and writes
manifest zero. `Index.open` validates schema fingerprint. `Index.writer`
creates an exclusive `.writer.lock` with `O_CREAT | O_EXCL`; `close()` releases
it idempotently. Stale-lock recovery is explicit and outside V1.

- [x] **Step 4: Run GREEN**

```bash
uv run pytest tests/contract/test_index_lifecycle.py -q
```

- [x] **Step 5: Commit**

```bash
git add src/minilucene/index.py src/minilucene/writer.py src/minilucene/errors.py src/minilucene/__init__.py tests/contract/test_index_lifecycle.py
git commit -m "feat: own index and writer lifecycle"
```

### Task 7: Implement deterministic flush without publication

**Files:**
- Modify: `src/minilucene/writer.py`
- Create: `tests/storage/test_writer_flush.py`

- [x] **Step 1: Write visibility and threshold tests**

```python
def test_flush_creates_segment_but_does_not_change_manifest(index):
    with index.writer() as writer:
        writer.add_document(id="1", body="alpha")
        segment = writer.flush()
        assert segment.generation == 1
        assert index.manifest().segments == ()


def test_document_threshold_flushes_before_next_add(index_with_threshold_one):
    with index_with_threshold_one.writer() as writer:
        writer.add_document(id="1", body="alpha")
        writer.add_document(id="2", body="beta")
        assert writer.segment_generations == (1,)
        assert writer.buffered_document_count == 1
```

- [x] **Step 2: Run RED**

```bash
uv run pytest tests/storage/test_writer_flush.py -q
```

- [x] **Step 3: Implement flush**

Before each add, validate and analyze the complete document into a temporary
prepared document. Mutate the RAM buffer only after preparation succeeds.
Flush freezes `SegmentImage`, publishes it, appends its descriptor only to the
writer's current segment set, increments generation, and replaces the RAM
buffer only after publication succeeds. Empty flush returns `None`.

Automatic flush uses `FlushPolicy(max_documents, max_postings)` and checks the
logical counts before admitting the next document.

- [x] **Step 4: Run GREEN**

```bash
uv run pytest tests/storage/test_writer_flush.py tests/contract/test_memory_search.py -q
```

- [x] **Step 5: Commit**

```bash
git add src/minilucene/writer.py tests/storage/test_writer_flush.py
git commit -m "feat: flush writer buffers to immutable segments"
```

### Task 8: Commit and reopen equivalent disk search

**Files:**
- Modify: `src/minilucene/writer.py`
- Modify: `src/minilucene/index.py`
- Create: `src/minilucene/reader.py`
- Create: `tests/storage/test_commit_recovery.py`
- Create: `tests/contract/test_disk_search.py`

- [x] **Step 1: Write old-or-new crash tests**

Inject failures at: segment data write, segment metadata write, segment rename,
manifest temp write, and manifest replace. For each failure reopen the index
and assert it yields the last successfully published manifest only.

```python
def test_complete_segment_without_manifest_is_ignored_after_reopen(index):
    with index.writer() as writer:
        writer.add_document(id="1", body="orphan")
        writer.flush()
    reopened = type(index).open(index.path)
    assert reopened.open_reader().max_doc == 0
```

- [x] **Step 2: Write equivalence contract**

Build the same corpus in `MemoryIndex` and disk `Index`, commit, reopen, search
term/phrase/prefix/boolean queries, and compare total hits, stored fields,
scores with `pytest.approx`, and final order.

- [x] **Step 3: Run RED**

```bash
uv run pytest tests/storage/test_commit_recovery.py tests/contract/test_disk_search.py -q
```

- [x] **Step 4: Implement commit**

Commit flushes, verifies all referenced segments, creates the next immutable
manifest, publishes it atomically, then updates writer committed state. A
failed manifest publication leaves the prior committed manifest authoritative
and keeps the writer open for explicit retry or close.

- [x] **Step 5: Implement committed reader**

`Index.open_reader()` loads exactly the manifest's segments, constructs one
multi-segment reader view, computes global corpus statistics, and searches
through the Phase 1 scorer/collector path. It never scans unreferenced
directories.

- [x] **Step 6: Run GREEN and phase verification**

```bash
uv run pytest tests/storage/test_commit_recovery.py tests/contract/test_disk_search.py -q
uv run ruff check src tests tools
uv run pytest -q
uv run python -m compileall -q src tests tools
git diff --check
```

- [x] **Step 7: Commit**

```bash
git add src/minilucene/writer.py src/minilucene/index.py src/minilucene/reader.py tests/storage/test_commit_recovery.py tests/contract/test_disk_search.py
git commit -m "feat: atomically commit and reopen indexes"
```

### Task 9: Accept immutable storage and commit

**Files:**
- Create: `tests/acceptance/test_phase2_storage_commit.py`
- Create: `docs/phase2-storage-commit.md`

- [x] **Step 1: Add one restart acceptance**

Create two segments, commit, reopen through a fresh `Index`, and prove stored
fields, phrase hits, BM25 scores, schema fingerprint, generation ordering, and
absence of orphan visibility match the in-memory oracle.

- [x] **Step 2: Run phase acceptance**

```bash
uv sync --dev
uv run pytest tests/acceptance/test_phase2_storage_commit.py -q
uv run ruff check src tests tools
uv run pytest -q
uv run python -m compileall -q src tests tools
git diff --check
```

- [x] **Step 3: Write the phase report**

`docs/phase2-storage-commit.md` records the segment format, manifest authority,
flush/commit distinction, crash matrix, verification commands, and the absence
of refresh, deletion, merge, query parsing, network, and vector behavior.

- [x] **Step 4: Commit acceptance**

```bash
git add tests/acceptance/test_phase2_storage_commit.py docs/phase2-storage-commit.md
git commit -m "test: accept immutable storage and commit"
git status --short
```

Expected: clean worktree.

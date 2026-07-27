# MiniLucene NRT Mutation and Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Execute inline and complete tasks in order.

**Goal:** Add immutable reader snapshots, refresh-visible uncommitted state, delete/update overlays, explicit segment merge, and reference-owned cleanup without changing old readers.

**Architecture:** A writer publishes new immutable `ReaderSnapshot` values. Per-segment immutable live-doc files mask deletes. Refresh and commit publish different roots. Merge builds a new segment off to the side and swaps the writer's segment set only after success. `SegmentRegistry` retains obsolete files until no owner references them.

**Tech Stack:** Python 3.12 standard library, pytest, Ruff, uv.

---

### Task 1: Freeze reader snapshots and closed-state behavior

**Files:**
- Modify: `src/minilucene/reader.py`
- Create: `src/minilucene/snapshot.py`
- Create: `tests/nrt/test_reader_snapshot.py`

- [x] **Step 1: Write snapshot and close tests**

```python
import pytest

from minilucene.errors import AlreadyClosedError


def test_reader_snapshot_never_changes_after_later_commit(index):
    with index.writer() as writer:
        writer.add_document(id="1", body="old")
        writer.commit()
    old_reader = index.open_reader()
    with index.writer() as writer:
        writer.add_document(id="2", body="new")
        writer.commit()
    assert old_reader.max_doc == 1
    assert index.open_reader().max_doc == 2


def test_reader_close_is_idempotent_and_operations_fail(index_with_doc):
    reader = index_with_doc.open_reader()
    reader.close()
    reader.close()
    with pytest.raises(AlreadyClosedError):
        reader.document(0)
```

- [x] **Step 2: Run RED**

```bash
uv run pytest tests/nrt/test_reader_snapshot.py -q
```

- [x] **Step 3: Implement immutable snapshot values**

```python
@dataclass(frozen=True)
class SegmentSnapshot:
    generation: int
    image: SegmentImage
    live_docs: frozenset[int]


@dataclass(frozen=True)
class ReaderSnapshot:
    schema_fingerprint: str
    segments: tuple[SegmentSnapshot, ...]
    corpus_stats: CorpusStats
    commit_generation: int | None
```

`IndexReader` holds exactly one snapshot and lifecycle flag. Searches take a
local reference to the snapshot before checking segment data. Closing releases
ownership once and never mutates the snapshot value.

- [x] **Step 4: Run GREEN**

```bash
uv run pytest tests/nrt/test_reader_snapshot.py tests/contract/test_disk_search.py -q
```

- [x] **Step 5: Commit**

```bash
git add src/minilucene/reader.py src/minilucene/snapshot.py tests/nrt/test_reader_snapshot.py
git commit -m "feat: freeze point-in-time reader snapshots"
```

### Task 2: Publish NRT readers through explicit refresh

**Files:**
- Modify: `src/minilucene/writer.py`
- Modify: `src/minilucene/index.py`
- Create: `tests/nrt/test_refresh_visibility.py`

- [x] **Step 1: Write the three-boundary tests**

```python
def test_refresh_sees_flushed_uncommitted_documents(index):
    committed = index.open_reader()
    with index.writer() as writer:
        writer.add_document(id="1", body="visible")
        nrt = writer.refresh()
        assert nrt.search(TermQuery("body", "visible"), 10).total_hits == 1
        assert committed.max_doc == 0
        assert index.open_reader().max_doc == 0


def test_uncommitted_refresh_state_disappears_after_process_reopen(index):
    with index.writer() as writer:
        writer.add_document(id="1", body="ephemeral")
        assert writer.refresh().max_doc == 1
    reopened = type(index).open(index.path)
    assert reopened.open_reader().max_doc == 0
```

- [x] **Step 2: Run RED**

```bash
uv run pytest tests/nrt/test_refresh_visibility.py -q
```

- [x] **Step 3: Implement refresh**

`writer.refresh()` flushes the RAM buffer, captures the writer's current
segment set and live-doc masks, computes one global live-doc `CorpusStats`,
creates a new reader, and records only the writer-owned unpublished reader
handle needed for cleanup. It does not write `manifest.json`.

Repeated refresh with no state change returns a distinct reader object sharing
the same immutable snapshot.

- [x] **Step 4: Run GREEN**

```bash
uv run pytest tests/nrt/test_refresh_visibility.py -q
```

- [x] **Step 5: Commit**

```bash
git add src/minilucene/writer.py src/minilucene/index.py tests/nrt/test_refresh_visibility.py
git commit -m "feat: publish explicit near-real-time readers"
```

### Task 3: Store immutable live-doc generations

**Files:**
- Create: `src/minilucene/storage/live_docs.py`
- Modify: `src/minilucene/storage/manifest.py`
- Create: `tests/unit/storage/test_live_docs.py`
- Create: `tests/storage/test_live_docs_commit.py`

- [x] **Step 1: Write codec and manifest-reference tests**

```python
from minilucene.storage.live_docs import LiveDocsCodec


def test_live_docs_round_trip_and_checksum():
    encoded = LiveDocsCodec.encode(max_doc=5, live_docs=frozenset({0, 2, 4}))
    assert LiveDocsCodec.decode(5, encoded) == frozenset({0, 2, 4})


def test_manifest_points_to_exact_immutable_live_docs_generation(index):
    with index.writer() as writer:
        writer.add_document(id="1", body="alpha")
        writer.commit()
        writer.delete_by_term("id", "1")
        writer.commit()
    commit = index.manifest().segments[0]
    assert commit.live_docs_generation == 1
    assert commit.live_docs_checksum
```

- [x] **Step 2: Run RED**

```bash
uv run pytest tests/unit/storage/test_live_docs.py tests/storage/test_live_docs_commit.py -q
```

- [x] **Step 3: Implement the codec and store**

Encode `max_doc` plus a fixed-length bitset; unused high bits must be zero.
Files are named:

```text
segments/seg_000001/live_000001.bin
```

Publication writes a unique temp file, fsyncs, atomically renames, and fsyncs
the segment directory. Existing live-doc files never change. Manifest entries
carry generation and SHA-256; `None` means all documents are live.

- [x] **Step 4: Run GREEN**

```bash
uv run pytest tests/unit/storage/test_live_docs.py tests/storage/test_live_docs_commit.py -q
```

- [x] **Step 5: Commit**

```bash
git add src/minilucene/storage/live_docs.py src/minilucene/storage/manifest.py tests/unit/storage/test_live_docs.py tests/storage/test_live_docs_commit.py
git commit -m "feat: persist immutable live-document masks"
```

### Task 4: Delete by exact term across buffer and segments

**Files:**
- Modify: `src/minilucene/writer.py`
- Modify: `src/minilucene/index/memory.py`
- Create: `tests/nrt/test_delete_by_term.py`

- [x] **Step 1: Write buffered, flushed, stale-reader, and stats tests**

```python
def test_delete_matches_buffered_and_flushed_documents(index):
    with index.writer() as writer:
        writer.add_document(id="same", body="first")
        writer.flush()
        writer.add_document(id="same", body="second")
        assert writer.delete_by_term("id", "same") == 2
        reader = writer.refresh()
        assert reader.max_doc == 0


def test_old_reader_keeps_deleted_document_and_new_stats_exclude_it(index):
    with index.writer() as writer:
        writer.add_document(id="1", body="rare")
        writer.add_document(id="2", body="common")
        writer.commit()
    old = index.open_reader()
    with index.writer() as writer:
        writer.delete_by_term("id", "1")
        new = writer.refresh()
    assert old.search(TermQuery("body", "rare"), 10).total_hits == 1
    assert new.search(TermQuery("body", "rare"), 10).total_hits == 0
    assert new.corpus_stats.live_doc_count == 1
```

- [x] **Step 2: Run RED**

```bash
uv run pytest tests/nrt/test_delete_by_term.py -q
```

- [x] **Step 3: Implement exact-term deletion**

Validate the term field is indexed. For buffered documents, maintain a
buffer-local live set so local doc IDs remain dense and postings remain
immutable until flush; flush skips deleted buffered docs and remaps survivors
dense. For existing segments, derive a new `frozenset` from current live docs.
Apply all derived masks to writer state only after every segment scan succeeds.

Return the number of newly deleted live documents. Repeating the same delete
returns zero.

- [x] **Step 4: Run GREEN**

```bash
uv run pytest tests/nrt/test_delete_by_term.py -q
```

- [x] **Step 5: Commit**

```bash
git add src/minilucene/writer.py src/minilucene/index/memory.py tests/nrt/test_delete_by_term.py
git commit -m "feat: delete live documents by exact term"
```

### Task 5: Define update as atomic writer-state delete plus add

**Files:**
- Modify: `src/minilucene/writer.py`
- Create: `tests/nrt/test_update_document.py`

- [x] **Step 1: Write replacement and rollback tests**

```python
import pytest


def test_update_deletes_all_matches_then_adds_one_replacement(index):
    with index.writer() as writer:
        writer.add_document(id="1", body="old one")
        writer.add_document(id="1", body="old two")
        writer.commit()
        deleted = writer.update_document(
            field="id", term="1", id="1", body="replacement"
        )
        assert deleted == 2
        reader = writer.refresh()
    assert reader.search(TermQuery("body", "old"), 10).total_hits == 0
    assert reader.search(TermQuery("body", "replacement"), 10).total_hits == 1


def test_invalid_replacement_leaves_delete_state_unchanged(index):
    with index.writer() as writer:
        writer.add_document(id="1", body="old")
        writer.commit()
        with pytest.raises(TypeError):
            writer.update_document(field="id", term="1", id="1", body=7)
        assert writer.refresh().search(TermQuery("body", "old"), 10).total_hits == 1
```

- [x] **Step 2: Run RED**

```bash
uv run pytest tests/nrt/test_update_document.py -q
```

- [x] **Step 3: Implement prepare-then-swap**

Prepare and analyze the replacement document first. Derive delete masks
without mutating writer state. Copy the RAM buffer, apply buffered deletes, add
the prepared replacement, then swap masks and RAM buffer together. Commit and
refresh publish both sides together.

- [x] **Step 4: Run GREEN**

```bash
uv run pytest tests/nrt/test_update_document.py -q
```

- [x] **Step 5: Commit**

```bash
git add src/minilucene/writer.py tests/nrt/test_update_document.py
git commit -m "feat: update as delete plus add"
```

### Task 6: Recompute global live-document BM25 statistics

**Files:**
- Modify: `src/minilucene/search/stats.py`
- Modify: `src/minilucene/reader.py`
- Create: `tests/nrt/test_live_bm25_stats.py`

- [x] **Step 1: Write multi-segment counterexamples**

Construct two logically identical indexes:

1. one segment containing only live documents;
2. three segments containing the same live documents plus deleted documents.

Assert every term query yields equal `N`, `df`, `avgdl`, scores, and order.
Also assert one segment cannot expose a local-IDF API to its scorer.

- [x] **Step 2: Run RED**

```bash
uv run pytest tests/nrt/test_live_bm25_stats.py -q
```

- [x] **Step 3: Centralize snapshot statistics**

`ReaderSnapshot.build` walks each segment's live doc IDs, accumulates global
document count, per-field document count/total length, and per-field/term live
document frequency. It freezes `CorpusStats` once. Per-segment scorers require
this value as a constructor argument.

- [x] **Step 4: Run GREEN**

```bash
uv run pytest tests/nrt/test_live_bm25_stats.py tests/unit/search/test_bm25.py -q
```

- [x] **Step 5: Commit**

```bash
git add src/minilucene/search/stats.py src/minilucene/reader.py tests/nrt/test_live_bm25_stats.py
git commit -m "fix: score from global live-document statistics"
```

### Task 7: Merge selected segments with dense doc-ID remapping

**Files:**
- Create: `src/minilucene/merge.py`
- Modify: `src/minilucene/writer.py`
- Create: `tests/nrt/test_segment_merge.py`

- [x] **Step 1: Write logical-equivalence tests**

```python
def test_merge_skips_deletes_and_preserves_search_results(index_with_segments):
    before = index_with_segments.writer_refresh_reader()
    expected = snapshot_results(before)
    with index_with_segments.writer() as writer:
        merged = writer.merge(writer.segment_generations)
        after = writer.refresh()
    assert merged.max_doc == before.num_live_docs
    assert snapshot_results(after) == expected
    assert after.segment_generations == (merged.generation,)
```

Compare term, phrase, prefix, boolean, stored fields, field lengths, scores, and
Top-K order before and after merge. Assert new local doc IDs are dense and
ordered by selected segment order then prior local doc ID.

- [x] **Step 2: Write failure-before-swap test**

Inject failure while publishing merge output. Assert writer segment
generations and refresh results remain exactly unchanged and the output is not
referenced.

- [x] **Step 3: Run RED**

```bash
uv run pytest tests/nrt/test_segment_merge.py -q
```

- [x] **Step 4: Implement merge off to the side**

Capture selected segment snapshots. Reject duplicates, unknown generations, or
fewer than two segments. Copy only live documents into a new RAM builder in
stable order, freeze/publish one image, then replace selected descriptors at
the position of the earliest selected segment in one writer-state assignment.
Unselected segments retain order.

- [x] **Step 5: Run GREEN**

```bash
uv run pytest tests/nrt/test_segment_merge.py -q
```

- [x] **Step 6: Commit**

```bash
git add src/minilucene/merge.py src/minilucene/writer.py tests/nrt/test_segment_merge.py
git commit -m "feat: merge immutable segments explicitly"
```

### Task 8: Retain segment files by explicit owner references

**Files:**
- Create: `src/minilucene/storage/registry.py`
- Modify: `src/minilucene/index.py`
- Modify: `src/minilucene/reader.py`
- Modify: `src/minilucene/writer.py`
- Create: `tests/nrt/test_segment_ownership.py`

- [x] **Step 1: Write retained-reader cleanup tests**

```python
def test_obsolete_segment_waits_for_old_reader_close(index):
    old = build_commit_and_open_reader(index)
    old_paths = tuple(index.segment_paths())
    merge_and_commit(index)
    index.collect_garbage()
    assert all(path.exists() for path in old_paths)
    old.close()
    index.collect_garbage()
    assert all(not path.exists() for path in old_paths)
```

Also prove two readers retain independently, close is idempotent, committed
manifest references always retain, writer current state retains uncommitted
segments, and temporary paths are never registered.

- [x] **Step 2: Run RED**

```bash
uv run pytest tests/nrt/test_segment_ownership.py -q
```

- [x] **Step 3: Implement `SegmentRegistry`**

Track owners by opaque owner ID to generation sets. `acquire` and `release` are
idempotent only for the exact owner lifecycle; duplicate acquire is an error.
Garbage collection computes:

```text
complete segment directories
- manifest references
- active owner references
= removable obsolete directories
```

It never deletes unknown-version or malformed directories automatically; it
reports them as retained diagnostics.

- [x] **Step 4: Run GREEN**

```bash
uv run pytest tests/nrt/test_segment_ownership.py -q
```

- [x] **Step 5: Commit**

```bash
git add src/minilucene/storage/registry.py src/minilucene/index.py src/minilucene/reader.py src/minilucene/writer.py tests/nrt/test_segment_ownership.py
git commit -m "feat: retain segments by explicit owners"
```

### Task 9: Close writer and index without leaked ownership

**Files:**
- Modify: `src/minilucene/writer.py`
- Modify: `src/minilucene/index.py`
- Create: `tests/nrt/test_close_lifecycle.py`

- [x] **Step 1: Write close-order and diagnostics tests**

Assert writer close blocks new mutation, discards unpublished RAM/NRT state,
releases its readers and segment owners, releases the lock last, and is
idempotent. Assert index close does not invalidate external readers and reports
their owner IDs/generations.

- [x] **Step 2: Run RED**

```bash
uv run pytest tests/nrt/test_close_lifecycle.py -q
```

- [x] **Step 3: Implement explicit lifecycle states**

Use `OPEN`, `CLOSING`, `CLOSED`. Every public mutation admits only in `OPEN`.
Close captures and clears writer-owned unpublished readers, releases segment
owners, then lock. Exceptions are aggregated into `CloseError` after every
cleanup step is attempted.

- [x] **Step 4: Run GREEN**

```bash
uv run pytest tests/nrt/test_close_lifecycle.py -q
```

- [x] **Step 5: Commit**

```bash
git add src/minilucene/writer.py src/minilucene/index.py tests/nrt/test_close_lifecycle.py
git commit -m "feat: settle index lifecycle ownership"
```

### Task 10: Accept NRT mutation and merge

**Files:**
- Create: `tests/acceptance/test_phase3_nrt_mutation.py`
- Create: `docs/phase3-nrt-mutation.md`

- [x] **Step 1: Add lifecycle acceptance**

In one test: commit initial corpus, retain old reader, add and refresh, delete
and update, prove old/new visibility, simulate restart to lose NRT-only state,
repeat and commit, merge, compare results and scores, close all owners, collect
garbage, and assert owner count zero.

- [x] **Step 2: Run phase acceptance**

```bash
uv sync --dev
uv run pytest tests/acceptance/test_phase3_nrt_mutation.py -q
uv run ruff check src tests tools
uv run pytest -q
uv run python -m compileall -q src tests tools
git diff --check
```

- [x] **Step 3: Write phase report**

`docs/phase3-nrt-mutation.md` records flush/refresh/commit visibility, immutable
live-doc generations, update semantics, merge remapping, owner retention,
failure experiments, and verification evidence.

- [x] **Step 4: Commit acceptance**

```bash
git add tests/acceptance/test_phase3_nrt_mutation.py docs/phase3-nrt-mutation.md
git commit -m "test: accept NRT mutation and merge"
git status --short
```

Expected: clean worktree.

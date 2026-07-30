# Chapter 5: Segments and Near-Real-Time Visibility

“The document was written” is ambiguous in a search engine. It might mean the
document is still in a mutable RAM buffer, an immutable segment now exists, a
new in-process reader can see it, or a process restart will recover it. Those
states are not equivalent. MiniLucene makes the distinction unusually crisp:
`flush` creates a segment, `refresh` creates a point-in-time reader, and
`commit` publishes the restart root.

## Learning objectives

By the end of this chapter, you can:

1. state the visibility guarantee of `flush`, `refresh`, and `commit`;
2. explain why existing readers do not change after refresh or commit;
3. trace immutable segment ownership through a reader snapshot;
4. predict what reopen sees before and after commit; and
5. describe near-real-time search without confusing it with durability.

## Mechanism: three publication boundaries

An `IndexWriter` begins with the segment generations named by the current
manifest and a fresh `RamIndexBuilder`. `IndexWriter.add_document` in
`src/minilucene/writer.py` validates and prepares the incoming document before
mutating the buffer. Its `FlushPolicy` can trigger a flush based on buffered
document or distinct-posting counts, but an explicit call makes the mechanism
easiest to observe.

### Flush: RAM becomes an immutable segment

`IndexWriter.flush` returns immediately with `None` for an empty buffer.
Otherwise it first compacts only the buffer's live documents into a new
`RamIndexBuilder`. It chooses an unused generation, converts the frozen memory
segment to `SegmentImage`, and calls `SegmentStore.publish`. After publication,
the writer appends the generation to its private segment list, installs an
all-live mask, resets the RAM buffer, and updates its process-local ownership.

The segment files are durable as files, but the committed `manifest.json` still
names the old generation set. `Index.open_reader` in
`src/minilucene/index/directory.py` always reads that manifest. Therefore a
reader opened through the index immediately after `flush` does not see the new
segment. If the process exits now, reopening also does not see it. The segment
is an orphan candidate, not a committed root.

### Refresh: publish a new in-process view

`IndexWriter.refresh` first calls `flush`, then opens every generation in the
writer's current private segment list, captures the matching live-document
masks, and constructs an `IndexReader` with `commit_generation=None`.
That new reader sees flushed changes, including writer-side deletions.

Refresh does not replace a global mutable reader. It returns a new
point-in-time object. In `src/minilucene/reader.py`, `IndexReader.__init__`
creates a `ReaderSnapshot` containing a tuple of `SegmentSnapshot` values, live
masks, corpus statistics, schema fingerprint, and optional commit generation.
An earlier reader retains its original tuples and statistics. No later refresh,
delete, merge, or commit mutates them.

That point-in-time property applies to ranking as well as membership. Corpus
statistics are computed for the snapshot's live documents. A new reader may
have different document frequency and average length; an old reader continues
to score against its captured statistics.

### Commit: publish the restart root

`IndexWriter.commit` also begins by flushing. It reopens and validates every
segment it intends to publish. Dirty deletion masks are written as new
live-doc generations because segment postings are immutable. Then
`Manifest.next_from` constructs the next commit generation and
`ManifestStore.write_atomic` publishes it.

In `src/minilucene/storage/manifest.py`, `ManifestStore.write_atomic` writes
canonical JSON to a temporary file, fsyncs it, atomically replaces
`manifest.json`, and fsyncs the index directory. The new manifest is the sole
restart publication boundary. A later `Index.open` reads it, validates its
schema fingerprint, and `Index.open_reader` opens exactly its segment and
live-doc generations.

Commit does not mutate a previously opened reader. It only changes what future
manifest-based readers and future processes can open. A refresh reader created
before commit has `commit_generation=None` even if its segment tuple later
becomes committed; its identity records how it was published.

The state transition can be summarized:

```text
add_document
    │
    ▼
writer RAM buffer
    │ flush
    ▼
immutable segment files ────────┐
    │ refresh                    │ commit
    ▼                            ▼
new in-process Reader       atomic manifest
(old readers unchanged)          │
                                 ▼
                         future/restarted readers
```

### Ownership and obsolete generations

Point-in-time readers require lifetime management. A reader may still need a
segment after a writer merges it away or a newer manifest stops naming it.
`IndexReader.__init__` acquires generations in the process-local
`SegmentRegistry`; `IndexReader.close` releases them. Writers similarly replace
their owned generation set as their private view changes.

`Index.collect_garbage` delegates to `SegmentRegistry.collect_garbage` in
`src/minilucene/storage/registry.py`. A complete obsolete segment is removable
only when it is absent from the current manifest and no process-local reader or
writer owns it. This is not a distributed lease or cross-process reference
tracker. It protects lifetimes within the running process. The project also
uses a writer lock and deliberately does not recover stale lock files.

### Near-real-time is a visibility term

Near-real-time (NRT) search means new indexed content can become searchable by
refreshing a reader without performing a durable commit for every change. It
reduces visibility latency and amortizes expensive durable publication. It does
not mean synchronous durability, replication, consensus, or real-time deadline
guarantees.

MiniLucene's API makes the caller manage reader replacement explicitly. A
production service would normally own a current searcher/reader manager,
refresh on a policy, and safely hand snapshots to concurrent requests. This
project does not provide such a server or background refresh loop.

### A timeline for reasoning about failures

Imagine a writer adds document A, flushes, refreshes, and crashes before
commit. Queries using that refresh reader could see A while the process lived.
After restart, A is absent because the old manifest remains the root. The
segment may remain on disk, but automatically adopting it would be unsafe: the
system cannot know whether the caller intended to publish that writer state.

Now imagine commit completes while a previously opened reader keeps serving.
New readers see A; the old reader does not. This is snapshot isolation, not an
accidental stale cache. The application chooses when to retire the old reader,
whose ownership keeps its segment files from being collected.

The states form a useful visibility table:

| State | Writer/private state | Refresh reader | New manifest reader | Restart |
|---|---:|---:|---:|---:|
| after add | yes | no | no | no |
| after flush | segment | no | no | no |
| after refresh | segment | yes | no | no |
| after commit | segment | yes if refreshed | yes | yes |

“No after restart” means not part of the recovered index even if orphan bytes
survive. “Yes if refreshed” reminds us that commit does not push changes into an
existing reader. This vocabulary is more precise than saying only “written” or
“saved.”

## Compared with Apache Lucene

Apache Lucene's `IndexWriter` also buffers changes and flushes immutable
segments. `DirectoryReader.open(IndexWriter)` and
`DirectoryReader.openIfChanged` support NRT readers; `SearcherManager` and
controlled reopen threads help applications manage refreshed searchers.
Durable commits publish Lucene commit points, and deletion/merge policy manages
files with richer reference tracking.

MiniLucene preserves the conceptual separation but simplifies policy and
concurrency. Refresh is explicit and synchronous. There is one writer lock, no
background flush or refresh thread, no `SearcherManager`, no commit user data,
no rollback API, no automatic merge scheduler, and only process-local ownership
tracking. A crash can leave a stale `.writer.lock`. The file format and
manifest are not Lucene compatible. MiniLucene also excludes deleted documents
from snapshot BM25 statistics immediately, while Lucene segment statistics may
continue to include them until merge. See the NRT/lifecycle rows in the
[behavior matrix](../behavior-matrix.md), the
[Lucene mapping](../lucene-mapping.md), and
[NRT mutation notes](../phase3-nrt-mutation.md).

## Hands-on experiment: see all three boundaries

```bash
export UV_CACHE_DIR=/tmp/minilucene-uv-cache
uv run --offline python - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory

from minilucene import Index, Schema, TextField
from minilucene.query import TermQuery

with TemporaryDirectory() as tmp:
    path = Path(tmp) / "index"
    index = Index.create(path, Schema(body=TextField(stored=True)))
    with index.writer() as writer:
        writer.add_document(body="alpha")
        segment = writer.flush()
        with index.open_reader() as committed:
            hits = committed.search(TermQuery("body", "alpha")).total_hits
            print("after flush", segment.generation, hits)

        fresh = writer.refresh()
        hits = fresh.search(TermQuery("body", "alpha")).total_hits
        print("after refresh", hits, fresh.snapshot.commit_generation)

        writer.commit()
        with Index.open(path) as reopened, reopened.open_reader() as reader:
            hits = reader.search(TermQuery("body", "alpha")).total_hits
            print("after commit", hits, reopened.manifest().commit_generation)
        fresh.close()
    index.close()
PY
```

Measured output:

```text
after flush 1 0
after refresh 1 None
after commit 1 1
```

Generation 1 exists after flush, yet the manifest-based reader sees zero hits.
The refresh reader sees the hit but is explicitly not attached to a commit
generation. After commit, a separately reopened index sees one hit at commit
generation 1.

Run the lifecycle contracts:

```bash
uv run --offline pytest -q tests/contract/test_index_lifecycle.py \
  tests/nrt/test_refresh_visibility.py tests/nrt/test_reader_snapshot.py
```

Measured result:

```text
14 passed in 0.80s
```

## Exercises

1. **Understanding:** If `flush` fsyncs segment files, why does reopen still
   ignore the segment?

    ??? note "Reference answer"
        Durability of component bytes and publication of the index root are
        separate. Reopen trusts only the atomically committed manifest; an
        unnamed segment is not part of that snapshot.

2. **Understanding:** Why must refresh return a new reader instead of mutating
   an old one?

    ??? note "Reference answer"
        Queries need a stable segment set, live masks, and corpus statistics.
        Mutation during use would break point-in-time consistency and make
        scores/results depend on timing.

3. **Hands-on:** Open a reader before adding `alpha`, then refresh and query both
   readers. Acceptance: the old reader reports zero and the refreshed reader
   reports one, even after commit.

    ??? note "Reference answer"
        Keep the first reader open, add/refresh through the writer, and search
        both objects. Close both at the end. Their different snapshots are the
        intended result; no source change is needed.

4. **Hands-on:** Remove the `writer.commit()` line and reopen the index while
   the writer is still alive. Acceptance: the refresh reader reports one, while
   the reopened manifest reader reports zero.

    ??? note "Reference answer"
        This is the exact NRT-without-durability boundary. The segment exists
        and the writer can publish it to an in-process reader, but the restart
        root remains at commit generation zero.

## Summary

MiniLucene gives three precise meanings to publication. Flush freezes RAM into
validated segment files; refresh returns a new point-in-time in-process view;
commit atomically changes what future and restarted readers recover. Existing
readers remain stable throughout. Chapter 6 builds on that immutability by
showing how deletion and update change live-document masks without rewriting
old postings.

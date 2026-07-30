# Commit Atomicity

## Learning objectives

By the end of this chapter, you will be able to:

1. identify `manifest.json` as MiniLucene's only restart-visible commit root;
2. explain the temp-write, file-fsync, rename, directory-fsync publication sequence;
3. classify segment and live-doc files created before a failed manifest replacement as invisible orphans;
4. reason through the repository's commit failure matrix; and
5. contrast MiniLucene's commit protocol with Apache Lucene's `segments_N` and two-phase commit facilities.

## 1. A durable file is not necessarily committed

MiniLucene can have many complete files on disk that are not part of the
recoverable index. The authoritative question after restart is not “which
segment directories exist?” but “which generations does `manifest.json`
name?”

`src/minilucene/storage/manifest.py`, `Manifest` records the schema
fingerprint, commit generation, ordered `SegmentCommit` entries, and the next
generation counters. Each `SegmentCommit` names a segment generation and,
when deletions exist, a live-doc generation plus checksum. The manifest thus
describes one complete point-in-time graph:

```text
manifest.json
  ├── seg_000003/segment.json → data files and checksums
  │    └── live_000002.bin → deletion mask named by manifest
  └── seg_000006/segment.json → data files and checksums
```

`src/minilucene/index/directory.py`, `Index.open()` requires the manifest,
loads the persisted schema, checks its fingerprint against the manifest, and
does not scan segment directories to invent a newer state.
`Index.open_reader()` then opens exactly the manifest's ordered segment
references and their named live-doc generations.

That ordering is part of the snapshot. It determines global document-ID
translation and deterministic tie-breaking. A recovery routine must not sort
directories and silently replace manifest order.

## 2. Commit prepares children before publishing the root

The coordinator is `src/minilucene/writer.py`, `IndexWriter.commit()`.
It first calls `flush()`, making buffered live documents into an immutable
segment. It then reopens every writer-owned segment through
`SegmentStore.open()`. Reopening validates schema fingerprints, metadata,
lengths, and SHA-256 checksums before any new root can name the bytes.

For a dirty deletion mask, `commit()` allocates a fresh live-doc generation
and calls `src/minilucene/storage/live_docs.py`,
`LiveDocsStore.publish()`. It never overwrites the mask referenced by an older
reader or commit. If the segment is fully live, its `SegmentCommit` contains no
live-doc reference.

Only after all segment and mask children are durable does
`IndexWriter.commit()` build `Manifest.next_from()` and call
`ManifestStore.write_atomic()`. The manifest replacement is last because it
turns already-written children from unreachable files into the recoverable
index.

This is an important kind of atomicity: the root switches atomically, while
the child files are immutable and prepared in advance. It is not one giant
filesystem transaction.

## 3. Why fsync appears twice

`src/minilucene/storage/manifest.py`,
`ManifestStore.write_atomic()` serializes canonical compact JSON and performs:

```text
write manifest.tmp
fsync manifest.tmp
replace manifest.tmp → manifest.json
fsync index directory
```

The first fsync asks the operating system to make the temporary file's content
durable before it becomes authoritative. `src/minilucene/storage/filesystem.py`,
`FileSystemOps.replace()` uses `os.replace()`, which maps to an atomic rename
on the expected same-filesystem setup. A reader opening the destination sees
the old complete name or the new complete name, not half of the JSON.

The directory fsync has a different job: it persists the directory-entry
replacement itself. Syncing only the file content does not prove that the new
name binding will survive power loss on every supported filesystem.

MiniLucene applies the same pattern when publishing the persisted schema,
segment directories, and live-doc files. The exact guarantees still depend on
the operating system, filesystem, and storage device honoring these calls.
Atomic rename also requires source and destination to be on the same
filesystem, which the colocated temporary path ensures.

## 4. Old root or new root, never a synthesized middle

Suppose commit generation 4 names segments `(1, 3)`. A writer publishes
segment 5 and attempts commit generation 5 naming `(1, 3, 5)`.

- Failure while writing segment 5: no new manifest is attempted; generation 4
  remains authoritative.
- Failure after segment 5's final rename but before manifest replacement:
  segment 5 is a complete orphan; generation 4 remains authoritative.
- Failure while replacing `manifest.json`: the expected atomic rename model
  leaves the old complete manifest authoritative.
- Success through the directory fsync: generation 5 is the new recoverable
  root.

The code intentionally does not “finish” a failed commit during `Index.open()`
by finding the orphan. That would be guessing the writer's intent and could
publish a segment without its intended deletes or ordering.

`src/minilucene/storage/manifest.py`, `ManifestStore.read()` is strict. It
rejects invalid UTF-8/JSON, unknown or extra fields, unknown format versions,
inconsistent generation counters, duplicate segments, and incomplete
live-doc metadata. Referenced segment corruption fails closed in
`SegmentStore.open()` rather than being skipped.

A commit generation is a monotonic identity, not proof that every earlier
attempt succeeded. `Manifest.next_from()` advances from the currently readable
manifest, while segment allocation may skip generations already occupied by
orphans. Gaps are therefore normal diagnostic evidence, not a reason to scan
and attach missing directories. The only safe relationship is the one
explicitly recorded by the validated root.

The same rule applies to a leftover `manifest.tmp`: recovery reads
`manifest.json`, not whichever JSON file has the newest timestamp. A temporary
file may hold incomplete bytes, a complete but unpublished root, or data from
a failed attempt; modification time cannot distinguish them. Reusing the
fixed temporary pathname on a later commit is safe because it is never a
recovery root. The later protocol overwrites and syncs it before another rename
attempt.

## 5. Orphan collection respects ownership

An orphan is invisible, but immediate deletion is not always safe. A
process-local NRT reader may still own an uncommitted segment, and an old
reader may own a segment removed by a newer committed merge.

`src/minilucene/storage/registry.py`,
`SegmentRegistry.collect_garbage()` calculates protected generations from:

```text
current manifest generations
UNION every reader owner's generations
UNION the writer owner's generations
```

It removes only recognized, complete `seg_NNNNNN` directories outside that
set. Unknown or malformed paths stay for diagnosis. This registry protects
owners only inside the current process; it is not cross-process reference
counting. That limitation is documented in the
[MiniLucene-to-Lucene mapping](../lucene-mapping.md).

Generation allocation also avoids collision with complete orphans:
`IndexWriter.flush()`, `commit()`, and `merge()` advance until the target
generation does not exist. A failed publication therefore does not cause a
later writer to overwrite diagnostic evidence.

## 6. Contrast with Apache Lucene

The conceptual correspondence is `manifest.json` to Lucene's latest
`segments_N` commit point represented by `SegmentInfos`. In both designs, a
small atomically published root names the files belonging to a consistent
commit; immutable files prepared earlier can exist without being part of that
commit.

MiniLucene deliberately omits important production machinery:

- Its manifest is custom JSON and is not Lucene codec compatible.
- `IndexWriter` has no `prepareCommit()`, `rollback()`, or two-phase commit
  protocol for coordinating multiple resources.
- There is no configurable `IndexDeletionPolicy`, retained commit history, or
  snapshot deletion policy. MiniLucene exposes one current root.
- Its writer lock can be stranded by a process crash; there is no safe stale
  lock validation or force-unlock API.
- Its registry is in-process and cannot protect a reader in another process.

The [atomic commit](../behavior-matrix.md), complete orphan recovery,
checksum-corruption, and segment ownership rows in the behavior matrix bind
these claims to executable tests. The mapping document's manifest, writer,
registry, and lock rows explain where the analogy to real Lucene stops.

## 7. Hands-on experiment: a failed root replacement

The following experiment injects a failure at the manifest rename boundary.
It uses a test-style filesystem subclass but does not modify repository code.

```bash
UV_CACHE_DIR=/tmp/minilucene-uv-cache uv run python - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory

from minilucene import Index, KeywordField, Schema, TextField
from minilucene.query import TermQuery
from minilucene.storage.filesystem import FileSystemOps
from minilucene.storage.manifest import ManifestStore


class FailManifestReplace(FileSystemOps):
    def replace(self, source: Path, destination: Path) -> None:
        if destination.name == "manifest.json":
            raise OSError("injected manifest replace failure")
        super().replace(source, destination)


schema = Schema(
    id=KeywordField(stored=True),
    body=TextField(stored=True),
)

with TemporaryDirectory() as directory:
    path = Path(directory)
    index = Index.create(path, schema)
    with index.writer() as writer:
        writer.add_document(id="1", body="committed")
        writer.commit()

    try:
        with index.writer() as writer:
            writer.add_document(id="2", body="orphan")
            writer._manifest_store = ManifestStore(
                path, fs=FailManifestReplace()
            )
            writer.commit()
    except OSError as error:
        print(error)

    reopened = Index.open(path)
    reader = reopened.open_reader()
    print(f"commit_generation={reopened.manifest().commit_generation}")
    print(
        "committed_hits="
        f"{reader.search(TermQuery('body', 'committed')).total_hits}"
    )
    print(
        "orphan_hits="
        f"{reader.search(TermQuery('body', 'orphan')).total_hits}"
    )
    segment_names = sorted(
        item.name for item in (path / "segments").iterdir()
    )
    print(f"segment_directories={segment_names}")
    reader.close()
    reopened.close()
    index.close()
PY
```

Measured output:

```text
injected manifest replace failure
commit_generation=1
committed_hits=1
orphan_hits=0
segment_directories=['seg_000001', 'seg_000002']
```

The second segment is complete enough to remain on disk, yet recovery follows
commit generation 1. Presence is not publication.

## 8. Exercises

### Exercise 1 — understanding

Why must segment and live-doc files be synced before the manifest replacement?

??? note "Reference answer"

    The manifest makes those children reachable during recovery. Publishing the
    root first could leave a durable manifest naming missing or partial child
    bytes. Preparing immutable children first turns a pre-root crash into
    harmless unreachable orphans.

### Exercise 2 — failure classification

Classify these states after reopen: (a) a temporary segment directory, (b) a
complete unreferenced segment, and (c) a manifest-referenced segment with a bad
checksum.

??? note "Reference answer"

    (a) and (b) are not part of the recovered reader; the complete
    unreferenced directory is an orphan. (c) is not silently ignored:
    `SegmentStore.open()` fails closed because the authoritative root names
    corrupted data.

### Exercise 3 — hands-on code change

Without editing `src/`, copy `src/minilucene/storage/manifest.py` to a scratch
directory and add comments for four injectable crash points in
`write_atomic()`. Write a table predicting the authoritative root after each
point.

Acceptance: the table must cover before temp-file fsync, after temp-file fsync,
after rename, and after directory fsync; it must distinguish an atomic
visibility claim from a durability claim.

??? note "Reference answer"

    Before rename, the old root remains named. After rename but before
    directory fsync, processes normally observe the new complete file, but
    crash durability of the name is not established. After directory fsync,
    the new root is the intended durable result. The exact post-power-loss
    behavior depends on filesystem guarantees, so the table should not claim
    more than the protocol establishes.

## Summary

MiniLucene commits by preparing immutable children and atomically replacing
one small manifest root. File fsync protects content; rename switches
visibility; directory fsync protects the name change. Recovery never promotes
orphans by guesswork, and garbage collection must honor every live owner. With
durable snapshots established, the next chapter follows a query through BM25
scoring and a bounded Top-K heap.

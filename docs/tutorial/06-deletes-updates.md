# Deletes and Updates

## Learning objectives

By the end of this chapter, you will be able to:

1. explain why deleting a document changes a live-doc mask instead of rewriting postings;
2. trace an exact-term delete from `IndexWriter._derive_delete()` to a new live-doc generation at commit;
3. explain why `update_document()` means “validate, delete every match, then add one replacement”;
4. demonstrate that an old reader remains a point-in-time view while a new reader sees the mutation; and
5. distinguish MiniLucene's live-only statistics from Apache Lucene's pre-merge statistics.

## 1. Immutable segments make deletion an overlay

The segment written by `IndexWriter.flush()` is immutable. Reopening and editing
`postings.bin` would undermine the simple failure model established by that
rule: a segment is either a complete, checksummed image or it is not usable.
MiniLucene therefore represents a deletion as a second, versioned object: a
set of live local document IDs.

`src/minilucene/storage/live_docs.py`, `LiveDocsCodec.encode()` packs that set
into a bitset. Local document `d` occupies bit `d % 8` in byte `d // 8`.
`LiveDocsCodec.decode()` checks the recorded `max_doc`, the exact byte length,
and unused high bits before returning an immutable `frozenset`. These checks
matter because a mask created for a different segment size must not silently
hide or expose documents.

The writer keeps one mask per segment in
`src/minilucene/writer.py`, `IndexWriter.__init__()`. A segment without a
live-doc file starts with `frozenset(range(image.max_doc))`: every local
document is live. The postings, stored fields, and norms remain unchanged when
the mask later loses an ID.

This gives two identities that should not be confused:

```text
segment generation 7     immutable postings/stored fields/norms
live-doc generation 3    the third committed visibility mask for segment 7
```

`src/minilucene/storage/live_docs.py`, `LiveDocsStore.publish()` writes each
new mask under the segment directory, computes its SHA-256 checksum, fsyncs the
temporary file, renames it, and fsyncs the directory. The manifest eventually
names both generations and the checksum. A mask file that is durable but not
named by the manifest is no more visible after restart than an orphan segment.

## 2. Exact-term delete is derive, then swap

The public mutation is `src/minilucene/writer.py`,
`IndexWriter.delete_by_term(field, term)`. Its important work happens in
`IndexWriter._derive_delete()`.

First, `_derive_delete()` rejects an unknown field, a non-indexed field, and
an empty delete term. It then copies the current per-segment mask dictionary.
For each writer-owned segment it opens the validated segment image, finds
postings for the exact field and exact term, intersects those local IDs with
the current live set, and derives a smaller set. It separately finds matching
documents in the RAM buffer.

Only after all derivation succeeds does `delete_by_term()` replace
`self._live_docs`, mark changed segment generations dirty, and replace the
buffer live set. This arrangement avoids partially applying a delete if a
later segment fails to open. The return value is the number of *newly* deleted
live documents, so repeating the same deletion returns zero.

The match is exact after indexing analysis. For a `KeywordField`, deleting
`id="doc-1"` is natural. For a standard-analyzed `TextField`, the caller must
provide an indexed term such as lowercase `kafka`; this API does not parse a
query string and does not analyze the delete term for you.

The granularity also explains “delete all matches.” Postings map one term to
every document containing it, so the writer cannot infer that an ID field was
intended to be unique. There is no hidden primary-key table. If an application
needs uniqueness, it must validate that invariant itself or accept that one
update may retire several documents. Conversely, `delete_by_term()` cannot
express Boolean, phrase, or prefix deletion; those features need a separately
specified query-matching snapshot, not a string convention smuggled into this
exact-term API.

Search excludes deleted documents in
`src/minilucene/search/reader.py`, `ReaderView.postings()`: it translates only
postings whose local IDs are in the snapshot's mask. `ReaderView._build_corpus_stats()`
also counts only live IDs. Consequently deletion immediately changes hit sets,
document frequency, average length, and BM25 inputs for a newly opened reader.

## 3. Update is delete-all plus one validated add

MiniLucene has no in-place update. `src/minilucene/writer.py`,
`IndexWriter.update_document()` implements the common inverted-index model:

```text
validate and analyze replacement
        ↓
derive deletion of every exact-term match
        ↓
build next RAM buffer and append one replacement
        ↓
swap all writer mutation state together
```

The ordering is the lesson. `self._buffer.prepare_document(replacement)` runs
first. If the replacement violates the schema, nothing has been deleted.
Next, `_derive_delete()` computes masks without publishing them. A fresh
`RamIndexBuilder` copies buffered documents and adds the prepared replacement.
Only then does the writer swap masks, dirty generations, buffer, and buffer
live IDs.

The integer returned by `update_document()` is the number of old live matches,
not the ID of the replacement. If three documents share a supposedly unique
keyword, all three are deleted and exactly one replacement is added. Uniqueness
is an application invariant, not a schema feature in MiniLucene.

This operation is atomic only with respect to the writer's in-process state.
It does not publish a reader automatically and does not become restart-durable
automatically. Call `refresh()` for a new NRT reader or `commit()` for a new
recoverable root.

## 4. Point-in-time readers do not absorb mutations

`src/minilucene/writer.py`, `IndexWriter.refresh()` flushes the current buffer,
captures an ordered tuple of immutable segment images and live masks, and
constructs an `IndexReader`. A committed reader is similarly built by
`src/minilucene/index/directory.py`, `Index.open_reader()` from the manifest.

`src/minilucene/reader.py`, `IndexReader.__init__()` wraps these values in the
frozen `ReaderSnapshot` defined in `src/minilucene/snapshot.py`. It also
acquires ownership of the referenced segment generations. Later deletes
replace writer masks; they do not mutate the `frozenset` already owned by the
reader. Later commits replace `manifest.json`; they do not edit a reader's
snapshot.

The observable timeline is:

```text
reader A opens ───── sees old document ───── sees old document ── close
                         delete + commit
reader B opens afterward ─────────────────── sees no old document
```

This is point-in-time isolation, not transaction rollback. Reader A is
deliberately stale. `IndexReader.close()` releases only its own registry owner
and is idempotent. Obsolete segment directories can be collected only after
they are absent from the manifest, absent from the writer, and absent from
every reader owner; see `src/minilucene/storage/registry.py`,
`SegmentRegistry.collect_garbage()`.

When debugging an apparent “delete did not work,” identify the observation
boundary before inspecting bytes. Ask which reader performed the search,
whether that reader predates the mutation, whether the writer was refreshed or
committed, and whether the delete term is the exact indexed term. Looking only
at old postings is misleading because their continued presence is expected.
Looking only at a live-doc file is also insufficient because the manifest may
not name that generation. The correct evidence is a specific reader snapshot
plus its ordered segment and mask tuple.

## 5. Contrast with Apache Lucene

The transferable idea is strong: Apache Lucene also keeps immutable segment
data and records deletions through per-segment live-doc bits. MiniLucene's
`live_*.bin` corresponds conceptually to Lucene's `LiveDocsFormat`, `.liv`
files, and `Bits` views. A Lucene update by term likewise deletes matching
documents and adds a new document rather than editing an existing posting.

The simplifications and differences are equally important:

- MiniLucene serializes mutation through one Python writer and one RAM buffer;
  Lucene has concurrent indexing machinery, buffered delete packets, sequence
  numbers, and richer update APIs.
- MiniLucene eagerly materializes segment images and masks into each reader;
  Lucene uses leaf readers, shared segment cores, caches, and reopen logic.
- MiniLucene's corpus statistics exclude deleted documents immediately.
  Lucene's segment term statistics generally retain deleted documents until
  merge, so a production merge can change scores even when the live content is
  unchanged.
- MiniLucene has string fields only and no doc values, numeric point updates,
  soft deletes, or update-by-query facility.

These boundaries are recorded in the repository's
[MiniLucene-to-Lucene mapping](../lucene-mapping.md) under live docs, readers,
live-only corpus statistics, and writer simplifications. Executable claims for
[exact-term delete](../behavior-matrix.md), atomic update, reader snapshots,
and segment ownership are tied to named pytest nodes in the behavior matrix.

## 6. Hands-on experiment: two readers, two times

Run this from the repository root. It uses only a temporary directory and the
public Python API.

```bash
UV_CACHE_DIR=/tmp/minilucene-uv-cache uv run python - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory

from minilucene import Index, KeywordField, Schema, TextField
from minilucene.query import TermQuery

schema = Schema(
    id=KeywordField(stored=True),
    body=TextField(stored=True),
)

with TemporaryDirectory() as directory:
    index = Index.create(Path(directory), schema)
    with index.writer() as writer:
        writer.add_document(id="doc-1", body="old searchable text")
        writer.commit()

    old_reader = index.open_reader()
    with index.writer() as writer:
        deleted = writer.update_document(
            field="id",
            term="doc-1",
            id="doc-1",
            body="new searchable text",
        )
        writer.commit()

    new_reader = index.open_reader()
    old_old = old_reader.search(TermQuery("body", "old")).total_hits
    old_new = old_reader.search(TermQuery("body", "new")).total_hits
    new_old = new_reader.search(TermQuery("body", "old")).total_hits
    new_new = new_reader.search(TermQuery("body", "new")).total_hits
    repeated = 0
    with index.writer() as writer:
        repeated = writer.delete_by_term("id", "missing")

    print(f"updated_old_documents={deleted}")
    print(f"old_reader old={old_old} new={old_new}")
    print(f"new_reader old={new_old} new={new_new}")
    print(f"delete_missing={repeated}")
    old_reader.close()
    new_reader.close()
    index.close()
PY
```

Measured output:

```text
updated_old_documents=1
old_reader old=1 new=0
new_reader old=0 new=1
delete_missing=0
```

The two readers disagree by design. The old reader owns its original segment
and all-live mask; the new reader follows the new manifest and mask generation.

## 7. Exercises

### Exercise 1 — understanding

Why does a repeated `delete_by_term("id", "doc-1")` return zero after the first
successful deletion, even though the old postings still contain `doc-1`?

??? note "Reference answer"

    `_derive_delete()` intersects posting matches with the *current live set*.
    The posting remains immutable, but the local document ID is no longer live,
    so it is not counted or removed again.

### Exercise 2 — understanding

An invalid replacement omits a required field. Should the matching old
documents disappear?

??? note "Reference answer"

    No. `IndexWriter.update_document()` calls
    `RamIndexBuilder.prepare_document()` before deriving or swapping deletion
    state. Validation failure therefore leaves masks and the RAM buffer
    unchanged.

### Exercise 3 — hands-on code change

Without changing `src/`, copy `src/minilucene/writer.py` to a scratch directory
and sketch a `delete_by_query(query)` method. Mark exactly where a full match
set would be derived and where writer state would be swapped. Do not implement
query parsing inside the writer.

Acceptance: your scratch diff must keep validation/derivation before the first
assignment to `_live_docs`, `_dirty_live_docs`, or `_buffer_live_docs`, and
must explain how buffered and flushed documents are both covered.

??? note "Reference answer"

    A sound sketch accepts a closed `Query` object, builds a temporary
    `ReaderView` for flushed segments plus a separate RAM-buffer match, derives
    all next masks, and only then swaps the three writer fields. Query-string
    parsing stays in `query_parser`; a failure while matching any segment must
    leave the writer untouched.

## Summary

MiniLucene preserves immutable segments by moving deletion visibility into
versioned live-doc masks. Delete derives complete next state before swapping
it; update validates first and then performs delete-all plus add-one; readers
keep frozen masks and therefore remain point-in-time views. The next chapter
asks how those segment and mask generations become one crash-safe durable
truth.

# Merge and Beyond

## Learning objectives

By the end of this chapter, you will be able to:

1. explain why merging rewrites selected immutable segments instead of concatenating files;
2. trace live-document filtering, dense document-ID remapping, and writer-set replacement;
3. distinguish successful merge publication from durable commit and garbage collection;
4. explain the remaining automatic-merge and post-DAAT optimization gaps; and
5. use the project's gaps as a concrete reading roadmap into Apache Lucene.

## 1. Why merge exists

Flush creates immutable segments. Frequent flushes therefore create many small
segments, and deletions leave dead postings and stored values inside older
segments. A search snapshot can remain logically correct by consulting every
segment and filtering with live-doc masks, but physical work and file count
grow.

A merge creates a new immutable segment containing only live documents from a
selected set. It can reduce the number of segment readers, discard deleted
physical content, and reset local IDs densely. It does not modify its input
segments.

MiniLucene makes merge explicit:

```python
writer.merge((generation_a, generation_b))
```

This is a teaching choice, not production automation. The caller chooses at
least two unique generations already owned by the writer.
`src/minilucene/writer.py`, `IndexWriter.merge()` rejects too few,
duplicate, or unknown generations before mutation.

## 2. Capture immutable inputs

`IndexWriter.merge()` preserves the writer's current segment order when it
builds `ordered_selected`. It opens every selected segment through the
checksummed `SegmentStore` and pairs each image with the writer's current
live-doc `frozenset`.

The pair is the logical input:

```text
immutable SegmentImage + point-in-time live-doc mask
```

Using only the segment image would resurrect deleted documents. Reading a mask
later could mix generations. Capturing the tuple first gives
`src/minilucene/merge.py`, `merge_segment_images()` a stable view.

The writer allocates a new segment generation and skips any generation that
already exists, including a complete orphan from an earlier failed
publication. No input directory is overwritten.

## 3. Remap live documents densely

`merge_segment_images()` makes one `old local ID → new local ID` map per input
segment. It visits `sorted(live_docs)`, assigns the next dense ID, copies the
stored document, and copies each field length. Deleted IDs receive no mapping.

It then walks every field, term, and posting in the input images. A posting is
copied only if its old local ID appears in the map. The new posting keeps the
original term frequency and position tuple but uses the new dense ID.

This direct postings copy matters. Reconstructing the index only from stored
fields would lose indexed-but-not-stored text. Re-analyzing stored text could
also change results if analyzer behavior changed. MiniLucene treats the
validated segment image as the source for indexed structures.

Suppose the selected segments contain:

```text
segment 2: live IDs {0, 2}
segment 5: live IDs {1}
```

The merged maps are `{0: 0, 2: 1}` and `{1: 2}`. The output has
`max_doc == 3`, no deletion mask, and local IDs `0, 1, 2`.

## 4. Publish output before swapping writer state

After constructing the `SegmentImage`, `IndexWriter.merge()` calls
`SegmentStore.publish()`. Only after publication succeeds does it build and
assign the next writer segment list, live-doc dictionary, metadata dictionary,
dirty set, and generation counter.

The replacement is inserted at the earliest selected slot. Unselected
segments keep their relative order. This preserves deterministic global
document ordering even when the selected inputs were nonadjacent.

Failure before the state swap leaves the old writer set authoritative. The
published-output boundary is tested by
`tests/acceptance/test_failure_matrix.py`,
`test_merge_publish_failure_preserves_writer_set()`.

A successful `merge()` is still not a durable commit. It changes writer state
and publishes a new immutable segment directory, but `manifest.json` still
names the previous commit until `IndexWriter.commit()` succeeds. An NRT
`refresh()` can see writer state before commit; a process reopen cannot.

## 5. Old readers and old files survive as needed

An old reader may refer to the input segments after the writer has merged and
committed the output. Because its `ReaderSnapshot` is frozen, its results stay
unchanged. It must not be invalidated merely because a newer reader can use
the compacted segment.

`IndexWriter.merge()` updates the writer owner in
`src/minilucene/storage/registry.py`, `SegmentRegistry.replace()`.
After commit removes the old generations from the manifest, they are eligible
for `Index.collect_garbage()` only when no reader owner retains them.
`SegmentRegistry.collect_garbage()` enforces that union of manifest, writer,
and reader ownership.

Merge also clears live-doc metadata for the new segment because only live
documents were copied. The output begins all-live. Old mask files remain under
old segment directories and disappear with those directories when collection
is safe.

MiniLucene's live-only BM25 statistics mean the same logical query receives
the same score before and after merge. This differs from Apache Lucene, where
deleted documents can remain in pre-merge segment statistics; physically
dropping them can change scores.

## 6. Contrast with Apache Lucene merge machinery

Real Lucene uses a `MergePolicy` to select work and a `MergeScheduler` to run
it. `TieredMergePolicy` considers segment sizes, deletion reclaim, allowed
segment counts, and an optimization cost rather than asking the application to
list generations for every merge. Merges may run concurrently with indexing,
and production code handles warmer/cache behavior, I/O throttling, compound
files, failure accounting, and commit/deletion policy interactions.

MiniLucene has none of that scheduling machinery. Its explicit synchronous
method makes four invariants visible:

1. capture immutable images and exact live masks;
2. build a new dense immutable image;
3. publish the output before swapping writer state; and
4. defer input deletion until roots and owners release them.

These invariants transfer even though the operational system is dramatically
simpler. The [explicit merge](../behavior-matrix.md), merge publication
failure, segment ownership, and “no automatic merge scheduler” rows define the
implemented boundary. The [MiniLucene-to-Lucene mapping](../lucene-mapping.md)
names `MergePolicy` and `MergeScheduler` as production counterparts.

## 7. The next query-execution gaps

Merge is only one path forward. MiniLucene now advances postings in document
order, composes term/Boolean scorers, streams matches into Top-K, and fetches
stored content only for winners. [Chapter 11](11-daat.md) implements and tests
that DAAT slice. Phrase trees still fall back to complete sets and score
dictionaries, and the cursor layer has no skip data or competitive-score
pruning.

A useful progression beyond this repository is:

```text
current linear PostingsIterator.advance()
  → encoded skip data and block-aware advance
  → phrase approximation + positional confirmation
  → per-leaf scorer/collector execution
  → block-max metadata and competitive skipping
```

Do not jump directly to WAND. First migrate phrase matching without changing
its frozen score semantics, add observable cursor statistics, and measure
whether skipping metadata helps the actual corpus. Keep differential tests
against the preserved set oracle at every step.

## 8. A practical route into real Lucene

Use MiniLucene modules as questions to bring to Lucene, not as file-format or
API compatibility:

- From `storage/manifest.py`, read about `SegmentInfos`, `segments_N`, commit
  points, and `IndexDeletionPolicy`.
- From `storage/live_docs.py`, inspect `LiveDocsFormat`, `.liv` files, and leaf
  reader live bits.
- From `writer.py` and `merge.py`, study `IndexWriter`, flush control,
  `TieredMergePolicy`, and `ConcurrentMergeScheduler`.
- From `search/scorer.py`, study `Weight`, `Scorer`, `DocIdSetIterator`,
  conjunction/disjunction scorers, and two-phase iteration.
- From `search/collector.py`, study `Collector`, `LeafCollector`, and
  `TopScoreDocCollector`.
- From `query_parser/` and `search/rewrite.py`, study Lucene query parsers and
  `MultiTermQuery` rewrite methods.

The repository also states important non-goals: no Lucene codec compatibility,
network adapter, distributed coordination, vector retrieval, numeric/range
fields, doc values, sorting, faceting, or automatic merge scheduler. See the
[behavior matrix](../behavior-matrix.md) and
[mapping](../lucene-mapping.md). A roadmap is honest only when it begins from
these current boundaries.

## 9. Hands-on experiment: merge live documents

Run from the repository root:

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
        writer.add_document(id="1", body="common first")
        writer.flush()
        writer.add_document(id="2", body="common deleted")
        writer.flush()
        writer.add_document(id="3", body="common third")
        writer.commit()

    with index.writer() as writer:
        writer.delete_by_term("id", "2")
        before = writer.segment_generations
        merged = writer.merge(before)
        after = writer.segment_generations
        writer.commit()

    reader = index.open_reader()
    results = reader.search(TermQuery("body", "common"), top_k=10)
    print(f"before={before}")
    print(f"after={after}")
    print(f"merged_generation={merged.generation}")
    print(f"total_hits={results.total_hits}")
    print(
        "ids="
        f"{[hit.stored_fields['id'] for hit in results.hits]}"
    )
    reader.close()
    index.close()
PY
```

Measured output:

```text
before=(1, 2, 3)
after=(4,)
merged_generation=4
total_hits=2
ids=['1', '3']
```

The deleted document is not copied, and three input segments become one
all-live output segment.

Run the focused executable evidence:

```bash
UV_CACHE_DIR=/tmp/minilucene-uv-cache uv run pytest tests/nrt/test_segment_merge.py -q
```

Measured output:

```text
6 passed in 1.26s
```

## 10. Exercises

### Exercise 1 — data flow

Why must merge copy postings directly instead of rebuilding only from stored
fields?

??? note "Reference answer"

    Indexed fields need not be stored. Rebuilding from stored fields would
    lose such searchable content. It could also change positions or terms if
    analysis changed. Copying validated postings, positions, norms, and stored
    values preserves the indexed snapshot.

### Exercise 2 — lifecycle

After merge and commit, why can `collect_garbage()` still retain the input
segments?

??? note "Reference answer"

    An old reader may still own them. Removal requires the generations to be
    absent from the manifest, writer owner, and every reader owner. Commit
    changes the durable root; it does not invalidate existing point-in-time
    readers.

### Exercise 3 — hands-on policy design

Do not edit `src/`. Write a scratch `select_merge(segments)` policy using
segment byte sizes and deletion ratios. It should return either an ordered
tuple of at least two generations or no work.

Acceptance: provide deterministic tests for “too many small segments,” “one
large plus one small segment,” and “high deletion reclaim.” State a maximum
merge width and prove the function never returns unknown or duplicate
generations.

??? note "Reference answer"

    One acceptable teaching policy sorts candidates by `(size, generation)`,
    chooses up to a fixed width when the small-segment count exceeds a
    threshold, and separately prioritizes segments above a deletion-ratio
    threshold. It returns generations in current writer order. Tests assert
    width, uniqueness, membership, deterministic selection, and no work for a
    healthy layout. This is not `TieredMergePolicy`; it is a bounded exercise
    that makes inputs and invariants explicit.

### Exercise 4 — roadmap

Choose phrase two-phase iteration or automatic merge scheduling as a next
subsystem. Write a one-page design with an invariant, a minimal API, a failure
boundary, and an executable acceptance test.

??? note "Reference answer"

    A phrase design can use term conjunction as approximation and positions as
    confirmation, then compare hits and scores with the complete-set oracle. A
    merge-scheduler design should separate deterministic selection from
    execution, retain writer single-ownership, and inject publication failure
    to prove the old writer set remains authoritative.

## Summary

Explicit merge captures immutable segments plus exact live masks, remaps only
live documents densely, publishes a new segment, and swaps writer state only
after success. Commit and owner-aware garbage collection are separate later
boundaries. MiniLucene stops before automatic `TieredMergePolicy`, phrase
two-phase iteration, skip data, and competitive-score pruning. These are
concrete next interfaces. Chapter 11 now develops the implemented DAAT base.

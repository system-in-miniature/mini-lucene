# Phase 3: NRT Mutation and Merge Acceptance

> **Language**: English | [简体中文](zh/phase3-nrt-mutation.md)

## Accepted visibility model

MiniLucene now has three executable and distinct boundaries:

```text
flush
  creates an immutable segment in writer state

refresh
  returns a new in-process point-in-time reader

commit
  atomically replaces the recoverable manifest
```

Refresh-visible data disappears after a simulated process reopen unless it was
committed. An existing reader never changes after any later refresh, delete,
update, commit, or merge.

## Accepted mutation behavior

- Each `IndexReader` owns one frozen `ReaderSnapshot`.
- Closing a reader is idempotent and releases only that reader's segment
  references.
- Live docs are immutable bitset generations with max-doc validation and
  SHA-256 manifest references.
- Delete-by-term derives every buffer and segment mask before swapping writer
  state.
- Repeated delete counts only newly deleted live documents.
- Update validates and prepares the replacement before atomically swapping
  `delete all exact-term matches + add one replacement`.
- Deleted documents contribute neither hits, document frequency, average field
  length, nor BM25 score.
- Explicit merge copies live postings and positions directly, so indexed but
  non-stored text remains searchable.
- Merge remaps local document IDs densely and preserves norms and stored fields.
- Merge failure before writer-set swap leaves the old segment set authoritative.
- Generation allocation skips complete orphan segments and live-doc files
  created before failed publication.

## Ownership and cleanup

A process-local registry tracks independent reader and writer owners by segment
generation. Garbage collection removes a segment only when it is:

```text
absent from manifest
AND absent from every reader owner
AND absent from the writer owner
AND a recognized complete segment directory
```

Malformed or unknown directories are retained for diagnosis. `Index.close()`
stops new admissions and reports external readers instead of invalidating them.
Writer close transitions through `OPEN → CLOSING → CLOSED`, releases segment
ownership, then releases its lock.

## Accepted commands

Executed on 2026-07-27:

```text
uv run pytest tests/acceptance/test_phase3_nrt_mutation.py -q
1 passed

uv run ruff check src tests tools
All checks passed

uv run pytest -q
149 passed

uv run python -m compileall -q src tests tools
exit 0

git diff --check
exit 0
```

## Deferred by phase boundary

Phase 3 has no query-string parser, highlighting, evaluation corpus, CLI,
network adapter, distributed coordination, automatic merge scheduler, or
vector retrieval.

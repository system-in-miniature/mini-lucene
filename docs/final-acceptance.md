# MiniLucene V1 Final Acceptance

> **Language**: English | [简体中文](zh/final-acceptance.md)

Accepted on 2026-07-27 in:

```text
~/MiniLucene-workspace/MiniLucene
```

The implementation tree tested before this evidence-only commit was:

```text
18db98104c5d3aeb3e75d453d2a4ec87ace43c1d
```

## Verification gates

```text
uv sync --dev
Resolved 8 packages
Audited 7 packages

uv run ruff check src tests tools
All checks passed

uv run pytest -q
227 passed in 5.78s

uv run python -m compileall -q src tests tools
exit 0

git diff --check
exit 0
```

The unfinished-marker scan found only deliberate empty exception/data classes,
cleanup `except` branches, one context-manager body, and examples inside the
frozen implementation plans. It found no skipped acceptance or unfinished
production implementation.

The executable behavior matrix validates that every documentation row resolves
to exactly one collected pytest node. It includes supported behavior, failure
experiments, lifecycle closeout, and explicit V1 non-goals.

The post-implementation completion audit also reconciled all four executable
phase plans against the focused commit history, phase reports, and acceptance
nodes. All 196 actionable plan steps are checked; no actionable step remains
open.

## Failure and recovery evidence

Acceptance covers:

1. document validation and analysis failure before RAM mutation;
2. segment data failure before final-directory rename;
3. a complete orphan before manifest replacement;
4. successful manifest replacement while an old reader retains old files;
5. checksum corruption failing closed on reader open;
6. refresh-visible but uncommitted state disappearing after reopen;
7. stale readers across refresh, delete, update, and merge;
8. merge publication failure before writer-set swap;
9. repeated close with cleanup failure aggregation.

The public end-to-end acceptance creates a fielded index, commits and reopens
it, parses a boolean phrase query, applies global BM25 and bounded Top-K,
retrieves stored fields, safely highlights original text, refreshes new state,
updates and deletes documents, retains an old reader, explicitly merges,
reopens again, and evaluates result IDs.

The owner-zero acceptance ends with:

```text
writer_owner = None
reader_owners = ()
segment_owners = {}
temporary_jobs = ()
.writer.lock absent
.tmp-* absent
```

## Installed-package smoke

```text
uv build
Successfully built dist/minilucene_reference-0.1.0.tar.gz
Successfully built dist/minilucene_reference-0.1.0-py3-none-any.whl

uv pip install --python <isolated-venv>/bin/python <wheel>
Installed minilucene-reference==0.1.0

<isolated-venv>/bin/python -c \
  "import minilucene; print(minilucene.__version__)"
0.1.0

<isolated-venv>/bin/minilucene --help
exit 0
```

## Accepted scope

V1 supports direct Python and local CLI use of:

- schema, stored/indexed/tokenized field semantics, and analyzers;
- positional inverted indexes and term, boolean, phrase, prefix, and match-all
  queries;
- global live-document BM25, field boosts, and deterministic bounded Top-K;
- immutable checksummed educational segments and atomic manifests;
- point-in-time readers, NRT refresh, delete, update, merge, and ownership-aware
  garbage collection;
- query parsing, safe highlighting, deterministic evaluation metrics, and a
  frozen relevance corpus.

V1 explicitly excludes TCP/HTTP adapters, remote compatibility, distributed
replication or coordination, Apache Lucene codec compatibility, production
index optimizations, automatic merge scheduling, vector fields, ANN, and
hybrid retrieval.

No `course/` or `chapters/` directory exists. Course design remains a separate
future task after acceptance of this reference project.

# MiniLucene DAAT Query Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `test-driven-development` and execute each task in order. Do not commit:
> this task's user instruction explicitly forbids git commits.

**Goal:** Stream supported Boolean query trees doc-at-a-time into Top-K and
fetch stored content only for final winners while preserving the set scorer as
an oracle and fallback.

**Architecture:** A standalone iterator module owns ordered doc-ID movement.
Scorer nodes compile the closed query AST onto those cursors and reuse the
existing BM25 formula. The existing collector becomes a lightweight first
phase; the searcher materializes public hits in a second phase.

**Tech Stack:** Python 3.12, dataclasses, `heapq`, pytest, Ruff, MkDocs
Markdown.

---

### Task 1: Cursor contract

**Files:**
- Create: `src/minilucene/search/iterators.py`
- Create: `tests/unit/search/test_iterators.py`

- [ ] Write tests that assert `UNPOSITIONED`, `NO_MORE_DOCS`, empty/singleton
  behavior, `next()`, and first-doc-at-least-target `advance()`.
- [ ] Run `uv run pytest tests/unit/search/test_iterators.py -q` and confirm
  import failure because the module is absent.
- [ ] Implement strictly ordered `PostingsIterator`, zipper-based
  `ConjunctionIterator`, heap-based `DisjunctionIterator`, and
  `ReqExclIterator`, with class docstrings mapping each design to Lucene.
- [ ] Re-run the iterator tests and Ruff for the new files.

### Task 2: DAAT scorer compilation and oracle comparison

**Files:**
- Modify: `src/minilucene/search/scorer.py`
- Create: `tests/unit/search/test_daat_scorer.py`

- [ ] Write fixed examples and a seeded random corpus/query-tree differential
  test comparing `iter_scored_docs()` with `score_query()`.
- [ ] Include nested MUST, SHOULD, MUST_NOT, only-negative, match-all, empty
  posting, phrase fallback, and unrevised-prefix fallback cases.
- [ ] Run the scorer tests and confirm failure because the streaming API is
  absent.
- [ ] Add internal term, Boolean, and match-all scorer nodes. Compile the
  entire supported tree or return unsupported; let the public stream fall
  back to `score_query().items()` for unsupported trees.
- [ ] Re-run scorer tests and relevant existing ranking/query tests.

### Task 3: Lightweight Top-K and two-phase search

**Files:**
- Modify: `src/minilucene/search/collector.py`
- Modify: `src/minilucene/search/searcher.py`
- Modify: `src/minilucene/search/__init__.py`
- Modify: `tests/unit/search/test_topk.py`
- Create: `tests/contract/test_collect_then_fetch.py`

- [ ] Write collector tests for retained snapshot doc IDs and a search
  contract test that instruments `stored_fields()` to observe
  `matched > fetched == K`.
- [ ] Run the focused tests and confirm expected failures.
- [ ] Store lightweight scored candidates in `TopKCollector`; preserve
  `top_docs()` compatibility for direct collector tests and expose ordered
  winners to the searcher.
- [ ] Change `IndexSearcher.search()` to stream DAAT scores into the collector,
  then fetch/highlight only ordered winners and assemble public `TopDocs`.
- [ ] Re-run collector, memory/disk search, highlighting, and ranking tests.

### Task 4: Bilingual teaching and claim synchronization

**Files:**
- Create: `docs/tutorial/11-daat.md`
- Create: `docs/zh/tutorial/11-daat.md`
- Modify: `docs/tutorial/index.md`
- Modify: `docs/zh/tutorial/index.md`
- Modify: `mkdocs.yml`
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `docs/lucene-mapping.md`
- Modify: `docs/zh/lucene-mapping.md`
- Modify: `docs/tutorial/03-inverted-index.md`
- Modify: `docs/zh/tutorial/03-inverted-index.md`
- Modify: `docs/tutorial/08-scoring.md`
- Modify: `docs/zh/tutorial/08-scoring.md`
- Modify: `docs/tutorial/09-query-language.md`
- Modify: `docs/zh/tutorial/09-query-language.md`
- Modify: `docs/tutorial/10-merge-and-beyond.md`
- Modify: `docs/zh/tutorial/10-merge-and-beyond.md`

- [ ] Add the bilingual chapter with ASCII traces, a reproducible differential
  experiment and measured output, fallback table, roadmap, and exercises.
- [ ] Add Chapter 11 to both book indexes and both MkDocs navigation trees.
- [ ] Replace every current claim that DAAT or late fetch is absent while
  retaining accurate limitations for phrase fallback, linear advance, skip
  lists, two-phase matching, WAND, MaxScore, and production tuning.
- [ ] Run the chapter's commands and paste fresh stable output.

### Task 5: Final verification and metrics

**Files:** all changed files.

- [ ] Run `uv run pytest -q` and require zero failures.
- [ ] Run `uv run ruff check src tests tools`.
- [ ] Run `uv run python -m compileall -q src tests tools`.
- [ ] Run `git diff --check`.
- [ ] Search for stale DAAT/early-fetch claims across README and docs.
- [ ] Count new production module lines, randomized corpus/query combinations,
  observed matched/fetched counts, and bilingual Chapter 11 word/character
  counts for the final report.


# Phase 1: Retrieval Kernel Acceptance

## Accepted public loop

The in-memory reference path is:

```text
Schema
→ validated Unicode document
→ field analyzer
→ immutable positional RAM segment
→ closed Query AST
→ live reader statistics
→ BM25 scorer
→ bounded Top-K collector
→ stored fields
```

The primary direct API is `MemoryIndex.add_document()` plus
`MemoryIndex.search(query, top_k=...)`. No transport adapter participates in
the semantic tests.

## Frozen behavior

- `TextField`, `KeywordField`, and `StoredField` keep stored, indexed,
  tokenized, positional, and boosted behavior independent.
- Schema fingerprints use canonical sorted JSON and SHA-256.
- Validation and analysis complete before a RAM builder mutates.
- Standard analysis lowercases terms while preserving original offsets and
  stopword position gaps.
- Posting lists contain one posting per field/term/document, ordered by dense
  local document ID.
- Phrase queries carry normalized query positions, so removed stopwords do not
  collapse gaps.
- Boolean queries implement the frozen MUST/SHOULD/MUST_NOT rules; an
  only-negative query matches nothing.
- Prefix queries read the term dictionary and fail when their configured
  expansion cap is exceeded.
- BM25 defaults are `k1=1.2` and `b=0.75`; field boosts multiply individual
  term contributions.
- One `CorpusStats` value spans all live documents in a reader view.
- `TopKCollector` retains at most K hits while counting every match.
- Equal scores order by segment generation and then local document ID.

## Executable evidence

Phase acceptance:

```text
tests/acceptance/test_phase1_retrieval_kernel.py
```

Focused contracts live under:

```text
tests/contract/test_schema.py
tests/unit/analysis/test_pipeline.py
tests/contract/test_memory_index.py
tests/contract/test_query_matching.py
tests/unit/search/test_corpus_stats.py
tests/unit/search/test_bm25.py
tests/contract/test_ranking.py
tests/unit/search/test_topk.py
tests/contract/test_memory_search.py
```

Accepted commands on 2026-07-27:

```text
uv run pytest tests/acceptance/test_phase1_retrieval_kernel.py -q
1 passed

uv run ruff check src tests tools
All checks passed

uv run pytest -q
54 passed

uv run python -m compileall -q src tests tools
exit 0

git diff --check
exit 0
```

## Deferred by phase boundary

Phase 1 deliberately has no disk segment codec, manifest, restart recovery,
refresh, commit, deletion, update, merge, query-string parser, highlighting,
CLI, network adapter, distributed coordination, or vector retrieval.

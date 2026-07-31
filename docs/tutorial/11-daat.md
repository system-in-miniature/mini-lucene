# Doc-at-a-Time Query Execution

## Learning objectives

By the end of this chapter, you will be able to:

1. explain why materializing complete match sets grows with total hits;
2. trace `next()` and `advance(target)` through a posting cursor;
3. execute conjunctions with zipper alignment and disjunctions with a heap;
4. explain MUST_NOT as a required-stream filter;
5. distinguish DAAT collection from the later stored-field fetch; and
6. use the set-algebra scorer as a differential-testing oracle.

## 1. Why complete sets stop scaling

The original `query/match.py` implementation is intentionally easy to read.
Each leaf becomes a `set[int]`; AND intersects sets, OR unions sets, and NOT
subtracts a prohibited set. `search/scorer.py`, `score_query()`, then builds a
complete `dict[int, float]`.

That is a valuable semantic oracle, but its ownership model grows with the
number of matches:

```text
term A postings ──→ set A ─┐
                           ├─→ complete intersection ─→ complete score dict
term B postings ──→ set B ─┘
```

If two common terms each match millions of documents, both sets exist before
the intersection can be consumed. A Top-K heap later in the pipeline cannot
recover that memory.

DAAT changes the ownership contract. Every node holds only its current
position and bounded per-clause merge state:

```text
posting cursors → iterator tree → one (doc_id, score) at a time → Top-K
```

MiniLucene keeps the set implementation. It remains the simplest executable
definition of Boolean semantics and the oracle used to test the streaming
path.

## 2. The cursor contract

`src/minilucene/search/iterators.py`, `PostingsIterator`, wraps one sorted
posting list. Its state machine is:

```text
UNPOSITIONED (-1)
      │ next() / advance(target)
      ▼
 current live posting ── next()/advance() ──→ later posting
      │
      └─────────────────────────────────────→ NO_MORE_DOCS
```

- `doc()` observes the current state.
- `next()` moves to the following posting.
- `advance(target)` moves to the first posting with `doc_id >= target`.
- exhaustion is stable: later calls still return `NO_MORE_DOCS`.

For postings `[1, 4, 9, 15]`, `advance(5)` lands on `9`, not `5` and not
`15`. The target is a lower bound.

MiniLucene's `advance()` scans linearly because the educational segment codec
does not store skip data. The interface matters even before the optimization:
composite iterators can request a jump without depending on how a posting
format implements it. Real Lucene `PostingsEnum` implementations use skip
lists and block-level metadata to make many advances cheaper.

## 3. AND is zipper alignment

`ConjunctionIterator` corresponds to Lucene's `ConjunctionDISI`. It never
builds an intersection set. Instead, it advances the lagging cursors until all
doc IDs agree.

```text
A:  1   3   5       9      12
B:  0   3   4       9  11  12
C:      3       8   9      12
        ▲               aligned outputs: 3, 9, 12
```

Suppose A is on 5 while B advances to 9. Document 5 can no longer be in the
intersection, so A advances directly toward 9. If another child overshoots to
12, 12 becomes the new target and alignment restarts.

Pseudocode:

```text
target = first child
repeat:
    for each remaining child:
        child.advance(target)
        if child > target:
            first.advance(child)
            restart alignment with the larger target
    if every child == target:
        emit target
```

An empty child terminates the whole conjunction immediately. This is the
natural streaming equivalent of intersecting with the empty set.

## 4. OR is a minimum-heap merge

`DisjunctionIterator` corresponds to Lucene's
`DisjunctionDISIApproximation`. It keeps one `(doc_id, child)` entry for each
non-exhausted child:

```text
A: 1       5       9
B:   2     5   8
C:         5           10

heap tops: 1 → 2 → 5 → 8 → 9 → 10
                     ^
          all three cursors at 5 advance together,
          so document 5 is emitted only once
```

Heap state is `O(number of clauses)`, not `O(number of matches)`. The current
document may be shared by several children; those children remain positioned
there long enough for the Boolean scorer to sum every matching clause's BM25
contribution. On the next call, all heap entries equal to the emitted doc ID
advance before the next minimum is selected.

## 5. MUST_NOT filters a required stream

`ReqExclIterator` mirrors the role of Lucene's `ReqExclScorer`. It receives a
positive iterator and a prohibited iterator:

```text
required:    1  2     4        7  9
prohibited:  0  2  3           7     10
output:      1        4           9
```

For each required candidate, the prohibited cursor advances only to that
candidate. Equal means reject; greater means accept because prohibited doc IDs
cannot move backwards.

The compiler in `search/scorer.py` preserves MiniLucene's existing Boolean
contract:

- MUST children form a conjunction.
- Without MUST, SHOULD children form a disjunction.
- With MUST, SHOULD is optional but adds score when it matches.
- MUST_NOT children form a disjunction used as the exclusion stream.
- A query containing only MUST_NOT still matches nothing.

Nested Boolean queries compile recursively, so an AND child can itself be an
OR or a filtered subtree.

## 6. Streaming BM25 and explicit fallback

`iter_scored_docs()` compiles term, match-all, and Boolean nodes into scorer
cursors. A term scorer holds the current `Posting`, so it has the same
`term_frequency` used by the oracle. It calls the existing `BM25.term_score()`
with the same live `df`, live document count, field length, average field
length, and schema boost. Boolean scorers sum matching positive children in
clause order.

Not every query type has migrated:

| Query after rewrite | Execution |
|---|---|
| `TermQuery` | DAAT |
| `MatchAllQuery` | DAAT over the reader's live-doc IDs |
| term/match-all `BooleanQuery` | recursive DAAT |
| `PrefixQuery` | normally rewrites to term/Boolean, then DAAT |
| `PhraseQuery` | complete-tree fallback to `score_query()` |
| unrevised `PrefixQuery` passed directly to the scorer | complete-tree fallback |

Fallback is whole-tree, not leaf-by-leaf. If a Boolean tree contains a phrase,
the complete tree runs through the oracle path. This keeps matching and score
addition exactly consistent while positional two-phase iteration remains a
roadmap item.

## 7. Two phases: collect, then fetch

`IndexSearcher.search()` now has two explicit phases:

```text
Phase 1 — query execution
iterator tree → (snapshot doc ID, score)
              → address
              → TopKCollector retains at most K lightweight candidates

Phase 2 — result materialization
final K candidates → stored_fields()
                   → highlight_document()
                   → public SearchHit objects
```

The collector counts every match but stores only score, snapshot doc ID,
segment generation, and local doc ID for competitive candidates. It does not
read stored fields or highlight text. `top_k=0` therefore traverses and counts
the stream but performs zero stored-field fetches.

This fixes an important distinction from the old pipeline. “The collector
retains at most K” is now true end to end for expensive hit materialization:
only final winners become `SearchHit` objects. It does **not** mean all query
work is `O(K)`. Every match is still scored, phrase fallback materializes full
sets/maps, and no WAND-like competitive-score skipping exists.

## 8. Differential experiment: DAAT versus the oracle

The teaching safety net is
`tests/unit/search/test_daat_scorer.py`. With deterministic seed `0xDAA7`, it
builds 24 random corpora. For each corpus it generates 40 nested Boolean query
trees up to depth three from AND/MUST, OR/SHOULD, and NOT/MUST_NOT clauses.
That is:

```text
24 corpora × 40 queries = 960 corpus/query comparisons
```

Each comparison requires identical document IDs and approximately identical
floating-point scores:

```python
oracle = score_query(reader, query)
actual = dict(iter_scored_docs(reader, query))
assert actual.keys() == oracle.keys()
assert actual == pytest.approx(oracle)
```

Run the cursor and differential suites:

```bash
UV_CACHE_DIR=/tmp/minilucene-uv-cache uv run pytest \
  tests/unit/search/test_iterators.py \
  tests/unit/search/test_daat_scorer.py -q
```

Measured output:

```text
......................                                                   [100%]
22 passed in 0.19s
```

The late-fetch contract is separately executable:

```bash
UV_CACHE_DIR=/tmp/minilucene-uv-cache uv run pytest \
  tests/contract/test_collect_then_fetch.py -q
```

Measured output:

```text
..                                                                       [100%]
2 passed in 0.04s
```

That test observes `10 matched / 3 fetched` for `top_k=3`, and
`4 matched / 0 fetched` for `top_k=0`. Timing varies; counts and zero failures
are the stable evidence.

## 9. What real Lucene adds

MiniLucene now teaches the cursor shape, not the production optimization
stack. Real Lucene goes further with:

- encoded skip data and block-aware `advance`;
- per-leaf scorers rather than one educational global-doc cursor;
- approximation plus confirmation through `TwoPhaseIterator`, important for
  phrase and other expensive matches;
- impacts and block maximum scores;
- WAND, Block-Max WAND, and MaxScore-style pruning of noncompetitive docs;
- specialized bulk scorers and collector coordination.

A sensible roadmap is: migrate phrase matching to approximation plus
positional confirmation, add observable advance counters, introduce skip data
in the codec, then benchmark before considering WAND or MaxScore. Optimization
must remain checked against the set oracle.

## 10. Exercises

### Exercise 1 — trace a conjunction

Given postings `A=[2, 5, 8, 13]`, `B=[1, 5, 9, 13]`, and
`C=[5, 7, 13]`, write every target change made by zipper alignment.

??? note "Reference answer"

    The first output is 5. After A advances to 8, B overshoots to 9, A
    advances to 13, and B and C both advance to 13. The second output is 13;
    advancing any exhausted child then terminates the conjunction.

### Exercise 2 — add early-termination statistics

Add counters to a scratch copy of `ConjunctionIterator`: number of
`advance()` calls, target changes, and early terminations caused by an
exhausted child. Write tests for one empty child, one sparse child, and three
fully aligned children.

Acceptance: counters must not change emitted doc IDs; the sparse case must
show at least one target change; the empty-child case must attribute exactly
one early termination.

??? note "Reference answer"

    Keep statistics observational: increment beside existing transitions,
    never use a counter to control execution. A small frozen dataclass returned
    by `stats()` avoids exposing writable iterator internals.

### Exercise 3 — design phrase two-phase iteration

Sketch a phrase scorer whose approximation is a conjunction of term postings
and whose confirmation checks positions. State where term BM25 contributions
are read and how the existing phrase-scoring semantics remain unchanged.

??? note "Reference answer"

    The approximation emits only docs containing every term. A confirmation
    method calls the positional predicate before collection. Once confirmed,
    score each component term from its cursor's current posting and sum in
    query-term order. Differential tests must still compare both hits and
    scores with `score_query()` before removing phrase fallback.

## Summary

MiniLucene now compiles supported Boolean trees into bounded-state doc-ID
cursors: zipper conjunction, heap disjunction, and required/excluded
filtering. BM25 is produced one document at a time and fed directly to Top-K;
stored fields and highlights are fetched only for final winners. The original
set and score-dictionary path remains both the fallback for unmigrated query
types and the oracle that makes the structural change trustworthy.

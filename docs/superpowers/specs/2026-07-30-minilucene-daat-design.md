# MiniLucene DAAT Query Execution Design

## Goal

Add a doc-at-a-time execution path for rewritten term, match-all, and Boolean
query trees without removing the existing set-algebra matcher/scorer. Search
must collect lightweight Top-K identities before fetching stored fields and
building highlights.

## Chosen architecture

The cursor layer lives in `search/iterators.py`, independently from query
semantics and BM25. `PostingsIterator` exposes the posting-list cursor;
`ConjunctionIterator` aligns children like Lucene's `ConjunctionDISI`;
`DisjunctionIterator` merges children with a minimum heap like
`DisjunctionDISIApproximation`; `ReqExclIterator` filters a required stream
against a prohibited stream like `ReqExclScorer`.

`search/scorer.py` compiles a supported rewritten query tree into scorer
nodes that implement the same cursor interface plus `score()`. Term nodes
read the current posting's term frequency and use the existing `BM25`
implementation and the same live corpus statistics, field lengths, and field
boosts as `score_query()`. Boolean nodes preserve the repository's frozen
semantics:

- MUST children determine candidates by conjunction.
- With no MUST, SHOULD children determine candidates by disjunction.
- SHOULD is optional when MUST exists but still contributes to score.
- MUST_NOT children are unioned and passed to the exclusion iterator.
- A Boolean query containing only MUST_NOT matches nothing.

The compiler rejects an entire tree if any leaf is not migrated. The public
streaming entry point then falls back to the existing `score_query()` oracle.
`PhraseQuery` is the intentional fallback. An unrevised `PrefixQuery` also
falls back; normal `IndexSearcher` use rewrites prefix queries into supported
term/Boolean trees first. This whole-tree rule avoids partially materialized
hybrid semantics.

## Iterator contract

Before iteration `doc()` is `UNPOSITIONED` (`-1`). `next()` moves to the next
document, and `advance(target)` moves to the first document whose ID is at
least `target`. Exhaustion is represented by `NO_MORE_DOCS`. Calls after
exhaustion remain exhausted. Posting lists are validated as strictly
increasing. MiniLucene's `advance` is linear because its educational codec has
no skip data; real Lucene postings use skip lists and block-level structures.

## Collect then fetch

`TopKCollector` stores a lightweight internal candidate containing score,
segment generation, local doc ID, and snapshot-global doc ID. It never needs
stored fields or highlights during heap admission. `IndexSearcher.search()`
streams `(doc_id, score)` into that collector, obtains the final candidates,
then loads stored fields and highlights only those winners. The public
`TopDocs` and `SearchHit` shapes remain unchanged, including deterministic
tie-breaking and complete `total_hits`.

`top_k=0` still consumes and counts the complete match stream but fetches no
stored fields.

## Testing

Cursor unit tests cover unpositioned/exhausted state, empty and singleton
postings, exact and overshooting `advance`, conjunction alignment,
heap-deduplicated disjunction, and required/excluded filtering.

A deterministic property-style test builds random small corpora and nested
term-only Boolean trees with AND/OR/NOT structure. For every case it compares
the DAAT stream with `score_query()` for identical doc IDs and approximately
identical per-document scores. Contract tests instrument stored-field access
and highlighting inputs to prove that matched documents can exceed fetched
documents and that fetched documents never exceed K.

## Documentation

Chapter 11 is bilingual and teaches cursor execution, conjunction zippering,
heap disjunction, exclusion, whole-tree fallback, collect-then-fetch, and the
oracle differential experiment. README, mapping, Chapters 3, 8, 9, and 10,
book indexes, and MkDocs navigation are updated. Skip lists, two-phase phrase
iteration, WAND, Block-Max WAND, and MaxScore remain explicit roadmap items.


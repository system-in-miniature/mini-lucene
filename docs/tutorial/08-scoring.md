# Scoring and Top-K

## Learning objectives

By the end of this chapter, you will be able to:

1. compute the four inputs MiniLucene uses for a BM25 term contribution;
2. trace matching, scoring, stored-field loading, and Top-K collection;
3. explain deterministic tie-breaking and why `top_k=0` still counts matches;
4. identify the current phrase-scoring and collect-then-fetch deviations from Apache Lucene; and
5. verify that deleted documents do not contribute to MiniLucene corpus statistics.

## 1. Matching and scoring are separate stages

A query first decides *which* documents are eligible and then assigns scores.
`src/minilucene/search/scorer.py`, `score_query()` begins with
`match_query(reader, query)`, which materializes a complete `set[int]` of
candidate snapshot document IDs. This is a correctness-friendly teaching
boundary: Boolean and phrase logic can be understood independently from
ranking.

For a `TermQuery`, `score_query()` calls `_term_scores()`. For each live
posting it reads:

- `tf`: term frequency in this document and field;
- `df`: live document frequency for this field and term;
- `n`: total live documents in the reader snapshot;
- `dl`: analyzed field length of this document; and
- `avgdl`: average analyzed length among live documents with the field.

The implementation obtains `df`, `n`, and `avgdl` from
`src/minilucene/search/stats.py`, `CorpusStats`; these values are frozen by
`src/minilucene/search/reader.py`, `ReaderView._build_corpus_stats()`.
That function iterates only the snapshot's live local IDs. A newly deleted
document therefore contributes neither a match nor background statistics.

This is a deliberate MiniLucene semantic choice. It keeps scoring stable
across explicit merge because merge copies exactly the same live corpus.

## 2. BM25 rewards evidence but saturates repetition

`src/minilucene/search/bm25.py`, `BM25.term_score()` implements:

```text
idf = log(1 + (n - df + 0.5) / (df + 0.5))
normalized_length = dl / avgdl if avgdl != 0 else 0
norm = 1 - b + b * normalized_length
tf_weight = tf * (k1 + 1) / (tf + k1 * norm)
score = idf * tf_weight
```

The defaults are `k1=1.2` and `b=0.75`.

IDF makes a rarer term more informative. The fraction in `tf_weight` grows
when the term repeats, but its numerator and denominator both grow with `tf`,
so the benefit saturates rather than remaining linear. Length normalization
reduces the advantage a long document gets merely from having more places to
contain a term. When `avgdl` is zero, the code sets `normalized_length=0`, so
`norm=1-b` (the default is `0.25`), rather than substituting a norm of `1.0`.
For `n=df=tf=1`, `dl=avgdl=0`, and the defaults, this gives
`score=0.486846584149`; using a norm of `1.0` would incorrectly give
`0.287682072452`.

`BM25.__post_init__()` rejects a negative/non-finite `k1` and a `b` outside
`[0, 1]`. `term_score()` rejects invalid counts and lengths and returns zero
for `tf == 0`, `df == 0`, or `n == 0`.

MiniLucene then multiplies the contribution by the schema field boost in
`_term_scores()`. This is educational but opposite to modern Lucene's
direction: current Lucene uses query-time boosts such as `BoostQuery`; it
removed index-time field boosts. The difference is explicit in the
[MiniLucene-to-Lucene mapping](../lucene-mapping.md).

A BM25 score is neither a probability nor a percentage. It is meaningful for
ordering documents under the same query, reader snapshot, similarity
parameters, schema boosts, and corpus statistics. Changing the live corpus can
change IDF and average length, so absolute values from different snapshots are
not directly calibrated. Tests in this repository compare controlled rankings
or approximate scores under frozen inputs; they do not assign a universal
“good relevance” threshold.

## 3. Composite scores

`src/minilucene/search/scorer.py`, `score_query()` follows the closed query AST:

- a term receives one BM25 contribution;
- a prefix is normally rewritten first, then matching expanded terms
  contribute;
- a Boolean query sums scores of non-prohibited child queries, but only for
  documents admitted by Boolean matching;
- match-all gives every candidate score `0.0`; and
- a phrase first requires positional matching, then sums the BM25
  contributions of its component terms for eligible documents.

The phrase branch needs an honesty label. MiniLucene proves adjacency with
positions, but it does **not** calculate phrase frequency. A document with the
phrase once and many scattered repetitions of its terms can receive a larger
score than a document containing the phrase repeatedly. Apache Lucene's
`PhraseQuery` scoring uses phrase frequency through its phrase matcher and
similarity. The two systems can therefore rank the same phrase matches
differently.

Prefix scoring also sums expanded term contributions. The expansion itself is
bounded and fail-fast, which Chapter 9 examines.

## 4. A heap retains at most K hits

`src/minilucene/search/collector.py`, `TopKCollector` separates total match
count from retained results. Every call to `collect()` increments
`total_hits`. When `top_k == 0`, it stops there: callers can count matches
without retaining hit objects.

For positive K, the collector maintains a min-heap of at most K entries.
The key is:

```python
(score, -segment_generation, -local_doc_id)
```

The smallest retained key is the easiest result to evict. Higher scores win.
For equal scores, a lower segment generation wins; inside a segment, a lower
local document ID wins. `top_docs()` finally sorts winners by descending score,
then ascending segment generation and local ID. The ordering is deterministic
across runs for the same snapshot.

The collector's memory for hit objects is `O(K)`, while `total_hits` still
counts the entire match set. `max_retained` exists as an observable test hook
and never exceeds K.

Tie-breaking uses segment and local IDs rather than stored application IDs.
Those physical IDs are stable within one reader snapshot but can change after
merge, so applications must not treat this fallback order as a permanent
external identity. MiniLucene preserves scores across merge through live-only
statistics, yet equal-scoring documents can receive new dense local IDs. A
product requiring stable business order needs an explicit sort key; field
sorting itself is outside V1.

## 5. The important collect-then-fetch deviation

It is tempting to conclude that an `O(K)` heap makes the whole search path
`O(K)`. The source says otherwise.

`src/minilucene/search/searcher.py`, `IndexSearcher.search()` first rewrites
the query and calls `score_query()`, which materializes a complete score
dictionary. It then loops over every scored document. Before calling
`collector.collect()`, it resolves the address, loads stored fields, and calls
`highlight_document()`.

```text
MiniLucene
complete match set → complete score dict
→ fetch stored fields/highlight every match → Top-K heap

typical Lucene direction
postings iterators/scorers → collect top doc IDs and scores
→ fetch stored fields/highlight only winners
```

Thus MiniLucene retains only K `SearchHit` objects, but matching and scoring
use memory proportional to all matches, and stored-field/highlighting work is
performed for all matches. It has no document-at-a-time iterator, postings
skips, block-max WAND, two-phase iterator, leaf collector, or late fetch stage.

This is not a minor optimization disclaimer; it is the current execution
architecture. The behavior matrix promises [bounded Top-K](../behavior-matrix.md)
retention, not an `O(K)` query engine. The mapping's query-execution warning
records the deviation explicitly.

## 6. Contrast with Apache Lucene

The BM25 concepts transfer: term frequency saturation, inverse document
frequency, length normalization, and a similarity object are central in real
Lucene too. So are collectors that retain competitive hits and deterministic
tie policies.

Several production details do not transfer directly:

- Apache Lucene scores over leaf readers using iterator-based `Scorer`
  implementations rather than complete Python sets and dictionaries.
- Lucene can skip noncompetitive postings and use optimized conjunction,
  disjunction, two-phase, and top-score collection machinery.
- Lucene usually fetches stored fields after collecting winning doc IDs.
- Deleted documents can remain in Lucene's segment statistics until merge;
  MiniLucene excludes them immediately.
- MiniLucene phrase scoring sums term scores rather than phrase frequency.
- MiniLucene fixes boost in the schema instead of wrapping a query in a
  query-time boost.

Consult the global BM25, bounded Top-K, live statistics, and ranking rows in
the [behavior matrix](../behavior-matrix.md), and the “Semantics reversed”
rows in the [mapping](../lucene-mapping.md), before treating measured
MiniLucene scores as Apache Lucene predictions.

## 7. Hands-on experiment: saturation, length, and the heap

Run from the repository root:

```bash
UV_CACHE_DIR=/tmp/minilucene-uv-cache uv run python - <<'PY'
from minilucene import MemoryIndex, Schema, TextField
from minilucene.query import TermQuery
from minilucene.search.bm25 import BM25

schema = Schema(body=TextField(stored=True))
index = MemoryIndex(schema)
index.add_document(body="kafka")
index.add_document(body="kafka kafka kafka kafka")
index.add_document(body="kafka filler filler filler filler filler")
index.add_document(body="unrelated")

results = index.search(TermQuery("body", "kafka"), top_k=2)
print(f"total_hits={results.total_hits}")
print(f"retained={len(results.hits)}")
for hit in results.hits:
    print(f"{hit.stored_fields['body']!r} score={hit.score:.6f}")

count_only = index.search(TermQuery("body", "kafka"), top_k=0)
print(
    f"count_only total={count_only.total_hits} "
    f"retained={len(count_only.hits)}"
)
print(
    "zero_avgdl="
    f"{BM25().term_score(tf=1, df=1, n=1, dl=0, avgdl=0):.12f}"
)
PY
```

Measured output:

```text
total_hits=3
retained=2
'kafka kafka kafka kafka' score=0.570680
'kafka' score=0.490428
count_only total=3 retained=0
zero_avgdl=0.486846584149
```

Four repetitions score more than one, but not four times more. The longer
document with one occurrence is outside Top-2 because length normalization
reduces its contribution. `top_k=0` still traverses and counts all three
matches.

For executable formula checks, also run:

```bash
UV_CACHE_DIR=/tmp/minilucene-uv-cache uv run pytest tests/unit/search/test_bm25.py tests/unit/search/test_topk.py -q
```

Measured output:

```text
10 passed in 0.04s
```

Elapsed time varies; the pass count and zero failures are the stable evidence.

## 8. Exercises

### Exercise 1 — calculation

If `n=10`, `df=2`, `tf=1`, and `dl=avgdl`, which parts of the BM25 formula are
affected if `tf` becomes 4?

??? note "Reference answer"

    `idf` is unchanged because `n` and `df` are unchanged. Length
    normalization is unchanged because `dl/avgdl` is unchanged. Only
    `tf_weight` changes, and it grows sublinearly toward its saturation limit.

### Exercise 2 — architecture

Why does `TopKCollector.max_retained <= K` not prove that search memory is
`O(K)`?

??? note "Reference answer"

    `score_query()` already materializes a complete candidate set and score
    dictionary. The collector bounds only retained `SearchHit` objects, not
    matching or scoring state. `IndexSearcher.search()` also fetches and
    highlights every match before heap admission.

### Exercise 3 — hands-on code change

Do not edit `src/`. Copy `src/minilucene/search/searcher.py` to a scratch
directory and sketch a two-phase “collect addresses, then fetch winners”
variant. List which collector return type would need to change.

Acceptance: the scratch diff must avoid `stored_fields()` and
`highlight_document()` before Top-K selection, preserve `total_hits`, and
describe how winner addresses are converted to final `SearchHit` objects.

??? note "Reference answer"

    The first phase can collect lightweight `(score, segment_generation,
    local_doc_id, snapshot_doc_id)` records. After `top_docs()` identifies
    winners, a second phase resolves stored fields and highlights only those
    records. The collector should return lightweight scored addresses rather
    than the current fully materialized `SearchHit`; the public `TopDocs` can
    still be assembled after fetch.

## Summary

MiniLucene separates match eligibility from BM25 contributions, freezes
live-only statistics, and uses a deterministic heap to retain at most K hits.
That heap does not change the current full-materialization architecture:
scores, stored fields, and highlights are produced for every match, and phrase
scores sum term evidence rather than phrase frequency. The next chapter moves
one stage earlier and examines how text becomes the closed query AST that this
scorer accepts.

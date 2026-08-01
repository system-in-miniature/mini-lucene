# Stage 30 · Document-at-a-time execution

### Goal

Build document-at-a-time execution and explain its boundary from an executable counterexample, runtime state, and the critical statement.

??? note "Deliverable files"
    - `src/minilucene/search/__init__.py`
    - `src/minilucene/search/collector.py`
    - `src/minilucene/search/iterators.py`
    - `src/minilucene/search/scorer.py`
    - `src/minilucene/search/searcher.py`
    - `tests/contract/test_collect_then_fetch.py`
    - `tests/unit/search/test_daat_scorer.py`
    - `tests/unit/search/test_iterators.py`
    - `tests/unit/search/test_topk.py`

### The problem at this point

Materializing full result sets for every query node hides streaming behavior and scales with all matches before Top-K can discard most of them.

### Test contract

#### See the failure first

Differential tests generate nested boolean queries and require DAAT hits and scores to equal the existing set-based oracle, including fallback cases.

??? note "File diff: tests/contract/test_collect_then_fetch.py"
    ```diff
    diff --git a/tests/contract/test_collect_then_fetch.py b/tests/contract/test_collect_then_fetch.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..6416ed9391a6d98f3f2a97e24e613a93f87ef17f
    --- /dev/null
    +++ b/tests/contract/test_collect_then_fetch.py
    @@ -0,0 +1,53 @@
    +from minilucene.index.memory import RamIndexBuilder
    +from minilucene.query import TermQuery
    +from minilucene.schema import Schema, TextField
    +from minilucene.search.reader import ReaderView
    +from minilucene.search.searcher import IndexSearcher
    +
    +
    +class CountingReader(ReaderView):
    +    def __init__(self, schema, segments):
    +        super().__init__(schema, segments)
    +        self.fetched_doc_ids: list[int] = []
    +
    +    def stored_fields(self, doc_id):
    +        self.fetched_doc_ids.append(doc_id)
    +        return super().stored_fields(doc_id)
    +
    +
    +def test_search_fetches_stored_fields_only_for_final_top_k():
    +    schema = Schema(body=TextField(stored=True))
    +    builder = RamIndexBuilder(schema)
    +    for frequency in range(1, 11):
    +        builder.add_document({"body": " ".join(["term"] * frequency)})
    +    reader = CountingReader(schema, (builder.freeze(generation=1),))
    +
    +    results = IndexSearcher(reader).search(
    +        TermQuery("body", "term"),
    +        top_k=3,
    +        highlight_fields=("body",),
    +    )
    +
    +    assert results.total_hits == 10
    +    assert len(results.hits) == 3
    +    assert len(reader.fetched_doc_ids) == 3
    +    assert all(hit.highlights["body"] for hit in results.hits)
    +    with pytest.raises(TypeError):
    +        results.hits[0].highlights["body"] = "changed"
    +
    +
    +def test_top_k_zero_counts_without_fetching_stored_fields():
    +    schema = Schema(body=TextField(stored=True))
    +    builder = RamIndexBuilder(schema)
    +    for _ in range(4):
    +        builder.add_document({"body": "term"})
    +    reader = CountingReader(schema, (builder.freeze(generation=1),))
    +
    +    results = IndexSearcher(reader).search(
    +        TermQuery("body", "term"), top_k=0
    +    )
    +
    +    assert results.total_hits == 4
    +    assert results.hits == ()
    +    assert reader.fetched_doc_ids == []
    +import pytest
    ```

**What this test locks**

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

**How it constructs the counterexample**

Differential tests generate nested boolean queries and require DAAT hits and scores to equal the existing set-based oracle, including fallback cases.

**Key test statement**

```python
assert results.total_hits == 10
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

**What a failure means**

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

??? note "File diff: tests/unit/search/test_daat_scorer.py"
    ```diff
    diff --git a/tests/unit/search/test_daat_scorer.py b/tests/unit/search/test_daat_scorer.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..11ecbfadf87d684912254ebc242415af26c23ec2
    --- /dev/null
    +++ b/tests/unit/search/test_daat_scorer.py
    @@ -0,0 +1,190 @@
    +import random
    +
    +import pytest
    +
    +from minilucene.index.memory import RamIndexBuilder
    +from minilucene.query import (
    +    BooleanClause,
    +    BooleanQuery,
    +    MatchAllQuery,
    +    Occur,
    +    PhraseQuery,
    +    PrefixQuery,
    +    Query,
    +    TermQuery,
    +)
    +from minilucene.schema import Schema, TextField
    +from minilucene.search.reader import ReaderView
    +from minilucene.search.scorer import iter_scored_docs, score_query
    +
    +VOCABULARY = ("alpha", "beta", "gamma", "delta", "epsilon", "zeta")
    +CORPUS_COUNT = 24
    +QUERIES_PER_CORPUS = 40
    +
    +
    +def build_reader(documents: tuple[str, ...]) -> ReaderView:
    +    schema = Schema(body=TextField(stored=True))
    +    builder = RamIndexBuilder(schema)
    +    for document in documents:
    +        builder.add_document({"body": document})
    +    return ReaderView(schema, (builder.freeze(generation=1),))
    +
    +
    +def random_query(rng: random.Random, depth: int = 0) -> Query:
    +    if depth >= 3 or rng.random() < 0.38:
    +        return TermQuery("body", rng.choice(VOCABULARY))
    +    clause_count = rng.randint(1, 4)
    +    clauses = []
    +    for _ in range(clause_count):
    +        occur = rng.choice((Occur.MUST, Occur.SHOULD, Occur.MUST_NOT))
    +        clauses.append(
    +            BooleanClause(occur, random_query(rng, depth + 1))
    +        )
    +    return BooleanQuery(tuple(clauses))
    +
    +
    +def assert_stream_matches_oracle(reader: ReaderView, query: Query) -> None:
    +    oracle = score_query(reader, query)
    +    actual = dict(iter_scored_docs(reader, query))
    +    assert actual.keys() == oracle.keys()
    +    assert actual == pytest.approx(oracle)
    +
    +
    +def test_daat_matches_set_oracle_for_seeded_random_corpora_and_queries():
    +    rng = random.Random(0xDAA7)
    +    for _ in range(CORPUS_COUNT):
    +        documents = tuple(
    +            " ".join(
    +                rng.choice(VOCABULARY)
    +                for _ in range(rng.randint(0, 10))
    +            )
    +            for _ in range(rng.randint(0, 12))
    +        )
    +        reader = build_reader(documents)
    +        for _ in range(QUERIES_PER_CORPUS):
    +            assert_stream_matches_oracle(reader, random_query(rng))
    +
    +
    +@pytest.mark.parametrize(
    +    "query",
    +    [
    +        TermQuery("body", "missing"),
    +        MatchAllQuery(),
    +        BooleanQuery(
    +            (
    +                BooleanClause(
    +                    Occur.MUST_NOT, TermQuery("body", "alpha")
    +                ),
    +            )
    +        ),
    +        BooleanQuery(
    +            (
    +                BooleanClause(Occur.MUST, TermQuery("body", "alpha")),
    +                BooleanClause(
    +                    Occur.SHOULD, TermQuery("body", "beta")
    +                ),
    +                BooleanClause(
    +                    Occur.MUST_NOT, TermQuery("body", "gamma")
    +                ),
    +            )
    +        ),
    +    ],
    +)
    +def test_daat_fixed_boolean_edges_match_oracle(query: Query):
    +    reader = build_reader(
    +        ("alpha", "alpha beta", "alpha gamma", "beta", "")
    +    )
    +    assert_stream_matches_oracle(reader, query)
    +
    +
    +def test_daat_matches_oracle_across_segments_and_live_doc_masks():
    +    schema = Schema(body=TextField(stored=True))
    +    segments = []
    +    for generation, documents in enumerate(
    +        (
    +            ("alpha beta", "alpha gamma", "beta"),
    +            ("alpha alpha", "alpha beta gamma", "delta"),
    +        ),
    +        start=1,
    +    ):
    +        builder = RamIndexBuilder(schema)
    +        for document in documents:
    +            builder.add_document({"body": document})
    +        segments.append(builder.freeze(generation=generation))
    +    reader = ReaderView(
    +        schema,
    +        tuple(segments),
    +        (frozenset({0, 2}), frozenset({0, 1, 2})),
    +    )
    +    query = BooleanQuery(
    +        (
    +            BooleanClause(Occur.MUST, TermQuery("body", "alpha")),
    +            BooleanClause(Occur.SHOULD, TermQuery("body", "beta")),
    +            BooleanClause(
    +                Occur.MUST_NOT, TermQuery("body", "gamma")
    +            ),
    +        )
    +    )
    +    assert_stream_matches_oracle(reader, query)
    +
    +
    +def test_boolean_score_addition_preserves_original_clause_order_exactly():
    +    class UnitSimilarity:
    +        def term_score(self, **_kwargs):
    +            return 1.0
    +
    +    schema = Schema(
    +        small_a=TextField(stored=True),
    +        small_b=TextField(stored=True),
    +        huge=TextField(stored=True, boost=1e16),
    +    )
    +    builder = RamIndexBuilder(schema)
    +    builder.add_document(
    +        {"small_a": "a", "small_b": "", "huge": "required"}
    +    )
    +    builder.add_document(
    +        {"small_a": "a", "small_b": "b", "huge": "required"}
    +    )
    +    reader = ReaderView(schema, (builder.freeze(generation=1),))
    +    query = BooleanQuery(
    +        (
    +            BooleanClause(
    +                Occur.SHOULD, TermQuery("small_a", "a")
    +            ),
    +            BooleanClause(
    +                Occur.SHOULD, TermQuery("small_b", "b")
    +            ),
    +            BooleanClause(
    +                Occur.MUST, TermQuery("huge", "required")
    +            ),
    +        )
    +    )
    +
    +    oracle = score_query(reader, query, UnitSimilarity())
    +    actual = dict(iter_scored_docs(reader, query, UnitSimilarity()))
    +
    +    assert actual == oracle
    +    assert oracle[1] > oracle[0]
    +
    +
    +@pytest.mark.parametrize(
    +    "query",
    +    [
    +        PhraseQuery("body", ("alpha", "beta")),
    +        PrefixQuery("body", "al"),
    +        BooleanQuery(
    +            (
    +                BooleanClause(
    +                    Occur.MUST,
    +                    PhraseQuery("body", ("alpha", "beta")),
    +                ),
    +                BooleanClause(
    +                    Occur.SHOULD, TermQuery("body", "gamma")
    +                ),
    +            )
    +        ),
    +    ],
    +)
    +def test_unmigrated_leaf_falls_back_for_the_entire_tree(query: Query):
    +    reader = build_reader(("alpha beta", "alpha x beta", "gamma"))
    +    assert_stream_matches_oracle(reader, query)
    ```

**What this test locks**

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

**How it constructs the counterexample**

Differential tests generate nested boolean queries and require DAAT hits and scores to equal the existing set-based oracle, including fallback cases.

**Key test statement**

```python
assert results.total_hits == 10
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

**What a failure means**

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

??? note "File diff: tests/unit/search/test_iterators.py"
    ```diff
    diff --git a/tests/unit/search/test_iterators.py b/tests/unit/search/test_iterators.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..a29f828140218a80e1dfa134398c1007b0a06fcc
    --- /dev/null
    +++ b/tests/unit/search/test_iterators.py
    @@ -0,0 +1,123 @@
    +import pytest
    +
    +from minilucene.index.postings import Posting
    +from minilucene.search.iterators import (
    +    NO_MORE_DOCS,
    +    UNPOSITIONED,
    +    ConjunctionIterator,
    +    DisjunctionIterator,
    +    LiveDocsIterator,
    +    PostingsIterator,
    +    ReqExclIterator,
    +)
    +
    +
    +def postings(*doc_ids: int) -> tuple[Posting, ...]:
    +    return tuple(Posting(doc_id, 1, (0,)) for doc_id in doc_ids)
    +
    +
    +def drain(iterator) -> list[int]:
    +    result = []
    +    while (doc_id := iterator.next()) != NO_MORE_DOCS:
    +        result.append(doc_id)
    +    return result
    +
    +
    +def test_postings_iterator_empty_and_exhausted_states_are_stable():
    +    iterator = PostingsIterator(())
    +    assert iterator.doc() == UNPOSITIONED
    +    assert iterator.next() == NO_MORE_DOCS
    +    assert iterator.doc() == NO_MORE_DOCS
    +    assert iterator.next() == NO_MORE_DOCS
    +    assert iterator.advance(100) == NO_MORE_DOCS
    +
    +
    +def test_postings_iterator_singleton_and_advance_land_on_first_gte_target():
    +    singleton = PostingsIterator(postings(7))
    +    assert singleton.advance(7) == 7
    +    assert singleton.posting.term_frequency == 1
    +    assert singleton.next() == NO_MORE_DOCS
    +
    +    iterator = PostingsIterator(postings(1, 4, 9, 15))
    +    assert iterator.advance(-1) == 1
    +    assert iterator.advance(4) == 4
    +    assert iterator.advance(5) == 9
    +    assert iterator.advance(30) == NO_MORE_DOCS
    +
    +
    +def test_postings_iterator_rejects_non_increasing_doc_ids():
    +    with pytest.raises(ValueError, match="strictly increasing"):
    +        PostingsIterator(postings(2, 2))
    +
    +
    +@pytest.mark.parametrize("doc_id", [-1, NO_MORE_DOCS])
    +def test_postings_iterator_rejects_reserved_doc_ids(doc_id):
    +    with pytest.raises(ValueError, match="document range"):
    +        PostingsIterator(postings(doc_id))
    +
    +
    +def test_live_docs_iterator_scans_existing_mask_without_posting_objects():
    +    iterator = LiveDocsIterator(8, frozenset({1, 4, 7}))
    +    assert iterator.advance(-1) == 1
    +    assert iterator.advance(3) == 4
    +    assert iterator.next() == 7
    +    assert iterator.next() == NO_MORE_DOCS
    +
    +
    +def test_conjunction_iterator_zipper_aligns_all_children():
    +    iterator = ConjunctionIterator(
    +        (
    +            PostingsIterator(postings(1, 3, 5, 9, 12)),
    +            PostingsIterator(postings(0, 3, 4, 9, 11, 12)),
    +            PostingsIterator(postings(3, 8, 9, 12)),
    +        )
    +    )
    +    assert iterator.advance(4) == 9
    +    assert iterator.next() == 12
    +    assert iterator.next() == NO_MORE_DOCS
    +
    +
    +def test_conjunction_iterator_with_empty_child_is_empty():
    +    iterator = ConjunctionIterator(
    +        (PostingsIterator(postings(1)), PostingsIterator(()))
    +    )
    +    assert drain(iterator) == []
    +
    +
    +def test_disjunction_iterator_heap_merges_and_deduplicates():
    +    iterator = DisjunctionIterator(
    +        (
    +            PostingsIterator(postings(1, 5, 9)),
    +            PostingsIterator(postings(2, 5, 8)),
    +            PostingsIterator(postings(5, 10)),
    +        )
    +    )
    +    assert drain(iterator) == [1, 2, 5, 8, 9, 10]
    +
    +
    +def test_disjunction_iterator_advance_rebuilds_heap_at_target():
    +    iterator = DisjunctionIterator(
    +        (
    +            PostingsIterator(postings(1, 5, 9)),
    +            PostingsIterator(postings(2, 6, 8)),
    +        )
    +    )
    +    assert iterator.advance(6) == 6
    +    assert drain(iterator) == [8, 9]
    +
    +
    +def test_req_excl_iterator_filters_prohibited_docs():
    +    iterator = ReqExclIterator(
    +        PostingsIterator(postings(1, 2, 4, 7, 9)),
    +        PostingsIterator(postings(0, 2, 3, 7, 10)),
    +    )
    +    assert drain(iterator) == [1, 4, 9]
    +
    +
    +def test_req_excl_iterator_supports_advance():
    +    iterator = ReqExclIterator(
    +        PostingsIterator(postings(1, 4, 7, 9)),
    +        PostingsIterator(postings(4, 8)),
    +    )
    +    assert iterator.advance(4) == 7
    +    assert iterator.next() == 9
    ```

**What this test locks**

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

**How it constructs the counterexample**

Differential tests generate nested boolean queries and require DAAT hits and scores to equal the existing set-based oracle, including fallback cases.

**Key test statement**

```python
assert results.total_hits == 10
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

**What a failure means**

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

??? note "File diff: tests/unit/search/test_topk.py"
    ```diff
    diff --git a/tests/unit/search/test_topk.py b/tests/unit/search/test_topk.py
    index 9c53fd5f91701a3e561a42d4b158d37084702ae2..ef5f5dd78259d0c5d5780aa2e08bbfd947a19c34 100644
    --- a/tests/unit/search/test_topk.py
    +++ b/tests/unit/search/test_topk.py
    @@ -37,3 +37,28 @@ def test_zero_topk_counts_hits_without_retaining_them():
         assert result.total_hits == 1
         assert result.hits == ()
         assert collector.max_retained == 0
    +
    +
    +def test_collector_retains_lightweight_snapshot_doc_ids():
    +    collector = TopKCollector(2)
    +    collector.collect(1.0, 2, 4, doc_id=10)
    +    collector.collect(3.0, 3, 1, doc_id=20)
    +    collector.collect(2.0, 3, 2, doc_id=21)
    +    assert [
    +        (candidate.doc_id, candidate.score)
    +        for candidate in collector.top_candidates()
    +    ] == [(20, 3.0), (21, 2.0)]
    +
    +
    +def test_collector_keeps_direct_materialized_hit_compatibility():
    +    collector = TopKCollector(1)
    +    collector.collect(
    +        2.0,
    +        1,
    +        3,
    +        {"body": "term"},
    +        {"body": "<em>term</em>"},
    +    )
    +    hit = collector.top_docs().hits[0]
    +    assert hit.stored_fields == {"body": "term"}
    +    assert hit.highlights == {"body": "<em>term</em>"}
    ```

**What this test locks**

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

**How it constructs the counterexample**

Differential tests generate nested boolean queries and require DAAT hits and scores to equal the existing set-based oracle, including fallback cases.

**Key test statement**

```python
assert results.total_hits == 10
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

**What a failure means**

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

A doc iterator exposes current doc ID and monotonic advance; conjunction aligns cursors, disjunction heap-merges them, exclusion filters a required stream, and streaming scorers retain BM25 evidence.

### Why this mechanism is necessary

Materializing full result sets for every query node hides streaming behavior and scales with all matches before Top-K can discard most of them. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

The planner builds iterator/scorer trees from rewritten queries, collectors consume candidates without stored fields, and a second phase fetches only winners.

### Mechanism blocks

#### Document-at-a-time execution mechanism

The planner builds iterator/scorer trees from rewritten queries, collectors consume candidates without stored fields, and a second phase fetches only winners.

??? note "File diff: src/minilucene/search/collector.py"
    ```diff
    diff --git a/src/minilucene/search/collector.py b/src/minilucene/search/collector.py
    index 3e1746cc5605d12246dbd82b531b7e74af5324ff..1399c9a2f67bf26d3659b0ba6b93123e1bc6d28d 100644
    --- a/src/minilucene/search/collector.py
    +++ b/src/minilucene/search/collector.py
    @@ -22,6 +22,18 @@ class TopDocs:
         hits: tuple[SearchHit, ...]


    +@dataclass(frozen=True, slots=True)
    +class CollectedDoc:
    +    """Lightweight first-phase winner retained before stored-field fetch."""
    +
    +    doc_id: int
    +    score: float
    +    segment_generation: int
    +    local_doc_id: int
    +    stored_fields: Mapping[str, str] | None = None
    +    highlights: Mapping[str, str] | None = None
    +
    +
     class TopKCollector:
         def __init__(self, top_k: int) -> None:
             if not isinstance(top_k, int) or top_k < 0:
    @@ -30,7 +42,7 @@ class TopKCollector:
             self.total_hits = 0
             self.max_retained = 0
             self._heap: list[
    -            tuple[tuple[float, int, int], SearchHit]
    +            tuple[tuple[float, int, int], CollectedDoc]
             ] = []

         def collect(
    @@ -40,36 +52,63 @@ class TopKCollector:
             local_doc_id: int,
             stored_fields: Mapping[str, str] | None = None,
             highlights: Mapping[str, str] | None = None,
    +        *,
    +        doc_id: int | None = None,
         ) -> None:
             if not math.isfinite(score):
                 raise ValueError("collected score must be finite")
             self.total_hits += 1
             if self.top_k == 0:
                 return
    -        hit = SearchHit(
    +        candidate = CollectedDoc(
    +            doc_id=local_doc_id if doc_id is None else doc_id,
                 score=score,
                 segment_generation=segment_generation,
                 local_doc_id=local_doc_id,
    -            stored_fields=MappingProxyType(dict(stored_fields or {})),
    -            highlights=MappingProxyType(dict(highlights or {})),
    +            stored_fields=(
    +                None
    +                if stored_fields is None
    +                else MappingProxyType(dict(stored_fields))
    +            ),
    +            highlights=(
    +                None
    +                if highlights is None
    +                else MappingProxyType(dict(highlights))
    +            ),
             )
             key = (score, -segment_generation, -local_doc_id)
    -        item = (key, hit)
    +        item = (key, candidate)
             if len(self._heap) < self.top_k:
                 heapq.heappush(self._heap, item)
             elif key > self._heap[0][0]:
                 heapq.heapreplace(self._heap, item)
             self.max_retained = max(self.max_retained, len(self._heap))

    +    def top_candidates(self) -> tuple[CollectedDoc, ...]:
    +        return tuple(
    +            sorted(
    +                (candidate for _, candidate in self._heap),
    +                key=lambda candidate: (
    +                    -candidate.score,
    +                    candidate.segment_generation,
    +                    candidate.local_doc_id,
    +                ),
    +            )
    +        )
    +
         def top_docs(self) -> TopDocs:
             hits = tuple(
    -            sorted(
    -                (hit for _, hit in self._heap),
    -                key=lambda hit: (
    -                    -hit.score,
    -                    hit.segment_generation,
    -                    hit.local_doc_id,
    +            SearchHit(
    +                score=candidate.score,
    +                segment_generation=candidate.segment_generation,
    +                local_doc_id=candidate.local_doc_id,
    +                stored_fields=(
    +                    candidate.stored_fields or MappingProxyType({})
    +                ),
    +                highlights=(
    +                    candidate.highlights or MappingProxyType({})
                     ),
                 )
    +            for candidate in self.top_candidates()
             )
             return TopDocs(total_hits=self.total_hits, hits=hits)
    ```

??? note "File diff: src/minilucene/search/iterators.py"
    ```diff
    diff --git a/src/minilucene/search/iterators.py b/src/minilucene/search/iterators.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..3722752a8064d0cfe3c7444c1e0dd81b299a5fa4
    --- /dev/null
    +++ b/src/minilucene/search/iterators.py
    @@ -0,0 +1,273 @@
    +"""Ordered document-ID cursors used by MiniLucene's DAAT query path."""
    +
    +import heapq
    +from collections.abc import Sequence
    +from collections.abc import Set as AbstractSet
    +from typing import Protocol
    +
    +from minilucene.index.postings import Posting
    +
    +UNPOSITIONED = -1
    +NO_MORE_DOCS = (1 << 63) - 1
    +
    +
    +class DocIdIterator(Protocol):
    +    """The small ``DocIdSetIterator``-like contract used by composites."""
    +
    +    def doc(self) -> int: ...
    +
    +    def next(self) -> int: ...
    +
    +    def advance(self, target: int) -> int: ...
    +
    +
    +class PostingsIterator:
    +    """Cursor over one term's postings, analogous to Lucene ``PostingsEnum``.
    +
    +    DAAT execution keeps only a position in the ordered posting list instead
    +    of materializing every matching document in a set. ``advance(target)``
    +    lands on the first doc ID greater than or equal to ``target``. This
    +    educational codec stores no skip data, so advance is deliberately linear;
    +    real Lucene posting formats use skip lists and block structures to jump.
    +    """
    +
    +    def __init__(self, postings: Sequence[Posting]) -> None:
    +        self._postings = tuple(postings)
    +        if any(
    +            posting.doc_id < 0 or posting.doc_id >= NO_MORE_DOCS
    +            for posting in self._postings
    +        ):
    +            raise ValueError("posting doc ID outside document range")
    +        if any(
    +            left.doc_id >= right.doc_id
    +            for left, right in zip(
    +                self._postings, self._postings[1:], strict=False
    +            )
    +        ):
    +            raise ValueError("posting doc IDs must be strictly increasing")
    +        self._index = -1
    +        self._doc = UNPOSITIONED
    +
    +    @property
    +    def posting(self) -> Posting:
    +        if self._doc in (UNPOSITIONED, NO_MORE_DOCS):
    +            raise RuntimeError("postings iterator is not on a document")
    +        return self._postings[self._index]
    +
    +    def doc(self) -> int:
    +        return self._doc
    +
    +    def next(self) -> int:
    +        if self._doc == NO_MORE_DOCS:
    +            return NO_MORE_DOCS
    +        self._index += 1
    +        if self._index >= len(self._postings):
    +            self._doc = NO_MORE_DOCS
    +        else:
    +            self._doc = self._postings[self._index].doc_id
    +        return self._doc
    +
    +    def advance(self, target: int) -> int:
    +        if self._doc == NO_MORE_DOCS:
    +            return NO_MORE_DOCS
    +        if self._doc != UNPOSITIONED and self._doc >= target:
    +            return self._doc
    +        while self.next() < target:
    +            pass
    +        return self._doc
    +
    +
    +class LiveDocsIterator:
    +    """Scan an existing live-doc mask as Lucene match-all scorers scan bits.
    +
    +    The reader already owns the live-doc set, so this cursor keeps only one
    +    integer position and performs no per-query copy or synthetic posting
    +    allocation. Like the educational postings cursor, advance is linear.
    +    """
    +
    +    def __init__(
    +        self, max_doc: int, live_doc_ids: AbstractSet[int]
    +    ) -> None:
    +        if max_doc < 0 or any(
    +            doc_id < 0 or doc_id >= max_doc for doc_id in live_doc_ids
    +        ):
    +            raise ValueError("live doc ID outside document range")
    +        self._max_doc = max_doc
    +        self._live_doc_ids = live_doc_ids
    +        self._doc = UNPOSITIONED
    +
    +    def doc(self) -> int:
    +        return self._doc
    +
    +    def _scan(self, candidate: int) -> int:
    +        while (
    +            candidate < self._max_doc
    +            and candidate not in self._live_doc_ids
    +        ):
    +            candidate += 1
    +        self._doc = (
    +            candidate if candidate < self._max_doc else NO_MORE_DOCS
    +        )
    +        return self._doc
    +
    +    def next(self) -> int:
    +        if self._doc == NO_MORE_DOCS:
    +            return NO_MORE_DOCS
    +        return self._scan(0 if self._doc == UNPOSITIONED else self._doc + 1)
    +
    +    def advance(self, target: int) -> int:
    +        if self._doc == NO_MORE_DOCS:
    +            return NO_MORE_DOCS
    +        if self._doc != UNPOSITIONED and self._doc >= target:
    +            return self._doc
    +        return self._scan(max(0, target))
    +
    +
    +class ConjunctionIterator:
    +    """Zipper-align required cursors like Lucene ``ConjunctionDISI``.
    +
    +    A conjunction never owns a complete intersection. It advances the lagging
    +    child to the current leader; if that child overshoots, the new doc ID
    +    becomes the leader and alignment restarts. A document is emitted only when
    +    every child is positioned on that same ID.
    +    """
    +
    +    def __init__(self, children: Sequence[DocIdIterator]) -> None:
    +        self.children = tuple(children)
    +        self._doc = UNPOSITIONED
    +
    +    def doc(self) -> int:
    +        return self._doc
    +
    +    def _align(self, target: int) -> int:
    +        if not self.children or target == NO_MORE_DOCS:
    +            self._doc = NO_MORE_DOCS
    +            return self._doc
    +        while target != NO_MORE_DOCS:
    +            aligned = True
    +            for child in self.children[1:]:
    +                candidate = child.advance(target)
    +                if candidate == NO_MORE_DOCS:
    +                    self._doc = NO_MORE_DOCS
    +                    return self._doc
    +                if candidate > target:
    +                    target = self.children[0].advance(candidate)
    +                    aligned = False
    +                    break
    +            if aligned:
    +                self._doc = target
    +                return self._doc
    +        self._doc = NO_MORE_DOCS
    +        return self._doc
    +
    +    def next(self) -> int:
    +        if self._doc == NO_MORE_DOCS:
    +            return NO_MORE_DOCS
    +        if not self.children:
    +            self._doc = NO_MORE_DOCS
    +            return self._doc
    +        return self._align(self.children[0].next())
    +
    +    def advance(self, target: int) -> int:
    +        if self._doc == NO_MORE_DOCS:
    +            return NO_MORE_DOCS
    +        if self._doc != UNPOSITIONED and self._doc >= target:
    +            return self._doc
    +        if not self.children:
    +            self._doc = NO_MORE_DOCS
    +            return self._doc
    +        return self._align(self.children[0].advance(target))
    +
    +
    +class DisjunctionIterator:
    +    """Minimum-heap union like Lucene ``DisjunctionDISIApproximation``.
    +
    +    The heap contains one current doc ID per non-exhausted child. Equal IDs
    +    are emitted once; all children on that ID advance together on the next
    +    call. This bounds merge state by the number of clauses rather than the
    +    number of matching documents.
    +    """
    +
    +    def __init__(self, children: Sequence[DocIdIterator]) -> None:
    +        self.children = tuple(children)
    +        self._heap: list[tuple[int, int]] = []
    +        self._doc = UNPOSITIONED
    +
    +    def doc(self) -> int:
    +        return self._doc
    +
    +    def _push(self, child_index: int, doc_id: int) -> None:
    +        if doc_id != NO_MORE_DOCS:
    +            heapq.heappush(self._heap, (doc_id, child_index))
    +
    +    def _initialize(self, target: int | None = None) -> int:
    +        for index, child in enumerate(self.children):
    +            doc_id = child.next() if target is None else child.advance(target)
    +            self._push(index, doc_id)
    +        self._doc = self._heap[0][0] if self._heap else NO_MORE_DOCS
    +        return self._doc
    +
    +    def next(self) -> int:
    +        if self._doc == NO_MORE_DOCS:
    +            return NO_MORE_DOCS
    +        if self._doc == UNPOSITIONED:
    +            return self._initialize()
    +        current = self._doc
    +        while self._heap and self._heap[0][0] == current:
    +            _, index = heapq.heappop(self._heap)
    +            self._push(index, self.children[index].next())
    +        self._doc = self._heap[0][0] if self._heap else NO_MORE_DOCS
    +        return self._doc
    +
    +    def advance(self, target: int) -> int:
    +        if self._doc == NO_MORE_DOCS:
    +            return NO_MORE_DOCS
    +        if self._doc != UNPOSITIONED and self._doc >= target:
    +            return self._doc
    +        if self._doc == UNPOSITIONED:
    +            return self._initialize(target)
    +        while self._heap and self._heap[0][0] < target:
    +            _, index = heapq.heappop(self._heap)
    +            self._push(index, self.children[index].advance(target))
    +        self._doc = self._heap[0][0] if self._heap else NO_MORE_DOCS
    +        return self._doc
    +
    +
    +class ReqExclIterator:
    +    """Filter a required stream with a prohibited stream like ``ReqExclScorer``.
    +
    +    The excluded cursor is advanced only as far as the current required doc.
    +    A required candidate is emitted unless the prohibited cursor lands on the
    +    same ID, implementing MUST_NOT without building a subtraction set.
    +    """
    +
    +    def __init__(
    +        self, required: DocIdIterator, excluded: DocIdIterator
    +    ) -> None:
    +        self.required = required
    +        self.excluded = excluded
    +        self._doc = UNPOSITIONED
    +
    +    def doc(self) -> int:
    +        return self._doc
    +
    +    def _accept(self, candidate: int) -> int:
    +        while candidate != NO_MORE_DOCS:
    +            if self.excluded.advance(candidate) != candidate:
    +                self._doc = candidate
    +                return self._doc
    +            candidate = self.required.next()
    +        self._doc = NO_MORE_DOCS
    +        return self._doc
    +
    +    def next(self) -> int:
    +        if self._doc == NO_MORE_DOCS:
    +            return NO_MORE_DOCS
    +        return self._accept(self.required.next())
    +
    +    def advance(self, target: int) -> int:
    +        if self._doc == NO_MORE_DOCS:
    +            return NO_MORE_DOCS
    +        if self._doc != UNPOSITIONED and self._doc >= target:
    +            return self._doc
    +        return self._accept(self.required.advance(target))
    ```

??? note "File diff: src/minilucene/search/scorer.py"
    ```diff
    diff --git a/src/minilucene/search/scorer.py b/src/minilucene/search/scorer.py
    index f56cf9473c99a6be16e4d878dcc40cdf8e2fb053..7585dee044f9c6149aeff62647338746fd80e212 100644
    --- a/src/minilucene/search/scorer.py
    +++ b/src/minilucene/search/scorer.py
    @@ -1,3 +1,6 @@
    +from collections.abc import Iterator
    +from typing import Protocol
    +
     from minilucene.query.match import match_query
     from minilucene.query.model import (
         BooleanQuery,
    @@ -9,6 +12,15 @@ from minilucene.query.model import (
         TermQuery,
     )
     from minilucene.search.bm25 import BM25
    +from minilucene.search.iterators import (
    +    NO_MORE_DOCS,
    +    ConjunctionIterator,
    +    DisjunctionIterator,
    +    DocIdIterator,
    +    LiveDocsIterator,
    +    PostingsIterator,
    +    ReqExclIterator,
    +)
     from minilucene.search.reader import ReaderView


    @@ -90,3 +102,181 @@ def score_query(
                     )
                 return scores
         return {}
    +
    +
    +class _Scorer(DocIdIterator, Protocol):
    +    def score(self) -> float: ...
    +
    +
    +class _TermScorer:
    +    def __init__(
    +        self, reader: ReaderView, query: TermQuery, bm25: BM25
    +    ) -> None:
    +        self._iterator = PostingsIterator(
    +            reader.postings(query.field, query.term)
    +        )
    +        self._reader = reader
    +        self._field = query.field
    +        self._boost = reader.schema[query.field].boost
    +        stats = reader.corpus_stats
    +        self._df = stats.doc_frequency(query.field, query.term)
    +        self._n = stats.live_doc_count
    +        self._average_length = stats.average_length(query.field)
    +        self._bm25 = bm25
    +
    +    def doc(self) -> int:
    +        return self._iterator.doc()
    +
    +    def next(self) -> int:
    +        return self._iterator.next()
    +
    +    def advance(self, target: int) -> int:
    +        return self._iterator.advance(target)
    +
    +    def score(self) -> float:
    +        posting = self._iterator.posting
    +        return self._boost * self._bm25.term_score(
    +            tf=posting.term_frequency,
    +            df=self._df,
    +            n=self._n,
    +            dl=self._reader.field_length(self._field, posting.doc_id),
    +            avgdl=self._average_length,
    +        )
    +
    +
    +class _MatchAllScorer:
    +    def __init__(self, reader: ReaderView) -> None:
    +        self._iterator = LiveDocsIterator(
    +            reader.max_doc, reader.live_doc_ids
    +        )
    +
    +    def doc(self) -> int:
    +        return self._iterator.doc()
    +
    +    def next(self) -> int:
    +        return self._iterator.next()
    +
    +    def advance(self, target: int) -> int:
    +        return self._iterator.advance(target)
    +
    +    def score(self) -> float:
    +        return 0.0
    +
    +
    +class _BooleanScorer:
    +    def __init__(
    +        self,
    +        must: tuple[_Scorer, ...],
    +        should: tuple[_Scorer, ...],
    +        prohibited: tuple[_Scorer, ...],
    +        scoring_children: tuple[_Scorer, ...],
    +    ) -> None:
    +        if must:
    +            positive: DocIdIterator = (
    +                must[0]
    +                if len(must) == 1
    +                else ConjunctionIterator(must)
    +            )
    +        elif should:
    +            positive = (
    +                should[0]
    +                if len(should) == 1
    +                else DisjunctionIterator(should)
    +            )
    +        else:
    +            positive = DisjunctionIterator(())
    +
    +        if prohibited:
    +            excluded: DocIdIterator = (
    +                prohibited[0]
    +                if len(prohibited) == 1
    +                else DisjunctionIterator(prohibited)
    +            )
    +            positive = ReqExclIterator(positive, excluded)
    +
    +        self._iterator = positive
    +        self._scoring_children = scoring_children
    +
    +    def doc(self) -> int:
    +        return self._iterator.doc()
    +
    +    def next(self) -> int:
    +        return self._iterator.next()
    +
    +    def advance(self, target: int) -> int:
    +        return self._iterator.advance(target)
    +
    +    def score(self) -> float:
    +        doc_id = self.doc()
    +        total = 0.0
    +        for child in self._scoring_children:
    +            if child.doc() < doc_id:
    +                child.advance(doc_id)
    +            if child.doc() == doc_id:
    +                total += child.score()
    +        return total
    +
    +
    +def _compile_scorer(
    +    reader: ReaderView, query: Query, bm25: BM25
    +) -> _Scorer | None:
    +    match query:
    +        case TermQuery():
    +            return _TermScorer(reader, query, bm25)
    +        case MatchAllQuery():
    +            return _MatchAllScorer(reader)
    +        case BooleanQuery(clauses):
    +            compiled: list[tuple[Occur, _Scorer]] = []
    +            for clause in clauses:
    +                child = _compile_scorer(reader, clause.query, bm25)
    +                if child is None:
    +                    return None
    +                compiled.append((clause.occur, child))
    +            return _BooleanScorer(
    +                tuple(
    +                    child
    +                    for occur, child in compiled
    +                    if occur is Occur.MUST
    +                ),
    +                tuple(
    +                    child
    +                    for occur, child in compiled
    +                    if occur is Occur.SHOULD
    +                ),
    +                tuple(
    +                    child
    +                    for occur, child in compiled
    +                    if occur is Occur.MUST_NOT
    +                ),
    +                tuple(
    +                    child
    +                    for occur, child in compiled
    +                    if occur is not Occur.MUST_NOT
    +                ),
    +            )
    +        case PhraseQuery() | PrefixQuery():
    +            return None
    +    return None
    +
    +
    +def iter_scored_docs(
    +    reader: ReaderView, query: Query, bm25: BM25 | None = None
    +) -> Iterator[tuple[int, float]]:
    +    """Yield ``(doc_id, score)`` in doc-ID order without full result maps.
    +
    +    Term, match-all, and Boolean trees compile to DAAT scorer cursors. If any
    +    leaf is not migrated, the entire tree falls back to ``score_query`` so a
    +    mixed execution plan cannot change matching or BM25 semantics. Phrase
    +    queries currently fall back; unrevised prefix queries do too, while the
    +    normal searcher rewrite turns prefixes into supported term/Boolean trees.
    +    """
    +
    +    similarity = bm25 or BM25()
    +    scorer = _compile_scorer(reader, query, similarity)
    +    if scorer is None:
    +        scores = score_query(reader, query, similarity)
    +        for doc_id in sorted(scores):
    +            yield doc_id, scores[doc_id]
    +        return
    +    while (doc_id := scorer.next()) != NO_MORE_DOCS:
    +        yield doc_id, scorer.score()
    ```

??? note "File diff: src/minilucene/search/searcher.py"
    ```diff
    diff --git a/src/minilucene/search/searcher.py b/src/minilucene/search/searcher.py
    index 67cfa2665774671fcc97610feb58fa62cf80cefa..8b087423d738acfc723d000fe01b959d6df2b85a 100644
    --- a/src/minilucene/search/searcher.py
    +++ b/src/minilucene/search/searcher.py
    @@ -1,3 +1,5 @@
    +from types import MappingProxyType
    +
     from minilucene.highlight import (
         highlight_document,
         validate_highlight_fields,
    @@ -5,9 +7,9 @@ from minilucene.highlight import (
     from minilucene.query.model import Query
     from minilucene.query_parser import parse_query
     from minilucene.search.bm25 import BM25
    -from minilucene.search.collector import TopDocs, TopKCollector
    +from minilucene.search.collector import SearchHit, TopDocs, TopKCollector
     from minilucene.search.reader import ReaderView
    -from minilucene.search.scorer import score_query
    +from minilucene.search.scorer import iter_scored_docs


     class IndexSearcher:
    @@ -27,21 +29,33 @@ class IndexSearcher:
             validate_highlight_fields(self.reader.schema, highlight_fields)
             rewritten = self.reader.rewrite(query)
             collector = TopKCollector(top_k)
    -        for doc_id, score in score_query(
    +        for doc_id, score in iter_scored_docs(
                 self.reader, rewritten, self.similarity
    -        ).items():
    +        ):
                 address = self.reader.address(doc_id)
    -            stored_fields = self.reader.stored_fields(doc_id)
                 collector.collect(
                     score,
                     address.segment_generation,
                     address.local_doc_id,
    -                stored_fields,
    -                highlight_document(
    -                    stored_fields, rewritten, highlight_fields
    -                ),
    +                doc_id=doc_id,
    +            )
    +        hits = []
    +        for candidate in collector.top_candidates():
    +            stored_fields = self.reader.stored_fields(candidate.doc_id)
    +            hits.append(
    +                SearchHit(
    +                    score=candidate.score,
    +                    segment_generation=candidate.segment_generation,
    +                    local_doc_id=candidate.local_doc_id,
    +                    stored_fields=MappingProxyType(dict(stored_fields)),
    +                    highlights=MappingProxyType(
    +                        highlight_document(
    +                            stored_fields, rewritten, highlight_fields
    +                        )
    +                    ),
    +                )
                 )
    -        return collector.top_docs()
    +        return TopDocs(total_hits=collector.total_hits, hits=tuple(hits))

         def search_text(
             self,
    ```

**What it is and why it appears**

A doc iterator exposes current doc ID and monotonic advance; conjunction aligns cursors, disjunction heap-merges them, exclusion filters a required stream, and streaming scorers retain BM25 evidence.

**Runtime role**

The planner builds iterator/scorer trees from rewritten queries, collectors consume candidates without stored fields, and a second phase fetches only winners.

**Statement understanding**

Differential equality makes the old executor an oracle while the new iterator contract changes cost and control flow without silently changing semantics.

#### Package, fixture, and project support

Keep exports, test corpora, dependencies, and the runtime environment reproducible.

??? note "Supporting file diffs (1 file)"
    **`src/minilucene/search/__init__.py`**

    ```diff
    diff --git a/src/minilucene/search/__init__.py b/src/minilucene/search/__init__.py
    index 9a180bb8d02904ac791327e499b73fad1f256551..ee48244bce25e388810775a11683c7f90e36bc7d 100644
    --- a/src/minilucene/search/__init__.py
    +++ b/src/minilucene/search/__init__.py
    @@ -1,12 +1,18 @@
     from minilucene.search.bm25 import BM25
    -from minilucene.search.collector import SearchHit, TopDocs, TopKCollector
    +from minilucene.search.collector import (
    +    CollectedDoc,
    +    SearchHit,
    +    TopDocs,
    +    TopKCollector,
    +)
     from minilucene.search.reader import DocAddress, ReaderView
    -from minilucene.search.scorer import score_query
    +from minilucene.search.scorer import iter_scored_docs, score_query
     from minilucene.search.searcher import IndexSearcher
     from minilucene.search.stats import CorpusStats

     __all__ = [
         "BM25",
    +    "CollectedDoc",
         "CorpusStats",
         "DocAddress",
         "IndexSearcher",
    @@ -14,5 +20,6 @@ __all__ = [
         "SearchHit",
         "TopDocs",
         "TopKCollector",
    +    "iter_scored_docs",
         "score_query",
     ]
    ```


### Verification evidence

Run `uv run pytest -q $(cat journey/stages/30-daat-execution/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Differential equality makes the old executor an oracle while the new iterator contract changes cost and control flow without silently changing semantics.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 11](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/11-daat.md)

[Complete reference patch / 完整参考补丁](https://github.com/system-in-miniature/mini-lucene/blob/main/journey/stages/30-daat-execution/stage.patch)

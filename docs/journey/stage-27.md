# Stage 27 · Deterministic relevance evaluation

### Goal

Build deterministic relevance evaluation and explain its boundary from an executable counterexample, runtime state, and the critical statement.

??? note "Deliverable files"
    - `src/minilucene/evaluation.py`
    - `tests/evaluation/test_metrics.py`
    - `tests/evaluation/test_reference_corpus.py`
    - `tests/fixtures/corpus.json`
    - `tests/fixtures/qrels.json`
    - `tests/fixtures/queries.json`
    - `tests/support/__init__.py`
    - `tests/support/reference_corpus.py`

### The problem at this point

A few hand-inspected hits cannot show whether ranking changes improve or regress a fixed retrieval task.

### Test contract

#### See the failure first

Metric tests cover ties, missing judgments, empty relevant sets, cutoffs, and a frozen corpus with expected per-query results.

??? note "File diff: tests/evaluation/test_metrics.py"
    ```diff
    diff --git a/tests/evaluation/test_metrics.py b/tests/evaluation/test_metrics.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..1872eb9b13cadf210c4cd1cb382c8d294d68918e
    --- /dev/null
    +++ b/tests/evaluation/test_metrics.py
    @@ -0,0 +1,70 @@
    +import math
    +
    +import pytest
    +
    +from minilucene.evaluation import (
    +    mean_reciprocal_rank,
    +    ndcg_at_k,
    +    precision_at_k,
    +    recall_at_k,
    +)
    +
    +
    +def test_binary_metrics():
    +    ranked = ("d1", "d2", "d3")
    +    relevant = {"d2", "d3", "d4"}
    +    assert precision_at_k(ranked, relevant, 2) == 0.5
    +    assert recall_at_k(ranked, relevant, 2) == pytest.approx(1 / 3)
    +    assert mean_reciprocal_rank([ranked], [relevant]) == 0.5
    +
    +
    +def test_ndcg_uses_graded_relevance():
    +    assert ndcg_at_k(("b", "a"), {"a": 3, "b": 1}, 2) < 1.0
    +    assert ndcg_at_k(("a", "b"), {"a": 3, "b": 1}, 2) == 1.0
    +
    +
    +def test_zero_k_and_empty_relevance_are_defined():
    +    assert precision_at_k(("d1",), {"d1"}, 0) == 0.0
    +    assert recall_at_k(("d1",), set(), 10) == 0.0
    +    assert ndcg_at_k(("d1",), {}, 10) == 0.0
    +    assert mean_reciprocal_rank([], []) == 0.0
    +
    +
    +def test_mrr_averages_queries_including_misses():
    +    assert mean_reciprocal_rank(
    +        [("a", "b"), ("c",), ("d", "e")],
    +        [{"b"}, {"missing"}, {"d"}],
    +    ) == pytest.approx((0.5 + 0.0 + 1.0) / 3)
    +
    +
    +@pytest.mark.parametrize(
    +    "operation",
    +    [
    +        lambda: precision_at_k(("d1", "d1"), {"d1"}, 2),
    +        lambda: recall_at_k(("d1", "d1"), {"d1"}, 2),
    +        lambda: ndcg_at_k(("d1", "d1"), {"d1": 1}, 2),
    +        lambda: mean_reciprocal_rank(
    +            [("d1", "d1")], [{"d1"}]
    +        ),
    +    ],
    +)
    +def test_duplicate_ranked_ids_are_rejected(operation):
    +    with pytest.raises(ValueError, match="duplicate"):
    +        operation()
    +
    +
    +@pytest.mark.parametrize("k", [-1, 1.5, True])
    +def test_invalid_k_is_rejected(k):
    +    with pytest.raises(ValueError, match="non-negative integer"):
    +        precision_at_k(("d1",), {"d1"}, k)
    +
    +
    +@pytest.mark.parametrize("grade", [-1, math.inf, math.nan])
    +def test_ndcg_rejects_invalid_grades(grade):
    +    with pytest.raises(ValueError, match="finite and non-negative"):
    +        ndcg_at_k(("d1",), {"d1": grade}, 1)
    +
    +
    +def test_mrr_requires_one_relevance_set_per_query():
    +    with pytest.raises(ValueError, match="same number"):
    +        mean_reciprocal_rank([("a",)], [])
    ```

**What this test locks**

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

**How it constructs the counterexample**

Metric tests cover ties, missing judgments, empty relevant sets, cutoffs, and a frozen corpus with expected per-query results.

**Key test statement**

```python
assert precision_at_k(ranked, relevant, 2) == 0.5
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

**What a failure means**

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

??? note "File diff: tests/evaluation/test_reference_corpus.py"
    ```diff
    diff --git a/tests/evaluation/test_reference_corpus.py b/tests/evaluation/test_reference_corpus.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..ae944fbf0422a000f3161501c913a329cecec97f
    --- /dev/null
    +++ b/tests/evaluation/test_reference_corpus.py
    @@ -0,0 +1,204 @@
    +from pathlib import Path
    +
    +import pytest
    +
    +from minilucene import Index, KeywordField, MemoryIndex, Schema, TextField
    +from minilucene.query import (
    +    BooleanClause,
    +    BooleanQuery,
    +    Occur,
    +    PhraseQuery,
    +    TermQuery,
    +)
    +from minilucene.query_parser import parse_query
    +from tests.support.reference_corpus import load_reference_corpus
    +
    +FIXTURES = Path(__file__).parents[1] / "fixtures"
    +
    +
    +@pytest.fixture
    +def reference():
    +    return load_reference_corpus(FIXTURES)
    +
    +
    +@pytest.fixture
    +def schema():
    +    return Schema(
    +        id=KeywordField(stored=True),
    +        title=TextField(stored=True, boost=2.0),
    +        body=TextField(stored=True),
    +        author=KeywordField(stored=True),
    +    )
    +
    +
    +def _ids(top_docs):
    +    return tuple(hit.stored_fields["id"] for hit in top_docs.hits)
    +
    +
    +def _snapshot(reader, queries):
    +    snapshot = {}
    +    for query in queries:
    +        results = reader.search(
    +            parse_query(
    +                query.text, reader.schema, query.default_field
    +            ),
    +            top_k=10,
    +        )
    +        snapshot[query.id] = (
    +            _ids(results),
    +            tuple(hit.score for hit in results.hits),
    +        )
    +    return snapshot
    +
    +
    +def test_fixture_ids_and_references_are_closed(reference):
    +    document_ids = {document["id"] for document in reference.documents}
    +    query_ids = {query.id for query in reference.queries}
    +    assert len(document_ids) == len(reference.documents)
    +    assert len(query_ids) == len(reference.queries)
    +    assert set(reference.qrels) == query_ids
    +    assert all(
    +        set(grades) <= document_ids
    +        for grades in reference.qrels.values()
    +    )
    +
    +
    +def test_title_boost_changes_order_relative_to_equal_body_matches():
    +    schema = Schema(
    +        id=KeywordField(stored=True),
    +        title=TextField(stored=True, boost=3.0),
    +        body=TextField(stored=True),
    +    )
    +    index = MemoryIndex(schema)
    +    index.add_document(id="title", title="kafka", body="neutral")
    +    index.add_document(id="body", title="neutral", body="kafka")
    +    query = BooleanQuery(
    +        (
    +            BooleanClause(
    +                Occur.SHOULD, TermQuery("title", "kafka")
    +            ),
    +            BooleanClause(
    +                Occur.SHOULD, TermQuery("body", "kafka")
    +            ),
    +        )
    +    )
    +    assert _ids(index.search(query, top_k=2)) == ("title", "body")
    +
    +
    +def test_bm25_term_frequency_saturates_instead_of_growing_linearly():
    +    schema = Schema(
    +        id=KeywordField(stored=True),
    +        body=TextField(stored=True),
    +    )
    +    index = MemoryIndex(schema)
    +    index.add_document(id="five", body="kafka " * 5)
    +    index.add_document(id="hundred", body="kafka " * 100)
    +    results = index.search(TermQuery("body", "kafka"), top_k=2)
    +    scores = {
    +        hit.stored_fields["id"]: hit.score for hit in results.hits
    +    }
    +    assert scores["hundred"] / scores["five"] < 2.0
    +
    +
    +def test_phrase_recall_is_narrower_than_boolean_conjunction():
    +    schema = Schema(
    +        id=KeywordField(stored=True),
    +        body=TextField(stored=True),
    +    )
    +    index = MemoryIndex(schema)
    +    index.add_document(id="adjacent", body="distributed system")
    +    index.add_document(
    +        id="separated",
    +        body="distributed applications improve system",
    +    )
    +    phrase = index.search(
    +        PhraseQuery("body", ("distributed", "system")), top_k=10
    +    )
    +    conjunction = index.search(
    +        BooleanQuery(
    +            (
    +                BooleanClause(
    +                    Occur.MUST,
    +                    TermQuery("body", "distributed"),
    +                ),
    +                BooleanClause(
    +                    Occur.MUST, TermQuery("body", "system")
    +                ),
    +            )
    +        ),
    +        top_k=10,
    +    )
    +    assert _ids(phrase) == ("adjacent",)
    +    assert set(_ids(conjunction)) == {"adjacent", "separated"}
    +
    +
    +def test_deleted_documents_affect_neither_hits_nor_statistics(tmp_path):
    +    schema = Schema(
    +        id=KeywordField(stored=True),
    +        title=TextField(stored=True),
    +        body=TextField(stored=True),
    +        author=KeywordField(stored=True),
    +    )
    +    index = Index.create(tmp_path, schema)
    +    with index.writer() as writer:
    +        writer.add_document(
    +            id="live",
    +            title="live",
    +            body="kafka replicas",
    +            author="a",
    +        )
    +        writer.flush()
    +        writer.add_document(
    +            id="deleted",
    +            title="noise",
    +            body="kafka " * 100,
    +            author="b",
    +        )
    +        writer.commit()
    +    with index.writer() as writer:
    +        assert writer.delete_by_term("id", "deleted") == 1
    +        reader = writer.refresh()
    +    try:
    +        assert reader.corpus_stats.live_doc_count == 1
    +        assert reader.corpus_stats.doc_frequency("body", "kafka") == 1
    +        assert reader.corpus_stats.average_length("body") == 2.0
    +        assert _ids(reader.search(TermQuery("body", "kafka"))) == (
    +            "live",
    +        )
    +    finally:
    +        reader.close()
    +        index.close()
    +
    +
    +def test_rankings_survive_commit_reopen_and_merge(
    +    tmp_path, reference, schema
    +):
    +    index = Index.create(tmp_path, schema)
    +    with index.writer() as writer:
    +        for position, document in enumerate(reference.documents):
    +            writer.add_document(**document)
    +            if position == 1:
    +                writer.flush()
    +        writer.commit()
    +
    +    committed = Index.open(tmp_path)
    +    reader_before = committed.open_reader()
    +    expected = _snapshot(reader_before, reference.queries)
    +    reader_before.close()
    +
    +    with committed.writer() as writer:
    +        assert len(writer.segment_generations) == 2
    +        writer.merge(writer.segment_generations)
    +        writer.commit()
    +    reader_after = Index.open(tmp_path).open_reader()
    +    actual = _snapshot(reader_after, reference.queries)
    +    reader_after.close()
    +    committed.close()
    +    index.close()
    +
    +    assert actual.keys() == expected.keys()
    +    for query_id in expected:
    +        assert actual[query_id][0] == expected[query_id][0]
    +        assert actual[query_id][1] == pytest.approx(
    +            expected[query_id][1]
    +        )
    ```

**What this test locks**

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

**How it constructs the counterexample**

Metric tests cover ties, missing judgments, empty relevant sets, cutoffs, and a frozen corpus with expected per-query results.

**Key test statement**

```python
assert precision_at_k(ranked, relevant, 2) == 0.5
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

**What a failure means**

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

??? note "File diff: tests/support/__init__.py"
    ```diff
    diff --git a/tests/support/__init__.py b/tests/support/__init__.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..a6bfaa6022511cbabf1c379d036c6cc55dcdf8f0
    --- /dev/null
    +++ b/tests/support/__init__.py
    @@ -0,0 +1 @@
    +"""Test-only support helpers."""
    ```

**What this test locks**

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

**How it constructs the counterexample**

Metric tests cover ties, missing judgments, empty relevant sets, cutoffs, and a frozen corpus with expected per-query results.

**Key test statement**

```python
assert precision_at_k(ranked, relevant, 2) == 0.5
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

**What a failure means**

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

??? note "File diff: tests/support/reference_corpus.py"
    ```diff
    diff --git a/tests/support/reference_corpus.py b/tests/support/reference_corpus.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..c32445257f9575a397dc28eb49487849db1803c1
    --- /dev/null
    +++ b/tests/support/reference_corpus.py
    @@ -0,0 +1,117 @@
    +import json
    +from dataclasses import dataclass
    +from pathlib import Path
    +
    +
    +@dataclass(frozen=True, slots=True)
    +class ReferenceQuery:
    +    id: str
    +    text: str
    +    default_field: str
    +
    +
    +@dataclass(frozen=True, slots=True)
    +class ReferenceCorpus:
    +    documents: tuple[dict[str, str], ...]
    +    queries: tuple[ReferenceQuery, ...]
    +    qrels: dict[str, dict[str, int]]
    +
    +
    +def _read_object(path: Path) -> dict[str, object]:
    +    payload = json.loads(
    +        path.read_text(encoding="utf-8", errors="strict")
    +    )
    +    if not isinstance(payload, dict):
    +        raise TypeError(f"fixture must contain an object: {path}")
    +    return payload
    +
    +
    +def load_reference_corpus(directory: Path) -> ReferenceCorpus:
    +    corpus_payload = _read_object(directory / "corpus.json")
    +    queries_payload = _read_object(directory / "queries.json")
    +    qrels_payload = _read_object(directory / "qrels.json")
    +
    +    raw_documents = corpus_payload.get("documents")
    +    raw_queries = queries_payload.get("queries")
    +    raw_qrels = qrels_payload.get("qrels")
    +    if not isinstance(raw_documents, list):
    +        raise TypeError("corpus documents must be a list")
    +    if not isinstance(raw_queries, list):
    +        raise TypeError("queries must be a list")
    +    if not isinstance(raw_qrels, dict):
    +        raise TypeError("qrels must be an object")
    +
    +    documents: list[dict[str, str]] = []
    +    for raw in raw_documents:
    +        if (
    +            not isinstance(raw, dict)
    +            or any(
    +                not isinstance(key, str)
    +                or not isinstance(value, str)
    +                for key, value in raw.items()
    +            )
    +            or not raw.get("id")
    +        ):
    +            raise ValueError("every document requires string fields and id")
    +        documents.append(dict(raw))
    +    if len({document["id"] for document in documents}) != len(
    +        documents
    +    ):
    +        raise ValueError("document IDs must be unique")
    +
    +    queries: list[ReferenceQuery] = []
    +    for raw in raw_queries:
    +        if not isinstance(raw, dict):
    +            raise TypeError("every query must be an object")
    +        try:
    +            query = ReferenceQuery(
    +                id=raw["id"],
    +                text=raw["text"],
    +                default_field=raw["default_field"],
    +            )
    +        except (KeyError, TypeError) as error:
    +            raise ValueError("query fixture is invalid") from error
    +        if any(
    +            not isinstance(value, str) or not value
    +            for value in (
    +                query.id,
    +                query.text,
    +                query.default_field,
    +            )
    +        ):
    +            raise ValueError("query fields must be non-empty strings")
    +        queries.append(query)
    +    if len({query.id for query in queries}) != len(queries):
    +        raise ValueError("query IDs must be unique")
    +
    +    qrels: dict[str, dict[str, int]] = {}
    +    for query_id, raw_grades in raw_qrels.items():
    +        if not isinstance(query_id, str) or not isinstance(
    +            raw_grades, dict
    +        ):
    +            raise TypeError("qrels entries must be objects")
    +        grades: dict[str, int] = {}
    +        for document_id, grade in raw_grades.items():
    +            if (
    +                not isinstance(document_id, str)
    +                or not isinstance(grade, int)
    +                or isinstance(grade, bool)
    +                or grade < 0
    +            ):
    +                raise ValueError(
    +                    "qrel grades must be non-negative integers"
    +                )
    +            grades[document_id] = grade
    +        qrels[query_id] = grades
    +
    +    query_ids = {query.id for query in queries}
    +    document_ids = {document["id"] for document in documents}
    +    if set(qrels) != query_ids:
    +        raise ValueError("qrels must cover every query exactly")
    +    if any(set(grades) - document_ids for grades in qrels.values()):
    +        raise ValueError("qrels reference unknown documents")
    +    return ReferenceCorpus(
    +        documents=tuple(documents),
    +        queries=tuple(queries),
    +        qrels=qrels,
    +    )
    ```

**What this test locks**

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

**How it constructs the counterexample**

Metric tests cover ties, missing judgments, empty relevant sets, cutoffs, and a frozen corpus with expected per-query results.

**Key test statement**

```python
assert precision_at_k(ranked, relevant, 2) == 0.5
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

**What a failure means**

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

Precision, recall, average precision, reciprocal rank, and nDCG are deterministic functions of ranked IDs and qrels; fixtures freeze the evaluation world.

### Why this mechanism is necessary

A few hand-inspected hits cannot show whether ranking changes improve or regress a fixed retrieval task. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

The harness builds the reference index, runs declared queries, computes metrics at fixed cutoffs, and compares stable aggregates.

### Mechanism blocks

#### Deterministic relevance evaluation mechanism

The harness builds the reference index, runs declared queries, computes metrics at fixed cutoffs, and compares stable aggregates.

??? note "File diff: src/minilucene/evaluation.py"
    ```diff
    diff --git a/src/minilucene/evaluation.py b/src/minilucene/evaluation.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..2e95c0d9ee8c5f6ee1e0cc0ea9a6660816ec017c
    --- /dev/null
    +++ b/src/minilucene/evaluation.py
    @@ -0,0 +1,100 @@
    +import math
    +from collections.abc import Hashable, Mapping, Sequence
    +from collections.abc import Set as AbstractSet
    +from numbers import Real
    +
    +
    +def _validate_k(k: int) -> None:
    +    if not isinstance(k, int) or isinstance(k, bool) or k < 0:
    +        raise ValueError("k must be a non-negative integer")
    +
    +
    +def _validate_ranked[T: Hashable](ranked: Sequence[T]) -> None:
    +    if len(set(ranked)) != len(ranked):
    +        raise ValueError("ranked IDs contain a duplicate")
    +
    +
    +def precision_at_k[T: Hashable](
    +    ranked: Sequence[T], relevant: AbstractSet[T], k: int
    +) -> float:
    +    _validate_k(k)
    +    _validate_ranked(ranked)
    +    if k == 0:
    +        return 0.0
    +    return sum(item in relevant for item in ranked[:k]) / k
    +
    +
    +def recall_at_k[T: Hashable](
    +    ranked: Sequence[T], relevant: AbstractSet[T], k: int
    +) -> float:
    +    _validate_k(k)
    +    _validate_ranked(ranked)
    +    if not relevant:
    +        return 0.0
    +    return sum(item in relevant for item in ranked[:k]) / len(relevant)
    +
    +
    +def mean_reciprocal_rank[T: Hashable](
    +    rankings: Sequence[Sequence[T]],
    +    relevant_sets: Sequence[AbstractSet[T]],
    +) -> float:
    +    if len(rankings) != len(relevant_sets):
    +        raise ValueError(
    +            "rankings and relevance sets must have the same number"
    +        )
    +    for ranked in rankings:
    +        _validate_ranked(ranked)
    +    if not rankings:
    +        return 0.0
    +    reciprocal_sum = 0.0
    +    for ranked, relevant in zip(
    +        rankings, relevant_sets, strict=True
    +    ):
    +        reciprocal_sum += next(
    +            (
    +                1.0 / rank
    +                for rank, item in enumerate(ranked, start=1)
    +                if item in relevant
    +            ),
    +            0.0,
    +        )
    +    return reciprocal_sum / len(rankings)
    +
    +
    +def _validate_grades[T: Hashable](
    +    relevance: Mapping[T, Real],
    +) -> None:
    +    for grade in relevance.values():
    +        if (
    +            not isinstance(grade, Real)
    +            or isinstance(grade, bool)
    +            or not math.isfinite(float(grade))
    +            or grade < 0
    +        ):
    +            raise ValueError(
    +                "relevance grades must be finite and non-negative"
    +            )
    +
    +
    +def _dcg(grades: Sequence[Real]) -> float:
    +    return sum(
    +        (2.0 ** float(grade) - 1.0) / math.log2(rank + 1)
    +        for rank, grade in enumerate(grades, start=1)
    +    )
    +
    +
    +def ndcg_at_k[T: Hashable](
    +    ranked: Sequence[T], relevance: Mapping[T, Real], k: int
    +) -> float:
    +    _validate_k(k)
    +    _validate_ranked(ranked)
    +    _validate_grades(relevance)
    +    if k == 0:
    +        return 0.0
    +    actual = _dcg(
    +        tuple(relevance.get(item, 0.0) for item in ranked[:k])
    +    )
    +    ideal = _dcg(
    +        tuple(sorted(relevance.values(), reverse=True)[:k])
    +    )
    +    return 0.0 if ideal == 0.0 else actual / ideal
    ```

**What it is and why it appears**

Precision, recall, average precision, reciprocal rank, and nDCG are deterministic functions of ranked IDs and qrels; fixtures freeze the evaluation world.

**Runtime role**

The harness builds the reference index, runs declared queries, computes metrics at fixed cutoffs, and compares stable aggregates.

**Statement understanding**

Explicit tie ordering and fixed fixtures make a score change observable as evidence rather than an anecdotal ranking impression.

#### Package, fixture, and project support

Keep exports, test corpora, dependencies, and the runtime environment reproducible.

??? note "Supporting file diffs (3 files)"
    **`tests/fixtures/corpus.json`**

    ```diff
    diff --git a/tests/fixtures/corpus.json b/tests/fixtures/corpus.json
    new file mode 100644
    index 0000000000000000000000000000000000000000..0bae23eaf733a91563f4e627d1b15cbf99342091
    --- /dev/null
    +++ b/tests/fixtures/corpus.json
    @@ -0,0 +1,34 @@
    +{
    +  "documents": [
    +    {
    +      "id": "doc-1",
    +      "title": "Understanding Kafka Replication",
    +      "body": "Kafka uses partition leaders and follower replicas.",
    +      "author": "jonah"
    +    },
    +    {
    +      "id": "doc-2",
    +      "title": "RabbitMQ Messaging",
    +      "body": "RabbitMQ routes messages through exchanges and queues.",
    +      "author": "sam"
    +    },
    +    {
    +      "id": "doc-3",
    +      "title": "Distributed Systems",
    +      "body": "Distributed applications improve the system through replication.",
    +      "author": "jonah"
    +    },
    +    {
    +      "id": "doc-4",
    +      "title": "Search Ranking",
    +      "body": "BM25 balances term frequency and document length.",
    +      "author": "lee"
    +    },
    +    {
    +      "id": "doc-5",
    +      "title": "Follower Operations",
    +      "body": "A follower replica can refresh its local snapshot.",
    +      "author": "sam"
    +    }
    +  ]
    +}
    ```

    **`tests/fixtures/qrels.json`**

    ```diff
    diff --git a/tests/fixtures/qrels.json b/tests/fixtures/qrels.json
    new file mode 100644
    index 0000000000000000000000000000000000000000..649ead8c3530c4d00ef85436efb607dffea06334
    --- /dev/null
    +++ b/tests/fixtures/qrels.json
    @@ -0,0 +1,14 @@
    +{
    +  "qrels": {
    +    "q-kafka": {
    +      "doc-1": 3
    +    },
    +    "q-followers": {
    +      "doc-1": 3,
    +      "doc-5": 2
    +    },
    +    "q-ranking": {
    +      "doc-4": 3
    +    }
    +  }
    +}
    ```

    **`tests/fixtures/queries.json`**

    ```diff
    diff --git a/tests/fixtures/queries.json b/tests/fixtures/queries.json
    new file mode 100644
    index 0000000000000000000000000000000000000000..427f1fec146bdf5668341ebceaf08b0b92539704
    --- /dev/null
    +++ b/tests/fixtures/queries.json
    @@ -0,0 +1,19 @@
    +{
    +  "queries": [
    +    {
    +      "id": "q-kafka",
    +      "text": "kafka",
    +      "default_field": "body"
    +    },
    +    {
    +      "id": "q-followers",
    +      "text": "\"follower replicas\" OR \"follower replica\"",
    +      "default_field": "body"
    +    },
    +    {
    +      "id": "q-ranking",
    +      "text": "title:ranking OR body:frequency",
    +      "default_field": "body"
    +    }
    +  ]
    +}
    ```


### Verification evidence

Run `uv run pytest -q $(cat journey/stages/27-relevance-evaluation/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Explicit tie ordering and fixed fixtures make a score change observable as evidence rather than an anecdotal ranking impression.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 8](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/08-scoring.md)

[Complete reference patch / 完整参考补丁](https://github.com/system-in-miniature/mini-lucene/blob/main/journey/stages/27-relevance-evaluation/stage.patch)

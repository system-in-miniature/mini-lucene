# Stage 04 · Closed query matching

### Goal

Build closed query matching and explain its boundary from an executable counterexample, runtime state, and the critical statement.

??? note "Deliverable files"
    - `src/minilucene/query/__init__.py`
    - `src/minilucene/query/match.py`
    - `src/minilucene/query/model.py`
    - `tests/contract/test_query_matching.py`
    - `tests/helpers/__init__.py`
    - `tests/helpers/corpus.py`

### The problem at this point

An index has postings but no explicit language for composing term, phrase, and boolean predicates.

### Test contract

#### See the failure first

The tests build nested AND, OR, NOT, and phrase queries whose positional or set behavior differs under naive evaluation.

??? note "File diff: tests/contract/test_query_matching.py"
    ```diff
    diff --git a/tests/contract/test_query_matching.py b/tests/contract/test_query_matching.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..aeb43bcbe1de3cc0077164861768cc8f780bd287
    --- /dev/null
    +++ b/tests/contract/test_query_matching.py
    @@ -0,0 +1,97 @@
    +import pytest
    +
    +from minilucene.query import (
    +    BooleanClause,
    +    BooleanQuery,
    +    MatchAllQuery,
    +    Occur,
    +    PhraseQuery,
    +    PrefixQuery,
    +    QueryError,
    +    TermQuery,
    +)
    +from tests.helpers.corpus import build_memory_reader
    +
    +
    +def test_phrase_requires_consecutive_positions():
    +    reader = build_memory_reader(
    +        ("distributed system", "distributed applications improve the system")
    +    )
    +    assert reader.match(PhraseQuery("body", ("distributed", "system"))) == {0}
    +
    +
    +def test_phrase_preserves_analyzed_stopword_gap():
    +    reader = build_memory_reader(
    +        ("distributed system", "distributed the system")
    +    )
    +    query = PhraseQuery(
    +        "body",
    +        ("distributed", "system"),
    +        positions=(0, 2),
    +    )
    +    assert reader.match(query) == {1}
    +
    +
    +def test_boolean_and_prefix_have_frozen_set_semantics():
    +    reader = build_memory_reader(
    +        ("kafka replicas", "rabbit replicas", "kafka")
    +    )
    +    query = BooleanQuery(
    +        (
    +            BooleanClause(Occur.MUST, PrefixQuery("body", "kaf")),
    +            BooleanClause(Occur.MUST, TermQuery("body", "replicas")),
    +            BooleanClause(Occur.MUST_NOT, TermQuery("body", "rabbit")),
    +        )
    +    )
    +    assert reader.match(query) == {0}
    +
    +
    +def test_should_is_required_without_must_and_optional_with_must():
    +    reader = build_memory_reader(("kafka", "kafka replicas", "replicas"))
    +    only_should = BooleanQuery(
    +        (
    +            BooleanClause(Occur.SHOULD, TermQuery("body", "kafka")),
    +            BooleanClause(Occur.SHOULD, TermQuery("body", "replicas")),
    +        )
    +    )
    +    with_must = BooleanQuery(
    +        (
    +            BooleanClause(Occur.MUST, TermQuery("body", "kafka")),
    +            BooleanClause(Occur.SHOULD, TermQuery("body", "replicas")),
    +        )
    +    )
    +    assert reader.match(only_should) == {0, 1, 2}
    +    assert reader.match(with_must) == {0, 1}
    +
    +
    +def test_only_must_not_matches_nothing():
    +    reader = build_memory_reader(("kafka", "rabbit"))
    +    query = BooleanQuery(
    +        (BooleanClause(Occur.MUST_NOT, TermQuery("body", "kafka")),)
    +    )
    +    assert reader.match(query) == set()
    +    assert reader.match(MatchAllQuery()) == {0, 1}
    +
    +
    +def test_prefix_expansion_limit_fails_explicitly():
    +    reader = build_memory_reader(("alpha alpine amber",))
    +    reader.max_prefix_expansions = 1
    +    with pytest.raises(QueryError, match="prefix expansion limit"):
    +        reader.match(PrefixQuery("body", "al"))
    +
    +
    +@pytest.mark.parametrize(
    +    "factory",
    +    [
    +        lambda: TermQuery("", "term"),
    +        lambda: PhraseQuery("body", ()),
    +        lambda: PhraseQuery("body", ("a", "b"), positions=(0,)),
    +        lambda: PhraseQuery("body", ("a", "b"), positions=(0, 0)),
    +        lambda: PhraseQuery("body", ("a",), slop=1),
    +        lambda: PrefixQuery("body", ""),
    +        lambda: BooleanQuery(()),
    +    ],
    +)
    +def test_invalid_query_values_are_rejected(factory):
    +    with pytest.raises(QueryError):
    +        factory()
    ```

**What this test locks**

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

**How it constructs the counterexample**

The tests build nested AND, OR, NOT, and phrase queries whose positional or set behavior differs under naive evaluation.

**Key test statement**

```python
assert reader.match(PhraseQuery("body", ("distributed", "system"))) == {0}
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

**What a failure means**

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

??? note "File diff: tests/helpers/__init__.py"
    ```diff
    diff --git a/tests/helpers/__init__.py b/tests/helpers/__init__.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..e87d79e938474bd7a02eea6800444f679a83a9dc
    --- /dev/null
    +++ b/tests/helpers/__init__.py
    @@ -0,0 +1 @@
    +"""Reusable test fixtures that exercise MiniLucene's public contracts."""
    ```

**What this test locks**

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

**How it constructs the counterexample**

The tests build nested AND, OR, NOT, and phrase queries whose positional or set behavior differs under naive evaluation.

**Key test statement**

```python
assert reader.match(PhraseQuery("body", ("distributed", "system"))) == {0}
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

**What a failure means**

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

??? note "File diff: tests/helpers/corpus.py"
    ```diff
    diff --git a/tests/helpers/corpus.py b/tests/helpers/corpus.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..c71d8d795733402ad8f48eac1faa618aecd324cc
    --- /dev/null
    +++ b/tests/helpers/corpus.py
    @@ -0,0 +1,55 @@
    +from minilucene.index.memory import RamIndexBuilder
    +from minilucene.schema import Schema, TextField
    +
    +
    +class SingleSegmentReader:
    +    def __init__(self, segment):
    +        self.segment = segment
    +        self.max_doc = segment.max_doc
    +        self.max_prefix_expansions = 1_024
    +
    +    def postings(self, field, term):
    +        return self.segment.postings.get(field, {}).get(term, ())
    +
    +    def terms_with_prefix(self, field, prefix):
    +        return tuple(
    +            term
    +            for term in self.segment.postings.get(field, {})
    +            if term.startswith(prefix)
    +        )
    +
    +    def has_phrase(self, field, terms, query_positions, doc_id):
    +        positions = []
    +        for term in terms:
    +            posting = next(
    +                (
    +                    item
    +                    for item in self.postings(field, term)
    +                    if item.doc_id == doc_id
    +                ),
    +                None,
    +            )
    +            if posting is None:
    +                return False
    +            positions.append(set(posting.positions))
    +        return any(
    +            all(
    +                start + query_position in term_positions
    +                for query_position, term_positions in zip(
    +                    query_positions, positions, strict=True
    +                )
    +            )
    +            for start in positions[0]
    +        )
    +
    +    def match(self, query):
    +        from minilucene.query.match import match_query
    +
    +        return match_query(self, query)
    +
    +
    +def build_memory_reader(documents):
    +    builder = RamIndexBuilder(Schema(body=TextField(stored=True)))
    +    for document in documents:
    +        builder.add_document({"body": document})
    +    return SingleSegmentReader(builder.freeze(generation=0))
    ```

**What this test locks**

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

**How it constructs the counterexample**

The tests build nested AND, OR, NOT, and phrase queries whose positional or set behavior differs under naive evaluation.

**Key test statement**

```python
assert reader.match(PhraseQuery("body", ("distributed", "system"))) == {0}
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

**What a failure means**

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

A closed AST enumerates supported query forms; matching is a pure operation over a reader snapshot and returns document evidence.

### Why this mechanism is necessary

An index has postings but no explicit language for composing term, phrase, and boolean predicates. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

Leaf queries read postings, phrase matching aligns positions, and boolean nodes combine child results under explicit occurrence rules.

### Mechanism blocks

#### Closed query matching mechanism

Leaf queries read postings, phrase matching aligns positions, and boolean nodes combine child results under explicit occurrence rules.

??? note "File diff: src/minilucene/query/match.py"
    ```diff
    diff --git a/src/minilucene/query/match.py b/src/minilucene/query/match.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..914d4dc16beb10f3ea714a436d5fc72a479db417
    --- /dev/null
    +++ b/src/minilucene/query/match.py
    @@ -0,0 +1,110 @@
    +from collections.abc import Iterable
    +from typing import Protocol
    +
    +from minilucene.index.postings import Posting
    +from minilucene.query.model import (
    +    BooleanClause,
    +    BooleanQuery,
    +    MatchAllQuery,
    +    Occur,
    +    PhraseQuery,
    +    PrefixQuery,
    +    Query,
    +    QueryError,
    +    TermQuery,
    +)
    +
    +
    +class MatchReader(Protocol):
    +    max_doc: int
    +    max_prefix_expansions: int
    +
    +    def postings(self, field: str, term: str) -> Iterable[Posting]: ...
    +
    +    def terms_with_prefix(self, field: str, prefix: str) -> tuple[str, ...]: ...
    +
    +    def has_phrase(
    +        self,
    +        field: str,
    +        terms: tuple[str, ...],
    +        query_positions: tuple[int, ...],
    +        doc_id: int,
    +    ) -> bool: ...
    +
    +
    +def _intersection(sets: list[set[int]]) -> set[int]:
    +    if not sets:
    +        return set()
    +    result = sets[0].copy()
    +    for values in sets[1:]:
    +        result.intersection_update(values)
    +    return result
    +
    +
    +def _union(sets: Iterable[set[int]]) -> set[int]:
    +    result: set[int] = set()
    +    for values in sets:
    +        result.update(values)
    +    return result
    +
    +
    +def match_boolean(
    +    reader: MatchReader, clauses: tuple[BooleanClause, ...]
    +) -> set[int]:
    +    must = [
    +        match_query(reader, clause.query)
    +        for clause in clauses
    +        if clause.occur is Occur.MUST
    +    ]
    +    should = [
    +        match_query(reader, clause.query)
    +        for clause in clauses
    +        if clause.occur is Occur.SHOULD
    +    ]
    +    prohibited = _union(
    +        match_query(reader, clause.query)
    +        for clause in clauses
    +        if clause.occur is Occur.MUST_NOT
    +    )
    +    if must:
    +        candidates = _intersection(must)
    +    elif should:
    +        candidates = _union(should)
    +    else:
    +        return set()
    +    return candidates - prohibited
    +
    +
    +def match_query(reader: MatchReader, query: Query) -> set[int]:
    +    match query:
    +        case TermQuery(field, term):
    +            return {
    +                posting.doc_id for posting in reader.postings(field, term)
    +            }
    +        case PhraseQuery(field, terms, positions, 0):
    +            candidates = _intersection(
    +                [
    +                    match_query(reader, TermQuery(field, term))
    +                    for term in terms
    +                ]
    +            )
    +            return {
    +                doc_id
    +                for doc_id in candidates
    +                if reader.has_phrase(
    +                    field, terms, positions, doc_id  # type: ignore[arg-type]
    +                )
    +            }
    +        case PrefixQuery(field, prefix):
    +            terms = reader.terms_with_prefix(field, prefix)
    +            if len(terms) > reader.max_prefix_expansions:
    +                raise QueryError("prefix expansion limit exceeded")
    +            return _union(
    +                match_query(reader, TermQuery(field, term))
    +                for term in terms
    +            )
    +        case MatchAllQuery():
    +            return set(range(reader.max_doc))
    +        case BooleanQuery(clauses):
    +            return match_boolean(reader, clauses)
    +    raise QueryError(f"unsupported query: {type(query).__name__}")
    ```

??? note "File diff: src/minilucene/query/model.py"
    ```diff
    diff --git a/src/minilucene/query/model.py b/src/minilucene/query/model.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..9ced717db8e98ff4cf5396ccf715d98c867bc395
    --- /dev/null
    +++ b/src/minilucene/query/model.py
    @@ -0,0 +1,100 @@
    +from __future__ import annotations
    +
    +from dataclasses import dataclass
    +from enum import StrEnum
    +from itertools import pairwise
    +
    +
    +class QueryError(ValueError):
    +    """Raised when a query value or rewrite is invalid."""
    +
    +
    +def _require_text(value: str, label: str) -> None:
    +    if not isinstance(value, str) or not value:
    +        raise QueryError(f"{label} must be a non-empty string")
    +
    +
    +@dataclass(frozen=True, slots=True)
    +class TermQuery:
    +    field: str
    +    term: str
    +
    +    def __post_init__(self) -> None:
    +        _require_text(self.field, "field")
    +        _require_text(self.term, "term")
    +
    +
    +@dataclass(frozen=True, slots=True)
    +class PhraseQuery:
    +    field: str
    +    terms: tuple[str, ...]
    +    positions: tuple[int, ...] | None = None
    +    slop: int = 0
    +
    +    def __post_init__(self) -> None:
    +        _require_text(self.field, "field")
    +        if not self.terms or any(not term for term in self.terms):
    +            raise QueryError("phrase terms must be non-empty")
    +        if self.slop != 0:
    +            raise QueryError("only phrase slop 0 is supported")
    +        positions = (
    +            tuple(range(len(self.terms)))
    +            if self.positions is None
    +            else tuple(self.positions)
    +        )
    +        if len(positions) != len(self.terms):
    +            raise QueryError("phrase positions must match phrase terms")
    +        if positions[0] != 0 or any(
    +            right <= left for left, right in pairwise(positions)
    +        ):
    +            raise QueryError(
    +                "phrase positions must start at zero and strictly increase"
    +            )
    +        object.__setattr__(self, "terms", tuple(self.terms))
    +        object.__setattr__(self, "positions", positions)
    +
    +
    +@dataclass(frozen=True, slots=True)
    +class PrefixQuery:
    +    field: str
    +    prefix: str
    +
    +    def __post_init__(self) -> None:
    +        _require_text(self.field, "field")
    +        _require_text(self.prefix, "prefix")
    +
    +
    +@dataclass(frozen=True, slots=True)
    +class MatchAllQuery:
    +    pass
    +
    +
    +class Occur(StrEnum):
    +    MUST = "MUST"
    +    SHOULD = "SHOULD"
    +    MUST_NOT = "MUST_NOT"
    +
    +
    +@dataclass(frozen=True, slots=True)
    +class BooleanClause:
    +    occur: Occur
    +    query: Query
    +
    +    def __post_init__(self) -> None:
    +        if not isinstance(self.occur, Occur):
    +            raise QueryError("boolean occurrence must be an Occur value")
    +
    +
    +@dataclass(frozen=True, slots=True)
    +class BooleanQuery:
    +    clauses: tuple[BooleanClause, ...]
    +
    +    def __post_init__(self) -> None:
    +        if not self.clauses:
    +            raise QueryError("boolean query requires at least one clause")
    +        object.__setattr__(self, "clauses", tuple(self.clauses))
    +
    +
    +type Query = (
    +    TermQuery | PhraseQuery | PrefixQuery | MatchAllQuery | BooleanQuery
    +)
    ```

**What it is and why it appears**

A closed AST enumerates supported query forms; matching is a pure operation over a reader snapshot and returns document evidence.

**Runtime role**

Leaf queries read postings, phrase matching aligns positions, and boolean nodes combine child results under explicit occurrence rules.

**Statement understanding**

Keeping the AST closed makes unsupported syntax impossible to smuggle into runtime matching as an unvalidated string.

#### Package, fixture, and project support

Keep exports, test corpora, dependencies, and the runtime environment reproducible.

??? note "Supporting file diffs (1 file)"
    **`src/minilucene/query/__init__.py`**

    ```diff
    diff --git a/src/minilucene/query/__init__.py b/src/minilucene/query/__init__.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..e22df3cef86d81c6275094cf9adb8796c2ad9e6d
    --- /dev/null
    +++ b/src/minilucene/query/__init__.py
    @@ -0,0 +1,23 @@
    +from minilucene.query.model import (
    +    BooleanClause,
    +    BooleanQuery,
    +    MatchAllQuery,
    +    Occur,
    +    PhraseQuery,
    +    PrefixQuery,
    +    Query,
    +    QueryError,
    +    TermQuery,
    +)
    +
    +__all__ = [
    +    "BooleanClause",
    +    "BooleanQuery",
    +    "MatchAllQuery",
    +    "Occur",
    +    "PhraseQuery",
    +    "PrefixQuery",
    +    "Query",
    +    "QueryError",
    +    "TermQuery",
    +]
    ```


### Verification evidence

Run `uv run pytest -q $(cat journey/stages/04-query-matching/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Keeping the AST closed makes unsupported syntax impossible to smuggle into runtime matching as an unvalidated string.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 3](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/03-inverted-index.md)

[Complete reference patch / 完整参考补丁](https://github.com/system-in-miniature/mini-lucene/blob/main/journey/stages/04-query-matching/stage.patch)

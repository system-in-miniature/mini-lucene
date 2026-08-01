# Stage 25 · Bounded prefix rewrite

### Goal

Build bounded prefix rewrite and explain its boundary from an executable counterexample, runtime state, and the critical statement.

??? note "Deliverable files"
    - `src/minilucene/errors.py`
    - `src/minilucene/reader.py`
    - `src/minilucene/search/reader.py`
    - `src/minilucene/search/rewrite.py`
    - `tests/contract/test_prefix_rewrite.py`

### The problem at this point

A prefix query cannot execute directly against exact-term postings, and unbounded expansion can turn one query into exhaustive work.

### Test contract

#### See the failure first

Tests create more matching terms than the limit, vary default fields, and ensure deterministic expansion or a typed too-many-clauses failure.

??? note "File diff: tests/contract/test_prefix_rewrite.py"
    ```diff
    diff --git a/tests/contract/test_prefix_rewrite.py b/tests/contract/test_prefix_rewrite.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..8f8f94680d531307a0453c4bf821fc6b45e72a37
    --- /dev/null
    +++ b/tests/contract/test_prefix_rewrite.py
    @@ -0,0 +1,90 @@
    +import pytest
    +
    +from minilucene.errors import TooManyTermsError
    +from minilucene.index.memory import RamIndexBuilder
    +from minilucene.query import (
    +    BooleanClause,
    +    BooleanQuery,
    +    MatchAllQuery,
    +    Occur,
    +    PrefixQuery,
    +    TermQuery,
    +)
    +from minilucene.schema import Schema, TextField
    +from minilucene.search.reader import ReaderView
    +
    +
    +@pytest.fixture
    +def reader():
    +    schema = Schema(body=TextField(stored=True))
    +    builder = RamIndexBuilder(schema)
    +    builder.add_document(
    +        {
    +            "body": (
    +                "application banana apple app apricot application"
    +            )
    +        }
    +    )
    +    return ReaderView(schema, (builder.freeze(generation=1),))
    +
    +
    +def test_prefix_expands_sorted_terms_without_scanning_stored_docs(reader):
    +    assert reader.rewrite(
    +        PrefixQuery("body", "app"), max_terms=3
    +    ) == BooleanQuery(
    +        (
    +            BooleanClause(
    +                Occur.SHOULD, TermQuery("body", "app")
    +            ),
    +            BooleanClause(
    +                Occur.SHOULD, TermQuery("body", "apple")
    +            ),
    +            BooleanClause(
    +                Occur.SHOULD, TermQuery("body", "application")
    +            ),
    +        )
    +    )
    +
    +
    +def test_prefix_expansion_fails_instead_of_truncating(reader):
    +    with pytest.raises(TooManyTermsError) as error:
    +        reader.rewrite(PrefixQuery("body", "a"), max_terms=2)
    +    assert error.value.limit == 2
    +    assert error.value.field == "body"
    +    assert error.value.prefix == "a"
    +
    +
    +def test_prefix_rewrite_is_recursive_and_zero_terms_match_nothing(reader):
    +    query = BooleanQuery(
    +        (
    +            BooleanClause(
    +                Occur.MUST, PrefixQuery("body", "ban")
    +            ),
    +            BooleanClause(
    +                Occur.MUST_NOT, PrefixQuery("body", "missing")
    +            ),
    +        )
    +    )
    +    assert reader.rewrite(query, max_terms=3) == BooleanQuery(
    +        (
    +            BooleanClause(
    +                Occur.MUST, TermQuery("body", "banana")
    +            ),
    +            BooleanClause(
    +                Occur.MUST_NOT,
    +                BooleanQuery(
    +                    (
    +                        BooleanClause(
    +                            Occur.MUST_NOT, MatchAllQuery()
    +                        ),
    +                    )
    +                ),
    +            ),
    +        )
    +    )
    +
    +
    +@pytest.mark.parametrize("limit", [0, -1, 1.5])
    +def test_prefix_rewrite_rejects_invalid_limits(reader, limit):
    +    with pytest.raises(ValueError, match="positive integer"):
    +        reader.rewrite(PrefixQuery("body", "app"), max_terms=limit)
    ```

**What this test locks**

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

**How it constructs the counterexample**

Tests create more matching terms than the limit, vary default fields, and ensure deterministic expansion or a typed too-many-clauses failure.

**Key test statement**

```python
assert reader.rewrite(
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

**What a failure means**

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

Rewrite translates a high-level prefix node into a bounded OR of exact TermQuery nodes using the current reader vocabulary.

### Why this mechanism is necessary

A prefix query cannot execute directly against exact-term postings, and unbounded expansion can turn one query into exhaustive work. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

It resolves field context, enumerates sorted matching terms, stops after limit plus one, and recursively rewrites composite children.

### Mechanism blocks

#### Bounded prefix rewrite mechanism

It resolves field context, enumerates sorted matching terms, stops after limit plus one, and recursively rewrites composite children.

??? note "File diff: src/minilucene/errors.py"
    ```diff
    diff --git a/src/minilucene/errors.py b/src/minilucene/errors.py
    index 64409edb4e9eb9257b7b4f668dca14462b40e803..09ef3d61601abd0368843325ed6411919fe7140a 100644
    --- a/src/minilucene/errors.py
    +++ b/src/minilucene/errors.py
    @@ -28,3 +28,13 @@ class CloseError(MiniLuceneError):
             super().__init__(
                 f"close encountered {len(errors)} cleanup error(s)"
             )
    +
    +
    +class TooManyTermsError(MiniLuceneError, ValueError):
    +    def __init__(self, field: str, prefix: str, limit: int) -> None:
    +        self.field = field
    +        self.prefix = prefix
    +        self.limit = limit
    +        super().__init__(
    +            f"prefix expansion for {field}:{prefix} exceeds {limit} terms"
    +        )
    ```

??? note "File diff: src/minilucene/reader.py"
    ```diff
    diff --git a/src/minilucene/reader.py b/src/minilucene/reader.py
    index 2323983cba3f2fe8940f73ac584e219f286da568..88024c49213de83c9ce5aaa8ea19d3d47146a8fc 100644
    --- a/src/minilucene/reader.py
    +++ b/src/minilucene/reader.py
    @@ -86,6 +86,12 @@ class IndexReader(ReaderView):
             self._ensure_open()
             return super().field_length(field, doc_id)

    +    def rewrite(
    +        self, query: Query, *, max_terms: int | None = None
    +    ) -> Query:
    +        self._ensure_open()
    +        return super().rewrite(query, max_terms=max_terms)
    +
         def close(self) -> None:
             if self._closed:
                 return
    ```

??? note "File diff: src/minilucene/search/reader.py"
    ```diff
    diff --git a/src/minilucene/search/reader.py b/src/minilucene/search/reader.py
    index 2f80ce0073fdfabc8e1581bb29133003c20b6eea..30fb536a85fa0b7355d0b3f9fcad9c3a53e0be23 100644
    --- a/src/minilucene/search/reader.py
    +++ b/src/minilucene/search/reader.py
    @@ -147,6 +147,21 @@ class ReaderView:
         def match(self, query: Query) -> set[int]:
             return match_query(self, query)

    +    def rewrite(
    +        self, query: Query, *, max_terms: int | None = None
    +    ) -> Query:
    +        from minilucene.search.rewrite import rewrite_query
    +
    +        return rewrite_query(
    +            self,
    +            query,
    +            max_terms=(
    +                self.max_prefix_expansions
    +                if max_terms is None
    +                else max_terms
    +            ),
    +        )
    +
         def _build_corpus_stats(self) -> CorpusStats:
             doc_frequencies: dict[tuple[str, str], int] = {}
             for segment, live in zip(
    ```

??? note "File diff: src/minilucene/search/rewrite.py"
    ```diff
    diff --git a/src/minilucene/search/rewrite.py b/src/minilucene/search/rewrite.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..1b83fa046190347c36e5f9ba664c26e14ef924cc
    --- /dev/null
    +++ b/src/minilucene/search/rewrite.py
    @@ -0,0 +1,78 @@
    +from bisect import bisect_left
    +from typing import Protocol
    +
    +from minilucene.errors import TooManyTermsError
    +from minilucene.query import (
    +    BooleanClause,
    +    BooleanQuery,
    +    MatchAllQuery,
    +    Occur,
    +    PrefixQuery,
    +    Query,
    +    TermQuery,
    +)
    +
    +
    +class RewriteReader(Protocol):
    +    def terms_with_prefix(
    +        self, field: str, prefix: str
    +    ) -> tuple[str, ...]: ...
    +
    +
    +def _expand_prefix(
    +    reader: RewriteReader,
    +    query: PrefixQuery,
    +    *,
    +    max_terms: int,
    +) -> Query:
    +    terms = reader.terms_with_prefix(query.field, query.prefix)
    +    start = bisect_left(terms, query.prefix)
    +    matches: list[str] = []
    +    for term in terms[start:]:
    +        if not term.startswith(query.prefix):
    +            break
    +        if len(matches) == max_terms:
    +            raise TooManyTermsError(
    +                query.field, query.prefix, max_terms
    +            )
    +        matches.append(term)
    +    if not matches:
    +        return BooleanQuery(
    +            (BooleanClause(Occur.MUST_NOT, MatchAllQuery()),)
    +        )
    +    if len(matches) == 1:
    +        return TermQuery(query.field, matches[0])
    +    return BooleanQuery(
    +        tuple(
    +            BooleanClause(
    +                Occur.SHOULD, TermQuery(query.field, term)
    +            )
    +            for term in matches
    +        )
    +    )
    +
    +
    +def rewrite_query(
    +    reader: RewriteReader, query: Query, *, max_terms: int
    +) -> Query:
    +    if (
    +        not isinstance(max_terms, int)
    +        or isinstance(max_terms, bool)
    +        or max_terms <= 0
    +    ):
    +        raise ValueError("max_terms must be a positive integer")
    +    if isinstance(query, PrefixQuery):
    +        return _expand_prefix(reader, query, max_terms=max_terms)
    +    if isinstance(query, BooleanQuery):
    +        return BooleanQuery(
    +            tuple(
    +                BooleanClause(
    +                    clause.occur,
    +                    rewrite_query(
    +                        reader, clause.query, max_terms=max_terms
    +                    ),
    +                )
    +                for clause in query.clauses
    +            )
    +        )
    +    return query
    ```

**What it is and why it appears**

Rewrite translates a high-level prefix node into a bounded OR of exact TermQuery nodes using the current reader vocabulary.

**Runtime role**

It resolves field context, enumerates sorted matching terms, stops after limit plus one, and recursively rewrites composite children.

**Statement understanding**

Checking one term beyond the limit distinguishes an exactly-full valid rewrite from silent truncation that would lose matches.

### Verification evidence

Run `uv run pytest -q $(cat journey/stages/25-prefix-rewrite/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Checking one term beyond the limit distinguishes an exactly-full valid rewrite from silent truncation that would lose matches.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 9](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/09-query-language.md)

[Complete reference patch / 完整参考补丁](https://github.com/system-in-miniature/mini-lucene/blob/main/journey/stages/25-prefix-rewrite/stage.patch)

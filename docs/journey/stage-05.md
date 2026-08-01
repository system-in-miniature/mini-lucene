# Stage 05 · Snapshot corpus statistics

### Goal

Build snapshot corpus statistics and explain its boundary from an executable counterexample, runtime state, and the critical statement.

??? note "Deliverable files"
    - `src/minilucene/query/match.py`
    - `src/minilucene/search/__init__.py`
    - `src/minilucene/search/reader.py`
    - `src/minilucene/search/stats.py`
    - `tests/helpers/corpus.py`
    - `tests/unit/search/test_corpus_stats.py`

### The problem at this point

Scoring each segment with local statistics makes identical terms incomparable across a multi-segment index.

### Test contract

#### See the failure first

The counterexample distributes documents unevenly across segments and checks document frequency and average field length over the whole snapshot.

??? note "File diff: tests/helpers/corpus.py"
    ```diff
    diff --git a/tests/helpers/corpus.py b/tests/helpers/corpus.py
    index c71d8d795733402ad8f48eac1faa618aecd324cc..57b0ab8156b73bb0e7efd798e32cdd41377d5d21 100644
    --- a/tests/helpers/corpus.py
    +++ b/tests/helpers/corpus.py
    @@ -6,6 +6,7 @@ class SingleSegmentReader:
         def __init__(self, segment):
             self.segment = segment
             self.max_doc = segment.max_doc
    +        self.live_doc_ids = frozenset(range(segment.max_doc))
             self.max_prefix_expansions = 1_024

         def postings(self, field, term):
    @@ -53,3 +54,22 @@ def build_memory_reader(documents):
         for document in documents:
             builder.add_document({"body": document})
         return SingleSegmentReader(builder.freeze(generation=0))
    +
    +
    +def build_multi_segment_reader(*, segments, deleted):
    +    from minilucene.search.reader import ReaderView
    +
    +    built = []
    +    live_docs = []
    +    for generation, (documents, removed) in enumerate(
    +        zip(segments, deleted, strict=True),
    +        start=1,
    +    ):
    +        builder = RamIndexBuilder(Schema(body=TextField(stored=True)))
    +        for document in documents:
    +            builder.add_document({"body": document})
    +        segment = builder.freeze(generation=generation)
    +        built.append(segment)
    +        live_docs.append(frozenset(range(segment.max_doc)) - frozenset(removed))
    +    schema = Schema(body=TextField(stored=True))
    +    return ReaderView(schema, tuple(built), tuple(live_docs))
    ```

**What this test locks**

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

**How it constructs the counterexample**

The counterexample distributes documents unevenly across segments and checks document frequency and average field length over the whole snapshot.

**Key test statement**

```python
assert stats.live_doc_count == 2
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

**What a failure means**

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

??? note "File diff: tests/unit/search/test_corpus_stats.py"
    ```diff
    diff --git a/tests/unit/search/test_corpus_stats.py b/tests/unit/search/test_corpus_stats.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..afc60e0487c488b190daebe3a90199830eb32901
    --- /dev/null
    +++ b/tests/unit/search/test_corpus_stats.py
    @@ -0,0 +1,46 @@
    +from minilucene.query import MatchAllQuery, TermQuery
    +from tests.helpers.corpus import build_multi_segment_reader
    +
    +
    +def test_corpus_stats_span_segments_and_only_live_documents():
    +    reader = build_multi_segment_reader(
    +        segments=(("kafka kafka", "rabbit"), ("kafka replicas",)),
    +        deleted=((1,), ()),
    +    )
    +    stats = reader.corpus_stats
    +    assert stats.live_doc_count == 2
    +    assert stats.doc_frequency("body", "kafka") == 2
    +    assert stats.average_length("body") == 2.0
    +
    +
    +def test_reader_translates_segment_local_ids_to_snapshot_ids_and_addresses():
    +    reader = build_multi_segment_reader(
    +        segments=(("alpha", "deleted"), ("alpha",)),
    +        deleted=((1,), ()),
    +    )
    +    assert [posting.doc_id for posting in reader.postings("body", "alpha")] == [
    +        0,
    +        2,
    +    ]
    +    assert reader.address(0).segment_generation == 1
    +    assert reader.address(2).segment_generation == 2
    +    assert reader.address(2).local_doc_id == 0
    +
    +
    +def test_match_all_and_term_queries_exclude_deleted_documents():
    +    reader = build_multi_segment_reader(
    +        segments=(("alpha", "alpha"),),
    +        deleted=((0,),),
    +    )
    +    assert reader.match(MatchAllQuery()) == {1}
    +    assert reader.match(TermQuery("body", "alpha")) == {1}
    +
    +
    +def test_stored_fields_and_lengths_resolve_through_snapshot_address():
    +    reader = build_multi_segment_reader(
    +        segments=(("one two",), ("three",)),
    +        deleted=((), ()),
    +    )
    +    assert reader.stored_fields(1) == {"body": "three"}
    +    assert reader.field_length("body", 0) == 2
    +    assert reader.field_length("body", 1) == 1
    ```

**What this test locks**

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

**How it constructs the counterexample**

The counterexample distributes documents unevenly across segments and checks document frequency and average field length over the whole snapshot.

**Key test statement**

```python
assert stats.live_doc_count == 2
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

**What a failure means**

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

Corpus statistics belong to a reader snapshot: live document count, per-field length totals, and term document frequency.

### Why this mechanism is necessary

Scoring each segment with local statistics makes identical terms incomparable across a multi-segment index. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

Opening a search reader walks all visible segment views once and freezes aggregate statistics beside them.

### Mechanism blocks

#### Snapshot corpus statistics mechanism

Opening a search reader walks all visible segment views once and freezes aggregate statistics beside them.

??? note "File diff: src/minilucene/query/match.py"
    ```diff
    diff --git a/src/minilucene/query/match.py b/src/minilucene/query/match.py
    index 914d4dc16beb10f3ea714a436d5fc72a479db417..5f4c52524477ea97a73cb12c0b4085a8355eee64 100644
    --- a/src/minilucene/query/match.py
    +++ b/src/minilucene/query/match.py
    @@ -18,6 +18,7 @@ from minilucene.query.model import (
     class MatchReader(Protocol):
         max_doc: int
         max_prefix_expansions: int
    +    live_doc_ids: frozenset[int]

         def postings(self, field: str, term: str) -> Iterable[Posting]: ...

    @@ -104,7 +105,7 @@ def match_query(reader: MatchReader, query: Query) -> set[int]:
                     for term in terms
                 )
             case MatchAllQuery():
    -            return set(range(reader.max_doc))
    +            return set(reader.live_doc_ids)
             case BooleanQuery(clauses):
                 return match_boolean(reader, clauses)
         raise QueryError(f"unsupported query: {type(query).__name__}")
    ```

??? note "File diff: src/minilucene/search/reader.py"
    ```diff
    diff --git a/src/minilucene/search/reader.py b/src/minilucene/search/reader.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..97cd1d7f6bbf5f8dee41f0c891a0b9564d31e5e7
    --- /dev/null
    +++ b/src/minilucene/search/reader.py
    @@ -0,0 +1,180 @@
    +from collections.abc import Mapping
    +from dataclasses import dataclass
    +
    +from minilucene.index.postings import MemorySegment, Posting
    +from minilucene.query.match import match_query
    +from minilucene.query.model import Query
    +from minilucene.schema import Schema
    +from minilucene.search.stats import CorpusStats, freeze_corpus_stats
    +
    +
    +@dataclass(frozen=True, slots=True)
    +class DocAddress:
    +    segment_generation: int
    +    local_doc_id: int
    +
    +
    +class ReaderView:
    +    def __init__(
    +        self,
    +        schema: Schema,
    +        segments: tuple[MemorySegment, ...],
    +        live_docs: tuple[frozenset[int], ...] | None = None,
    +        *,
    +        max_prefix_expansions: int = 1_024,
    +    ) -> None:
    +        self.schema = schema
    +        self.segments = segments
    +        self.max_prefix_expansions = max_prefix_expansions
    +        if live_docs is None:
    +            live_docs = tuple(
    +                frozenset(range(segment.max_doc)) for segment in segments
    +            )
    +        if len(live_docs) != len(segments):
    +            raise ValueError("live-doc masks must match segments")
    +        for segment, mask in zip(segments, live_docs, strict=True):
    +            if any(doc_id < 0 or doc_id >= segment.max_doc for doc_id in mask):
    +                raise ValueError("live-doc ID outside segment")
    +        self._live_docs = live_docs
    +        bases: list[int] = []
    +        next_base = 0
    +        for segment in segments:
    +            bases.append(next_base)
    +            next_base += segment.max_doc
    +        self._bases = tuple(bases)
    +        self.max_doc = next_base
    +        self.live_doc_ids = frozenset(
    +            base + local_doc_id
    +            for base, mask in zip(self._bases, live_docs, strict=True)
    +            for local_doc_id in mask
    +        )
    +        self.corpus_stats = self._build_corpus_stats()
    +
    +    def _resolve(self, doc_id: int) -> tuple[int, MemorySegment, int]:
    +        if doc_id < 0 or doc_id >= self.max_doc:
    +            raise IndexError(f"document ID outside reader: {doc_id}")
    +        for index in range(len(self.segments) - 1, -1, -1):
    +            base = self._bases[index]
    +            if doc_id >= base:
    +                return index, self.segments[index], doc_id - base
    +        raise IndexError(f"document ID outside reader: {doc_id}")
    +
    +    def address(self, doc_id: int) -> DocAddress:
    +        _, segment, local_doc_id = self._resolve(doc_id)
    +        return DocAddress(segment.generation, local_doc_id)
    +
    +    def postings(self, field: str, term: str) -> tuple[Posting, ...]:
    +        result: list[Posting] = []
    +        for base, segment, live in zip(
    +            self._bases, self.segments, self._live_docs, strict=True
    +        ):
    +            for posting in segment.postings.get(field, {}).get(term, ()):
    +                if posting.doc_id in live:
    +                    result.append(
    +                        Posting(
    +                            doc_id=base + posting.doc_id,
    +                            term_frequency=posting.term_frequency,
    +                            positions=posting.positions,
    +                        )
    +                    )
    +        return tuple(result)
    +
    +    def terms_with_prefix(
    +        self, field: str, prefix: str
    +    ) -> tuple[str, ...]:
    +        return tuple(
    +            sorted(
    +                {
    +                    term
    +                    for segment in self.segments
    +                    for term in segment.postings.get(field, {})
    +                    if term.startswith(prefix)
    +                }
    +            )
    +        )
    +
    +    def has_phrase(
    +        self,
    +        field: str,
    +        terms: tuple[str, ...],
    +        query_positions: tuple[int, ...],
    +        doc_id: int,
    +    ) -> bool:
    +        segment_index, segment, local_doc_id = self._resolve(doc_id)
    +        if local_doc_id not in self._live_docs[segment_index]:
    +            return False
    +        term_positions: list[set[int]] = []
    +        for term in terms:
    +            posting = next(
    +                (
    +                    item
    +                    for item in segment.postings.get(field, {}).get(term, ())
    +                    if item.doc_id == local_doc_id
    +                ),
    +                None,
    +            )
    +            if posting is None:
    +                return False
    +            term_positions.append(set(posting.positions))
    +        return any(
    +            all(
    +                start + query_position in positions
    +                for query_position, positions in zip(
    +                    query_positions, term_positions, strict=True
    +                )
    +            )
    +            for start in term_positions[0]
    +        )
    +
    +    def stored_fields(self, doc_id: int) -> Mapping[str, str]:
    +        index, segment, local_doc_id = self._resolve(doc_id)
    +        if local_doc_id not in self._live_docs[index]:
    +            raise KeyError(f"document is deleted: {doc_id}")
    +        return segment.stored_documents[local_doc_id]
    +
    +    def field_length(self, field: str, doc_id: int) -> int:
    +        index, segment, local_doc_id = self._resolve(doc_id)
    +        if local_doc_id not in self._live_docs[index]:
    +            raise KeyError(f"document is deleted: {doc_id}")
    +        return segment.field_lengths.get(
    +            field, (0,) * segment.max_doc
    +        )[local_doc_id]
    +
    +    def match(self, query: Query) -> set[int]:
    +        return match_query(self, query)
    +
    +    def _build_corpus_stats(self) -> CorpusStats:
    +        doc_frequencies: dict[tuple[str, str], int] = {}
    +        for segment, live in zip(
    +            self.segments, self._live_docs, strict=True
    +        ):
    +            for field, terms in segment.postings.items():
    +                for term, postings in terms.items():
    +                    frequency = sum(
    +                        posting.doc_id in live for posting in postings
    +                    )
    +                    key = (field, term)
    +                    doc_frequencies[key] = (
    +                        doc_frequencies.get(key, 0) + frequency
    +                    )
    +
    +        length_sums: dict[str, int] = {}
    +        length_counts: dict[str, int] = {}
    +        for segment, live in zip(
    +            self.segments, self._live_docs, strict=True
    +        ):
    +            for field, lengths in segment.field_lengths.items():
    +                for local_doc_id in live:
    +                    length = lengths[local_doc_id]
    +                    if length > 0:
    +                        length_sums[field] = length_sums.get(field, 0) + length
    +                        length_counts[field] = length_counts.get(field, 0) + 1
    +        averages = {
    +            field: length_sums[field] / count
    +            for field, count in length_counts.items()
    +        }
    +        return freeze_corpus_stats(
    +            live_doc_count=len(self.live_doc_ids),
    +            doc_frequencies=doc_frequencies,
    +            average_field_lengths=averages,
    +        )
    ```

??? note "File diff: src/minilucene/search/stats.py"
    ```diff
    diff --git a/src/minilucene/search/stats.py b/src/minilucene/search/stats.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..f7ccd82d285a0a8c28159bb35998ffe1fbb1e119
    --- /dev/null
    +++ b/src/minilucene/search/stats.py
    @@ -0,0 +1,31 @@
    +from collections.abc import Mapping
    +from dataclasses import dataclass
    +from types import MappingProxyType
    +
    +
    +@dataclass(frozen=True, slots=True)
    +class CorpusStats:
    +    live_doc_count: int
    +    doc_frequencies: Mapping[tuple[str, str], int]
    +    average_field_lengths: Mapping[str, float]
    +
    +    def doc_frequency(self, field: str, term: str) -> int:
    +        return self.doc_frequencies.get((field, term), 0)
    +
    +    def average_length(self, field: str) -> float:
    +        return self.average_field_lengths.get(field, 0.0)
    +
    +
    +def freeze_corpus_stats(
    +    *,
    +    live_doc_count: int,
    +    doc_frequencies: dict[tuple[str, str], int],
    +    average_field_lengths: dict[str, float],
    +) -> CorpusStats:
    +    return CorpusStats(
    +        live_doc_count=live_doc_count,
    +        doc_frequencies=MappingProxyType(dict(doc_frequencies)),
    +        average_field_lengths=MappingProxyType(
    +            dict(average_field_lengths)
    +        ),
    +    )
    ```

**What it is and why it appears**

Corpus statistics belong to a reader snapshot: live document count, per-field length totals, and term document frequency.

**Runtime role**

Opening a search reader walks all visible segment views once and freezes aggregate statistics beside them.

**Statement understanding**

Freezing statistics with the same segment set used for matching prevents scores from mixing two visibility generations.

#### Package, fixture, and project support

Keep exports, test corpora, dependencies, and the runtime environment reproducible.

??? note "Supporting file diffs (1 file)"
    **`src/minilucene/search/__init__.py`**

    ```diff
    diff --git a/src/minilucene/search/__init__.py b/src/minilucene/search/__init__.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..e7896ba128e109797bb2852a4a0914eb03446089
    --- /dev/null
    +++ b/src/minilucene/search/__init__.py
    @@ -0,0 +1,4 @@
    +from minilucene.search.reader import DocAddress, ReaderView
    +from minilucene.search.stats import CorpusStats
    +
    +__all__ = ["CorpusStats", "DocAddress", "ReaderView"]
    ```


### Verification evidence

Run `uv run pytest -q $(cat journey/stages/05-corpus-statistics/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Freezing statistics with the same segment set used for matching prevents scores from mixing two visibility generations.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 8](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/08-scoring.md)

[Complete reference patch / 完整参考补丁](https://github.com/system-in-miniature/mini-lucene/blob/main/journey/stages/05-corpus-statistics/stage.patch)

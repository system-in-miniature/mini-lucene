# MiniLucene Retrieval Kernel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete in-memory fielded lexical search kernel with positional analysis, query execution, global BM25, stored fields, and bounded Top-K.

**Architecture:** Immutable schema and token values feed one mutable `RamIndexBuilder`, which freezes into an immutable `MemorySegment`. Query rewriting and candidate matching operate on one `ReaderView`; BM25 weights use one global corpus-statistics snapshot and feed a fixed-size collector.

**Tech Stack:** Python 3.12 standard library, dataclasses, enum, re, math, heapq, pytest, Ruff, Hatchling, uv.

---

### Task 1: Bootstrap the standalone package and test contract

**Files:**
- Create: `pyproject.toml`
- Create: `src/minilucene/__init__.py`
- Create: `tests/test_public_surface.py`
- Create: `tools/__init__.py`

- [ ] **Step 1: Write the public import RED test**

```python
from minilucene import (
    KeywordField,
    MemoryIndex,
    Schema,
    TextField,
)


def test_public_surface_imports():
    schema = Schema(
        id=KeywordField(stored=True),
        body=TextField(stored=True),
    )
    assert MemoryIndex(schema).schema == schema
```

- [ ] **Step 2: Run and verify RED**

Run:

```bash
uv run pytest tests/test_public_surface.py -q
```

Expected: collection fails because `minilucene` is not importable.

- [ ] **Step 3: Create packaging and the temporary public shell**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "minilucene-reference"
version = "0.1.0"
description = "Direct-first MiniLucene reference implementation"
requires-python = ">=3.12"
dependencies = []

[dependency-groups]
dev = [
  "pytest>=9,<10",
  "ruff>=0.12,<1",
]

[tool.hatch.build.targets.wheel]
packages = ["src/minilucene"]

[tool.pytest.ini_options]
pythonpath = ["src", "."]
testpaths = ["tests"]
```

Create `src/minilucene/__init__.py` with imports from the schema and memory
modules introduced in Task 2; until Task 2 lands, define the four names in the
same file with constructors that preserve the test signature. Task 2 removes
that temporary shell in the same phase, so no phase boundary exposes it.

- [ ] **Step 4: Sync and run the test**

```bash
uv sync --dev
uv run pytest tests/test_public_surface.py -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock src tests/test_public_surface.py tools
git commit -m "chore: bootstrap MiniLucene reference package"
```

### Task 2: Freeze fields, schema, documents, and fingerprints

**Files:**
- Create: `src/minilucene/schema.py`
- Create: `src/minilucene/document.py`
- Modify: `src/minilucene/__init__.py`
- Create: `tests/contract/test_schema.py`

- [ ] **Step 1: Write schema and document contract tests**

```python
import pytest

from minilucene.document import freeze_document
from minilucene.schema import (
    KeywordField,
    Schema,
    SchemaError,
    StoredField,
    TextField,
)


def test_stored_indexed_and_tokenized_are_independent():
    schema = Schema(
        id=KeywordField(stored=True),
        body=TextField(stored=False, boost=2.0),
        source=StoredField(),
    )
    assert schema["id"].indexed and not schema["id"].tokenized
    assert schema["body"].indexed and schema["body"].store_positions
    assert schema["source"].stored and not schema["source"].indexed
    assert schema.fingerprint == schema.fingerprint


def test_document_rejects_unknown_fields_and_non_strings():
    schema = Schema(body=TextField())
    with pytest.raises(SchemaError, match="unknown field"):
        freeze_document(schema, {"missing": "x"})
    with pytest.raises(SchemaError, match="must be str"):
        freeze_document(schema, {"body": 1})
```

- [ ] **Step 2: Run and verify RED**

Run:

```bash
uv run pytest tests/contract/test_schema.py -q
```

Expected: imports fail for `schema` and `document`.

- [ ] **Step 3: Implement immutable schema values**

```python
# src/minilucene/schema.py
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from types import MappingProxyType
from typing import Iterator, Mapping


class SchemaError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class FieldType:
    indexed: bool
    tokenized: bool
    stored: bool
    store_positions: bool
    boost: float
    analyzer_name: str | None

    def __post_init__(self) -> None:
        if not math.isfinite(self.boost) or self.boost <= 0:
            raise SchemaError("field boost must be finite and positive")
        if self.store_positions and not self.indexed:
            raise SchemaError("positions require an indexed field")


def TextField(*, stored: bool = False, boost: float = 1.0) -> FieldType:
    return FieldType(True, True, stored, True, boost, "standard")


def KeywordField(*, stored: bool = False, boost: float = 1.0) -> FieldType:
    return FieldType(True, False, stored, False, boost, "keyword")


def StoredField() -> FieldType:
    return FieldType(False, False, True, False, 1.0, None)


class Schema(Mapping[str, FieldType]):
    def __init__(self, **fields: FieldType) -> None:
        if not fields:
            raise SchemaError("schema must contain at least one field")
        if any(not name or not isinstance(value, FieldType) for name, value in fields.items()):
            raise SchemaError("schema fields require non-empty names and FieldType values")
        self._fields = MappingProxyType(dict(sorted(fields.items())))
        payload = json.dumps(
            {name: asdict(field) for name, field in self._fields.items()},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        self.fingerprint = hashlib.sha256(payload).hexdigest()

    def __getitem__(self, key: str) -> FieldType:
        return self._fields[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._fields)

    def __len__(self) -> int:
        return len(self._fields)
```

```python
# src/minilucene/document.py
from types import MappingProxyType
from typing import Mapping

from minilucene.schema import Schema, SchemaError


FrozenDocument = Mapping[str, str]


def freeze_document(schema: Schema, values: Mapping[str, object]) -> FrozenDocument:
    unknown = sorted(set(values) - set(schema))
    if unknown:
        raise SchemaError(f"unknown field: {unknown[0]}")
    frozen: dict[str, str] = {}
    for name, value in values.items():
        if not isinstance(value, str):
            raise SchemaError(f"field {name} must be str")
        frozen[name] = value
    return MappingProxyType(dict(sorted(frozen.items())))
```

- [ ] **Step 4: Export the real public values and run tests**

```python
# src/minilucene/__init__.py
from minilucene.schema import KeywordField, Schema, StoredField, TextField

__all__ = ["KeywordField", "Schema", "StoredField", "TextField"]
```

Run:

```bash
uv run pytest tests/contract/test_schema.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/minilucene tests/contract/test_schema.py
git commit -m "feat: freeze field and document schema"
```

### Task 3: Build positional, offset-preserving analysis

**Files:**
- Create: `src/minilucene/analysis/__init__.py`
- Create: `src/minilucene/analysis/model.py`
- Create: `src/minilucene/analysis/pipeline.py`
- Create: `src/minilucene/analysis/standard.py`
- Create: `tests/unit/analysis/test_pipeline.py`

- [ ] **Step 1: Write token, binary keyword, lowercase, and stop-gap tests**

```python
from minilucene.analysis import (
    KeywordAnalyzer,
    StandardAnalyzer,
    Token,
)


def test_standard_analysis_preserves_offsets_and_stopword_gap():
    analyzer = StandardAnalyzer(stopwords=frozenset({"and"}))
    assert analyzer.analyze("Kafka AND Replicas") == (
        Token("kafka", 0, 0, 5),
        Token("replicas", 2, 10, 18),
    )


def test_keyword_analyzer_emits_whole_value():
    assert KeywordAnalyzer().analyze("Jonah Smith") == (
        Token("Jonah Smith", 0, 0, 11),
    )
```

- [ ] **Step 2: Run and verify RED**

Run:

```bash
uv run pytest tests/unit/analysis/test_pipeline.py -q
```

Expected: `minilucene.analysis` does not exist.

- [ ] **Step 3: Implement the closed analysis pipeline**

```python
# model.py
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Token:
    term: str
    position: int
    start_offset: int
    end_offset: int
```

```python
# pipeline.py
from collections.abc import Iterable, Protocol
from dataclasses import replace

from minilucene.analysis.model import Token


class Tokenizer(Protocol):
    def tokenize(self, text: str) -> tuple[Token, ...]: ...


class TokenFilter(Protocol):
    def apply(self, tokens: Iterable[Token]) -> tuple[Token, ...]: ...


class LowercaseFilter:
    def apply(self, tokens: Iterable[Token]) -> tuple[Token, ...]:
        return tuple(replace(token, term=token.term.lower()) for token in tokens)


class StopwordFilter:
    def __init__(self, stopwords: frozenset[str]) -> None:
        self.stopwords = stopwords

    def apply(self, tokens: Iterable[Token]) -> tuple[Token, ...]:
        return tuple(token for token in tokens if token.term not in self.stopwords)


class Analyzer:
    def __init__(self, tokenizer: Tokenizer, filters: tuple[TokenFilter, ...]) -> None:
        self.tokenizer = tokenizer
        self.filters = filters

    def analyze(self, text: str) -> tuple[Token, ...]:
        tokens = self.tokenizer.tokenize(text)
        for filter_ in self.filters:
            tokens = filter_.apply(tokens)
        return tokens
```

`standard.py` uses `re.compile(r"\w+", re.UNICODE).finditer(text)` and assigns
positions before filtering. `KeywordTokenizer` emits no token for an empty
string and otherwise one exact token. Export `StandardAnalyzer`,
`KeywordAnalyzer`, and `Token` from `analysis/__init__.py`.

- [ ] **Step 4: Run analyzer tests**

```bash
uv run pytest tests/unit/analysis/test_pipeline.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/minilucene/analysis tests/unit/analysis
git commit -m "feat: add positional analysis pipeline"
```

### Task 4: Freeze a complete in-memory positional segment

**Files:**
- Create: `src/minilucene/index/__init__.py`
- Create: `src/minilucene/index/postings.py`
- Create: `src/minilucene/index/memory.py`
- Create: `tests/contract/test_memory_index.py`

- [ ] **Step 1: Write postings, stored-field, and length tests**

```python
from minilucene.index.memory import RamIndexBuilder
from minilucene.schema import KeywordField, Schema, StoredField, TextField


def test_ram_segment_contains_positions_lengths_and_only_stored_values():
    schema = Schema(
        id=KeywordField(stored=True),
        body=TextField(stored=False),
        source=StoredField(),
    )
    builder = RamIndexBuilder(schema)
    builder.add_document(
        {"id": "d1", "body": "Kafka kafka replicas", "source": "manual"}
    )
    segment = builder.freeze(generation=1)

    posting = segment.postings["body"]["kafka"][0]
    assert (posting.doc_id, posting.term_frequency, posting.positions) == (
        0,
        2,
        (0, 1),
    )
    assert segment.field_lengths["body"] == (3,)
    assert segment.stored_documents == ({"id": "d1", "source": "manual"},)
```

- [ ] **Step 2: Run and verify RED**

```bash
uv run pytest tests/contract/test_memory_index.py -q
```

Expected: import fails for `RamIndexBuilder`.

- [ ] **Step 3: Implement immutable postings and segment values**

```python
# postings.py
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True, slots=True)
class Posting:
    doc_id: int
    term_frequency: int
    positions: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class MemorySegment:
    generation: int
    max_doc: int
    postings: Mapping[str, Mapping[str, tuple[Posting, ...]]]
    stored_documents: tuple[Mapping[str, str], ...]
    field_lengths: Mapping[str, tuple[int, ...]]
```

`RamIndexBuilder.add_document()` validates and freezes the entire document
before mutating builder collections. For indexed fields it selects the
standard or keyword analyzer from `FieldType.analyzer_name`, groups token
positions per term, and appends exactly one posting per `(field, term, doc)`.
For stored fields it copies only stored values. `freeze()` sorts fields and
terms, converts every collection to tuples and mapping proxies, and validates
dense doc IDs plus increasing positions.

- [ ] **Step 4: Run the contract**

```bash
uv run pytest tests/contract/test_memory_index.py -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/minilucene/index tests/contract/test_memory_index.py
git commit -m "feat: build immutable positional RAM segments"
```

### Task 5: Define and execute the closed Query AST

**Files:**
- Create: `src/minilucene/query/__init__.py`
- Create: `src/minilucene/query/model.py`
- Create: `src/minilucene/query/match.py`
- Create: `tests/contract/test_query_matching.py`

- [ ] **Step 1: Write term, phrase, prefix, and boolean counterexamples**

```python
from minilucene.query import (
    BooleanClause,
    BooleanQuery,
    Occur,
    PhraseQuery,
    PrefixQuery,
    TermQuery,
)
from tests.helpers.corpus import build_memory_reader


def test_phrase_requires_consecutive_positions():
    reader = build_memory_reader(
        ("distributed system", "distributed applications improve the system")
    )
    assert reader.match(PhraseQuery("body", ("distributed", "system"))) == {0}


def test_phrase_preserves_analyzed_stopword_gap():
    reader = build_memory_reader(("distributed system", "distributed the system"))
    query = PhraseQuery(
        "body",
        ("distributed", "system"),
        positions=(0, 2),
    )
    assert reader.match(query) == {1}


def test_boolean_and_prefix_have_frozen_set_semantics():
    reader = build_memory_reader(("kafka replicas", "rabbit replicas", "kafka"))
    query = BooleanQuery(
        (
            BooleanClause(Occur.MUST, PrefixQuery("body", "kaf")),
            BooleanClause(Occur.MUST, TermQuery("body", "replicas")),
            BooleanClause(Occur.MUST_NOT, TermQuery("body", "rabbit")),
        )
    )
    assert reader.match(query) == {0}
```

- [ ] **Step 2: Run and verify RED**

```bash
uv run pytest tests/contract/test_query_matching.py -q
```

Expected: query imports fail.

- [ ] **Step 3: Implement immutable query values and set matching**

`query/model.py` defines frozen dataclasses for `TermQuery`, `PhraseQuery`,
`PrefixQuery`, `BooleanClause`, `BooleanQuery`, and `MatchAllQuery`, plus an
`Occur` string enum. Constructors reject empty terms, empty phrase terms,
nonzero phrase slop, phrase-position length mismatches or non-increasing
positions, empty boolean clauses, and empty prefixes. `PhraseQuery.positions`
defaults to `(0, 1, ...)`.

`query/match.py` implements:

```python
def match_query(reader: ReaderView, query: Query) -> set[int]:
    match query:
        case TermQuery(field, term):
            return {posting.doc_id for posting in reader.postings(field, term)}
        case PhraseQuery(field, terms, positions, 0):
            candidates = set.intersection(
                *(match_query(reader, TermQuery(field, term)) for term in terms)
            )
            return {
                doc_id
                for doc_id in candidates
                if reader.has_phrase(field, terms, positions, doc_id)
            }
        case PrefixQuery(field, prefix):
            terms = reader.terms_with_prefix(field, prefix)
            if len(terms) > reader.max_prefix_expansions:
                raise QueryError("prefix expansion limit exceeded")
            return set().union(
                *(match_query(reader, TermQuery(field, term)) for term in terms)
            )
        case MatchAllQuery():
            return set(range(reader.max_doc))
        case BooleanQuery(clauses):
            return match_boolean(reader, clauses)
```

`match_boolean()` applies the exact MUST/SHOULD/MUST_NOT rules from the spec.
Phrase matching looks up each term's positions for the candidate and tests
whether `p + query_position` exists for every normalized query position.

- [ ] **Step 4: Run query tests**

```bash
uv run pytest tests/contract/test_query_matching.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/minilucene/query tests/contract/test_query_matching.py tests/helpers
git commit -m "feat: execute positional query AST"
```

### Task 6: Compute one global live-document corpus-statistics snapshot

**Files:**
- Create: `src/minilucene/search/stats.py`
- Create: `src/minilucene/search/reader.py`
- Create: `tests/unit/search/test_corpus_stats.py`

- [ ] **Step 1: Write global statistics tests**

```python
from tests.helpers.corpus import build_multi_segment_reader


def test_corpus_stats_span_segments_and_only_live_documents():
    reader = build_multi_segment_reader(
        segments=(("kafka kafka", "rabbit"), ("kafka replicas",)),
        deleted=((1,), ()),
    )
    stats = reader.corpus_stats
    assert stats.live_doc_count == 2
    assert stats.doc_frequency("body", "kafka") == 2
    assert stats.average_length("body") == 2.0
```

- [ ] **Step 2: Run and verify RED**

```bash
uv run pytest tests/unit/search/test_corpus_stats.py -q
```

Expected: search reader imports fail.

- [ ] **Step 3: Implement immutable reader and stats**

`ReaderView` receives an ordered tuple of immutable segments and equally sized
live-doc frozensets. It assigns each hit a `DocAddress(segment_generation,
local_doc_id)`. It exposes sorted terms, postings filtered by live docs, stored
fields, lengths, phrase positions, and one precomputed `CorpusStats`.

```python
@dataclass(frozen=True, slots=True)
class CorpusStats:
    live_doc_count: int
    doc_frequencies: Mapping[tuple[str, str], int]
    average_field_lengths: Mapping[str, float]

    def doc_frequency(self, field: str, term: str) -> int:
        return self.doc_frequencies.get((field, term), 0)

    def average_length(self, field: str) -> float:
        return self.average_field_lengths.get(field, 0.0)
```

Build document frequency by counting one live posting per segment document,
not term frequency. Average length excludes deleted documents and documents
without that field.

- [ ] **Step 4: Run stats tests**

```bash
uv run pytest tests/unit/search/test_corpus_stats.py -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/minilucene/search tests/unit/search tests/helpers
git commit -m "feat: snapshot global corpus statistics"
```

### Task 7: Implement BM25 saturation and field boosts

**Files:**
- Create: `src/minilucene/search/bm25.py`
- Create: `src/minilucene/search/scorer.py`
- Create: `tests/unit/search/test_bm25.py`
- Create: `tests/contract/test_ranking.py`

- [ ] **Step 1: Write math and ranking counterexamples**

```python
import pytest

from minilucene.search.bm25 import BM25
from tests.helpers.corpus import search_memory


def test_bm25_tf_saturates():
    bm25 = BM25(k1=1.2, b=0.75)
    one = bm25.term_score(tf=1, df=1, n=10, dl=10, avgdl=10)
    ten = bm25.term_score(tf=10, df=1, n=10, dl=10, avgdl=10)
    hundred = bm25.term_score(tf=100, df=1, n=10, dl=10, avgdl=10)
    assert ten > one
    assert hundred - ten < ten - one


def test_title_boost_changes_ranking():
    hits = search_memory(
        documents=(
            {"title": "kafka", "body": "nothing"},
            {"title": "nothing", "body": "kafka kafka"},
        ),
        query="kafka",
        title_boost=3.0,
    )
    assert hits[0].stored_fields["id"] == "0"
```

- [ ] **Step 2: Run and verify RED**

```bash
uv run pytest tests/unit/search/test_bm25.py tests/contract/test_ranking.py -q
```

Expected: BM25 and scorer imports fail.

- [ ] **Step 3: Implement BM25 and scorer weights**

```python
@dataclass(frozen=True, slots=True)
class BM25:
    k1: float = 1.2
    b: float = 0.75

    def term_score(
        self, *, tf: int, df: int, n: int, dl: int, avgdl: float
    ) -> float:
        if tf <= 0 or df <= 0 or n <= 0:
            return 0.0
        idf = math.log(1.0 + (n - df + 0.5) / (df + 0.5))
        norm = 1.0 - self.b + self.b * (dl / avgdl if avgdl else 0.0)
        return idf * (tf * (self.k1 + 1.0)) / (tf + self.k1 * norm)
```

`score_query()` first rewrites prefix queries to boolean term queries, calls
`match_query()` for candidates, and sums positive term contributions. Phrase
queries sum their component term scores only for phrase-matching documents.
Boolean `MUST_NOT` clauses are never scored. Multiply each contribution by
the field's frozen boost.

- [ ] **Step 4: Run BM25 and ranking tests**

```bash
uv run pytest tests/unit/search/test_bm25.py tests/contract/test_ranking.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/minilucene/search tests/unit/search/test_bm25.py tests/contract/test_ranking.py
git commit -m "feat: rank with global BM25 and field boosts"
```

### Task 8: Collect bounded Top-K and expose MemoryIndex search

**Files:**
- Create: `src/minilucene/search/collector.py`
- Create: `src/minilucene/search/searcher.py`
- Modify: `src/minilucene/index/memory.py`
- Modify: `src/minilucene/__init__.py`
- Create: `tests/unit/search/test_topk.py`
- Create: `tests/contract/test_memory_search.py`

- [ ] **Step 1: Write heap-oracle and public search tests**

```python
from minilucene import MemoryIndex, Schema, TextField
from minilucene.query import TermQuery
from minilucene.search.collector import TopKCollector


def test_heap_topk_matches_complete_sort_oracle():
    scored = ((score, 1, doc) for doc, score in enumerate((1.0, 5.0, 3.0, 5.0)))
    collector = TopKCollector(2)
    for score, segment, doc in scored:
        collector.collect(score, segment, doc)
    assert [(hit.score, hit.local_doc_id) for hit in collector.top_docs().hits] == [
        (5.0, 1),
        (5.0, 3),
    ]
    assert collector.max_retained == 2


def test_public_memory_index_returns_stored_fields():
    index = MemoryIndex(Schema(body=TextField(stored=True)))
    index.add_document(body="kafka replicas")
    result = index.search(TermQuery("body", "kafka"), top_k=10)
    assert result.total_hits == 1
    assert result.hits[0].stored_fields == {"body": "kafka replicas"}
```

- [ ] **Step 2: Run and verify RED**

```bash
uv run pytest tests/unit/search/test_topk.py tests/contract/test_memory_search.py -q
```

Expected: collector and public `MemoryIndex` are missing.

- [ ] **Step 3: Implement the bounded collector and facade**

`SearchHit` contains score, segment generation, local doc ID, and an immutable
stored-field mapping. `TopDocs` contains total hit count and an ordered hit
tuple.

The collector heap stores the current worst hit at index zero using key
`(score, -segment_generation, -local_doc_id)`. Replace only when a new hit has
a better final ordering. `top_docs()` sorts the retained K by
`(-score, segment_generation, local_doc_id)`.

`MemoryIndex` owns a `RamIndexBuilder`; every search freezes a generation-zero
segment, builds one `ReaderView`, and delegates to `IndexSearcher`. The public
facade accepts keyword arguments for documents and exports the real schema,
query, and result values from `minilucene.__init__`.

- [ ] **Step 4: Run focused and full tests**

```bash
uv run pytest tests/unit/search/test_topk.py tests/contract/test_memory_search.py -q
uv run pytest -q
```

Expected: both commands exit `0`.

- [ ] **Step 5: Commit**

```bash
git add src/minilucene tests/unit/search/test_topk.py tests/contract/test_memory_search.py
git commit -m "feat: expose bounded in-memory Top-K search"
```

### Task 9: Accept the retrieval kernel invariants

**Files:**
- Create: `tests/acceptance/test_phase1_retrieval_kernel.py`
- Create: `docs/phase1-retrieval-kernel.md`

- [ ] **Step 1: Write one end-to-end kernel acceptance**

```python
from minilucene import KeywordField, MemoryIndex, Schema, TextField
from minilucene.query import BooleanClause, BooleanQuery, Occur, PhraseQuery, TermQuery


def test_fielded_phrase_bm25_topk_and_stored_fields_close_one_loop():
    index = MemoryIndex(
        Schema(
            id=KeywordField(stored=True),
            title=TextField(stored=True, boost=2.0),
            body=TextField(stored=True),
        )
    )
    index.add_document(id="1", title="Kafka", body="follower replicas")
    index.add_document(
        id="2",
        title="Queues",
        body="follower processes coordinate distant replicas",
    )
    query = BooleanQuery(
        (
            BooleanClause(Occur.MUST, TermQuery("title", "kafka")),
            BooleanClause(
                Occur.MUST,
                PhraseQuery("body", ("follower", "replicas")),
            ),
        )
    )
    result = index.search(query, top_k=1)
    assert result.total_hits == 1
    assert result.hits[0].stored_fields["id"] == "1"
```

- [ ] **Step 2: Run the acceptance and full verification**

```bash
uv run pytest tests/acceptance/test_phase1_retrieval_kernel.py -q
uv run ruff check src tests tools
uv run pytest -q
uv run python -m compileall -q src tests tools
git diff --check
```

Expected: every command exits `0`.

- [ ] **Step 3: Write the phase report**

`docs/phase1-retrieval-kernel.md` records the public API, exact query semantics,
BM25 defaults, Top-K tie-break, test commands, and deliberate absence of disk,
refresh, parser, highlighting, vector, and network behavior.

- [ ] **Step 4: Commit Phase 1 acceptance**

```bash
git add docs/phase1-retrieval-kernel.md tests/acceptance/test_phase1_retrieval_kernel.py
git commit -m "test: accept MiniLucene retrieval kernel"
git status --short
git log -1 --oneline
```

Expected: clean worktree and last commit
`test: accept MiniLucene retrieval kernel`.

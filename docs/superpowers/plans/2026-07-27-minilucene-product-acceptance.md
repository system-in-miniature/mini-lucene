# MiniLucene Product Closure and Final Acceptance Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Execute inline and complete tasks in order.

**Goal:** Close the V1 product loop with a strict query parser, safe highlighting, relevance metrics and corpus, a thin local CLI, executable behavior mapping, and owner-zero end-to-end acceptance.

**Architecture:** Parser output is the existing closed Query AST. Highlighting is a read-only consumer of stored text, analyzers, and rewritten queries. Evaluation consumes `TopDocs` only. The CLI is an adapter over the public Python API and owns no search semantics.

**Tech Stack:** Python 3.12 standard library (`argparse`, `html`, `json`), pytest, Ruff, uv.

---

### Task 1: Tokenize the closed query language with source offsets

**Files:**
- Create: `src/minilucene/query_parser/__init__.py`
- Create: `src/minilucene/query_parser/lexer.py`
- Create: `src/minilucene/query_parser/errors.py`
- Create: `tests/unit/query_parser/test_lexer.py`

- [ ] **Step 1: Write lexical tests**

```python
import pytest

from minilucene.query_parser.errors import QuerySyntaxError
from minilucene.query_parser.lexer import TokenKind, lex


def test_lexer_preserves_offsets_and_quoted_text():
    tokens = lex('title:kafka AND body:"follower replicas"')
    assert [(token.kind, token.text, token.start) for token in tokens] == [
        (TokenKind.WORD, "title", 0),
        (TokenKind.COLON, ":", 5),
        (TokenKind.WORD, "kafka", 6),
        (TokenKind.AND, "AND", 12),
        (TokenKind.WORD, "body", 16),
        (TokenKind.COLON, ":", 20),
        (TokenKind.PHRASE, "follower replicas", 21),
        (TokenKind.EOF, "", 40),
    ]


def test_unclosed_phrase_reports_opening_offset():
    with pytest.raises(QuerySyntaxError) as error:
        lex('"broken')
    assert error.value.offset == 0
```

Cover parentheses, unary `-`, case-insensitive operators, escaped quote and
backslash inside phrases, one trailing `*`, and illegal wildcard placement.

- [ ] **Step 2: Run RED**

```bash
uv run pytest tests/unit/query_parser/test_lexer.py -q
```

- [ ] **Step 3: Implement deterministic lexer**

`QuerySyntaxError(message, offset, source)` renders the offset plus a caret.
Whitespace separates expressions. `AND`, `OR`, and `NOT` are operators only
when a complete unquoted word. Asterisk is legal only as the final character
of a non-empty word.

- [ ] **Step 4: Run GREEN**

```bash
uv run pytest tests/unit/query_parser/test_lexer.py -q
```

- [ ] **Step 5: Commit**

```bash
git add src/minilucene/query_parser tests/unit/query_parser/test_lexer.py
git commit -m "feat: tokenize closed query syntax"
```

### Task 2: Parse precedence, fields, phrases, and prefixes

**Files:**
- Create: `src/minilucene/query_parser/parser.py`
- Create: `tests/unit/query_parser/test_parser.py`

- [ ] **Step 1: Write AST equality tests**

```python
from minilucene.query import (
    BooleanClause,
    BooleanQuery,
    Occur,
    PhraseQuery,
    PrefixQuery,
    TermQuery,
)
from minilucene.query_parser import parse_query


def test_and_binds_tighter_than_or(schema):
    assert parse_query("a OR b AND c", schema, "body") == BooleanQuery(
        (
            BooleanClause(Occur.SHOULD, TermQuery("body", "a")),
            BooleanClause(
                Occur.SHOULD,
                BooleanQuery(
                    (
                        BooleanClause(Occur.MUST, TermQuery("body", "b")),
                        BooleanClause(Occur.MUST, TermQuery("body", "c")),
                    )
                ),
            ),
        )
    )


def test_fielded_phrase_is_analyzed_with_positions(schema):
    assert parse_query('body:"distributed the system"', schema, "body") == (
        PhraseQuery("body", ("distributed", "system"), positions=(0, 2))
    )


def test_fielded_prefix(schema):
    assert parse_query("title:kaf*", schema, "body") == PrefixQuery(
        "title", "kaf"
    )
```

Cover parentheses, unary NOT/minus, implicit OR, unknown/non-indexed fields,
empty analyzer output, only-negative query semantics, and syntax offsets.

- [ ] **Step 2: Run RED**

```bash
uv run pytest tests/unit/query_parser/test_parser.py -q
```

- [ ] **Step 3: Implement recursive descent**

Functions:

```text
parse_or
→ parse_and
→ parse_unary
→ parse_primary
```

Adjacent primaries are implicit OR. Field scope applies to exactly one term,
phrase, prefix, or parenthesized expression. Bare expressions use
`default_field`. Analyze text through the schema field analyzer; normalize
phrase positions by subtracting the first surviving position and never
renumber later stopword gaps.

- [ ] **Step 4: Run GREEN**

```bash
uv run pytest tests/unit/query_parser/test_parser.py -q
```

- [ ] **Step 5: Commit**

```bash
git add src/minilucene/query_parser/parser.py src/minilucene/query_parser/__init__.py tests/unit/query_parser/test_parser.py
git commit -m "feat: parse queries into the closed AST"
```

### Task 3: Rewrite prefix queries with a hard expansion cap

**Files:**
- Create: `src/minilucene/search/rewrite.py`
- Modify: `src/minilucene/reader.py`
- Create: `tests/contract/test_prefix_rewrite.py`

- [ ] **Step 1: Write sorted expansion and overflow tests**

```python
import pytest

from minilucene.errors import TooManyTermsError
from minilucene.query import PrefixQuery


def test_prefix_expands_sorted_terms_without_scanning_stored_docs(reader):
    rewritten = reader.rewrite(PrefixQuery("body", "app"), max_terms=3)
    assert rewritten.positive_terms() == (
        ("body", "app"),
        ("body", "apple"),
        ("body", "application"),
    )


def test_prefix_expansion_fails_instead_of_truncating(reader):
    with pytest.raises(TooManyTermsError) as error:
        reader.rewrite(PrefixQuery("body", "a"), max_terms=2)
    assert error.value.limit == 2
```

- [ ] **Step 2: Run RED**

```bash
uv run pytest tests/contract/test_prefix_rewrite.py -q
```

- [ ] **Step 3: Implement rewrite**

Build one sorted per-field term union from segment dictionaries. Use binary
search to find the prefix start, collect until the prefix stops matching, and
raise on the `(limit + 1)`th term. Rewrite to positive term clauses; zero
expansions become a match-none internal query. Apply recursively inside boolean
queries.

- [ ] **Step 4: Run GREEN**

```bash
uv run pytest tests/contract/test_prefix_rewrite.py -q
```

- [ ] **Step 5: Commit**

```bash
git add src/minilucene/search/rewrite.py src/minilucene/reader.py tests/contract/test_prefix_rewrite.py
git commit -m "feat: bound prefix query expansion"
```

### Task 4: Highlight matching stored text safely

**Files:**
- Create: `src/minilucene/highlight.py`
- Modify: `src/minilucene/search/results.py`
- Modify: `src/minilucene/search/searcher.py`
- Create: `tests/contract/test_highlighting.py`

- [ ] **Step 1: Write term, phrase, escape, and eligibility tests**

```python
def test_highlight_uses_original_offsets_and_escapes_text(searcher):
    result = searcher.search_text(
        '"follower replicas"',
        default_field="body",
        top_k=1,
        highlight_fields=("body",),
    )
    assert result.hits[0].highlights["body"] == (
        "Kafka &amp; <em>follower replicas</em>."
    )


def test_nonstored_or_keyword_field_cannot_be_highlighted(searcher):
    with pytest.raises(ValueError, match="stored TextField"):
        searcher.search(
            TermQuery("author", "jonah"),
            top_k=1,
            highlight_fields=("author",),
        )
```

Add tests for lowercase matching with original case, overlapping term offsets,
phrase gaps, no match, and literal `<script>` escaping.

- [ ] **Step 2: Run RED**

```bash
uv run pytest tests/contract/test_highlighting.py -q
```

- [ ] **Step 3: Implement re-analysis highlighting**

Rewrite the query first. Extract positive term and phrase constraints for one
field. Re-analyze stored text, identify matching token offsets and matched
phrase position sequences, merge overlapping/adjacent intervals, escape every
plain and matched slice separately, and wrap matched slices with `<em>`.
Return one complete escaped field value per requested field; no fragment
scoring is performed.

- [ ] **Step 4: Run GREEN**

```bash
uv run pytest tests/contract/test_highlighting.py -q
```

- [ ] **Step 5: Commit**

```bash
git add src/minilucene/highlight.py src/minilucene/search/results.py src/minilucene/search/searcher.py tests/contract/test_highlighting.py
git commit -m "feat: highlight stored text from analyzer offsets"
```

### Task 5: Implement relevance metrics as pure consumers

**Files:**
- Create: `src/minilucene/evaluation.py`
- Create: `tests/evaluation/test_metrics.py`

- [ ] **Step 1: Write hand-computed metric tests**

```python
import pytest

from minilucene.evaluation import (
    mean_reciprocal_rank,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)


def test_binary_metrics():
    ranked = ("d1", "d2", "d3")
    relevant = {"d2", "d3", "d4"}
    assert precision_at_k(ranked, relevant, 2) == 0.5
    assert recall_at_k(ranked, relevant, 2) == pytest.approx(1 / 3)
    assert mean_reciprocal_rank([ranked], [relevant]) == 0.5


def test_ndcg_uses_graded_relevance():
    assert ndcg_at_k(("b", "a"), {"a": 3, "b": 1}, 2) < 1.0
```

Cover `k=0`, empty relevant sets, duplicate ranked IDs rejection, multiple
queries in MRR, ideal DCG zero, and finite/nonnegative grades.

- [ ] **Step 2: Run RED**

```bash
uv run pytest tests/evaluation/test_metrics.py -q
```

- [ ] **Step 3: Implement pure functions**

The module imports no index, writer, reader, scorer, or storage modules.
Metrics accept sequences/mappings and return floats. Invalid inputs fail
before arithmetic.

- [ ] **Step 4: Run GREEN**

```bash
uv run pytest tests/evaluation/test_metrics.py -q
```

- [ ] **Step 5: Commit**

```bash
git add src/minilucene/evaluation.py tests/evaluation/test_metrics.py
git commit -m "feat: add deterministic relevance metrics"
```

### Task 6: Freeze the accepted corpus and ranking counterexamples

**Files:**
- Create: `tests/fixtures/corpus.json`
- Create: `tests/fixtures/queries.json`
- Create: `tests/fixtures/qrels.json`
- Create: `tests/evaluation/test_reference_corpus.py`

- [ ] **Step 1: Add deterministic fixture validation**

Fixture schema:

```json
{
  "documents": [
    {
      "id": "doc-1",
      "title": "Understanding Kafka Replication",
      "body": "Kafka uses partition leaders and follower replicas.",
      "author": "jonah"
    }
  ]
}
```

Queries have stable IDs, query text, and default field. Qrels map query ID to
document ID and integer grade.

- [ ] **Step 2: Add behavior counterexamples**

Tests prove:

- title boost changes order relative to equal body matches;
- 100 repeated terms do not gain 20 times the score of five occurrences;
- phrase query excludes separated positions matched by boolean conjunction;
- deleted documents affect neither hits nor IDF/average length;
- rankings and approximate scores are equal before and after
  flush/commit/reopen/merge.

- [ ] **Step 3: Run RED or expose failures**

```bash
uv run pytest tests/evaluation/test_reference_corpus.py -q
```

Expected: fixture loader or one asserted behavior is absent before implementation.

- [ ] **Step 4: Add a read-only fixture loader and make behaviors pass**

Keep fixture loading in `tests/support/reference_corpus.py`; do not add
production corpus assumptions.

- [ ] **Step 5: Run GREEN**

```bash
uv run pytest tests/evaluation/test_reference_corpus.py -q
```

- [ ] **Step 6: Commit**

```bash
git add tests/fixtures tests/support/reference_corpus.py tests/evaluation/test_reference_corpus.py
git commit -m "test: freeze reference relevance corpus"
```

### Task 7: Add one thin local CLI adapter

**Files:**
- Create: `src/minilucene/cli.py`
- Modify: `pyproject.toml`
- Create: `tests/contract/test_cli.py`

- [ ] **Step 1: Write subprocess-facing CLI tests**

Commands:

```text
minilucene create INDEX --schema SCHEMA_JSON
minilucene add INDEX DOCUMENT_JSON...
minilucene search INDEX QUERY --default-field body --top-k 10
minilucene delete INDEX FIELD TERM
minilucene merge INDEX SEGMENT...
```

Tests invoke `cli.main(argv)` with captured stdout/stderr. Search emits one
canonical JSON object containing `total_hits` and ordered hits. Domain failures
exit `2` with one concise stderr line; unexpected failures are not swallowed.

- [ ] **Step 2: Run RED**

```bash
uv run pytest tests/contract/test_cli.py -q
```

- [ ] **Step 3: Implement adapter-only CLI**

Parse arguments, deserialize JSON, call only public `Index`, writer, parser,
and searcher APIs, close every owner through context managers, and serialize
results. Do not access codecs, manifests, internal postings, or registry state.

- [ ] **Step 4: Run GREEN**

```bash
uv run pytest tests/contract/test_cli.py -q
```

- [ ] **Step 5: Commit**

```bash
git add src/minilucene/cli.py pyproject.toml tests/contract/test_cli.py
git commit -m "feat: add thin local search CLI"
```

### Task 8: Publish README and executable behavior matrix

**Files:**
- Create: `README.md`
- Create: `docs/behavior-matrix.md`
- Create: `tests/contract/test_behavior_matrix.py`

- [ ] **Step 1: Write matrix-link validation**

The test parses Markdown rows and asserts every row has:

```text
feature | public API | semantic boundary | executable test node ID
```

For each node ID, run pytest collection programmatically and assert exactly one
test is collected. Reject duplicate features and duplicate node IDs.

- [ ] **Step 2: Run RED**

```bash
uv run pytest tests/contract/test_behavior_matrix.py -q
```

- [ ] **Step 3: Write README**

README includes:

- what MiniLucene explains;
- direct Python quickstart;
- schema/analyzer/query/storage/NRT mental model;
- flush vs refresh vs commit;
- delete/update/merge semantics;
- exact V1 non-goals;
- development and verification commands;
- link to design, segment format, phase reports, and behavior matrix.

It must not claim Lucene format/API compatibility, production performance,
distributed behavior, vector retrieval, or course completion.

- [ ] **Step 4: Write behavior matrix**

Map every V1 feature and required failure experiment to a stable test node ID.
Include negative rows for TCP/HTTP, distribution, vector retrieval, Lucene
codec compatibility, and automatic merge scheduling, pointing to explicit
scope tests/document checks rather than implied support.

- [ ] **Step 5: Run GREEN**

```bash
uv run pytest tests/contract/test_behavior_matrix.py -q
```

- [ ] **Step 6: Commit**

```bash
git add README.md docs/behavior-matrix.md tests/contract/test_behavior_matrix.py
git commit -m "docs: map MiniLucene behavior to executable evidence"
```

### Task 9: Add complete failure and owner-zero acceptance

**Files:**
- Create: `tests/acceptance/test_failure_matrix.py`
- Create: `tests/acceptance/test_owner_zero.py`
- Create: `tests/acceptance/test_end_to_end.py`

- [ ] **Step 1: Consolidate failure matrix**

Parameterized acceptance covers:

1. validation/analyzer failure before RAM mutation;
2. segment data failure before rename;
3. complete orphan before manifest replace;
4. successful manifest replace with old files retained;
5. checksum corruption on open;
6. refresh-visible state lost after process reopen;
7. stale reader after refresh/delete/update/merge;
8. merge publish failure before writer-set swap;
9. repeated close and cleanup failure aggregation.

Each case asserts public behavior and authoritative on-disk roots, not only an
internal mock call.

- [ ] **Step 2: Add realistic end-to-end test**

Use the documented public API to create an index, add fielded corpus, commit,
reopen, parse boolean phrase query, BM25 Top-K, retrieve stored fields,
highlight, refresh new data, update, delete, commit, retain an old reader,
merge, reopen, and evaluate result IDs.

- [ ] **Step 3: Add owner-zero test**

After all external readers/writers close:

```python
diagnostics = index.lifecycle_diagnostics()
assert diagnostics.writer_owner is None
assert diagnostics.reader_owners == ()
assert diagnostics.segment_owners == {}
assert diagnostics.temporary_jobs == ()
assert not (index.path / ".writer.lock").exists()
assert not list(index.path.rglob(".tmp-*"))
```

- [ ] **Step 4: Run RED or expose uncovered cases**

```bash
uv run pytest tests/acceptance/test_failure_matrix.py tests/acceptance/test_owner_zero.py tests/acceptance/test_end_to_end.py -q
```

- [ ] **Step 5: Close only the evidenced gaps**

Change production code only for failures demonstrated by these tests. Preserve
the frozen public and storage contracts.

- [ ] **Step 6: Run GREEN**

```bash
uv run pytest tests/acceptance/test_failure_matrix.py tests/acceptance/test_owner_zero.py tests/acceptance/test_end_to_end.py -q
```

- [ ] **Step 7: Commit**

```bash
git add src tests/acceptance
git commit -m "test: accept MiniLucene failure and lifecycle semantics"
```

### Task 10: Final V1 acceptance and repository closeout

**Files:**
- Create: `docs/final-acceptance.md`
- Modify: `docs/behavior-matrix.md` only if collected node IDs changed

- [ ] **Step 1: Run every verification gate**

```bash
uv sync --dev
uv run ruff check src tests tools
uv run pytest -q
uv run python -m compileall -q src tests tools
git diff --check
rg -n 'TBD|TODO|FIXME|NotImplementedError|pass$' src tests docs README.md || true
git status --short
```

The text scan may match explanatory prose only. It must not find unfinished
production branches, skipped acceptance, or deferred core behavior.

- [ ] **Step 2: Run installed-package smoke test**

```bash
tmp_dir="$(mktemp -d)"
uv build
uv venv "$tmp_dir/venv"
uv pip install --python "$tmp_dir/venv/bin/python" dist/*.whl
"$tmp_dir/venv/bin/python" -c "import minilucene; print(minilucene.__version__)"
"$tmp_dir/venv/bin/minilucene" --help
```

Expected: wheel installs, import works, CLI help exits `0`.

- [ ] **Step 3: Audit scope**

```bash
test ! -d course
test ! -d chapters
rg -n 'FastAPI|Flask|socket|RESP|Raft|Sentinel|Cluster|HNSW|VectorField' src || true
```

Expected: no course directories; the source scan has no implementation of
network, distributed, or vector behavior.

- [ ] **Step 4: Write final acceptance evidence**

`docs/final-acceptance.md` records:

- exact git commit tested;
- test counts and commands;
- behavior-matrix validation;
- crash/failure cases;
- owner-zero diagnostics;
- package smoke output;
- V1 supported and excluded scope;
- statement that course design remains a separate future task.

- [ ] **Step 5: Commit and re-run clean-tree checks**

```bash
git add docs/final-acceptance.md docs/behavior-matrix.md
git commit -m "docs: record MiniLucene V1 final acceptance"
uv run ruff check src tests tools
uv run pytest -q
uv run python -m compileall -q src tests tools
git diff --check
git status --short
git log --oneline --decorate -12
```

Expected: every command exits `0`, the worktree is clean, and the latest commit
is `docs: record MiniLucene V1 final acceptance`.

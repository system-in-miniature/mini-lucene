# Stage 24 · Recursive-descent query parser

### Goal

Build recursive-descent query parser and explain its boundary from an executable counterexample, runtime state, and the critical statement.

??? note "Deliverable files"
    - `src/minilucene/analysis/standard.py`
    - `src/minilucene/query_parser/__init__.py`
    - `src/minilucene/query_parser/parser.py`
    - `tests/unit/query_parser/test_parser.py`

### The problem at this point

Tokens remain ambiguous until precedence, grouping, field scope, unary operators, and implicit composition are explicit.

### Test contract

#### See the failure first

Tests compare ASTs for mixed AND/OR/NOT, nested groups, fields, phrases, prefixes, and incomplete expressions.

??? note "File diff: tests/unit/query_parser/test_parser.py"
    ```diff
    diff --git a/tests/unit/query_parser/test_parser.py b/tests/unit/query_parser/test_parser.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..7fbfae514708da6539673e6b3fdbbe319fba30e1
    --- /dev/null
    +++ b/tests/unit/query_parser/test_parser.py
    @@ -0,0 +1,107 @@
    +import pytest
    +
    +from minilucene import Schema, StoredField, TextField
    +from minilucene.query import (
    +    BooleanClause,
    +    BooleanQuery,
    +    Occur,
    +    PhraseQuery,
    +    PrefixQuery,
    +    TermQuery,
    +)
    +from minilucene.query_parser import QuerySyntaxError, parse_query
    +
    +
    +@pytest.fixture
    +def schema():
    +    return Schema(
    +        title=TextField(stored=True),
    +        body=TextField(stored=True),
    +        raw=StoredField(),
    +    )
    +
    +
    +def test_and_binds_tighter_than_or(schema):
    +    assert parse_query("a OR b AND c", schema, "body") == BooleanQuery(
    +        (
    +            BooleanClause(Occur.SHOULD, TermQuery("body", "a")),
    +            BooleanClause(
    +                Occur.SHOULD,
    +                BooleanQuery(
    +                    (
    +                        BooleanClause(Occur.MUST, TermQuery("body", "b")),
    +                        BooleanClause(Occur.MUST, TermQuery("body", "c")),
    +                    )
    +                ),
    +            ),
    +        )
    +    )
    +
    +
    +def test_fielded_phrase_is_analyzed_with_positions(schema):
    +    assert parse_query(
    +        'body:"distributed the system"', schema, "body"
    +    ) == PhraseQuery(
    +        "body", ("distributed", "system"), positions=(0, 2)
    +    )
    +
    +
    +def test_fielded_prefix_is_analyzed(schema):
    +    assert parse_query("title:KAF*", schema, "body") == PrefixQuery(
    +        "title", "kaf"
    +    )
    +
    +
    +def test_parentheses_unary_and_implicit_or(schema):
    +    assert parse_query("title:(Kafka rabbit) AND -body:slow", schema, "body") == (
    +        BooleanQuery(
    +            (
    +                BooleanClause(
    +                    Occur.MUST,
    +                    BooleanQuery(
    +                        (
    +                            BooleanClause(
    +                                Occur.SHOULD,
    +                                TermQuery("title", "kafka"),
    +                            ),
    +                            BooleanClause(
    +                                Occur.SHOULD,
    +                                TermQuery("title", "rabbit"),
    +                            ),
    +                        )
    +                    ),
    +                ),
    +                BooleanClause(
    +                    Occur.MUST_NOT, TermQuery("body", "slow")
    +                ),
    +            )
    +        )
    +    )
    +
    +
    +def test_only_negative_query_remains_explicit(schema):
    +    assert parse_query("NOT kafka", schema, "body") == BooleanQuery(
    +        (BooleanClause(Occur.MUST_NOT, TermQuery("body", "kafka")),)
    +    )
    +
    +
    +@pytest.mark.parametrize(
    +    ("source", "message"),
    +    [
    +        ("unknown:value", "unknown field"),
    +        ("raw:value", "not indexed"),
    +        ('body:""', "no searchable terms"),
    +        ("body:!!!", "no searchable terms"),
    +        ("(kafka", "expected"),
    +        ("kafka AND", "expected"),
    +    ],
    +)
    +def test_invalid_queries_report_source_offsets(schema, source, message):
    +    with pytest.raises(QuerySyntaxError, match=message) as error:
    +        parse_query(source, schema, "body")
    +    assert 0 <= error.value.offset <= len(source)
    +
    +
    +def test_invalid_default_field_fails_at_start(schema):
    +    with pytest.raises(QuerySyntaxError, match="default field"):
    +        parse_query("kafka", schema, "missing")
    ```

**What this test locks**

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

**How it constructs the counterexample**

Tests compare ASTs for mixed AND/OR/NOT, nested groups, fields, phrases, prefixes, and incomplete expressions.

**Key test statement**

```python
assert parse_query("a OR b AND c", schema, "body") == BooleanQuery(
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

**What a failure means**

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

A recursive-descent layer per precedence level turns the closed token stream into the same closed query AST used by execution.

### Why this mechanism is necessary

Tokens remain ambiguous until precedence, grouping, field scope, unary operators, and implicit composition are explicit. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

Parsing advances tokens through OR, AND, unary, and primary functions, applies field scope deliberately, and requires full input consumption.

### Mechanism blocks

#### Recursive-descent query parser mechanism

Parsing advances tokens through OR, AND, unary, and primary functions, applies field scope deliberately, and requires full input consumption.

??? note "File diff: src/minilucene/analysis/standard.py"
    ```diff
    diff --git a/src/minilucene/analysis/standard.py b/src/minilucene/analysis/standard.py
    index ff4ce43259b37fda72f547db51a33dcf8834aff1..5eb10552d786f616dde6ab269d7e6f54e1dd84f4 100644
    --- a/src/minilucene/analysis/standard.py
    +++ b/src/minilucene/analysis/standard.py
    @@ -8,6 +8,7 @@ from minilucene.analysis.pipeline import (
     )

     _WORD_PATTERN = re.compile(r"\w+", re.UNICODE)
    +_DEFAULT_STOPWORDS = frozenset({"the"})


     class StandardTokenizer:
    @@ -31,7 +32,7 @@ class KeywordTokenizer:


     def StandardAnalyzer(
    -    *, stopwords: frozenset[str] = frozenset()
    +    *, stopwords: frozenset[str] = _DEFAULT_STOPWORDS
     ) -> Analyzer:
         return Analyzer(
             StandardTokenizer(),
    ```

??? note "File diff: src/minilucene/query_parser/parser.py"
    ```diff
    diff --git a/src/minilucene/query_parser/parser.py b/src/minilucene/query_parser/parser.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..2906eb8ebc3e77685823dbde20d0c45f1b0ba1b6
    --- /dev/null
    +++ b/src/minilucene/query_parser/parser.py
    @@ -0,0 +1,225 @@
    +from dataclasses import dataclass
    +
    +from minilucene.analysis import KeywordAnalyzer, StandardAnalyzer
    +from minilucene.analysis.model import Token
    +from minilucene.query import (
    +    BooleanClause,
    +    BooleanQuery,
    +    Occur,
    +    PhraseQuery,
    +    PrefixQuery,
    +    Query,
    +    TermQuery,
    +)
    +from minilucene.query_parser.errors import QuerySyntaxError
    +from minilucene.query_parser.lexer import LexToken, TokenKind, lex
    +from minilucene.schema import FieldType, Schema
    +
    +
    +@dataclass(frozen=True, slots=True)
    +class _Parsed:
    +    query: Query
    +    prohibited: bool = False
    +
    +
    +class _Parser:
    +    def __init__(
    +        self, source: str, schema: Schema, default_field: str
    +    ) -> None:
    +        self.source = source
    +        self.schema = schema
    +        self.tokens = lex(source)
    +        self.index = 0
    +        self._validate_field(default_field, 0, default=True)
    +        self.default_field = default_field
    +
    +    @property
    +    def current(self) -> LexToken:
    +        return self.tokens[self.index]
    +
    +    def advance(self) -> LexToken:
    +        token = self.current
    +        self.index += 1
    +        return token
    +
    +    def syntax(self, message: str, token: LexToken | None = None):
    +        target = token or self.current
    +        raise QuerySyntaxError(message, target.start, self.source)
    +
    +    def _validate_field(
    +        self, name: str, offset: int, *, default: bool = False
    +    ) -> FieldType:
    +        label = "default field" if default else "field"
    +        if name not in self.schema:
    +            raise QuerySyntaxError(
    +                f"unknown {label}: {name}", offset, self.source
    +            )
    +        field = self.schema[name]
    +        if not field.indexed:
    +            raise QuerySyntaxError(
    +                f"{label} is not indexed: {name}", offset, self.source
    +            )
    +        return field
    +
    +    def _analyze(
    +        self, field_name: str, text: str, token: LexToken
    +    ) -> tuple[Token, ...]:
    +        field = self._validate_field(field_name, token.start)
    +        if field.analyzer_name == "standard":
    +            analyzed = StandardAnalyzer().analyze(text)
    +        elif field.analyzer_name == "keyword":
    +            analyzed = KeywordAnalyzer().analyze(text)
    +        else:
    +            self.syntax(
    +                f"unknown analyzer for field: {field_name}", token
    +            )
    +        if not analyzed:
    +            self.syntax("query text produced no searchable terms", token)
    +        return analyzed
    +
    +    def parse(self) -> Query:
    +        if self.current.kind is TokenKind.EOF:
    +            self.syntax("expected query expression")
    +        parsed = self.parse_or(self.default_field)
    +        if self.current.kind is not TokenKind.EOF:
    +            self.syntax("unexpected token")
    +        return self._materialize(parsed)
    +
    +    @staticmethod
    +    def _materialize(parsed: _Parsed) -> Query:
    +        if not parsed.prohibited:
    +            return parsed.query
    +        return BooleanQuery(
    +            (BooleanClause(Occur.MUST_NOT, parsed.query),)
    +        )
    +
    +    def parse_or(self, field: str) -> _Parsed:
    +        items = [self.parse_and(field)]
    +        while True:
    +            if self.current.kind is TokenKind.OR:
    +                self.advance()
    +                items.append(self.parse_and(field))
    +            elif self.current.kind in {
    +                TokenKind.WORD,
    +                TokenKind.PHRASE,
    +                TokenKind.PREFIX,
    +                TokenKind.LPAREN,
    +                TokenKind.NOT,
    +                TokenKind.MINUS,
    +            }:
    +                items.append(self.parse_and(field))
    +            else:
    +                break
    +        if len(items) == 1:
    +            return items[0]
    +        return _Parsed(
    +            BooleanQuery(
    +                tuple(
    +                    BooleanClause(
    +                        Occur.MUST_NOT
    +                        if item.prohibited
    +                        else Occur.SHOULD,
    +                        item.query,
    +                    )
    +                    for item in items
    +                )
    +            )
    +        )
    +
    +    def parse_and(self, field: str) -> _Parsed:
    +        items = [self.parse_unary(field)]
    +        while self.current.kind is TokenKind.AND:
    +            self.advance()
    +            items.append(self.parse_unary(field))
    +        if len(items) == 1:
    +            return items[0]
    +        return _Parsed(
    +            BooleanQuery(
    +                tuple(
    +                    BooleanClause(
    +                        Occur.MUST_NOT if item.prohibited else Occur.MUST,
    +                        item.query,
    +                    )
    +                    for item in items
    +                )
    +            )
    +        )
    +
    +    def parse_unary(self, field: str) -> _Parsed:
    +        prohibited = False
    +        while self.current.kind in {TokenKind.NOT, TokenKind.MINUS}:
    +            self.advance()
    +            prohibited = not prohibited
    +        primary = self.parse_primary(field)
    +        return _Parsed(
    +            primary.query, prohibited ^ primary.prohibited
    +        )
    +
    +    def parse_primary(self, field: str) -> _Parsed:
    +        token = self.current
    +        if (
    +            token.kind is TokenKind.WORD
    +            and self.tokens[self.index + 1].kind is TokenKind.COLON
    +        ):
    +            field_token = self.advance()
    +            self.advance()
    +            self._validate_field(field_token.text, field_token.start)
    +            return self.parse_primary(field_token.text)
    +
    +        if token.kind is TokenKind.LPAREN:
    +            self.advance()
    +            if self.current.kind is TokenKind.RPAREN:
    +                self.syntax("expected query expression")
    +            parsed = self.parse_or(field)
    +            if self.current.kind is not TokenKind.RPAREN:
    +                self.syntax("expected closing parenthesis")
    +            self.advance()
    +            return parsed
    +
    +        if token.kind is TokenKind.WORD:
    +            self.advance()
    +            tokens = self._analyze(field, token.text, token)
    +            queries = tuple(
    +                TermQuery(field, analyzed.term) for analyzed in tokens
    +            )
    +            if len(queries) == 1:
    +                return _Parsed(queries[0])
    +            return _Parsed(
    +                BooleanQuery(
    +                    tuple(
    +                        BooleanClause(Occur.SHOULD, query)
    +                        for query in queries
    +                    )
    +                )
    +            )
    +
    +        if token.kind is TokenKind.PHRASE:
    +            self.advance()
    +            tokens = self._analyze(field, token.text, token)
    +            first_position = tokens[0].position
    +            return _Parsed(
    +                PhraseQuery(
    +                    field,
    +                    tuple(item.term for item in tokens),
    +                    positions=tuple(
    +                        item.position - first_position for item in tokens
    +                    ),
    +                )
    +            )
    +
    +        if token.kind is TokenKind.PREFIX:
    +            self.advance()
    +            tokens = self._analyze(field, token.text, token)
    +            if len(tokens) != 1:
    +                self.syntax(
    +                    "prefix must analyze to exactly one term", token
    +                )
    +            return _Parsed(PrefixQuery(field, tokens[0].term))
    +
    +        self.syntax("expected query expression")
    +
    +
    +def parse_query(
    +    source: str, schema: Schema, default_field: str
    +) -> Query:
    +    return _Parser(source, schema, default_field).parse()
    ```

**What it is and why it appears**

A recursive-descent layer per precedence level turns the closed token stream into the same closed query AST used by execution.

**Runtime role**

Parsing advances tokens through OR, AND, unary, and primary functions, applies field scope deliberately, and requires full input consumption.

**Statement understanding**

Full consumption rejects valid prefixes followed by garbage; separate precedence functions make grouping rules visible in code.

#### Package, fixture, and project support

Keep exports, test corpora, dependencies, and the runtime environment reproducible.

??? note "Supporting file diffs (1 file)"
    **`src/minilucene/query_parser/__init__.py`**

    ```diff
    diff --git a/src/minilucene/query_parser/__init__.py b/src/minilucene/query_parser/__init__.py
    index d64eefe8c0f54110849b4fce798759d79df474da..bfb0fc09a4863dfda4181098598e1ce0203fa2bb 100644
    --- a/src/minilucene/query_parser/__init__.py
    +++ b/src/minilucene/query_parser/__init__.py
    @@ -1,4 +1,11 @@
     from minilucene.query_parser.errors import QuerySyntaxError
     from minilucene.query_parser.lexer import LexToken, TokenKind, lex
    +from minilucene.query_parser.parser import parse_query

    -__all__ = ["LexToken", "QuerySyntaxError", "TokenKind", "lex"]
    +__all__ = [
    +    "LexToken",
    +    "QuerySyntaxError",
    +    "TokenKind",
    +    "lex",
    +    "parse_query",
    +]
    ```


### Verification evidence

Run `uv run pytest -q $(cat journey/stages/24-query-parser/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Full consumption rejects valid prefixes followed by garbage; separate precedence functions make grouping rules visible in code.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 9](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/09-query-language.md)

[Complete reference patch / 完整参考补丁](https://github.com/system-in-miniature/mini-lucene/blob/main/journey/stages/24-query-parser/stage.patch)

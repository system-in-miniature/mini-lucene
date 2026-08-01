# Stage 24 · 递归下降 Query Parser

### 目标

实现递归下降 Query Parser，并能从可执行反例、运行时状态与关键语句解释其边界。

??? note "交付文件"
    - `src/minilucene/analysis/standard.py`
    - `src/minilucene/query_parser/__init__.py`
    - `src/minilucene/query_parser/parser.py`
    - `tests/unit/query_parser/test_parser.py`

### 当前遇到的问题

Token 在 Precedence、Grouping、Field Scope、Unary Operator 与隐式组合明确前仍有歧义。

### 测试契约

#### 先看会坏在哪里

测试比较混合 AND/OR/NOT、嵌套 Group、Field、Phrase、Prefix 与不完整表达式的 AST。

??? note "文件差异：tests/unit/query_parser/test_parser.py"
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

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

测试比较混合 AND/OR/NOT、嵌套 Group、Field、Phrase、Prefix 与不完整表达式的 AST。

**关键测试语句**

```python
assert parse_query("a OR b AND c", schema, "body") == BooleanQuery(
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

每个 Precedence Level 一层递归下降，把封闭 Token Stream 转成执行使用的同一封闭 Query AST。

### 为什么需要这个机制

Token 在 Precedence、Grouping、Field Scope、Unary Operator 与隐式组合明确前仍有歧义。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Parsing 通过 OR、AND、Unary 与 Primary Function 推进 Token，有意应用 Field Scope，并要求完整消费输入。

### 机制板块

#### 递归下降 Query Parser机制

Parsing 通过 OR、AND、Unary 与 Primary Function 推进 Token，有意应用 Field Scope，并要求完整消费输入。

??? note "文件差异：src/minilucene/analysis/standard.py"
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

??? note "文件差异：src/minilucene/query_parser/parser.py"
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

**是什么，为什么现在需要**

每个 Precedence Level 一层递归下降，把封闭 Token Stream 转成执行使用的同一封闭 Query AST。

**在运行时做什么**

Parsing 通过 OR、AND、Unary 与 Primary Function 推进 Token，有意应用 Field Scope，并要求完整消费输入。

**关键语句理解**

完整消费拒绝后接垃圾的有效前缀；分离的 Precedence Function 让 Grouping Rule 在代码中可见。

#### 包、Fixture 与工程支撑

保持包导出、测试语料、依赖与运行环境可复现。

??? note "支撑文件差异（1 个文件）"
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


### 验证证据

运行 `uv run pytest -q $(cat journey/stages/24-query-parser/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

完整消费拒绝后接垃圾的有效前缀；分离的 Precedence Function 让 Grouping Rule 在代码中可见。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 9 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/09-query-language.md)

[Complete reference patch / 完整参考补丁](https://github.com/system-in-miniature/mini-lucene/blob/main/journey/stages/24-query-parser/stage.patch)

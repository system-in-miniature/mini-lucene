# Stage 23 · 封闭 Query Lexer

### 目标

实现封闭 Query Lexer，并能从可执行反例、运行时状态与关键语句解释其边界。

??? note "交付文件"
    - `src/minilucene/query_parser/__init__.py`
    - `src/minilucene/query_parser/errors.py`
    - `src/minilucene/query_parser/lexer.py`
    - `tests/unit/query_parser/test_lexer.py`

### 当前遇到的问题

用户 Query Text 需要保留 Source Span，并区分 Operator、Phrase、Prefix、Field 与 Error 的 Token。

### 测试契约

#### 先看会坏在哪里

Lexer 测试包含 Escape、未闭 Quote、非法 Star、Hyphenated Text 与精确 Error Offset。

??? note "文件差异：tests/unit/query_parser/test_lexer.py"
    ```diff
    diff --git a/tests/unit/query_parser/test_lexer.py b/tests/unit/query_parser/test_lexer.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..7c11d3b431745c3deece7031d497fc9390dcf2dc
    --- /dev/null
    +++ b/tests/unit/query_parser/test_lexer.py
    @@ -0,0 +1,62 @@
    +import pytest
    +
    +from minilucene.query_parser.errors import QuerySyntaxError
    +from minilucene.query_parser.lexer import TokenKind, lex
    +
    +
    +def test_lexer_preserves_offsets_and_quoted_text():
    +    tokens = lex('title:kafka AND body:"follower replicas"')
    +    assert [(token.kind, token.text, token.start) for token in tokens] == [
    +        (TokenKind.WORD, "title", 0),
    +        (TokenKind.COLON, ":", 5),
    +        (TokenKind.WORD, "kafka", 6),
    +        (TokenKind.AND, "AND", 12),
    +        (TokenKind.WORD, "body", 16),
    +        (TokenKind.COLON, ":", 20),
    +        (TokenKind.PHRASE, "follower replicas", 21),
    +        (TokenKind.EOF, "", 40),
    +    ]
    +
    +
    +def test_lexer_recognizes_grouping_unary_and_case_insensitive_operators():
    +    tokens = lex("(a and -b) Or NoT c")
    +    assert [token.kind for token in tokens] == [
    +        TokenKind.LPAREN,
    +        TokenKind.WORD,
    +        TokenKind.AND,
    +        TokenKind.MINUS,
    +        TokenKind.WORD,
    +        TokenKind.RPAREN,
    +        TokenKind.OR,
    +        TokenKind.NOT,
    +        TokenKind.WORD,
    +        TokenKind.EOF,
    +    ]
    +
    +
    +def test_lexer_decodes_only_quote_and_backslash_escapes_in_phrases():
    +    tokens = lex(r'"a \"quote\" and \\ path"')
    +    assert tokens[0].kind is TokenKind.PHRASE
    +    assert tokens[0].text == 'a "quote" and \\ path'
    +
    +
    +def test_lexer_marks_one_trailing_star_as_prefix():
    +    tokens = lex("kaf*")
    +    assert (tokens[0].kind, tokens[0].text) == (
    +        TokenKind.PREFIX,
    +        "kaf",
    +    )
    +
    +
    +@pytest.mark.parametrize("source", ["*kaf", "ka*f", "kaf**", "*"])
    +def test_illegal_wildcard_placement_reports_its_offset(source):
    +    with pytest.raises(QuerySyntaxError) as error:
    +        lex(source)
    +    assert error.value.offset == source.index("*")
    +
    +
    +def test_unclosed_phrase_reports_opening_offset_and_caret():
    +    with pytest.raises(QuerySyntaxError) as error:
    +        lex('"broken')
    +    assert error.value.offset == 0
    +    assert '"broken\n^' in str(error.value)
    ```

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

Lexer 测试包含 Escape、未闭 Quote、非法 Star、Hyphenated Text 与精确 Error Offset。

**关键测试语句**

```python
assert [(token.kind, token.text, token.start) for token in tokens] == [
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Lexer 是从 Character 到有限 Token Vocabulary 的保留证据翻译；它不决定 Precedence 或 Index Meaning。

### 为什么需要这个机制

用户 Query Text 需要保留 Source Span，并区分 Operator、Phrase、Prefix、Field 与 Error 的 Token。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Cursor 消费 Character、记录 Start/End Span、识别 Reserved Syntax，并在第一个不可能 Byte 发出类型化 Lexical Failure。

### 机制板块

#### 封闭 Query Lexer机制

Cursor 消费 Character、记录 Start/End Span、识别 Reserved Syntax，并在第一个不可能 Byte 发出类型化 Lexical Failure。

??? note "文件差异：src/minilucene/query_parser/errors.py"
    ```diff
    diff --git a/src/minilucene/query_parser/errors.py b/src/minilucene/query_parser/errors.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..0688290ad900925d704bf3d815f293463859d716
    --- /dev/null
    +++ b/src/minilucene/query_parser/errors.py
    @@ -0,0 +1,6 @@
    +class QuerySyntaxError(ValueError):
    +    def __init__(self, message: str, offset: int, source: str) -> None:
    +        self.message = message
    +        self.offset = offset
    +        self.source = source
    +        super().__init__(f"{message} at offset {offset}\n{source}\n{' ' * offset}^")
    ```

??? note "文件差异：src/minilucene/query_parser/lexer.py"
    ```diff
    diff --git a/src/minilucene/query_parser/lexer.py b/src/minilucene/query_parser/lexer.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..d62c96b96fbeeaeb7977170b74953cf6b7eeadf5
    --- /dev/null
    +++ b/src/minilucene/query_parser/lexer.py
    @@ -0,0 +1,124 @@
    +from dataclasses import dataclass
    +from enum import StrEnum
    +
    +from minilucene.query_parser.errors import QuerySyntaxError
    +
    +
    +class TokenKind(StrEnum):
    +    WORD = "WORD"
    +    PHRASE = "PHRASE"
    +    PREFIX = "PREFIX"
    +    AND = "AND"
    +    OR = "OR"
    +    NOT = "NOT"
    +    COLON = "COLON"
    +    LPAREN = "LPAREN"
    +    RPAREN = "RPAREN"
    +    MINUS = "MINUS"
    +    EOF = "EOF"
    +
    +
    +@dataclass(frozen=True, slots=True)
    +class LexToken:
    +    kind: TokenKind
    +    text: str
    +    start: int
    +    end: int
    +
    +
    +_PUNCTUATION = {
    +    ":": TokenKind.COLON,
    +    "(": TokenKind.LPAREN,
    +    ")": TokenKind.RPAREN,
    +    "-": TokenKind.MINUS,
    +}
    +_OPERATORS = {
    +    "AND": TokenKind.AND,
    +    "OR": TokenKind.OR,
    +    "NOT": TokenKind.NOT,
    +}
    +
    +
    +def _lex_phrase(source: str, start: int) -> tuple[LexToken, int]:
    +    index = start + 1
    +    characters: list[str] = []
    +    while index < len(source):
    +        character = source[index]
    +        if character == '"':
    +            return (
    +                LexToken(
    +                    TokenKind.PHRASE,
    +                    "".join(characters),
    +                    start,
    +                    index + 1,
    +                ),
    +                index + 1,
    +            )
    +        if character == "\\":
    +            escape_offset = index
    +            index += 1
    +            if index >= len(source):
    +                raise QuerySyntaxError(
    +                    "unterminated phrase escape", escape_offset, source
    +                )
    +            escaped = source[index]
    +            if escaped not in {'"', "\\"}:
    +                raise QuerySyntaxError(
    +                    "only quote and backslash may be escaped",
    +                    escape_offset,
    +                    source,
    +                )
    +            characters.append(escaped)
    +        else:
    +            characters.append(character)
    +        index += 1
    +    raise QuerySyntaxError("unclosed phrase", start, source)
    +
    +
    +def _lex_word(source: str, start: int) -> tuple[LexToken, int]:
    +    index = start
    +    while (
    +        index < len(source)
    +        and not source[index].isspace()
    +        and source[index] not in ':()-"'
    +    ):
    +        index += 1
    +    text = source[start:index]
    +    star = text.find("*")
    +    if star != -1:
    +        if star == 0 or star != len(text) - 1 or text.count("*") != 1:
    +            raise QuerySyntaxError(
    +                "asterisk is only legal once after a non-empty prefix",
    +                start + star,
    +                source,
    +            )
    +        return LexToken(TokenKind.PREFIX, text[:-1], start, index), index
    +    operator = _OPERATORS.get(text.upper())
    +    return LexToken(operator or TokenKind.WORD, text, start, index), index
    +
    +
    +def lex(source: str) -> tuple[LexToken, ...]:
    +    if not isinstance(source, str):
    +        raise TypeError("query source must be a string")
    +    tokens: list[LexToken] = []
    +    index = 0
    +    while index < len(source):
    +        character = source[index]
    +        if character.isspace():
    +            index += 1
    +            continue
    +        if character == '"':
    +            token, index = _lex_phrase(source, index)
    +            tokens.append(token)
    +            continue
    +        kind = _PUNCTUATION.get(character)
    +        if kind is not None:
    +            tokens.append(LexToken(kind, character, index, index + 1))
    +            index += 1
    +            continue
    +        token, index = _lex_word(source, index)
    +        if not token.text:
    +            raise QuerySyntaxError("unexpected character", token.start, source)
    +        tokens.append(token)
    +    tokens.append(LexToken(TokenKind.EOF, "", len(source), len(source)))
    +    return tuple(tokens)
    ```

**是什么，为什么现在需要**

Lexer 是从 Character 到有限 Token Vocabulary 的保留证据翻译；它不决定 Precedence 或 Index Meaning。

**在运行时做什么**

Cursor 消费 Character、记录 Start/End Span、识别 Reserved Syntax，并在第一个不可能 Byte 发出类型化 Lexical Failure。

**关键语句理解**

Tokenization 全程保留 Span，让后续 Parser Error 指向用户原文而非归一化重建文本。

#### 包、Fixture 与工程支撑

保持包导出、测试语料、依赖与运行环境可复现。

??? note "支撑文件差异（1 个文件）"
    **`src/minilucene/query_parser/__init__.py`**

    ```diff
    diff --git a/src/minilucene/query_parser/__init__.py b/src/minilucene/query_parser/__init__.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..d64eefe8c0f54110849b4fce798759d79df474da
    --- /dev/null
    +++ b/src/minilucene/query_parser/__init__.py
    @@ -0,0 +1,4 @@
    +from minilucene.query_parser.errors import QuerySyntaxError
    +from minilucene.query_parser.lexer import LexToken, TokenKind, lex
    +
    +__all__ = ["LexToken", "QuerySyntaxError", "TokenKind", "lex"]
    ```


### 验证证据

运行 `uv run pytest -q $(cat journey/stages/23-query-lexer/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

Tokenization 全程保留 Span，让后续 Parser Error 指向用户原文而非归一化重建文本。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 9 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/09-query-language.md)

[Complete reference patch / 完整参考补丁](https://github.com/system-in-miniature/mini-lucene/blob/main/journey/stages/23-query-lexer/stage.patch)

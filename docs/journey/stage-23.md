# Stage 23 · Closed query lexer

### Goal

Build closed query lexer and explain its boundary from an executable counterexample, runtime state, and the critical statement.

??? note "Deliverable files"
    - `src/minilucene/query_parser/__init__.py`
    - `src/minilucene/query_parser/errors.py`
    - `src/minilucene/query_parser/lexer.py`
    - `tests/unit/query_parser/test_lexer.py`

### The problem at this point

User query text needs tokens that preserve source spans and distinguish operators, phrases, prefixes, fields, and errors.

### Test contract

#### See the failure first

Lexer tests include escapes, unmatched quotes, illegal stars, hyphenated text, and exact error offsets.

??? note "File diff: tests/unit/query_parser/test_lexer.py"
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

**What this test locks**

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

**How it constructs the counterexample**

Lexer tests include escapes, unmatched quotes, illegal stars, hyphenated text, and exact error offsets.

**Key test statement**

```python
assert [(token.kind, token.text, token.start) for token in tokens] == [
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

**What a failure means**

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

The lexer is evidence-preserving translation from characters to a finite token vocabulary; it does not decide precedence or index meaning.

### Why this mechanism is necessary

User query text needs tokens that preserve source spans and distinguish operators, phrases, prefixes, fields, and errors. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

A cursor consumes characters, records start/end spans, recognizes reserved syntax, and emits typed lexical failures at the first impossible byte.

### Mechanism blocks

#### Closed query lexer mechanism

A cursor consumes characters, records start/end spans, recognizes reserved syntax, and emits typed lexical failures at the first impossible byte.

??? note "File diff: src/minilucene/query_parser/errors.py"
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

??? note "File diff: src/minilucene/query_parser/lexer.py"
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

**What it is and why it appears**

The lexer is evidence-preserving translation from characters to a finite token vocabulary; it does not decide precedence or index meaning.

**Runtime role**

A cursor consumes characters, records start/end spans, recognizes reserved syntax, and emits typed lexical failures at the first impossible byte.

**Statement understanding**

Keeping spans through tokenization lets later parser errors point to the user's original text rather than a normalized reconstruction.

#### Package, fixture, and project support

Keep exports, test corpora, dependencies, and the runtime environment reproducible.

??? note "Supporting file diffs (1 file)"
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


### Verification evidence

Run `uv run pytest -q $(cat journey/stages/23-query-lexer/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Keeping spans through tokenization lets later parser errors point to the user's original text rather than a normalized reconstruction.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 9](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/09-query-language.md)

[Complete reference patch / 完整参考补丁](https://github.com/system-in-miniature/mini-lucene/blob/main/journey/stages/23-query-lexer/stage.patch)

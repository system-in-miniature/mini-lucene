from dataclasses import dataclass
from enum import StrEnum

from minilucene.query_parser.errors import QuerySyntaxError


class TokenKind(StrEnum):
    WORD = "WORD"
    PHRASE = "PHRASE"
    PREFIX = "PREFIX"
    AND = "AND"
    OR = "OR"
    NOT = "NOT"
    COLON = "COLON"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    MINUS = "MINUS"
    EOF = "EOF"


@dataclass(frozen=True, slots=True)
class LexToken:
    kind: TokenKind
    text: str
    start: int
    end: int


_PUNCTUATION = {
    ":": TokenKind.COLON,
    "(": TokenKind.LPAREN,
    ")": TokenKind.RPAREN,
    "-": TokenKind.MINUS,
}
_OPERATORS = {
    "AND": TokenKind.AND,
    "OR": TokenKind.OR,
    "NOT": TokenKind.NOT,
}


def _lex_phrase(source: str, start: int) -> tuple[LexToken, int]:
    index = start + 1
    characters: list[str] = []
    while index < len(source):
        character = source[index]
        if character == '"':
            return (
                LexToken(
                    TokenKind.PHRASE,
                    "".join(characters),
                    start,
                    index + 1,
                ),
                index + 1,
            )
        if character == "\\":
            escape_offset = index
            index += 1
            if index >= len(source):
                raise QuerySyntaxError(
                    "unterminated phrase escape", escape_offset, source
                )
            escaped = source[index]
            if escaped not in {'"', "\\"}:
                raise QuerySyntaxError(
                    "only quote and backslash may be escaped",
                    escape_offset,
                    source,
                )
            characters.append(escaped)
        else:
            characters.append(character)
        index += 1
    raise QuerySyntaxError("unclosed phrase", start, source)


def _is_internal_hyphen(source: str, index: int) -> bool:
    return (
        index > 0
        and index + 1 < len(source)
        and source[index - 1].isalnum()
        and source[index + 1].isalnum()
    )


def _lex_word(source: str, start: int) -> tuple[LexToken, int]:
    index = start
    while index < len(source):
        character = source[index]
        if character.isspace() or character in ':()"':
            break
        if character == "-" and not _is_internal_hyphen(source, index):
            break
        index += 1
    text = source[start:index]
    star = text.find("*")
    if star != -1:
        if star == 0 or star != len(text) - 1 or text.count("*") != 1:
            raise QuerySyntaxError(
                "asterisk is only legal once after a non-empty prefix",
                start + star,
                source,
            )
        return LexToken(TokenKind.PREFIX, text[:-1], start, index), index
    operator = _OPERATORS.get(text.upper())
    return LexToken(operator or TokenKind.WORD, text, start, index), index


def lex(source: str) -> tuple[LexToken, ...]:
    if not isinstance(source, str):
        raise TypeError("query source must be a string")
    tokens: list[LexToken] = []
    index = 0
    while index < len(source):
        character = source[index]
        if character.isspace():
            index += 1
            continue
        if character == '"':
            token, index = _lex_phrase(source, index)
            tokens.append(token)
            continue
        kind = _PUNCTUATION.get(character)
        if kind is not None:
            tokens.append(LexToken(kind, character, index, index + 1))
            index += 1
            continue
        token, index = _lex_word(source, index)
        if not token.text:
            raise QuerySyntaxError("unexpected character", token.start, source)
        tokens.append(token)
    tokens.append(LexToken(TokenKind.EOF, "", len(source), len(source)))
    return tuple(tokens)

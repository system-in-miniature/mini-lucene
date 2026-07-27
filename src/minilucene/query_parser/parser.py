from dataclasses import dataclass

from minilucene.analysis import KeywordAnalyzer, StandardAnalyzer
from minilucene.analysis.model import Token
from minilucene.query import (
    BooleanClause,
    BooleanQuery,
    Occur,
    PhraseQuery,
    PrefixQuery,
    Query,
    TermQuery,
)
from minilucene.query_parser.errors import QuerySyntaxError
from minilucene.query_parser.lexer import LexToken, TokenKind, lex
from minilucene.schema import FieldType, Schema


@dataclass(frozen=True, slots=True)
class _Parsed:
    query: Query
    prohibited: bool = False


class _Parser:
    def __init__(
        self, source: str, schema: Schema, default_field: str
    ) -> None:
        self.source = source
        self.schema = schema
        self.tokens = lex(source)
        self.index = 0
        self._validate_field(default_field, 0, default=True)
        self.default_field = default_field

    @property
    def current(self) -> LexToken:
        return self.tokens[self.index]

    def advance(self) -> LexToken:
        token = self.current
        self.index += 1
        return token

    def syntax(self, message: str, token: LexToken | None = None):
        target = token or self.current
        raise QuerySyntaxError(message, target.start, self.source)

    def _validate_field(
        self, name: str, offset: int, *, default: bool = False
    ) -> FieldType:
        label = "default field" if default else "field"
        if name not in self.schema:
            raise QuerySyntaxError(
                f"unknown {label}: {name}", offset, self.source
            )
        field = self.schema[name]
        if not field.indexed:
            raise QuerySyntaxError(
                f"{label} is not indexed: {name}", offset, self.source
            )
        return field

    def _analyze(
        self, field_name: str, text: str, token: LexToken
    ) -> tuple[Token, ...]:
        field = self._validate_field(field_name, token.start)
        if field.analyzer_name == "standard":
            analyzed = StandardAnalyzer().analyze(text)
        elif field.analyzer_name == "keyword":
            analyzed = KeywordAnalyzer().analyze(text)
        else:
            self.syntax(
                f"unknown analyzer for field: {field_name}", token
            )
        if not analyzed:
            self.syntax("query text produced no searchable terms", token)
        return analyzed

    def parse(self) -> Query:
        if self.current.kind is TokenKind.EOF:
            self.syntax("expected query expression")
        parsed = self.parse_or(self.default_field)
        if self.current.kind is not TokenKind.EOF:
            self.syntax("unexpected token")
        return self._materialize(parsed)

    @staticmethod
    def _materialize(parsed: _Parsed) -> Query:
        if not parsed.prohibited:
            return parsed.query
        return BooleanQuery(
            (BooleanClause(Occur.MUST_NOT, parsed.query),)
        )

    def parse_or(self, field: str) -> _Parsed:
        items = [self.parse_and(field)]
        while True:
            if self.current.kind is TokenKind.OR:
                self.advance()
                items.append(self.parse_and(field))
            elif self.current.kind in {
                TokenKind.WORD,
                TokenKind.PHRASE,
                TokenKind.PREFIX,
                TokenKind.LPAREN,
                TokenKind.NOT,
                TokenKind.MINUS,
            }:
                items.append(self.parse_and(field))
            else:
                break
        if len(items) == 1:
            return items[0]
        return _Parsed(
            BooleanQuery(
                tuple(
                    BooleanClause(
                        Occur.MUST_NOT
                        if item.prohibited
                        else Occur.SHOULD,
                        item.query,
                    )
                    for item in items
                )
            )
        )

    def parse_and(self, field: str) -> _Parsed:
        items = [self.parse_unary(field)]
        while self.current.kind is TokenKind.AND:
            self.advance()
            items.append(self.parse_unary(field))
        if len(items) == 1:
            return items[0]
        return _Parsed(
            BooleanQuery(
                tuple(
                    BooleanClause(
                        Occur.MUST_NOT if item.prohibited else Occur.MUST,
                        item.query,
                    )
                    for item in items
                )
            )
        )

    def parse_unary(self, field: str) -> _Parsed:
        prohibited = False
        while self.current.kind in {TokenKind.NOT, TokenKind.MINUS}:
            self.advance()
            prohibited = not prohibited
        primary = self.parse_primary(field)
        return _Parsed(
            primary.query, prohibited ^ primary.prohibited
        )

    def parse_primary(self, field: str) -> _Parsed:
        token = self.current
        if (
            token.kind is TokenKind.WORD
            and self.tokens[self.index + 1].kind is TokenKind.COLON
        ):
            field_token = self.advance()
            self.advance()
            self._validate_field(field_token.text, field_token.start)
            return self.parse_primary(field_token.text)

        if token.kind is TokenKind.LPAREN:
            self.advance()
            if self.current.kind is TokenKind.RPAREN:
                self.syntax("expected query expression")
            parsed = self.parse_or(field)
            if self.current.kind is not TokenKind.RPAREN:
                self.syntax("expected closing parenthesis")
            self.advance()
            return parsed

        if token.kind is TokenKind.WORD:
            self.advance()
            tokens = self._analyze(field, token.text, token)
            queries = tuple(
                TermQuery(field, analyzed.term) for analyzed in tokens
            )
            if len(queries) == 1:
                return _Parsed(queries[0])
            return _Parsed(
                BooleanQuery(
                    tuple(
                        BooleanClause(Occur.SHOULD, query)
                        for query in queries
                    )
                )
            )

        if token.kind is TokenKind.PHRASE:
            self.advance()
            tokens = self._analyze(field, token.text, token)
            first_position = tokens[0].position
            return _Parsed(
                PhraseQuery(
                    field,
                    tuple(item.term for item in tokens),
                    positions=tuple(
                        item.position - first_position for item in tokens
                    ),
                )
            )

        if token.kind is TokenKind.PREFIX:
            self.advance()
            tokens = self._analyze(field, token.text, token)
            if len(tokens) != 1:
                self.syntax(
                    "prefix must analyze to exactly one term", token
                )
            return _Parsed(PrefixQuery(field, tokens[0].term))

        self.syntax("expected query expression")


def parse_query(
    source: str, schema: Schema, default_field: str
) -> Query:
    return _Parser(source, schema, default_field).parse()

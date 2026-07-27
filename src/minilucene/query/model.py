from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from itertools import pairwise


class QueryError(ValueError):
    """Raised when a query value or rewrite is invalid."""


def _require_text(value: str, label: str) -> None:
    if not isinstance(value, str) or not value:
        raise QueryError(f"{label} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class TermQuery:
    field: str
    term: str

    def __post_init__(self) -> None:
        _require_text(self.field, "field")
        _require_text(self.term, "term")


@dataclass(frozen=True, slots=True)
class PhraseQuery:
    field: str
    terms: tuple[str, ...]
    positions: tuple[int, ...] | None = None
    slop: int = 0

    def __post_init__(self) -> None:
        _require_text(self.field, "field")
        if not self.terms or any(not term for term in self.terms):
            raise QueryError("phrase terms must be non-empty")
        if self.slop != 0:
            raise QueryError("only phrase slop 0 is supported")
        positions = (
            tuple(range(len(self.terms)))
            if self.positions is None
            else tuple(self.positions)
        )
        if len(positions) != len(self.terms):
            raise QueryError("phrase positions must match phrase terms")
        if positions[0] != 0 or any(
            right <= left for left, right in pairwise(positions)
        ):
            raise QueryError(
                "phrase positions must start at zero and strictly increase"
            )
        object.__setattr__(self, "terms", tuple(self.terms))
        object.__setattr__(self, "positions", positions)


@dataclass(frozen=True, slots=True)
class PrefixQuery:
    field: str
    prefix: str

    def __post_init__(self) -> None:
        _require_text(self.field, "field")
        _require_text(self.prefix, "prefix")


@dataclass(frozen=True, slots=True)
class MatchAllQuery:
    pass


class Occur(StrEnum):
    MUST = "MUST"
    SHOULD = "SHOULD"
    MUST_NOT = "MUST_NOT"


@dataclass(frozen=True, slots=True)
class BooleanClause:
    occur: Occur
    query: Query

    def __post_init__(self) -> None:
        if not isinstance(self.occur, Occur):
            raise QueryError("boolean occurrence must be an Occur value")


@dataclass(frozen=True, slots=True)
class BooleanQuery:
    clauses: tuple[BooleanClause, ...]

    def __post_init__(self) -> None:
        if not self.clauses:
            raise QueryError("boolean query requires at least one clause")
        object.__setattr__(self, "clauses", tuple(self.clauses))


type Query = (
    TermQuery | PhraseQuery | PrefixQuery | MatchAllQuery | BooleanQuery
)

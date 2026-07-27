from collections.abc import Iterable
from typing import Protocol

from minilucene.index.postings import Posting
from minilucene.query.model import (
    BooleanClause,
    BooleanQuery,
    MatchAllQuery,
    Occur,
    PhraseQuery,
    PrefixQuery,
    Query,
    QueryError,
    TermQuery,
)


class MatchReader(Protocol):
    max_doc: int
    max_prefix_expansions: int

    def postings(self, field: str, term: str) -> Iterable[Posting]: ...

    def terms_with_prefix(self, field: str, prefix: str) -> tuple[str, ...]: ...

    def has_phrase(
        self,
        field: str,
        terms: tuple[str, ...],
        query_positions: tuple[int, ...],
        doc_id: int,
    ) -> bool: ...


def _intersection(sets: list[set[int]]) -> set[int]:
    if not sets:
        return set()
    result = sets[0].copy()
    for values in sets[1:]:
        result.intersection_update(values)
    return result


def _union(sets: Iterable[set[int]]) -> set[int]:
    result: set[int] = set()
    for values in sets:
        result.update(values)
    return result


def match_boolean(
    reader: MatchReader, clauses: tuple[BooleanClause, ...]
) -> set[int]:
    must = [
        match_query(reader, clause.query)
        for clause in clauses
        if clause.occur is Occur.MUST
    ]
    should = [
        match_query(reader, clause.query)
        for clause in clauses
        if clause.occur is Occur.SHOULD
    ]
    prohibited = _union(
        match_query(reader, clause.query)
        for clause in clauses
        if clause.occur is Occur.MUST_NOT
    )
    if must:
        candidates = _intersection(must)
    elif should:
        candidates = _union(should)
    else:
        return set()
    return candidates - prohibited


def match_query(reader: MatchReader, query: Query) -> set[int]:
    match query:
        case TermQuery(field, term):
            return {
                posting.doc_id for posting in reader.postings(field, term)
            }
        case PhraseQuery(field, terms, positions, 0):
            candidates = _intersection(
                [
                    match_query(reader, TermQuery(field, term))
                    for term in terms
                ]
            )
            return {
                doc_id
                for doc_id in candidates
                if reader.has_phrase(
                    field, terms, positions, doc_id  # type: ignore[arg-type]
                )
            }
        case PrefixQuery(field, prefix):
            terms = reader.terms_with_prefix(field, prefix)
            if len(terms) > reader.max_prefix_expansions:
                raise QueryError("prefix expansion limit exceeded")
            return _union(
                match_query(reader, TermQuery(field, term))
                for term in terms
            )
        case MatchAllQuery():
            return set(range(reader.max_doc))
        case BooleanQuery(clauses):
            return match_boolean(reader, clauses)
    raise QueryError(f"unsupported query: {type(query).__name__}")

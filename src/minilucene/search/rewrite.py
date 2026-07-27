from bisect import bisect_left
from typing import Protocol

from minilucene.errors import TooManyTermsError
from minilucene.query import (
    BooleanClause,
    BooleanQuery,
    MatchAllQuery,
    Occur,
    PrefixQuery,
    Query,
    TermQuery,
)


class RewriteReader(Protocol):
    def terms_with_prefix(
        self, field: str, prefix: str
    ) -> tuple[str, ...]: ...


def _expand_prefix(
    reader: RewriteReader,
    query: PrefixQuery,
    *,
    max_terms: int,
) -> Query:
    terms = reader.terms_with_prefix(query.field, query.prefix)
    start = bisect_left(terms, query.prefix)
    matches: list[str] = []
    for term in terms[start:]:
        if not term.startswith(query.prefix):
            break
        if len(matches) == max_terms:
            raise TooManyTermsError(
                query.field, query.prefix, max_terms
            )
        matches.append(term)
    if not matches:
        return BooleanQuery(
            (BooleanClause(Occur.MUST_NOT, MatchAllQuery()),)
        )
    if len(matches) == 1:
        return TermQuery(query.field, matches[0])
    return BooleanQuery(
        tuple(
            BooleanClause(
                Occur.SHOULD, TermQuery(query.field, term)
            )
            for term in matches
        )
    )


def rewrite_query(
    reader: RewriteReader, query: Query, *, max_terms: int
) -> Query:
    if (
        not isinstance(max_terms, int)
        or isinstance(max_terms, bool)
        or max_terms <= 0
    ):
        raise ValueError("max_terms must be a positive integer")
    if isinstance(query, PrefixQuery):
        return _expand_prefix(reader, query, max_terms=max_terms)
    if isinstance(query, BooleanQuery):
        return BooleanQuery(
            tuple(
                BooleanClause(
                    clause.occur,
                    rewrite_query(
                        reader, clause.query, max_terms=max_terms
                    ),
                )
                for clause in query.clauses
            )
        )
    return query

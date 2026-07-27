import html
from collections.abc import Mapping

from minilucene.analysis import StandardAnalyzer
from minilucene.analysis.model import Token
from minilucene.query import (
    BooleanQuery,
    Occur,
    PhraseQuery,
    Query,
    TermQuery,
)
from minilucene.schema import Schema

type Offset = tuple[int, int]
type PhraseConstraint = tuple[tuple[str, ...], tuple[int, ...]]


def validate_highlight_fields(
    schema: Schema, fields: tuple[str, ...]
) -> None:
    if len(set(fields)) != len(fields):
        raise ValueError("highlight fields must be unique")
    for name in fields:
        if name not in schema:
            raise ValueError(
                f"highlight field must be a stored TextField: {name}"
            )
        field = schema[name]
        if (
            not field.stored
            or not field.tokenized
            or field.analyzer_name != "standard"
        ):
            raise ValueError(
                f"highlight field must be a stored TextField: {name}"
            )


def _positive_constraints(
    query: Query,
    field: str,
    *,
    prohibited: bool = False,
) -> tuple[set[str], list[PhraseConstraint]]:
    terms: set[str] = set()
    phrases: list[PhraseConstraint] = []
    if prohibited:
        return terms, phrases
    if isinstance(query, TermQuery) and query.field == field:
        terms.add(query.term)
    elif isinstance(query, PhraseQuery) and query.field == field:
        phrases.append(
            (
                query.terms,
                query.positions
                if query.positions is not None
                else tuple(range(len(query.terms))),
            )
        )
    elif isinstance(query, BooleanQuery):
        for clause in query.clauses:
            nested_terms, nested_phrases = _positive_constraints(
                clause.query,
                field,
                prohibited=clause.occur is Occur.MUST_NOT,
            )
            terms.update(nested_terms)
            phrases.extend(nested_phrases)
    return terms, phrases


def _phrase_offsets(
    tokens: tuple[Token, ...], constraint: PhraseConstraint
) -> list[Offset]:
    terms, positions = constraint
    by_position = {token.position: token for token in tokens}
    matches: list[Offset] = []
    for first in tokens:
        if first.term != terms[0]:
            continue
        matched = [first]
        for term, relative_position in zip(
            terms[1:], positions[1:], strict=True
        ):
            token = by_position.get(
                first.position + relative_position
            )
            if token is None or token.term != term:
                break
            matched.append(token)
        else:
            matches.append(
                (matched[0].start_offset, matched[-1].end_offset)
            )
    return matches


def _merge_offsets(offsets: list[Offset]) -> tuple[Offset, ...]:
    if not offsets:
        return ()
    merged: list[list[int]] = []
    for start, end in sorted(offsets):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return tuple((start, end) for start, end in merged)


def highlight_text(text: str, query: Query, field: str) -> str:
    tokens = StandardAnalyzer().analyze(text)
    terms, phrases = _positive_constraints(query, field)
    offsets = [
        (token.start_offset, token.end_offset)
        for token in tokens
        if token.term in terms
    ]
    for phrase in phrases:
        offsets.extend(_phrase_offsets(tokens, phrase))

    pieces: list[str] = []
    cursor = 0
    for start, end in _merge_offsets(offsets):
        pieces.append(html.escape(text[cursor:start]))
        pieces.append(f"<em>{html.escape(text[start:end])}</em>")
        cursor = end
    pieces.append(html.escape(text[cursor:]))
    return "".join(pieces)


def highlight_document(
    stored_fields: Mapping[str, str],
    query: Query,
    fields: tuple[str, ...],
) -> dict[str, str]:
    return {
        field: highlight_text(stored_fields[field], query, field)
        for field in fields
        if field in stored_fields
    }

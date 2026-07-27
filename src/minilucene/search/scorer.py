from minilucene.query.match import match_query
from minilucene.query.model import (
    BooleanQuery,
    MatchAllQuery,
    Occur,
    PhraseQuery,
    PrefixQuery,
    Query,
    TermQuery,
)
from minilucene.search.bm25 import BM25
from minilucene.search.reader import ReaderView


def _term_scores(
    reader: ReaderView,
    query: TermQuery,
    bm25: BM25,
    eligible: set[int] | None = None,
) -> dict[int, float]:
    stats = reader.corpus_stats
    field = reader.schema[query.field]
    df = stats.doc_frequency(query.field, query.term)
    average_length = stats.average_length(query.field)
    scores: dict[int, float] = {}
    for posting in reader.postings(query.field, query.term):
        if eligible is not None and posting.doc_id not in eligible:
            continue
        scores[posting.doc_id] = field.boost * bm25.term_score(
            tf=posting.term_frequency,
            df=df,
            n=stats.live_doc_count,
            dl=reader.field_length(query.field, posting.doc_id),
            avgdl=average_length,
        )
    return scores


def _merge_scores(
    target: dict[int, float],
    source: dict[int, float],
    eligible: set[int],
) -> None:
    for doc_id, score in source.items():
        if doc_id in eligible:
            target[doc_id] = target.get(doc_id, 0.0) + score


def score_query(
    reader: ReaderView, query: Query, bm25: BM25 | None = None
) -> dict[int, float]:
    bm25 = bm25 or BM25()
    candidates = match_query(reader, query)
    match query:
        case TermQuery():
            return _term_scores(reader, query, bm25, candidates)
        case PhraseQuery(field, terms):
            scores: dict[int, float] = {}
            for term in terms:
                _merge_scores(
                    scores,
                    _term_scores(
                        reader, TermQuery(field, term), bm25, candidates
                    ),
                    candidates,
                )
            return scores
        case PrefixQuery(field, prefix):
            scores = {}
            for term in reader.terms_with_prefix(field, prefix):
                _merge_scores(
                    scores,
                    _term_scores(
                        reader, TermQuery(field, term), bm25, candidates
                    ),
                    candidates,
                )
            return scores
        case MatchAllQuery():
            return {doc_id: 0.0 for doc_id in candidates}
        case BooleanQuery(clauses):
            scores = {doc_id: 0.0 for doc_id in candidates}
            for clause in clauses:
                if clause.occur is Occur.MUST_NOT:
                    continue
                _merge_scores(
                    scores,
                    score_query(reader, clause.query, bm25),
                    candidates,
                )
            return scores
    return {}

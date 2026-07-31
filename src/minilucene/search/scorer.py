from collections.abc import Iterator
from typing import Protocol

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
from minilucene.search.iterators import (
    NO_MORE_DOCS,
    ConjunctionIterator,
    DisjunctionIterator,
    DocIdIterator,
    LiveDocsIterator,
    PostingsIterator,
    ReqExclIterator,
)
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


class _Scorer(DocIdIterator, Protocol):
    def score(self) -> float: ...


class _TermScorer:
    def __init__(
        self, reader: ReaderView, query: TermQuery, bm25: BM25
    ) -> None:
        self._iterator = PostingsIterator(
            reader.postings(query.field, query.term)
        )
        self._reader = reader
        self._field = query.field
        self._boost = reader.schema[query.field].boost
        stats = reader.corpus_stats
        self._df = stats.doc_frequency(query.field, query.term)
        self._n = stats.live_doc_count
        self._average_length = stats.average_length(query.field)
        self._bm25 = bm25

    def doc(self) -> int:
        return self._iterator.doc()

    def next(self) -> int:
        return self._iterator.next()

    def advance(self, target: int) -> int:
        return self._iterator.advance(target)

    def score(self) -> float:
        posting = self._iterator.posting
        return self._boost * self._bm25.term_score(
            tf=posting.term_frequency,
            df=self._df,
            n=self._n,
            dl=self._reader.field_length(self._field, posting.doc_id),
            avgdl=self._average_length,
        )


class _MatchAllScorer:
    def __init__(self, reader: ReaderView) -> None:
        self._iterator = LiveDocsIterator(
            reader.max_doc, reader.live_doc_ids
        )

    def doc(self) -> int:
        return self._iterator.doc()

    def next(self) -> int:
        return self._iterator.next()

    def advance(self, target: int) -> int:
        return self._iterator.advance(target)

    def score(self) -> float:
        return 0.0


class _BooleanScorer:
    def __init__(
        self,
        must: tuple[_Scorer, ...],
        should: tuple[_Scorer, ...],
        prohibited: tuple[_Scorer, ...],
        scoring_children: tuple[_Scorer, ...],
    ) -> None:
        if must:
            positive: DocIdIterator = (
                must[0]
                if len(must) == 1
                else ConjunctionIterator(must)
            )
        elif should:
            positive = (
                should[0]
                if len(should) == 1
                else DisjunctionIterator(should)
            )
        else:
            positive = DisjunctionIterator(())

        if prohibited:
            excluded: DocIdIterator = (
                prohibited[0]
                if len(prohibited) == 1
                else DisjunctionIterator(prohibited)
            )
            positive = ReqExclIterator(positive, excluded)

        self._iterator = positive
        self._scoring_children = scoring_children

    def doc(self) -> int:
        return self._iterator.doc()

    def next(self) -> int:
        return self._iterator.next()

    def advance(self, target: int) -> int:
        return self._iterator.advance(target)

    def score(self) -> float:
        doc_id = self.doc()
        total = 0.0
        for child in self._scoring_children:
            if child.doc() < doc_id:
                child.advance(doc_id)
            if child.doc() == doc_id:
                total += child.score()
        return total


def _compile_scorer(
    reader: ReaderView, query: Query, bm25: BM25
) -> _Scorer | None:
    match query:
        case TermQuery():
            return _TermScorer(reader, query, bm25)
        case MatchAllQuery():
            return _MatchAllScorer(reader)
        case BooleanQuery(clauses):
            compiled: list[tuple[Occur, _Scorer]] = []
            for clause in clauses:
                child = _compile_scorer(reader, clause.query, bm25)
                if child is None:
                    return None
                compiled.append((clause.occur, child))
            return _BooleanScorer(
                tuple(
                    child
                    for occur, child in compiled
                    if occur is Occur.MUST
                ),
                tuple(
                    child
                    for occur, child in compiled
                    if occur is Occur.SHOULD
                ),
                tuple(
                    child
                    for occur, child in compiled
                    if occur is Occur.MUST_NOT
                ),
                tuple(
                    child
                    for occur, child in compiled
                    if occur is not Occur.MUST_NOT
                ),
            )
        case PhraseQuery() | PrefixQuery():
            return None
    return None


def iter_scored_docs(
    reader: ReaderView, query: Query, bm25: BM25 | None = None
) -> Iterator[tuple[int, float]]:
    """Yield ``(doc_id, score)`` in doc-ID order without full result maps.

    Term, match-all, and Boolean trees compile to DAAT scorer cursors. If any
    leaf is not migrated, the entire tree falls back to ``score_query`` so a
    mixed execution plan cannot change matching or BM25 semantics. Phrase
    queries currently fall back; unrevised prefix queries do too, while the
    normal searcher rewrite turns prefixes into supported term/Boolean trees.
    """

    similarity = bm25 or BM25()
    scorer = _compile_scorer(reader, query, similarity)
    if scorer is None:
        scores = score_query(reader, query, similarity)
        for doc_id in sorted(scores):
            yield doc_id, scores[doc_id]
        return
    while (doc_id := scorer.next()) != NO_MORE_DOCS:
        yield doc_id, scorer.score()

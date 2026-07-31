import pytest

from minilucene.index.postings import Posting
from minilucene.search.iterators import (
    NO_MORE_DOCS,
    UNPOSITIONED,
    ConjunctionIterator,
    DisjunctionIterator,
    LiveDocsIterator,
    PostingsIterator,
    ReqExclIterator,
)


def postings(*doc_ids: int) -> tuple[Posting, ...]:
    return tuple(Posting(doc_id, 1, (0,)) for doc_id in doc_ids)


def drain(iterator) -> list[int]:
    result = []
    while (doc_id := iterator.next()) != NO_MORE_DOCS:
        result.append(doc_id)
    return result


def test_postings_iterator_empty_and_exhausted_states_are_stable():
    iterator = PostingsIterator(())
    assert iterator.doc() == UNPOSITIONED
    assert iterator.next() == NO_MORE_DOCS
    assert iterator.doc() == NO_MORE_DOCS
    assert iterator.next() == NO_MORE_DOCS
    assert iterator.advance(100) == NO_MORE_DOCS


def test_postings_iterator_singleton_and_advance_land_on_first_gte_target():
    singleton = PostingsIterator(postings(7))
    assert singleton.advance(7) == 7
    assert singleton.posting.term_frequency == 1
    assert singleton.next() == NO_MORE_DOCS

    iterator = PostingsIterator(postings(1, 4, 9, 15))
    assert iterator.advance(-1) == 1
    assert iterator.advance(4) == 4
    assert iterator.advance(5) == 9
    assert iterator.advance(30) == NO_MORE_DOCS


def test_postings_iterator_rejects_non_increasing_doc_ids():
    with pytest.raises(ValueError, match="strictly increasing"):
        PostingsIterator(postings(2, 2))


@pytest.mark.parametrize("doc_id", [-1, NO_MORE_DOCS])
def test_postings_iterator_rejects_reserved_doc_ids(doc_id):
    with pytest.raises(ValueError, match="document range"):
        PostingsIterator(postings(doc_id))


def test_live_docs_iterator_scans_existing_mask_without_posting_objects():
    iterator = LiveDocsIterator(8, frozenset({1, 4, 7}))
    assert iterator.advance(-1) == 1
    assert iterator.advance(3) == 4
    assert iterator.next() == 7
    assert iterator.next() == NO_MORE_DOCS


def test_conjunction_iterator_zipper_aligns_all_children():
    iterator = ConjunctionIterator(
        (
            PostingsIterator(postings(1, 3, 5, 9, 12)),
            PostingsIterator(postings(0, 3, 4, 9, 11, 12)),
            PostingsIterator(postings(3, 8, 9, 12)),
        )
    )
    assert iterator.advance(4) == 9
    assert iterator.next() == 12
    assert iterator.next() == NO_MORE_DOCS


def test_conjunction_iterator_with_empty_child_is_empty():
    iterator = ConjunctionIterator(
        (PostingsIterator(postings(1)), PostingsIterator(()))
    )
    assert drain(iterator) == []


def test_disjunction_iterator_heap_merges_and_deduplicates():
    iterator = DisjunctionIterator(
        (
            PostingsIterator(postings(1, 5, 9)),
            PostingsIterator(postings(2, 5, 8)),
            PostingsIterator(postings(5, 10)),
        )
    )
    assert drain(iterator) == [1, 2, 5, 8, 9, 10]


def test_disjunction_iterator_advance_rebuilds_heap_at_target():
    iterator = DisjunctionIterator(
        (
            PostingsIterator(postings(1, 5, 9)),
            PostingsIterator(postings(2, 6, 8)),
        )
    )
    assert iterator.advance(6) == 6
    assert drain(iterator) == [8, 9]


def test_req_excl_iterator_filters_prohibited_docs():
    iterator = ReqExclIterator(
        PostingsIterator(postings(1, 2, 4, 7, 9)),
        PostingsIterator(postings(0, 2, 3, 7, 10)),
    )
    assert drain(iterator) == [1, 4, 9]


def test_req_excl_iterator_supports_advance():
    iterator = ReqExclIterator(
        PostingsIterator(postings(1, 4, 7, 9)),
        PostingsIterator(postings(4, 8)),
    )
    assert iterator.advance(4) == 7
    assert iterator.next() == 9

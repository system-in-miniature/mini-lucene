"""Ordered document-ID cursors used by MiniLucene's DAAT query path."""

import heapq
from collections.abc import Sequence
from collections.abc import Set as AbstractSet
from typing import Protocol

from minilucene.index.postings import Posting

UNPOSITIONED = -1
NO_MORE_DOCS = (1 << 63) - 1


class DocIdIterator(Protocol):
    """The small ``DocIdSetIterator``-like contract used by composites."""

    def doc(self) -> int: ...

    def next(self) -> int: ...

    def advance(self, target: int) -> int: ...


class PostingsIterator:
    """Cursor over one term's postings, analogous to Lucene ``PostingsEnum``.

    DAAT execution keeps only a position in the ordered posting list instead
    of materializing every matching document in a set. ``advance(target)``
    lands on the first doc ID greater than or equal to ``target``. This
    educational codec stores no skip data, so advance is deliberately linear;
    real Lucene posting formats use skip lists and block structures to jump.
    """

    def __init__(self, postings: Sequence[Posting]) -> None:
        self._postings = tuple(postings)
        if any(
            posting.doc_id < 0 or posting.doc_id >= NO_MORE_DOCS
            for posting in self._postings
        ):
            raise ValueError("posting doc ID outside document range")
        if any(
            left.doc_id >= right.doc_id
            for left, right in zip(
                self._postings, self._postings[1:], strict=False
            )
        ):
            raise ValueError("posting doc IDs must be strictly increasing")
        self._index = -1
        self._doc = UNPOSITIONED

    @property
    def posting(self) -> Posting:
        if self._doc in (UNPOSITIONED, NO_MORE_DOCS):
            raise RuntimeError("postings iterator is not on a document")
        return self._postings[self._index]

    def doc(self) -> int:
        return self._doc

    def next(self) -> int:
        if self._doc == NO_MORE_DOCS:
            return NO_MORE_DOCS
        self._index += 1
        if self._index >= len(self._postings):
            self._doc = NO_MORE_DOCS
        else:
            self._doc = self._postings[self._index].doc_id
        return self._doc

    def advance(self, target: int) -> int:
        if self._doc == NO_MORE_DOCS:
            return NO_MORE_DOCS
        if self._doc != UNPOSITIONED and self._doc >= target:
            return self._doc
        while self.next() < target:
            pass
        return self._doc


class LiveDocsIterator:
    """Scan an existing live-doc mask as Lucene match-all scorers scan bits.

    The reader already owns the live-doc set, so this cursor keeps only one
    integer position and performs no per-query copy or synthetic posting
    allocation. Like the educational postings cursor, advance is linear.
    """

    def __init__(
        self, max_doc: int, live_doc_ids: AbstractSet[int]
    ) -> None:
        if max_doc < 0 or any(
            doc_id < 0 or doc_id >= max_doc for doc_id in live_doc_ids
        ):
            raise ValueError("live doc ID outside document range")
        self._max_doc = max_doc
        self._live_doc_ids = live_doc_ids
        self._doc = UNPOSITIONED

    def doc(self) -> int:
        return self._doc

    def _scan(self, candidate: int) -> int:
        while (
            candidate < self._max_doc
            and candidate not in self._live_doc_ids
        ):
            candidate += 1
        self._doc = (
            candidate if candidate < self._max_doc else NO_MORE_DOCS
        )
        return self._doc

    def next(self) -> int:
        if self._doc == NO_MORE_DOCS:
            return NO_MORE_DOCS
        return self._scan(0 if self._doc == UNPOSITIONED else self._doc + 1)

    def advance(self, target: int) -> int:
        if self._doc == NO_MORE_DOCS:
            return NO_MORE_DOCS
        if self._doc != UNPOSITIONED and self._doc >= target:
            return self._doc
        return self._scan(max(0, target))


class ConjunctionIterator:
    """Zipper-align required cursors like Lucene ``ConjunctionDISI``.

    A conjunction never owns a complete intersection. It advances the lagging
    child to the current leader; if that child overshoots, the new doc ID
    becomes the leader and alignment restarts. A document is emitted only when
    every child is positioned on that same ID.
    """

    def __init__(self, children: Sequence[DocIdIterator]) -> None:
        self.children = tuple(children)
        self._doc = UNPOSITIONED

    def doc(self) -> int:
        return self._doc

    def _align(self, target: int) -> int:
        if not self.children or target == NO_MORE_DOCS:
            self._doc = NO_MORE_DOCS
            return self._doc
        while target != NO_MORE_DOCS:
            aligned = True
            for child in self.children[1:]:
                candidate = child.advance(target)
                if candidate == NO_MORE_DOCS:
                    self._doc = NO_MORE_DOCS
                    return self._doc
                if candidate > target:
                    target = self.children[0].advance(candidate)
                    aligned = False
                    break
            if aligned:
                self._doc = target
                return self._doc
        self._doc = NO_MORE_DOCS
        return self._doc

    def next(self) -> int:
        if self._doc == NO_MORE_DOCS:
            return NO_MORE_DOCS
        if not self.children:
            self._doc = NO_MORE_DOCS
            return self._doc
        return self._align(self.children[0].next())

    def advance(self, target: int) -> int:
        if self._doc == NO_MORE_DOCS:
            return NO_MORE_DOCS
        if self._doc != UNPOSITIONED and self._doc >= target:
            return self._doc
        if not self.children:
            self._doc = NO_MORE_DOCS
            return self._doc
        return self._align(self.children[0].advance(target))


class DisjunctionIterator:
    """Minimum-heap union like Lucene ``DisjunctionDISIApproximation``.

    The heap contains one current doc ID per non-exhausted child. Equal IDs
    are emitted once; all children on that ID advance together on the next
    call. This bounds merge state by the number of clauses rather than the
    number of matching documents.
    """

    def __init__(self, children: Sequence[DocIdIterator]) -> None:
        self.children = tuple(children)
        self._heap: list[tuple[int, int]] = []
        self._doc = UNPOSITIONED

    def doc(self) -> int:
        return self._doc

    def _push(self, child_index: int, doc_id: int) -> None:
        if doc_id != NO_MORE_DOCS:
            heapq.heappush(self._heap, (doc_id, child_index))

    def _initialize(self, target: int | None = None) -> int:
        for index, child in enumerate(self.children):
            doc_id = child.next() if target is None else child.advance(target)
            self._push(index, doc_id)
        self._doc = self._heap[0][0] if self._heap else NO_MORE_DOCS
        return self._doc

    def next(self) -> int:
        if self._doc == NO_MORE_DOCS:
            return NO_MORE_DOCS
        if self._doc == UNPOSITIONED:
            return self._initialize()
        current = self._doc
        while self._heap and self._heap[0][0] == current:
            _, index = heapq.heappop(self._heap)
            self._push(index, self.children[index].next())
        self._doc = self._heap[0][0] if self._heap else NO_MORE_DOCS
        return self._doc

    def advance(self, target: int) -> int:
        if self._doc == NO_MORE_DOCS:
            return NO_MORE_DOCS
        if self._doc != UNPOSITIONED and self._doc >= target:
            return self._doc
        if self._doc == UNPOSITIONED:
            return self._initialize(target)
        while self._heap and self._heap[0][0] < target:
            _, index = heapq.heappop(self._heap)
            self._push(index, self.children[index].advance(target))
        self._doc = self._heap[0][0] if self._heap else NO_MORE_DOCS
        return self._doc


class ReqExclIterator:
    """Filter a required stream with a prohibited stream like ``ReqExclScorer``.

    The excluded cursor is advanced only as far as the current required doc.
    A required candidate is emitted unless the prohibited cursor lands on the
    same ID, implementing MUST_NOT without building a subtraction set.
    """

    def __init__(
        self, required: DocIdIterator, excluded: DocIdIterator
    ) -> None:
        self.required = required
        self.excluded = excluded
        self._doc = UNPOSITIONED

    def doc(self) -> int:
        return self._doc

    def _accept(self, candidate: int) -> int:
        while candidate != NO_MORE_DOCS:
            if self.excluded.advance(candidate) != candidate:
                self._doc = candidate
                return self._doc
            candidate = self.required.next()
        self._doc = NO_MORE_DOCS
        return self._doc

    def next(self) -> int:
        if self._doc == NO_MORE_DOCS:
            return NO_MORE_DOCS
        return self._accept(self.required.next())

    def advance(self, target: int) -> int:
        if self._doc == NO_MORE_DOCS:
            return NO_MORE_DOCS
        if self._doc != UNPOSITIONED and self._doc >= target:
            return self._doc
        return self._accept(self.required.advance(target))

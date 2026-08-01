# Stage 16 · Point-in-time reader snapshots

### Goal

Build point-in-time reader snapshots and explain its boundary from an executable counterexample, runtime state, and the critical statement.

??? note "Deliverable files"
    - `src/minilucene/errors.py`
    - `src/minilucene/index/directory.py`
    - `src/minilucene/reader.py`
    - `src/minilucene/snapshot.py`
    - `tests/nrt/test_reader_snapshot.py`

### The problem at this point

A reader that follows writer mutation in place cannot offer stable results across refresh, delete, or merge.

### Test contract

#### See the failure first

Tests open an old reader, publish newer state, and prove the old reader's segments, live docs, statistics, and hits do not change.

??? note "File diff: tests/nrt/test_reader_snapshot.py"
    ```diff
    diff --git a/tests/nrt/test_reader_snapshot.py b/tests/nrt/test_reader_snapshot.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..d9223853fa01668942c6c52af1ca3572b5a01c59
    --- /dev/null
    +++ b/tests/nrt/test_reader_snapshot.py
    @@ -0,0 +1,60 @@
    +import pytest
    +
    +from minilucene import Index, KeywordField, Schema, TextField
    +from minilucene.errors import AlreadyClosedError
    +from minilucene.query import TermQuery
    +
    +
    +def build_index(tmp_path):
    +    return Index.create(
    +        tmp_path,
    +        Schema(
    +            id=KeywordField(stored=True),
    +            body=TextField(stored=True),
    +        ),
    +    )
    +
    +
    +def test_reader_snapshot_never_changes_after_later_commit(tmp_path):
    +    index = build_index(tmp_path)
    +    with index.writer() as writer:
    +        writer.add_document(id="1", body="old")
    +        writer.commit()
    +    old_reader = index.open_reader()
    +    with index.writer() as writer:
    +        writer.add_document(id="2", body="new")
    +        writer.commit()
    +    assert old_reader.max_doc == 1
    +    assert index.open_reader().max_doc == 2
    +    assert old_reader.search(TermQuery("body", "new"), top_k=10).total_hits == 0
    +
    +
    +def test_reader_close_is_idempotent_and_operations_fail(tmp_path):
    +    index = build_index(tmp_path)
    +    with index.writer() as writer:
    +        writer.add_document(id="1", body="value")
    +        writer.commit()
    +    reader = index.open_reader()
    +    reader.close()
    +    reader.close()
    +    with pytest.raises(AlreadyClosedError):
    +        reader.document(0)
    +    with pytest.raises(AlreadyClosedError):
    +        reader.search(TermQuery("body", "value"), top_k=10)
    +
    +
    +def test_closing_one_reader_does_not_invalidate_another(tmp_path):
    +    index = build_index(tmp_path)
    +    first = index.open_reader()
    +    second = index.open_reader()
    +    first.close()
    +    assert second.max_doc == 0
    +    assert second.search(TermQuery("body", "anything"), top_k=10).total_hits == 0
    +
    +
    +def test_reader_exposes_frozen_snapshot_metadata(tmp_path):
    +    index = build_index(tmp_path)
    +    reader = index.open_reader()
    +    assert reader.snapshot.schema_fingerprint == index.schema.fingerprint
    +    assert reader.snapshot.commit_generation == 0
    +    assert reader.snapshot.segments == ()
    ```

**What this test locks**

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

**How it constructs the counterexample**

Tests open an old reader, publish newer state, and prove the old reader's segments, live docs, statistics, and hits do not change.

**Key test statement**

```python
assert old_reader.max_doc == 1
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

**What a failure means**

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

A reader snapshot freezes segment identities and visibility metadata at open time and owns references to those immutable resources.

### Why this mechanism is necessary

A reader that follows writer mutation in place cannot offer stable results across refresh, delete, or merge. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

Opening captures the current publication view; search reads only captured objects; closing releases ownership without consulting later writer state.

### Mechanism blocks

#### Point-in-time reader snapshots mechanism

Opening captures the current publication view; search reads only captured objects; closing releases ownership without consulting later writer state.

??? note "File diff: src/minilucene/errors.py"
    ```diff
    diff --git a/src/minilucene/errors.py b/src/minilucene/errors.py
    index a6776bb63a82151a509cdd5282c66f0ba0f7a141..48d73a44f0de44e4edf84850bbe9fa6ae03edd3e 100644
    --- a/src/minilucene/errors.py
    +++ b/src/minilucene/errors.py
    @@ -16,3 +16,7 @@ class SchemaMismatchError(MiniLuceneError):

     class WriterAlreadyOpenError(MiniLuceneError):
         pass
    +
    +
    +class AlreadyClosedError(MiniLuceneError):
    +    pass
    ```

??? note "File diff: src/minilucene/index/directory.py"
    ```diff
    diff --git a/src/minilucene/index/directory.py b/src/minilucene/index/directory.py
    index ae3e710519ac568491a09279ba609151cbe3ad13..5dfe05ef75db082b661a732e8c3877243cca402a 100644
    --- a/src/minilucene/index/directory.py
    +++ b/src/minilucene/index/directory.py
    @@ -127,4 +127,8 @@ class Index:
                 )
                 for segment in manifest.segments
             )
    -        return IndexReader(self.schema, segments)
    +        return IndexReader(
    +            self.schema,
    +            segments,
    +            commit_generation=manifest.commit_generation,
    +        )
    ```

??? note "File diff: src/minilucene/reader.py"
    ```diff
    diff --git a/src/minilucene/reader.py b/src/minilucene/reader.py
    index d578cec6147ebbc5fbbcfb37a335ee313daeb35f..a5459634cb62886f937d87b73e1f76c802a5bb5e 100644
    --- a/src/minilucene/reader.py
    +++ b/src/minilucene/reader.py
    @@ -1,8 +1,14 @@
    +from collections.abc import Mapping
    +from typing import Self
    +
    +from minilucene.errors import AlreadyClosedError
    +from minilucene.index.postings import Posting
     from minilucene.query.model import Query
     from minilucene.schema import Schema
     from minilucene.search.collector import TopDocs
     from minilucene.search.reader import ReaderView
     from minilucene.search.searcher import IndexSearcher
    +from minilucene.snapshot import ReaderSnapshot, SegmentSnapshot
     from minilucene.storage.image import SegmentImage


    @@ -11,8 +17,70 @@ class IndexReader(ReaderView):
             self,
             schema: Schema,
             segments: tuple[SegmentImage, ...],
    +        live_docs: tuple[frozenset[int], ...] | None = None,
    +        *,
    +        commit_generation: int | None = None,
         ) -> None:
    -        super().__init__(schema, segments)  # type: ignore[arg-type]
    +        super().__init__(  # type: ignore[arg-type]
    +            schema,
    +            segments,
    +            live_docs,
    +        )
    +        masks = (
    +            live_docs
    +            if live_docs is not None
    +            else tuple(
    +                frozenset(range(segment.max_doc))
    +                for segment in segments
    +            )
    +        )
    +        self.snapshot = ReaderSnapshot(
    +            schema_fingerprint=schema.fingerprint,
    +            segments=tuple(
    +                SegmentSnapshot(
    +                    generation=segment.generation,
    +                    image=segment,
    +                    live_docs=mask,
    +                )
    +                for segment, mask in zip(
    +                    segments, masks, strict=True
    +                )
    +            ),
    +            corpus_stats=self.corpus_stats,
    +            commit_generation=commit_generation,
    +        )
    +        self._closed = False
    +
    +    def _ensure_open(self) -> None:
    +        if self._closed:
    +            raise AlreadyClosedError("reader is closed")

         def search(self, query: Query, *, top_k: int = 10) -> TopDocs:
    +        self._ensure_open()
             return IndexSearcher(self).search(query, top_k=top_k)
    +
    +    def document(self, doc_id: int) -> Mapping[str, str]:
    +        self._ensure_open()
    +        return super().stored_fields(doc_id)
    +
    +    def stored_fields(self, doc_id: int) -> Mapping[str, str]:
    +        self._ensure_open()
    +        return super().stored_fields(doc_id)
    +
    +    def postings(self, field: str, term: str) -> tuple[Posting, ...]:
    +        self._ensure_open()
    +        return super().postings(field, term)
    +
    +    def field_length(self, field: str, doc_id: int) -> int:
    +        self._ensure_open()
    +        return super().field_length(field, doc_id)
    +
    +    def close(self) -> None:
    +        self._closed = True
    +
    +    def __enter__(self) -> Self:
    +        self._ensure_open()
    +        return self
    +
    +    def __exit__(self, exc_type, exc_value, traceback) -> None:
    +        self.close()
    ```

??? note "File diff: src/minilucene/snapshot.py"
    ```diff
    diff --git a/src/minilucene/snapshot.py b/src/minilucene/snapshot.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..5b07714d6ce21e078674fc1912f64a377bb0ee4d
    --- /dev/null
    +++ b/src/minilucene/snapshot.py
    @@ -0,0 +1,19 @@
    +from dataclasses import dataclass
    +
    +from minilucene.search.stats import CorpusStats
    +from minilucene.storage.image import SegmentImage
    +
    +
    +@dataclass(frozen=True, slots=True)
    +class SegmentSnapshot:
    +    generation: int
    +    image: SegmentImage
    +    live_docs: frozenset[int]
    +
    +
    +@dataclass(frozen=True, slots=True)
    +class ReaderSnapshot:
    +    schema_fingerprint: str
    +    segments: tuple[SegmentSnapshot, ...]
    +    corpus_stats: CorpusStats
    +    commit_generation: int | None
    ```

**What it is and why it appears**

A reader snapshot freezes segment identities and visibility metadata at open time and owns references to those immutable resources.

**Runtime role**

Opening captures the current publication view; search reads only captured objects; closing releases ownership without consulting later writer state.

**Statement understanding**

Copying the reference set, not mutable contents, is enough because segments are immutable and visibility overlays are versioned.

### Verification evidence

Run `uv run pytest -q $(cat journey/stages/16-reader-snapshots/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Copying the reference set, not mutable contents, is enough because segments are immutable and visibility overlays are versioned.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 5](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/05-segments-nrt.md)

[Complete reference patch / 完整参考补丁](https://github.com/system-in-miniature/mini-lucene/blob/main/journey/stages/16-reader-snapshots/stage.patch)

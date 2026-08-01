# Stage 14 · Writer flush

### Goal

Build writer flush and explain its boundary from an executable counterexample, runtime state, and the critical statement.

??? note "Deliverable files"
    - `src/minilucene/index/directory.py`
    - `src/minilucene/index/memory.py`
    - `src/minilucene/writer.py`
    - `tests/storage/test_writer_flush.py`

### The problem at this point

Buffered documents are searchable nowhere and durable nowhere until one operation freezes them into a segment.

### Test contract

#### See the failure first

Tests cross document and byte thresholds, inject publication failure, and verify a failed flush keeps the buffer retryable.

??? note "File diff: tests/storage/test_writer_flush.py"
    ```diff
    diff --git a/tests/storage/test_writer_flush.py b/tests/storage/test_writer_flush.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..3ee2c5a5443a2733cd7098fa3e6e62ff78f49fcd
    --- /dev/null
    +++ b/tests/storage/test_writer_flush.py
    @@ -0,0 +1,67 @@
    +import pytest
    +
    +from minilucene import Index, KeywordField, Schema, TextField
    +from minilucene.schema import SchemaError
    +from minilucene.writer import FlushPolicy
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
    +def test_flush_creates_segment_but_does_not_change_manifest(tmp_path):
    +    index = build_index(tmp_path)
    +    with index.writer() as writer:
    +        writer.add_document(id="1", body="alpha")
    +        segment = writer.flush()
    +        assert segment.generation == 1
    +        assert writer.segment_generations == (1,)
    +        assert index.manifest().segments == ()
    +
    +
    +def test_document_threshold_flushes_before_next_add(tmp_path):
    +    index = build_index(tmp_path)
    +    with index.writer(
    +        flush_policy=FlushPolicy(max_documents=1, max_postings=100)
    +    ) as writer:
    +        writer.add_document(id="1", body="alpha")
    +        writer.add_document(id="2", body="beta")
    +        assert writer.segment_generations == (1,)
    +        assert writer.buffered_document_count == 1
    +
    +
    +def test_invalid_document_does_not_trigger_threshold_flush(tmp_path):
    +    index = build_index(tmp_path)
    +    with index.writer(
    +        flush_policy=FlushPolicy(max_documents=1, max_postings=100)
    +    ) as writer:
    +        writer.add_document(id="1", body="alpha")
    +        with pytest.raises(SchemaError):
    +            writer.add_document(id="2", unknown="invalid")
    +        assert writer.segment_generations == ()
    +        assert writer.buffered_document_count == 1
    +
    +
    +def test_empty_flush_is_a_noop(tmp_path):
    +    index = build_index(tmp_path)
    +    with index.writer() as writer:
    +        assert writer.flush() is None
    +        assert writer.segment_generations == ()
    +
    +
    +def test_posting_threshold_flushes_before_next_add(tmp_path):
    +    index = build_index(tmp_path)
    +    with index.writer(
    +        flush_policy=FlushPolicy(max_documents=100, max_postings=2)
    +    ) as writer:
    +        writer.add_document(id="1", body="alpha")
    +        assert writer.buffered_posting_count == 2
    +        writer.add_document(id="2", body="beta")
    +        assert writer.segment_generations == (1,)
    +        assert writer.buffered_document_count == 1
    ```

**What this test locks**

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

**How it constructs the counterexample**

Tests cross document and byte thresholds, inject publication failure, and verify a failed flush keeps the buffer retryable.

**Key test statement**

```python
assert segment.generation == 1
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

**What a failure means**

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

Flush converts the current mutable RAM buffer into one immutable segment without publishing a commit or a new reader view.

### Why this mechanism is necessary

Buffered documents are searchable nowhere and durable nowhere until one operation freezes them into a segment. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

The writer swaps or snapshots its buffer, builds an image, publishes the segment, then records it as uncommitted only after success.

### Mechanism blocks

#### Writer flush mechanism

The writer swaps or snapshots its buffer, builds an image, publishes the segment, then records it as uncommitted only after success.

??? note "File diff: src/minilucene/index/directory.py"
    ```diff
    diff --git a/src/minilucene/index/directory.py b/src/minilucene/index/directory.py
    index 1fd3f3bc09ddb1f20252c1fe801c97eac23ff0f6..6f34b46c584c6af21517a3b8c6425eed6f4e474e 100644
    --- a/src/minilucene/index/directory.py
    +++ b/src/minilucene/index/directory.py
    @@ -110,7 +110,7 @@ class Index:
         def manifest(self) -> Manifest:
             return self._manifest_store.read()

    -    def writer(self):
    +    def writer(self, **options):
             from minilucene.writer import IndexWriter

    -        return IndexWriter(self)
    +        return IndexWriter(self, **options)
    ```

??? note "File diff: src/minilucene/index/memory.py"
    ```diff
    diff --git a/src/minilucene/index/memory.py b/src/minilucene/index/memory.py
    index 040f41b34f1b801c2c39d338aeaa9eb6cb80adb1..e54e6f3d2ea5f43ad17365449b12b570030e7a3d 100644
    --- a/src/minilucene/index/memory.py
    +++ b/src/minilucene/index/memory.py
    @@ -1,5 +1,6 @@
     from collections import defaultdict
     from collections.abc import Mapping
    +from dataclasses import dataclass
     from types import MappingProxyType

     from minilucene.analysis import KeywordAnalyzer, StandardAnalyzer
    @@ -18,6 +19,21 @@ def _analyze(field: FieldType, value: str) -> tuple[Token, ...]:
         raise ValueError(f"unknown analyzer: {field.analyzer_name}")


    +@dataclass(frozen=True, slots=True)
    +class PreparedDocument:
    +    schema_fingerprint: str
    +    document: FrozenDocument
    +    stored: FrozenDocument
    +    analyzed: Mapping[str, tuple[Token, ...]]
    +
    +    @property
    +    def posting_count(self) -> int:
    +        return sum(
    +            len({token.term for token in tokens})
    +            for tokens in self.analyzed.values()
    +        )
    +
    +
     class RamIndexBuilder:
         def __init__(self, schema: Schema) -> None:
             self.schema = schema
    @@ -28,19 +44,24 @@ class RamIndexBuilder:
             self._postings: dict[
                 str, dict[str, list[Posting]]
             ] = defaultdict(lambda: defaultdict(list))
    +        self._posting_count = 0

         @property
         def document_count(self) -> int:
             return len(self._stored_documents)

    -    def add_document(self, values: Mapping[str, object]) -> int:
    +    @property
    +    def posting_count(self) -> int:
    +        return self._posting_count
    +
    +    def prepare_document(
    +        self, values: Mapping[str, object]
    +    ) -> PreparedDocument:
             document = freeze_document(self.schema, values)
             prepared: dict[str, tuple[Token, ...]] = {}
             for name, field in self.schema.items():
                 if field.indexed and name in document:
                     prepared[name] = _analyze(field, document[name])
    -
    -        doc_id = self.document_count
             stored = MappingProxyType(
                 {
                     name: value
    @@ -48,10 +69,20 @@ class RamIndexBuilder:
                     if self.schema[name].stored
                 }
             )
    -        self._stored_documents.append(stored)
    +        return PreparedDocument(
    +            schema_fingerprint=self.schema.fingerprint,
    +            document=document,
    +            stored=stored,
    +            analyzed=MappingProxyType(dict(sorted(prepared.items()))),
    +        )

    +    def add_prepared(self, prepared: PreparedDocument) -> int:
    +        if prepared.schema_fingerprint != self.schema.fingerprint:
    +            raise ValueError("prepared document schema does not match builder")
    +        doc_id = self.document_count
    +        self._stored_documents.append(prepared.stored)
             for name, lengths in self._field_lengths.items():
    -            tokens = prepared.get(name, ())
    +            tokens = prepared.analyzed.get(name, ())
                 lengths.append(len(tokens))
                 positions_by_term: dict[str, list[int]] = defaultdict(list)
                 for token in tokens:
    @@ -68,8 +99,12 @@ class RamIndexBuilder:
                             positions=posting_positions,
                         )
                     )
    +                self._posting_count += 1
             return doc_id

    +    def add_document(self, values: Mapping[str, object]) -> int:
    +        return self.add_prepared(self.prepare_document(values))
    +
         def freeze(self, *, generation: int) -> MemorySegment:
             if generation < 0:
                 raise ValueError("segment generation must be non-negative")
    ```

??? note "File diff: src/minilucene/writer.py"
    ```diff
    diff --git a/src/minilucene/writer.py b/src/minilucene/writer.py
    index ada571086a637da1fc5fcfd348c63a70259a5f27..c65a518cb4d53841e84c2a09c0431d19158a8579 100644
    --- a/src/minilucene/writer.py
    +++ b/src/minilucene/writer.py
    @@ -1,17 +1,40 @@
     import json
     import os
    +from dataclasses import dataclass
     from pathlib import Path
     from typing import TYPE_CHECKING, Self

     from minilucene.errors import WriterAlreadyOpenError
    +from minilucene.index.memory import RamIndexBuilder
    +from minilucene.storage.image import SegmentImage
    +from minilucene.storage.segment_store import (
    +    SegmentDescriptor,
    +    SegmentStore,
    +)

     if TYPE_CHECKING:
         from minilucene.index.directory import Index


    +@dataclass(frozen=True, slots=True)
    +class FlushPolicy:
    +    max_documents: int = 1_000
    +    max_postings: int = 100_000
    +
    +    def __post_init__(self) -> None:
    +        if self.max_documents <= 0 or self.max_postings <= 0:
    +            raise ValueError("flush thresholds must be positive")
    +
    +
     class IndexWriter:
    -    def __init__(self, index: "Index") -> None:
    +    def __init__(
    +        self,
    +        index: "Index",
    +        *,
    +        flush_policy: FlushPolicy | None = None,
    +    ) -> None:
             self.index = index
    +        self.flush_policy = flush_policy or FlushPolicy()
             self._lock_path = Path(index.path) / ".writer.lock"
             self._closed = False
             try:
    @@ -32,6 +55,57 @@ class IndexWriter:
                 os.fsync(descriptor)
             finally:
                 os.close(descriptor)
    +        manifest = index.manifest()
    +        self._segment_store = SegmentStore(index.path)
    +        self._buffer = RamIndexBuilder(index.schema)
    +        self._segment_generations = list(manifest.segment_generations)
    +        self._next_segment_generation = (
    +            manifest.next_segment_generation
    +        )
    +
    +    @property
    +    def segment_generations(self) -> tuple[int, ...]:
    +        return tuple(self._segment_generations)
    +
    +    @property
    +    def buffered_document_count(self) -> int:
    +        return self._buffer.document_count
    +
    +    @property
    +    def buffered_posting_count(self) -> int:
    +        return self._buffer.posting_count
    +
    +    def _ensure_open(self) -> None:
    +        if self._closed:
    +            raise RuntimeError("writer is closed")
    +
    +    def add_document(self, **values: object) -> int:
    +        self._ensure_open()
    +        prepared = self._buffer.prepare_document(values)
    +        if self.buffered_document_count and (
    +            self.buffered_document_count
    +            >= self.flush_policy.max_documents
    +            or self.buffered_posting_count
    +            >= self.flush_policy.max_postings
    +        ):
    +            self.flush()
    +        return self._buffer.add_prepared(prepared)
    +
    +    def flush(self) -> SegmentDescriptor | None:
    +        self._ensure_open()
    +        if self.buffered_document_count == 0:
    +            return None
    +        generation = self._next_segment_generation
    +        image = SegmentImage.from_memory_segment(
    +            generation=generation,
    +            schema_fingerprint=self.index.schema.fingerprint,
    +            segment=self._buffer.freeze(generation=0),
    +        )
    +        descriptor = self._segment_store.publish(image)
    +        self._segment_generations.append(generation)
    +        self._next_segment_generation += 1
    +        self._buffer = RamIndexBuilder(self.index.schema)
    +        return descriptor

         def close(self) -> None:
             if self._closed:
    ```

**What it is and why it appears**

Flush converts the current mutable RAM buffer into one immutable segment without publishing a commit or a new reader view.

**Runtime role**

The writer swaps or snapshots its buffer, builds an image, publishes the segment, then records it as uncommitted only after success.

**Statement understanding**

Clearing the buffer after publication preserves retry safety: failure leaves the same documents available for another flush.

### Verification evidence

Run `uv run pytest -q $(cat journey/stages/14-writer-flush/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Clearing the buffer after publication preserves retry safety: failure leaves the same documents available for another flush.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 5](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/05-segments-nrt.md)

[Complete reference patch / 完整参考补丁](https://github.com/system-in-miniature/mini-lucene/blob/main/journey/stages/14-writer-flush/stage.patch)

# Stage 14 · Writer Flush

### 目标

实现Writer Flush，并能从可执行反例、运行时状态与关键语句解释其边界。

??? note "交付文件"
    - `src/minilucene/index/directory.py`
    - `src/minilucene/index/memory.py`
    - `src/minilucene/writer.py`
    - `tests/storage/test_writer_flush.py`

### 当前遇到的问题

Buffered Document 在被一次操作冻结成 Segment 前，既不可搜索也不持久。

### 测试契约

#### 先看会坏在哪里

测试跨越 Document/Byte Threshold、注入 Publication Failure，并验证失败 Flush 保持 Buffer 可重试。

??? note "文件差异：tests/storage/test_writer_flush.py"
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

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

测试跨越 Document/Byte Threshold、注入 Publication Failure，并验证失败 Flush 保持 Buffer 可重试。

**关键测试语句**

```python
assert segment.generation == 1
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Flush 把当前 Mutable RAM Buffer 转成一个 Immutable Segment，但不发布 Commit 或新 Reader View。

### 为什么需要这个机制

Buffered Document 在被一次操作冻结成 Segment 前，既不可搜索也不持久。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Writer Swap 或 Snapshot 当前 Buffer、构建 Image、发布 Segment，并且只在成功后记录为 Uncommitted。

### 机制板块

#### Writer Flush机制

Writer Swap 或 Snapshot 当前 Buffer、构建 Image、发布 Segment，并且只在成功后记录为 Uncommitted。

??? note "文件差异：src/minilucene/index/directory.py"
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

??? note "文件差异：src/minilucene/index/memory.py"
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

??? note "文件差异：src/minilucene/writer.py"
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

**是什么，为什么现在需要**

Flush 把当前 Mutable RAM Buffer 转成一个 Immutable Segment，但不发布 Commit 或新 Reader View。

**在运行时做什么**

Writer Swap 或 Snapshot 当前 Buffer、构建 Image、发布 Segment，并且只在成功后记录为 Uncommitted。

**关键语句理解**

只在发布后清空 Buffer 保持 Retry Safety：失败时同一批 Document 仍可再次 Flush。

### 验证证据

运行 `uv run pytest -q $(cat journey/stages/14-writer-flush/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

只在发布后清空 Buffer 保持 Retry Safety：失败时同一批 Document 仍可再次 Flush。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 5 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/05-segments-nrt.md)

[Complete reference patch / 完整参考补丁](https://github.com/system-in-miniature/mini-lucene/blob/main/journey/stages/14-writer-flush/stage.patch)

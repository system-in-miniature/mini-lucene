# Stage 17 · Near-real-time Refresh

### 目标

实现Near-real-time Refresh，并能从可执行反例、运行时状态与关键语句解释其边界。

??? note "交付文件"
    - `src/minilucene/storage/segment_store.py`
    - `src/minilucene/writer.py`
    - `tests/nrt/test_refresh_visibility.py`

### 当前遇到的问题

每次搜索都等待 Durable Commit，会让已 Flush 新数据在进程内不必要地不可见。

### 测试契约

#### 先看会坏在哪里

契约沿一条 Document Timeline 区分 Buffered、Flushed、Refreshed、Committed 与 Reopened View。

??? note "文件差异：tests/nrt/test_refresh_visibility.py"
    ```diff
    diff --git a/tests/nrt/test_refresh_visibility.py b/tests/nrt/test_refresh_visibility.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..5ba0cbc9c0dd12797a36e3183d5f4476c946ce4d
    --- /dev/null
    +++ b/tests/nrt/test_refresh_visibility.py
    @@ -0,0 +1,56 @@
    +from minilucene import Index, KeywordField, Schema, TextField
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
    +def test_refresh_sees_flushed_uncommitted_documents(tmp_path):
    +    index = build_index(tmp_path)
    +    committed = index.open_reader()
    +    with index.writer() as writer:
    +        writer.add_document(id="1", body="visible")
    +        nrt = writer.refresh()
    +        assert nrt.search(TermQuery("body", "visible"), top_k=10).total_hits == 1
    +        assert nrt.snapshot.commit_generation is None
    +        assert committed.max_doc == 0
    +        assert index.open_reader().max_doc == 0
    +
    +
    +def test_uncommitted_refresh_state_disappears_after_process_reopen(tmp_path):
    +    index = build_index(tmp_path)
    +    with index.writer() as writer:
    +        writer.add_document(id="1", body="ephemeral")
    +        assert writer.refresh().max_doc == 1
    +    reopened = Index.open(tmp_path)
    +    assert reopened.open_reader().max_doc == 0
    +
    +
    +def test_old_nrt_reader_stays_unchanged_after_later_refresh(tmp_path):
    +    index = build_index(tmp_path)
    +    with index.writer() as writer:
    +        writer.add_document(id="1", body="first")
    +        first = writer.refresh()
    +        writer.add_document(id="2", body="second")
    +        second = writer.refresh()
    +        assert first.max_doc == 1
    +        assert second.max_doc == 2
    +        assert first.search(TermQuery("body", "second"), top_k=10).total_hits == 0
    +
    +
    +def test_new_writer_skips_generation_of_prior_orphan(tmp_path):
    +    index = build_index(tmp_path)
    +    with index.writer() as writer:
    +        writer.add_document(id="1", body="orphan")
    +        assert writer.refresh().snapshot.segments[0].generation == 1
    +    with index.writer() as writer:
    +        writer.add_document(id="2", body="next")
    +        reader = writer.refresh()
    +        assert reader.snapshot.segments[0].generation == 2
    ```

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

契约沿一条 Document Timeline 区分 Buffered、Flushed、Refreshed、Committed 与 Reopened View。

**关键测试语句**

```python
assert nrt.search(TermQuery("body", "visible"), top_k=10).total_hits == 1
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Refresh 从当前 Segment 发布新的进程内 Snapshot；Commit 发布 Restart Root。Near-real-time 描述可见性而非较弱索引。

### 为什么需要这个机制

每次搜索都等待 Durable Commit，会让已 Flush 新数据在进程内不必要地不可见。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Refresh 必要时 Flush、捕获当前 Segment/Live-doc Generation，并返回 Reader，但不替换 Durable Manifest。

### 机制板块

#### Near-real-time Refresh机制

Refresh 必要时 Flush、捕获当前 Segment/Live-doc Generation，并返回 Reader，但不替换 Durable Manifest。

??? note "文件差异：src/minilucene/storage/segment_store.py"
    ```diff
    diff --git a/src/minilucene/storage/segment_store.py b/src/minilucene/storage/segment_store.py
    index b809a9b48390f86ebe211aa9ffa5d0937b52b28b..294c01091a2753a3deff73cd1da54b76faa7e6a4 100644
    --- a/src/minilucene/storage/segment_store.py
    +++ b/src/minilucene/storage/segment_store.py
    @@ -44,6 +44,11 @@ class SegmentStore:
         def _directory_name(generation: int) -> str:
             return f"seg_{generation:06d}"

    +    def generation_exists(self, generation: int) -> bool:
    +        return self.fs.exists(
    +            self.segments_path / self._directory_name(generation)
    +        )
    +
         def publish(self, image: SegmentImage) -> SegmentDescriptor:
             relative_path = Path("segments") / self._directory_name(
                 image.generation
    ```

??? note "文件差异：src/minilucene/writer.py"
    ```diff
    diff --git a/src/minilucene/writer.py b/src/minilucene/writer.py
    index 5746535d16c379f6a64cf1b29a0a9cc674879048..baae188c44b902865368f15986cb4f69e6973aa0 100644
    --- a/src/minilucene/writer.py
    +++ b/src/minilucene/writer.py
    @@ -6,6 +6,7 @@ from typing import TYPE_CHECKING, Self

     from minilucene.errors import WriterAlreadyOpenError
     from minilucene.index.memory import RamIndexBuilder
    +from minilucene.reader import IndexReader
     from minilucene.storage.image import SegmentImage
     from minilucene.storage.manifest import (
         Manifest,
    @@ -102,6 +103,8 @@ class IndexWriter:
             if self.buffered_document_count == 0:
                 return None
             generation = self._next_segment_generation
    +        while self._segment_store.generation_exists(generation):
    +            generation += 1
             image = SegmentImage.from_memory_segment(
                 generation=generation,
                 schema_fingerprint=self.index.schema.fingerprint,
    @@ -109,10 +112,25 @@ class IndexWriter:
             )
             descriptor = self._segment_store.publish(image)
             self._segment_generations.append(generation)
    -        self._next_segment_generation += 1
    +        self._next_segment_generation = generation + 1
             self._buffer = RamIndexBuilder(self.index.schema)
             return descriptor

    +    def refresh(self) -> IndexReader:
    +        self._ensure_open()
    +        self.flush()
    +        segments = tuple(
    +            self._segment_store.open(
    +                generation, self.index.schema.fingerprint
    +            )
    +            for generation in self._segment_generations
    +        )
    +        return IndexReader(
    +            self.index.schema,
    +            segments,
    +            commit_generation=None,
    +        )
    +
         def commit(self) -> Manifest:
             self._ensure_open()
             self.flush()
    ```

**是什么，为什么现在需要**

Refresh 从当前 Segment 发布新的进程内 Snapshot；Commit 发布 Restart Root。Near-real-time 描述可见性而非较弱索引。

**在运行时做什么**

Refresh 必要时 Flush、捕获当前 Segment/Live-doc Generation，并返回 Reader，但不替换 Durable Manifest。

**关键语句理解**

把 Refresh 与 Commit 分开，解释了 Document 为何现在可搜索，却可能在 Crash/Reopen 后消失。

### 验证证据

运行 `uv run pytest -q $(cat journey/stages/17-nrt-refresh/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

把 Refresh 与 Commit 分开，解释了 Document 为何现在可搜索，却可能在 Crash/Reopen 后消失。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 5 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/05-segments-nrt.md)

[Complete reference patch / 完整参考补丁](https://github.com/system-in-miniature/mini-lucene/blob/main/journey/stages/17-nrt-refresh/stage.patch)

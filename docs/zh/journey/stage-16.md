# Stage 16 · 时间点 Reader Snapshot

### 目标

实现时间点 Reader Snapshot，并能从可执行反例、运行时状态与关键语句解释其边界。

??? note "交付文件"
    - `src/minilucene/errors.py`
    - `src/minilucene/index/directory.py`
    - `src/minilucene/reader.py`
    - `src/minilucene/snapshot.py`
    - `tests/nrt/test_reader_snapshot.py`

### 当前遇到的问题

若 Reader 原地跟随 Writer Mutation，就无法在 Refresh、Delete 或 Merge 间提供稳定结果。

### 测试契约

#### 先看会坏在哪里

测试打开旧 Reader、发布新状态，并证明旧 Reader 的 Segment、Live Docs、Statistic 与 Hit 不变。

??? note "文件差异：tests/nrt/test_reader_snapshot.py"
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

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

测试打开旧 Reader、发布新状态，并证明旧 Reader 的 Segment、Live Docs、Statistic 与 Hit 不变。

**关键测试语句**

```python
assert old_reader.max_doc == 1
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Reader Snapshot 在 Open 时冻结 Segment Identity 与 Visibility Metadata，并拥有这些不可变资源的引用。

### 为什么需要这个机制

若 Reader 原地跟随 Writer Mutation，就无法在 Refresh、Delete 或 Merge 间提供稳定结果。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Open 捕获当前 Publication View；Search 只读取捕获对象；Close 释放 Ownership 且不查询后续 Writer State。

### 机制板块

#### 时间点 Reader Snapshot机制

Open 捕获当前 Publication View；Search 只读取捕获对象；Close 释放 Ownership 且不查询后续 Writer State。

??? note "文件差异：src/minilucene/errors.py"
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

??? note "文件差异：src/minilucene/index/directory.py"
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

??? note "文件差异：src/minilucene/reader.py"
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

??? note "文件差异：src/minilucene/snapshot.py"
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

**是什么，为什么现在需要**

Reader Snapshot 在 Open 时冻结 Segment Identity 与 Visibility Metadata，并拥有这些不可变资源的引用。

**在运行时做什么**

Open 捕获当前 Publication View；Search 只读取捕获对象；Close 释放 Ownership 且不查询后续 Writer State。

**关键语句理解**

因为 Segment 不可变且 Visibility Overlay 有版本，只复制 Reference Set 而非内容就足够。

### 验证证据

运行 `uv run pytest -q $(cat journey/stages/16-reader-snapshots/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

因为 Segment 不可变且 Visibility Overlay 有版本，只复制 Reference Set 而非内容就足够。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 5 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/05-segments-nrt.md)

[Complete reference patch / 完整参考补丁](https://github.com/system-in-miniature/mini-lucene/blob/main/journey/stages/16-reader-snapshots/stage.patch)

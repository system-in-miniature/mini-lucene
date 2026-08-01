# Stage 15 · 原子 Commit 与重开

### 目标

实现原子 Commit 与重开，并能从可执行反例、运行时状态与关键语句解释其边界。

??? note "交付文件"
    - `src/minilucene/__init__.py`
    - `src/minilucene/index/directory.py`
    - `src/minilucene/reader.py`
    - `src/minilucene/writer.py`
    - `tests/acceptance/test_phase2_storage_commit.py`
    - `tests/contract/test_disk_search.py`
    - `tests/storage/test_commit_recovery.py`

### 当前遇到的问题

Flushed Segment 虽已在磁盘，却要等 Manifest Root 发布后才能在 Restart 后可见。

### 测试契约

#### 先看会坏在哪里

Commit 测试在 Root Replacement 前和过程中失败、反复重开，并要求只看到完整上一代或下一代。

??? note "文件差异：tests/acceptance/test_phase2_storage_commit.py"
    ```diff
    diff --git a/tests/acceptance/test_phase2_storage_commit.py b/tests/acceptance/test_phase2_storage_commit.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..4af9be6fad70e784b4bd2b95cbb5b5da1e67794a
    --- /dev/null
    +++ b/tests/acceptance/test_phase2_storage_commit.py
    @@ -0,0 +1,64 @@
    +import pytest
    +
    +from minilucene import Index, KeywordField, MemoryIndex, Schema, TextField
    +from minilucene.query import PhraseQuery, TermQuery
    +
    +
    +def test_restart_reads_only_committed_checksummed_segments(tmp_path):
    +    schema = Schema(
    +        id=KeywordField(stored=True),
    +        title=TextField(stored=True, boost=2.0),
    +        body=TextField(stored=True),
    +    )
    +    documents = (
    +        {
    +            "id": "1",
    +            "title": "Kafka",
    +            "body": "follower replicas",
    +        },
    +        {
    +            "id": "2",
    +            "title": "Rabbit",
    +            "body": "message replicas",
    +        },
    +    )
    +    memory = MemoryIndex(schema)
    +    index = Index.create(tmp_path, schema)
    +    with index.writer() as writer:
    +        for document in documents:
    +            memory.add_document(**document)
    +            writer.add_document(**document)
    +            writer.flush()
    +        manifest = writer.commit()
    +
    +    assert manifest.segment_generations == (1, 2)
    +    reopened = Index.open(tmp_path)
    +    assert reopened.schema.fingerprint == schema.fingerprint
    +    reader = reopened.open_reader()
    +
    +    for query in (
    +        TermQuery("body", "replicas"),
    +        PhraseQuery("body", ("follower", "replicas")),
    +    ):
    +        expected = memory.search(query, top_k=10)
    +        actual = reader.search(query, top_k=10)
    +        assert actual.total_hits == expected.total_hits
    +        assert [
    +            hit.stored_fields["id"] for hit in actual.hits
    +        ] == [hit.stored_fields["id"] for hit in expected.hits]
    +        assert [hit.score for hit in actual.hits] == pytest.approx(
    +            [hit.score for hit in expected.hits]
    +        )
    +
    +    with reopened.writer() as writer:
    +        writer.add_document(id="3", title="Orphan", body="not committed")
    +        writer.flush()
    +    crashed_view = Index.open(tmp_path).open_reader()
    +    assert (
    +        crashed_view.search(
    +            TermQuery("body", "not"),
    +            top_k=10,
    +        ).total_hits
    +        == 0
    +    )
    +    assert crashed_view.max_doc == 2
    ```

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

Commit 测试在 Root Replacement 前和过程中失败、反复重开，并要求只看到完整上一代或下一代。

**关键测试语句**

```python
assert manifest.segment_generations == (1, 2)
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

??? note "文件差异：tests/contract/test_disk_search.py"
    ```diff
    diff --git a/tests/contract/test_disk_search.py b/tests/contract/test_disk_search.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..70d53ca7c7063a34f0e5bf9429e334440b2c3f81
    --- /dev/null
    +++ b/tests/contract/test_disk_search.py
    @@ -0,0 +1,72 @@
    +import pytest
    +
    +from minilucene import Index, KeywordField, MemoryIndex, Schema, TextField
    +from minilucene.query import (
    +    BooleanClause,
    +    BooleanQuery,
    +    Occur,
    +    PhraseQuery,
    +    PrefixQuery,
    +    TermQuery,
    +)
    +
    +
    +def test_disk_search_matches_in_memory_oracle_after_reopen(tmp_path):
    +    schema = Schema(
    +        id=KeywordField(stored=True),
    +        title=TextField(stored=True, boost=2.0),
    +        body=TextField(stored=True),
    +    )
    +    documents = (
    +        {
    +            "id": "1",
    +            "title": "Kafka",
    +            "body": "follower replicas",
    +        },
    +        {
    +            "id": "2",
    +            "title": "Rabbit",
    +            "body": "message replicas",
    +        },
    +        {
    +            "id": "3",
    +            "title": "Kafka internals",
    +            "body": "follower distant replicas",
    +        },
    +    )
    +    memory = MemoryIndex(schema)
    +    disk = Index.create(tmp_path, schema)
    +    with disk.writer() as writer:
    +        for position, document in enumerate(documents):
    +            memory.add_document(**document)
    +            writer.add_document(**document)
    +            if position == 0:
    +                writer.flush()
    +        writer.commit()
    +
    +    reader = Index.open(tmp_path).open_reader()
    +    queries = (
    +        TermQuery("title", "kafka"),
    +        PhraseQuery("body", ("follower", "replicas")),
    +        PrefixQuery("title", "kaf"),
    +        BooleanQuery(
    +            (
    +                BooleanClause(
    +                    Occur.MUST, TermQuery("title", "kafka")
    +                ),
    +                BooleanClause(
    +                    Occur.MUST_NOT, TermQuery("body", "distant")
    +                ),
    +            )
    +        ),
    +    )
    +    for query in queries:
    +        expected = memory.search(query, top_k=10)
    +        actual = reader.search(query, top_k=10)
    +        assert actual.total_hits == expected.total_hits
    +        assert [
    +            hit.stored_fields["id"] for hit in actual.hits
    +        ] == [hit.stored_fields["id"] for hit in expected.hits]
    +        assert [hit.score for hit in actual.hits] == pytest.approx(
    +            [hit.score for hit in expected.hits]
    +        )
    ```

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

Commit 测试在 Root Replacement 前和过程中失败、反复重开，并要求只看到完整上一代或下一代。

**关键测试语句**

```python
assert manifest.segment_generations == (1, 2)
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

??? note "文件差异：tests/storage/test_commit_recovery.py"
    ```diff
    diff --git a/tests/storage/test_commit_recovery.py b/tests/storage/test_commit_recovery.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..dab4f076a44b22fd243291da759fa12978b7ea24
    --- /dev/null
    +++ b/tests/storage/test_commit_recovery.py
    @@ -0,0 +1,81 @@
    +import pytest
    +
    +from minilucene import Index, KeywordField, Schema, TextField
    +from minilucene.query import TermQuery
    +from minilucene.storage.filesystem import FileSystemOps
    +from minilucene.storage.manifest import ManifestStore
    +
    +
    +class ReplaceFailingFileSystem(FileSystemOps):
    +    def replace(self, source, destination):
    +        if destination.name == "manifest.json":
    +            raise OSError("injected manifest replacement failure")
    +        super().replace(source, destination)
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
    +def test_complete_segment_without_manifest_is_ignored_after_reopen(tmp_path):
    +    index = build_index(tmp_path)
    +    with index.writer() as writer:
    +        writer.add_document(id="1", body="orphan")
    +        writer.flush()
    +    reopened = Index.open(tmp_path)
    +    assert reopened.open_reader().max_doc == 0
    +
    +
    +def test_commit_flushes_and_reopen_searches_committed_data(tmp_path):
    +    index = build_index(tmp_path)
    +    with index.writer() as writer:
    +        writer.add_document(id="1", body="committed data")
    +        manifest = writer.commit()
    +    assert manifest.commit_generation == 1
    +    reopened = Index.open(tmp_path)
    +    result = reopened.open_reader().search(
    +        TermQuery("body", "committed"),
    +        top_k=10,
    +    )
    +    assert result.total_hits == 1
    +    assert result.hits[0].stored_fields["id"] == "1"
    +
    +
    +def test_manifest_replace_failure_preserves_previous_commit(tmp_path):
    +    index = build_index(tmp_path)
    +    with index.writer() as writer:
    +        writer.add_document(id="old", body="stable")
    +        writer.commit()
    +
    +    with index.writer() as writer:
    +        writer.add_document(id="new", body="unpublished")
    +        writer._manifest_store = ManifestStore(
    +            tmp_path,
    +            fs=ReplaceFailingFileSystem(),
    +        )
    +        with pytest.raises(OSError, match="injected"):
    +            writer.commit()
    +
    +    reader = Index.open(tmp_path).open_reader()
    +    assert reader.search(TermQuery("body", "stable"), top_k=10).total_hits == 1
    +    assert (
    +        reader.search(TermQuery("body", "unpublished"), top_k=10).total_hits
    +        == 0
    +    )
    +
    +
    +def test_commit_preserves_explicit_segment_order(tmp_path):
    +    index = build_index(tmp_path)
    +    with index.writer() as writer:
    +        writer.add_document(id="1", body="first")
    +        writer.flush()
    +        writer.add_document(id="2", body="second")
    +        manifest = writer.commit()
    +    assert manifest.segment_generations == (1, 2)
    +    assert Index.open(tmp_path).open_reader().max_doc == 2
    ```

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

Commit 测试在 Root Replacement 前和过程中失败、反复重开，并要求只看到完整上一代或下一代。

**关键测试语句**

```python
assert manifest.segment_generations == (1, 2)
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Commit 是已持久 Segment Child 之上的发布协议；Reopen 严格从当前 Manifest 重建 Index。

### 为什么需要这个机制

Flushed Segment 虽已在磁盘，却要等 Manifest Root 发布后才能在 Restart 后可见。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Writer 先 Flush、准备全部引用 Child、写下一 Manifest、原子 Swap Root，并只在成功后推进 Committed Generation。

### 机制板块

#### 原子 Commit 与重开机制

Writer 先 Flush、准备全部引用 Child、写下一 Manifest、原子 Swap Root，并只在成功后推进 Committed Generation。

??? note "文件差异：src/minilucene/index/directory.py"
    ```diff
    diff --git a/src/minilucene/index/directory.py b/src/minilucene/index/directory.py
    index 6f34b46c584c6af21517a3b8c6425eed6f4e474e..ae3e710519ac568491a09279ba609151cbe3ad13 100644
    --- a/src/minilucene/index/directory.py
    +++ b/src/minilucene/index/directory.py
    @@ -6,9 +6,11 @@ from minilucene.errors import (
         IndexNotFoundError,
         SchemaMismatchError,
     )
    +from minilucene.reader import IndexReader
     from minilucene.schema import Schema
     from minilucene.storage.filesystem import FileSystemOps
     from minilucene.storage.manifest import Manifest, ManifestStore
    +from minilucene.storage.segment_store import SegmentStore

     _SCHEMA_FORMAT_VERSION = 1

    @@ -114,3 +116,15 @@ class Index:
             from minilucene.writer import IndexWriter

             return IndexWriter(self, **options)
    +
    +    def open_reader(self) -> IndexReader:
    +        manifest = self.manifest()
    +        segment_store = SegmentStore(self.path)
    +        segments = tuple(
    +            segment_store.open(
    +                segment.segment_generation,
    +                manifest.schema_fingerprint,
    +            )
    +            for segment in manifest.segments
    +        )
    +        return IndexReader(self.schema, segments)
    ```

??? note "文件差异：src/minilucene/reader.py"
    ```diff
    diff --git a/src/minilucene/reader.py b/src/minilucene/reader.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..d578cec6147ebbc5fbbcfb37a335ee313daeb35f
    --- /dev/null
    +++ b/src/minilucene/reader.py
    @@ -0,0 +1,18 @@
    +from minilucene.query.model import Query
    +from minilucene.schema import Schema
    +from minilucene.search.collector import TopDocs
    +from minilucene.search.reader import ReaderView
    +from minilucene.search.searcher import IndexSearcher
    +from minilucene.storage.image import SegmentImage
    +
    +
    +class IndexReader(ReaderView):
    +    def __init__(
    +        self,
    +        schema: Schema,
    +        segments: tuple[SegmentImage, ...],
    +    ) -> None:
    +        super().__init__(schema, segments)  # type: ignore[arg-type]
    +
    +    def search(self, query: Query, *, top_k: int = 10) -> TopDocs:
    +        return IndexSearcher(self).search(query, top_k=top_k)
    ```

??? note "文件差异：src/minilucene/writer.py"
    ```diff
    diff --git a/src/minilucene/writer.py b/src/minilucene/writer.py
    index c65a518cb4d53841e84c2a09c0431d19158a8579..5746535d16c379f6a64cf1b29a0a9cc674879048 100644
    --- a/src/minilucene/writer.py
    +++ b/src/minilucene/writer.py
    @@ -7,6 +7,11 @@ from typing import TYPE_CHECKING, Self
     from minilucene.errors import WriterAlreadyOpenError
     from minilucene.index.memory import RamIndexBuilder
     from minilucene.storage.image import SegmentImage
    +from minilucene.storage.manifest import (
    +    Manifest,
    +    ManifestStore,
    +    SegmentCommit,
    +)
     from minilucene.storage.segment_store import (
         SegmentDescriptor,
         SegmentStore,
    @@ -57,6 +62,7 @@ class IndexWriter:
                 os.close(descriptor)
             manifest = index.manifest()
             self._segment_store = SegmentStore(index.path)
    +        self._manifest_store = ManifestStore(index.path)
             self._buffer = RamIndexBuilder(index.schema)
             self._segment_generations = list(manifest.segment_generations)
             self._next_segment_generation = (
    @@ -107,6 +113,25 @@ class IndexWriter:
             self._buffer = RamIndexBuilder(self.index.schema)
             return descriptor

    +    def commit(self) -> Manifest:
    +        self._ensure_open()
    +        self.flush()
    +        for generation in self._segment_generations:
    +            self._segment_store.open(
    +                generation, self.index.schema.fingerprint
    +            )
    +        current = self.index.manifest()
    +        manifest = Manifest.next_from(
    +            current,
    +            segments=tuple(
    +                SegmentCommit(segment_generation=generation)
    +                for generation in self._segment_generations
    +            ),
    +            next_segment_generation=self._next_segment_generation,
    +        )
    +        self._manifest_store.write_atomic(manifest)
    +        return manifest
    +
         def close(self) -> None:
             if self._closed:
                 return
    ```

**是什么，为什么现在需要**

Commit 是已持久 Segment Child 之上的发布协议；Reopen 严格从当前 Manifest 重建 Index。

**在运行时做什么**

Writer 先 Flush、准备全部引用 Child、写下一 Manifest、原子 Swap Root，并只在成功后推进 Committed Generation。

**关键语句理解**

Root 前 Fsync Child、Replacement 后 Fsync Directory，建立 Crash Ordering 证明。

#### 包、Fixture 与工程支撑

保持包导出、测试语料、依赖与运行环境可复现。

??? note "支撑文件差异（1 个文件）"
    **`src/minilucene/__init__.py`**

    ```diff
    diff --git a/src/minilucene/__init__.py b/src/minilucene/__init__.py
    index 0c0404820979d3e11380105fc7aeeadd1bc1ef57..26578c0be111c3c4f0dbb9c9848861796ee3d2e9 100644
    --- a/src/minilucene/__init__.py
    +++ b/src/minilucene/__init__.py
    @@ -1,9 +1,11 @@
     from minilucene.index.directory import Index
     from minilucene.index.memory import MemoryIndex
    +from minilucene.reader import IndexReader
     from minilucene.schema import KeywordField, Schema, StoredField, TextField

     __all__ = [
         "Index",
    +    "IndexReader",
         "KeywordField",
         "MemoryIndex",
         "Schema",
    ```


### 验证证据

运行 `uv run pytest -q $(cat journey/stages/15-atomic-commit/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

Root 前 Fsync Child、Replacement 后 Fsync Directory，建立 Crash Ordering 证明。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 7 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/07-commit-atomicity.md)

[Complete reference patch / 完整参考补丁](https://github.com/system-in-miniature/mini-lucene/blob/main/journey/stages/15-atomic-commit/stage.patch)

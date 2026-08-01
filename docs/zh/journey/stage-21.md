# Stage 21 · 显式 Segment Merge

### 目标

实现显式 Segment Merge，并能从可执行反例、运行时状态与关键语句解释其边界。

??? note "交付文件"
    - `src/minilucene/merge.py`
    - `src/minilucene/writer.py`
    - `tests/nrt/test_segment_merge.py`

### 当前遇到的问题

大量 Immutable Segment 增加 Lookup 与文件开销，但 Merge 不能复活已删 Document 或错误重编号可见历史。

### 测试契约

#### 先看会坏在哪里

测试合并含删除的 Segment、保留旧 Reader、注入 Output Failure，并比较发布前后结果。

??? note "文件差异：tests/nrt/test_segment_merge.py"
    ```diff
    diff --git a/tests/nrt/test_segment_merge.py b/tests/nrt/test_segment_merge.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..4a122c7ef2c0b83c402029d72d154b5bea9acca0
    --- /dev/null
    +++ b/tests/nrt/test_segment_merge.py
    @@ -0,0 +1,104 @@
    +import pytest
    +
    +from minilucene import Index, KeywordField, Schema, TextField
    +from minilucene.query import PhraseQuery, TermQuery
    +from minilucene.storage.filesystem import FileSystemOps
    +
    +
    +def build_index(tmp_path):
    +    index = Index.create(
    +        tmp_path,
    +        Schema(
    +            id=KeywordField(stored=True),
    +            body=TextField(stored=False),
    +        ),
    +    )
    +    with index.writer() as writer:
    +        writer.add_document(id="1", body="kafka kafka replicas")
    +        writer.flush()
    +        writer.add_document(id="2", body="deleted document")
    +        writer.flush()
    +        writer.add_document(id="3", body="kafka follower replicas")
    +        writer.commit()
    +    return index
    +
    +
    +def snapshot_results(reader):
    +    results = {}
    +    for name, query in (
    +        ("term", TermQuery("body", "kafka")),
    +        ("phrase", PhraseQuery("body", ("follower", "replicas"))),
    +    ):
    +        top_docs = reader.search(query, top_k=10)
    +        results[name] = (
    +            top_docs.total_hits,
    +            tuple(hit.stored_fields["id"] for hit in top_docs.hits),
    +            tuple(hit.score for hit in top_docs.hits),
    +        )
    +    return results
    +
    +
    +def test_merge_skips_deletes_and_preserves_search_results(tmp_path):
    +    index = build_index(tmp_path)
    +    with index.writer() as writer:
    +        writer.delete_by_term("id", "2")
    +        before = writer.refresh()
    +        expected = snapshot_results(before)
    +        merged = writer.merge(writer.segment_generations)
    +        after = writer.refresh()
    +
    +    assert merged.max_doc == before.num_live_docs
    +    actual = snapshot_results(after)
    +    assert actual.keys() == expected.keys()
    +    for name in expected:
    +        assert actual[name][:2] == expected[name][:2]
    +        assert actual[name][2] == pytest.approx(expected[name][2])
    +    assert after.snapshot.segments[0].generation == merged.generation
    +    assert after.snapshot.segments[0].image.max_doc == 2
    +    assert tuple(after.snapshot.segments[0].image.stored_documents) == (0, 1)
    +
    +
    +class PostingWriteFailingFileSystem(FileSystemOps):
    +    def write_bytes(self, path, data):
    +        if path.name == "postings.bin":
    +            raise OSError("injected merge write failure")
    +        super().write_bytes(path, data)
    +
    +
    +def test_merge_failure_leaves_writer_segment_set_unchanged(tmp_path):
    +    index = build_index(tmp_path)
    +    with index.writer() as writer:
    +        before_generations = writer.segment_generations
    +        before = snapshot_results(writer.refresh())
    +        writer._segment_store.fs = PostingWriteFailingFileSystem()
    +        with pytest.raises(OSError, match="injected"):
    +            writer.merge(before_generations)
    +        assert writer.segment_generations == before_generations
    +        writer._segment_store.fs = FileSystemOps()
    +        assert snapshot_results(writer.refresh()) == before
    +
    +
    +@pytest.mark.parametrize(
    +    "selected",
    +    [(1,), (1, 1), (99, 1)],
    +)
    +def test_merge_rejects_invalid_selection_without_mutation(tmp_path, selected):
    +    index = build_index(tmp_path)
    +    with index.writer() as writer:
    +        before = writer.segment_generations
    +        with pytest.raises(ValueError):
    +            writer.merge(selected)
    +        assert writer.segment_generations == before
    +
    +
    +def test_merged_segment_commits_and_reopens(tmp_path):
    +    index = build_index(tmp_path)
    +    with index.writer() as writer:
    +        writer.delete_by_term("id", "2")
    +        writer.merge(writer.segment_generations)
    +        manifest = writer.commit()
    +    assert len(manifest.segments) == 1
    +    reader = Index.open(tmp_path).open_reader()
    +    assert reader.num_live_docs == 2
    +    assert reader.search(TermQuery("body", "deleted"), top_k=10).total_hits == 0
    +    assert reader.search(TermQuery("body", "kafka"), top_k=10).total_hits == 2
    ```

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

测试合并含删除的 Segment、保留旧 Reader、注入 Output Failure，并比较发布前后结果。

**关键测试语句**

```python
assert merged.max_doc == before.num_live_docs
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Merge 捕获不可变 Input，只把 Live Document 复制到新的 Dense Segment，并在 Output Publication 后交换 Writer Ownership。

### 为什么需要这个机制

大量 Immutable Segment 增加 Lookup 与文件开销，但 Merge 不能复活已删 Document 或错误重编号可见历史。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Writer Pin 输入 Generation、构建 Doc-ID Remap 与 Output Image、发布后替换当前 Segment Reference 并 Retire Input。

### 机制板块

#### 显式 Segment Merge机制

Writer Pin 输入 Generation、构建 Doc-ID Remap 与 Output Image、发布后替换当前 Segment Reference 并 Retire Input。

??? note "文件差异：src/minilucene/merge.py"
    ```diff
    diff --git a/src/minilucene/merge.py b/src/minilucene/merge.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..53e32b8a0d2d8c2e789f345f884e040543427fda
    --- /dev/null
    +++ b/src/minilucene/merge.py
    @@ -0,0 +1,73 @@
    +from collections import defaultdict
    +
    +from minilucene.index.postings import Posting
    +from minilucene.storage.image import SegmentImage
    +
    +
    +def merge_segment_images(
    +    *,
    +    generation: int,
    +    schema_fingerprint: str,
    +    segments: tuple[tuple[SegmentImage, frozenset[int]], ...],
    +) -> SegmentImage:
    +    doc_id_maps: list[dict[int, int]] = []
    +    stored_documents: dict[int, dict[str, str]] = {}
    +    next_doc_id = 0
    +    all_fields = {
    +        field
    +        for image, _ in segments
    +        for field in image.field_lengths
    +    }
    +    field_lengths: dict[str, list[int]] = {
    +        field: [] for field in all_fields
    +    }
    +
    +    for image, live_docs in segments:
    +        mapping: dict[int, int] = {}
    +        for old_doc_id in sorted(live_docs):
    +            mapping[old_doc_id] = next_doc_id
    +            stored_documents[next_doc_id] = dict(
    +                image.stored_documents[old_doc_id]
    +            )
    +            for field in all_fields:
    +                lengths = image.field_lengths.get(field)
    +                field_lengths[field].append(
    +                    lengths[old_doc_id] if lengths is not None else 0
    +                )
    +            next_doc_id += 1
    +        doc_id_maps.append(mapping)
    +
    +    postings: dict[str, dict[str, list[Posting]]] = defaultdict(
    +        lambda: defaultdict(list)
    +    )
    +    for (image, _), mapping in zip(
    +        segments, doc_id_maps, strict=True
    +    ):
    +        for field, terms in image.postings.items():
    +            for term, term_postings in terms.items():
    +                for posting in term_postings:
    +                    if posting.doc_id in mapping:
    +                        postings[field][term].append(
    +                            Posting(
    +                                doc_id=mapping[posting.doc_id],
    +                                term_frequency=posting.term_frequency,
    +                                positions=posting.positions,
    +                            )
    +                        )
    +
    +    return SegmentImage(
    +        generation=generation,
    +        schema_fingerprint=schema_fingerprint,
    +        stored_documents=stored_documents,
    +        postings={
    +            field: {
    +                term: tuple(term_postings)
    +                for term, term_postings in terms.items()
    +            }
    +            for field, terms in postings.items()
    +        },
    +        field_lengths={
    +            field: tuple(lengths)
    +            for field, lengths in field_lengths.items()
    +        },
    +    )
    ```

??? note "文件差异：src/minilucene/writer.py"
    ```diff
    diff --git a/src/minilucene/writer.py b/src/minilucene/writer.py
    index b703e8bb89d69b5a628e36e4e50f2da52fc8df5f..be777588c096c928c16450fb2e285d8d2e6b623b 100644
    --- a/src/minilucene/writer.py
    +++ b/src/minilucene/writer.py
    @@ -6,6 +6,7 @@ from typing import TYPE_CHECKING, Self

     from minilucene.errors import WriterAlreadyOpenError
     from minilucene.index.memory import RamIndexBuilder
    +from minilucene.merge import merge_segment_images
     from minilucene.reader import IndexReader
     from minilucene.storage.image import SegmentImage
     from minilucene.storage.live_docs import LiveDocsStore
    @@ -265,6 +266,76 @@ class IndexWriter:
             self._buffer_live_docs = next_buffer_live_docs
             return deleted

    +    def merge(
    +        self, segment_generations: tuple[int, ...] | list[int]
    +    ) -> SegmentDescriptor:
    +        self._ensure_open()
    +        selected = tuple(segment_generations)
    +        if len(selected) < 2:
    +            raise ValueError("merge requires at least two segments")
    +        if len(set(selected)) != len(selected):
    +            raise ValueError("merge segment generations must be unique")
    +        current_set = set(self._segment_generations)
    +        if any(generation not in current_set for generation in selected):
    +            raise ValueError("merge references unknown segment")
    +
    +        selected_set = set(selected)
    +        ordered_selected = tuple(
    +            generation
    +            for generation in self._segment_generations
    +            if generation in selected_set
    +        )
    +        captured = tuple(
    +            (
    +                self._segment_store.open(
    +                    generation, self.index.schema.fingerprint
    +                ),
    +                self._live_docs[generation],
    +            )
    +            for generation in ordered_selected
    +        )
    +
    +        generation = self._next_segment_generation
    +        while self._segment_store.generation_exists(generation):
    +            generation += 1
    +        image = merge_segment_images(
    +            generation=generation,
    +            schema_fingerprint=self.index.schema.fingerprint,
    +            segments=captured,
    +        )
    +        descriptor = self._segment_store.publish(image)
    +
    +        insertion_index = min(
    +            self._segment_generations.index(item)
    +            for item in ordered_selected
    +        )
    +        next_generations: list[int] = []
    +        for index, current in enumerate(self._segment_generations):
    +            if index == insertion_index:
    +                next_generations.append(generation)
    +            if current not in selected_set:
    +                next_generations.append(current)
    +
    +        next_live_docs = {
    +            item: mask
    +            for item, mask in self._live_docs.items()
    +            if item not in selected_set
    +        }
    +        next_live_docs[generation] = frozenset(range(image.max_doc))
    +        next_metadata = {
    +            item: metadata
    +            for item, metadata in self._live_docs_metadata.items()
    +            if item not in selected_set
    +        }
    +        next_metadata[generation] = None
    +
    +        self._segment_generations = next_generations
    +        self._live_docs = next_live_docs
    +        self._live_docs_metadata = next_metadata
    +        self._dirty_live_docs.difference_update(selected_set)
    +        self._next_segment_generation = generation + 1
    +        return descriptor
    +
         def commit(self) -> Manifest:
             self._ensure_open()
             self.flush()
    ```

**是什么，为什么现在需要**

Merge 捕获不可变 Input，只把 Live Document 复制到新的 Dense Segment，并在 Output Publication 后交换 Writer Ownership。

**在运行时做什么**

Writer Pin 输入 Generation、构建 Doc-ID Remap 与 Output Image、发布后替换当前 Segment Reference 并 Retire Input。

**关键语句理解**

先发布 Output 再 Swap State，使失败时旧 Segment Set 仍权威且旧 Reader 有效。

### 验证证据

运行 `uv run pytest -q $(cat journey/stages/21-segment-merge/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

先发布 Output 再 Swap State，使失败时旧 Segment Set 仍权威且旧 Reader 有效。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 10 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/10-merge-and-beyond.md)

[Complete reference patch / 完整参考补丁](https://github.com/system-in-miniature/mini-lucene/blob/main/journey/stages/21-segment-merge/stage.patch)

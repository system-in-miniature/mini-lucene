# Stage 20 · Update 与仅 Live 统计

### 目标

实现Update 与仅 Live 统计，并能从可执行反例、运行时状态与关键语句解释其边界。

??? note "交付文件"
    - `src/minilucene/writer.py`
    - `tests/nrt/test_live_bm25_stats.py`
    - `tests/nrt/test_update_document.py`

### 当前遇到的问题

把 Update 实现为先 Add 后 Delete 会删掉替代 Document，且已删除 Document 不应继续影响 Ranking。

### 测试契约

#### 先看会坏在哪里

反例 Update 多个 Match、注入 Add Failure，并比较多个 Snapshot 中删除前后的 BM25。

??? note "文件差异：tests/nrt/test_live_bm25_stats.py"
    ```diff
    diff --git a/tests/nrt/test_live_bm25_stats.py b/tests/nrt/test_live_bm25_stats.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..c52ea9b67cc1e5017bf226683b7925973a0ee323
    --- /dev/null
    +++ b/tests/nrt/test_live_bm25_stats.py
    @@ -0,0 +1,48 @@
    +import pytest
    +
    +from minilucene import Index, KeywordField, MemoryIndex, Schema, TextField
    +from minilucene.query import TermQuery
    +
    +
    +def test_deleted_documents_do_not_change_global_multisegment_bm25(tmp_path):
    +    schema = Schema(
    +        id=KeywordField(stored=True),
    +        body=TextField(stored=True),
    +    )
    +    live_documents = (
    +        {"id": "1", "body": "kafka kafka"},
    +        {"id": "3", "body": "kafka replicas"},
    +    )
    +    oracle = MemoryIndex(schema)
    +    for document in live_documents:
    +        oracle.add_document(**document)
    +
    +    index = Index.create(tmp_path, schema)
    +    with index.writer() as writer:
    +        writer.add_document(**live_documents[0])
    +        writer.flush()
    +        writer.add_document(
    +            id="2",
    +            body=("kafka " * 50) + "deleted noise",
    +        )
    +        writer.flush()
    +        writer.add_document(**live_documents[1])
    +        writer.commit()
    +    with index.writer() as writer:
    +        writer.delete_by_term("id", "2")
    +        reader = writer.refresh()
    +
    +    stats = reader.corpus_stats
    +    assert stats.live_doc_count == 2
    +    assert stats.doc_frequency("body", "kafka") == 2
    +    assert stats.average_length("body") == 2.0
    +
    +    query = TermQuery("body", "kafka")
    +    expected = oracle.search(query, top_k=10)
    +    actual = reader.search(query, top_k=10)
    +    assert [hit.stored_fields["id"] for hit in actual.hits] == [
    +        hit.stored_fields["id"] for hit in expected.hits
    +    ]
    +    assert [hit.score for hit in actual.hits] == pytest.approx(
    +        [hit.score for hit in expected.hits]
    +    )
    ```

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

反例 Update 多个 Match、注入 Add Failure，并比较多个 Snapshot 中删除前后的 BM25。

**关键测试语句**

```python
assert stats.live_doc_count == 2
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

??? note "文件差异：tests/nrt/test_update_document.py"
    ```diff
    diff --git a/tests/nrt/test_update_document.py b/tests/nrt/test_update_document.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..e286f0970c1e3bfc26f22267452f915252076fc2
    --- /dev/null
    +++ b/tests/nrt/test_update_document.py
    @@ -0,0 +1,98 @@
    +import pytest
    +
    +from minilucene import Index, KeywordField, Schema, TextField
    +from minilucene.query import TermQuery
    +from minilucene.schema import SchemaError
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
    +def test_update_deletes_all_matches_then_adds_one_replacement(tmp_path):
    +    index = build_index(tmp_path)
    +    with index.writer() as writer:
    +        writer.add_document(id="1", body="old one")
    +        writer.add_document(id="1", body="old two")
    +        writer.commit()
    +        deleted = writer.update_document(
    +            field="id",
    +            term="1",
    +            id="1",
    +            body="replacement",
    +        )
    +        assert deleted == 2
    +        reader = writer.refresh()
    +    assert reader.search(TermQuery("body", "old"), top_k=10).total_hits == 0
    +    assert (
    +        reader.search(
    +            TermQuery("body", "replacement"),
    +            top_k=10,
    +        ).total_hits
    +        == 1
    +    )
    +
    +
    +def test_invalid_replacement_leaves_delete_state_unchanged(tmp_path):
    +    index = build_index(tmp_path)
    +    with index.writer() as writer:
    +        writer.add_document(id="1", body="old")
    +        writer.commit()
    +        with pytest.raises(SchemaError):
    +            writer.update_document(
    +                field="id",
    +                term="1",
    +                id="1",
    +                body=7,
    +            )
    +        assert (
    +            writer.refresh().search(
    +                TermQuery("body", "old"),
    +                top_k=10,
    +            ).total_hits
    +            == 1
    +        )
    +
    +
    +def test_update_replaces_buffered_document_without_intermediate_visibility(
    +    tmp_path,
    +):
    +    index = build_index(tmp_path)
    +    with index.writer() as writer:
    +        writer.add_document(id="1", body="buffered old")
    +        assert (
    +            writer.update_document(
    +                field="id",
    +                term="1",
    +                id="1",
    +                body="buffered new",
    +            )
    +            == 1
    +        )
    +        reader = writer.refresh()
    +    assert reader.search(TermQuery("body", "old"), top_k=10).total_hits == 0
    +    assert reader.search(TermQuery("body", "new"), top_k=10).total_hits == 1
    +
    +
    +def test_committed_update_survives_reopen(tmp_path):
    +    index = build_index(tmp_path)
    +    with index.writer() as writer:
    +        writer.add_document(id="1", body="before")
    +        writer.commit()
    +    with index.writer() as writer:
    +        writer.update_document(
    +            field="id",
    +            term="1",
    +            id="1",
    +            body="after",
    +        )
    +        writer.commit()
    +    reader = Index.open(tmp_path).open_reader()
    +    assert reader.search(TermQuery("body", "before"), top_k=10).total_hits == 0
    +    assert reader.search(TermQuery("body", "after"), top_k=10).total_hits == 1
    ```

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

反例 Update 多个 Match、注入 Add Failure，并比较多个 Snapshot 中删除前后的 BM25。

**关键测试语句**

```python
assert stats.live_doc_count == 2
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Update 是在一次 Writer Operation 中删除全部旧身份匹配并加入一个已校验新 Document；Corpus Statistic 只统计 Live Document。

### 为什么需要这个机制

把 Update 实现为先 Add 后 Delete 会删掉替代 Document，且已删除 Document 不应继续影响 Ranking。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Writer 先校验 Replacement、从更新前 View 派生 Delete Mask，再 Buffer 新 Document；Reader 只聚合 Live Posting 与 Norm。

### 机制板块

#### Update 与仅 Live 统计机制

Writer 先校验 Replacement、从更新前 View 派生 Delete Mask，再 Buffer 新 Document；Reader 只聚合 Live Posting 与 Norm。

??? note "文件差异：src/minilucene/writer.py"
    ```diff
    diff --git a/src/minilucene/writer.py b/src/minilucene/writer.py
    index 214a9fd68607a3051d3725739b590a3df345cb8f..b703e8bb89d69b5a628e36e4e50f2da52fc8df5f 100644
    --- a/src/minilucene/writer.py
    +++ b/src/minilucene/writer.py
    @@ -183,8 +183,9 @@ class IndexWriter:
                 commit_generation=None,
             )

    -    def delete_by_term(self, field: str, term: str) -> int:
    -        self._ensure_open()
    +    def _derive_delete(
    +        self, field: str, term: str
    +    ) -> tuple[dict[int, frozenset[int]], set[int], set[int], int]:
             if field not in self.index.schema:
                 raise ValueError(f"unknown field: {field}")
             if not self.index.schema[field].indexed:
    @@ -216,9 +217,51 @@ class IndexWriter:
             )
             next_buffer_live_docs = self._buffer_live_docs - buffered_matches
             deleted += len(buffered_matches)
    +        return (
    +            derived_masks,
    +            changed_generations,
    +            next_buffer_live_docs,
    +            deleted,
    +        )
    +
    +    def delete_by_term(self, field: str, term: str) -> int:
    +        self._ensure_open()
    +        (
    +            derived_masks,
    +            changed_generations,
    +            next_buffer_live_docs,
    +            deleted,
    +        ) = self._derive_delete(field, term)
    +        self._live_docs = derived_masks
    +        self._dirty_live_docs.update(changed_generations)
    +        self._buffer_live_docs = next_buffer_live_docs
    +        return deleted
    +
    +    def update_document(
    +        self,
    +        *,
    +        field: str,
    +        term: str,
    +        **replacement: object,
    +    ) -> int:
    +        self._ensure_open()
    +        prepared = self._buffer.prepare_document(replacement)
    +        (
    +            derived_masks,
    +            changed_generations,
    +            next_buffer_live_docs,
    +            deleted,
    +        ) = self._derive_delete(field, term)
    +
    +        next_buffer = RamIndexBuilder(self.index.schema)
    +        for document in self._buffer.documents:
    +            next_buffer.add_document(dict(document))
    +        replacement_doc_id = next_buffer.add_prepared(prepared)
    +        next_buffer_live_docs.add(replacement_doc_id)

             self._live_docs = derived_masks
             self._dirty_live_docs.update(changed_generations)
    +        self._buffer = next_buffer
             self._buffer_live_docs = next_buffer_live_docs
             return deleted

    ```

**是什么，为什么现在需要**

Update 是在一次 Writer Operation 中删除全部旧身份匹配并加入一个已校验新 Document；Corpus Statistic 只统计 Live Document。

**在运行时做什么**

Writer 先校验 Replacement、从更新前 View 派生 Delete Mask，再 Buffer 新 Document；Reader 只聚合 Live Posting 与 Norm。

**关键语句理解**

删除前校验防止错误 Replacement 摧毁旧数据；Live Filtering 让 Ranking 与可见 Hit 一致。

### 验证证据

运行 `uv run pytest -q $(cat journey/stages/20-update-live-stats/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

删除前校验防止错误 Replacement 摧毁旧数据；Live Filtering 让 Ranking 与可见 Hit 一致。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 6 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/06-deletes-updates.md)

[Complete reference patch / 完整参考补丁](https://github.com/system-in-miniature/mini-lucene/blob/main/journey/stages/20-update-live-stats/stage.patch)

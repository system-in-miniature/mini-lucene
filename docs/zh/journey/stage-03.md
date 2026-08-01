# Stage 03 · 不可变 RAM 倒排索引

### 目标

实现不可变 RAM 倒排索引，并能从可执行反例、运行时状态与关键语句解释其边界。

??? note "交付文件"
    - `src/minilucene/index/__init__.py`
    - `src/minilucene/index/memory.py`
    - `src/minilucene/index/postings.py`
    - `tests/contract/test_memory_index.py`

### 当前遇到的问题

校验后的 Document 仍需要一种结构回答某 Term 出现在哪些 Document、哪些位置。

### 测试契约

#### 先看会坏在哪里

测试索引重复 Term 与多 Field，再修改源输入以证明已构建 Segment 不会变化。

??? note "文件差异：tests/contract/test_memory_index.py"
    ```diff
    diff --git a/tests/contract/test_memory_index.py b/tests/contract/test_memory_index.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..e40a6cf30f9e15a20493fc11b4785759beae2545
    --- /dev/null
    +++ b/tests/contract/test_memory_index.py
    @@ -0,0 +1,70 @@
    +import pytest
    +
    +from minilucene.index.memory import RamIndexBuilder
    +from minilucene.schema import (
    +    KeywordField,
    +    Schema,
    +    SchemaError,
    +    StoredField,
    +    TextField,
    +)
    +
    +
    +def test_ram_segment_contains_positions_lengths_and_only_stored_values():
    +    schema = Schema(
    +        id=KeywordField(stored=True),
    +        body=TextField(stored=False),
    +        source=StoredField(),
    +    )
    +    builder = RamIndexBuilder(schema)
    +    builder.add_document(
    +        {"id": "d1", "body": "Kafka kafka replicas", "source": "manual"}
    +    )
    +    segment = builder.freeze(generation=1)
    +
    +    posting = segment.postings["body"]["kafka"][0]
    +    assert (posting.doc_id, posting.term_frequency, posting.positions) == (
    +        0,
    +        2,
    +        (0, 1),
    +    )
    +    assert segment.field_lengths["body"] == (3,)
    +    assert segment.stored_documents == (
    +        {"id": "d1", "source": "manual"},
    +    )
    +
    +
    +def test_keyword_field_indexes_one_exact_term_without_positions():
    +    builder = RamIndexBuilder(Schema(author=KeywordField()))
    +    builder.add_document({"author": "Jonah Smith"})
    +    segment = builder.freeze(generation=3)
    +    posting = segment.postings["author"]["Jonah Smith"][0]
    +    assert posting.term_frequency == 1
    +    assert posting.positions == ()
    +
    +
    +def test_missing_indexed_field_has_zero_length():
    +    builder = RamIndexBuilder(
    +        Schema(id=KeywordField(stored=True), body=TextField())
    +    )
    +    builder.add_document({"id": "1"})
    +    segment = builder.freeze(generation=1)
    +    assert segment.field_lengths["body"] == (0,)
    +    assert segment.field_lengths["id"] == (1,)
    +
    +
    +def test_failed_document_validation_does_not_mutate_builder():
    +    builder = RamIndexBuilder(Schema(body=TextField()))
    +    with pytest.raises(SchemaError):
    +        builder.add_document({"unknown": "value"})
    +    assert builder.freeze(generation=1).max_doc == 0
    +
    +
    +def test_frozen_segment_collections_are_immutable():
    +    builder = RamIndexBuilder(Schema(body=TextField(stored=True)))
    +    builder.add_document({"body": "search"})
    +    segment = builder.freeze(generation=1)
    +    with pytest.raises(TypeError):
    +        segment.postings["body"]["search"] = ()
    +    with pytest.raises(TypeError):
    +        segment.stored_documents[0]["body"] = "changed"
    ```

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

测试索引重复 Term 与多 Field，再修改源输入以证明已构建 Segment 不会变化。

**关键测试语句**

```python
assert (posting.doc_id, posting.term_frequency, posting.positions) == (
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Posting 绑定 Term、Doc ID、Frequency 与 Position；Norm 保存 Field Length；不可变 Segment 冻结一次索引代次。

### 为什么需要这个机制

校验后的 Document 仍需要一种结构回答某 Term 出现在哪些 Document、哪些位置。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Builder 分析可索引字段、分配 Local Doc ID、累积有序 Posting 与 Norm，最后发布不可变 Mapping。

### 机制板块

#### 不可变 RAM 倒排索引机制

Builder 分析可索引字段、分配 Local Doc ID、累积有序 Posting 与 Norm，最后发布不可变 Mapping。

??? note "文件差异：src/minilucene/index/memory.py"
    ```diff
    diff --git a/src/minilucene/index/memory.py b/src/minilucene/index/memory.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..4e2bff6c5b4479d1b4d081ede519b00e87b928eb
    --- /dev/null
    +++ b/src/minilucene/index/memory.py
    @@ -0,0 +1,98 @@
    +from collections import defaultdict
    +from collections.abc import Mapping
    +from types import MappingProxyType
    +
    +from minilucene.analysis import KeywordAnalyzer, StandardAnalyzer
    +from minilucene.analysis.model import Token
    +from minilucene.document import FrozenDocument, freeze_document
    +from minilucene.index.postings import MemorySegment, Posting
    +from minilucene.schema import FieldType, Schema
    +
    +
    +def _analyze(field: FieldType, value: str) -> tuple[Token, ...]:
    +    if field.analyzer_name == "standard":
    +        return StandardAnalyzer().analyze(value)
    +    if field.analyzer_name == "keyword":
    +        return KeywordAnalyzer().analyze(value)
    +    raise ValueError(f"unknown analyzer: {field.analyzer_name}")
    +
    +
    +class RamIndexBuilder:
    +    def __init__(self, schema: Schema) -> None:
    +        self.schema = schema
    +        self._stored_documents: list[FrozenDocument] = []
    +        self._field_lengths: dict[str, list[int]] = {
    +            name: [] for name, field in schema.items() if field.indexed
    +        }
    +        self._postings: dict[
    +            str, dict[str, list[Posting]]
    +        ] = defaultdict(lambda: defaultdict(list))
    +
    +    @property
    +    def document_count(self) -> int:
    +        return len(self._stored_documents)
    +
    +    def add_document(self, values: Mapping[str, object]) -> int:
    +        document = freeze_document(self.schema, values)
    +        prepared: dict[str, tuple[Token, ...]] = {}
    +        for name, field in self.schema.items():
    +            if field.indexed and name in document:
    +                prepared[name] = _analyze(field, document[name])
    +
    +        doc_id = self.document_count
    +        stored = MappingProxyType(
    +            {
    +                name: value
    +                for name, value in document.items()
    +                if self.schema[name].stored
    +            }
    +        )
    +        self._stored_documents.append(stored)
    +
    +        for name, lengths in self._field_lengths.items():
    +            tokens = prepared.get(name, ())
    +            lengths.append(len(tokens))
    +            positions_by_term: dict[str, list[int]] = defaultdict(list)
    +            for token in tokens:
    +                positions_by_term[token.term].append(token.position)
    +            field = self.schema[name]
    +            for term, positions in positions_by_term.items():
    +                posting_positions = (
    +                    tuple(positions) if field.store_positions else ()
    +                )
    +                self._postings[name][term].append(
    +                    Posting(
    +                        doc_id=doc_id,
    +                        term_frequency=len(positions),
    +                        positions=posting_positions,
    +                    )
    +                )
    +        return doc_id
    +
    +    def freeze(self, *, generation: int) -> MemorySegment:
    +        if generation < 0:
    +            raise ValueError("segment generation must be non-negative")
    +        postings = MappingProxyType(
    +            {
    +                field: MappingProxyType(
    +                    {
    +                        term: tuple(term_postings)
    +                        for term, term_postings in sorted(terms.items())
    +                    }
    +                )
    +                for field, terms in sorted(self._postings.items())
    +            }
    +        )
    +        field_lengths = MappingProxyType(
    +            {
    +                field: tuple(lengths)
    +                for field, lengths in sorted(self._field_lengths.items())
    +            }
    +        )
    +        return MemorySegment(
    +            generation=generation,
    +            max_doc=self.document_count,
    +            postings=postings,
    +            stored_documents=tuple(self._stored_documents),
    +            field_lengths=field_lengths,
    +        )
    ```

??? note "文件差异：src/minilucene/index/postings.py"
    ```diff
    diff --git a/src/minilucene/index/postings.py b/src/minilucene/index/postings.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..4f04ba86364be7b0cb24f27abb28620a1b14ef60
    --- /dev/null
    +++ b/src/minilucene/index/postings.py
    @@ -0,0 +1,18 @@
    +from collections.abc import Mapping
    +from dataclasses import dataclass
    +
    +
    +@dataclass(frozen=True, slots=True)
    +class Posting:
    +    doc_id: int
    +    term_frequency: int
    +    positions: tuple[int, ...]
    +
    +
    +@dataclass(frozen=True, slots=True)
    +class MemorySegment:
    +    generation: int
    +    max_doc: int
    +    postings: Mapping[str, Mapping[str, tuple[Posting, ...]]]
    +    stored_documents: tuple[Mapping[str, str], ...]
    +    field_lengths: Mapping[str, tuple[int, ...]]
    ```

**是什么，为什么现在需要**

Posting 绑定 Term、Doc ID、Frequency 与 Position；Norm 保存 Field Length；不可变 Segment 冻结一次索引代次。

**在运行时做什么**

Builder 分析可索引字段、分配 Local Doc ID、累积有序 Posting 与 Norm，最后发布不可变 Mapping。

**关键语句理解**

对 Term、Document 与 Position 排序，使 Segment 确定且可无锁共享。

#### 包、Fixture 与工程支撑

保持包导出、测试语料、依赖与运行环境可复现。

??? note "支撑文件差异（1 个文件）"
    **`src/minilucene/index/__init__.py`**

    ```diff
    diff --git a/src/minilucene/index/__init__.py b/src/minilucene/index/__init__.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..526ed500ddd971e3a53f86bfbaacd97fed7a1870
    --- /dev/null
    +++ b/src/minilucene/index/__init__.py
    @@ -0,0 +1,4 @@
    +from minilucene.index.memory import RamIndexBuilder
    +from minilucene.index.postings import MemorySegment, Posting
    +
    +__all__ = ["MemorySegment", "Posting", "RamIndexBuilder"]
    ```


### 验证证据

运行 `uv run pytest -q $(cat journey/stages/03-ram-inverted-index/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

对 Term、Document 与 Position 排序，使 Segment 确定且可无锁共享。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 3 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/03-inverted-index.md)

[Complete reference patch / 完整参考补丁](https://github.com/system-in-miniature/mini-lucene/blob/main/journey/stages/03-ram-inverted-index/stage.patch)

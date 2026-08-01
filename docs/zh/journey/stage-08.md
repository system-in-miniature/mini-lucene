# Stage 08 · 不可变 Segment Image

### 目标

实现不可变 Segment Image，并能从可执行反例、运行时状态与关键语句解释其边界。

??? note "交付文件"
    - `src/minilucene/storage/__init__.py`
    - `src/minilucene/storage/image.py`
    - `tests/unit/storage/test_segment_image.py`

### 当前遇到的问题

内存 Segment 在交给磁盘 Codec 前，需要一个可被精确保留的 Canonical Value Object。

### 测试契约

#### 先看会坏在哪里

Round-trip 与 Validation 测试构造不一致的 Doc Count、Posting、Norm 与 Stored Field。

??? note "文件差异：tests/unit/storage/test_segment_image.py"
    ```diff
    diff --git a/tests/unit/storage/test_segment_image.py b/tests/unit/storage/test_segment_image.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..daaad6b6e37dd629ac376c0cdd566203faec2219
    --- /dev/null
    +++ b/tests/unit/storage/test_segment_image.py
    @@ -0,0 +1,67 @@
    +import pytest
    +
    +from minilucene.index.memory import RamIndexBuilder
    +from minilucene.schema import KeywordField, Schema, TextField
    +from minilucene.storage.image import SegmentImage
    +
    +
    +def test_segment_image_rejects_non_dense_documents():
    +    with pytest.raises(ValueError, match="dense"):
    +        SegmentImage(
    +            generation=1,
    +            schema_fingerprint="abc",
    +            stored_documents={1: {"id": "late"}},
    +            postings={},
    +            field_lengths={},
    +        )
    +
    +
    +def test_segment_image_from_ram_segment_is_deeply_immutable():
    +    schema = Schema(
    +        id=KeywordField(stored=True),
    +        body=TextField(stored=True),
    +    )
    +    builder = RamIndexBuilder(schema)
    +    builder.add_document({"id": "1", "body": "search search"})
    +    image = SegmentImage.from_memory_segment(
    +        generation=7,
    +        schema_fingerprint=schema.fingerprint,
    +        segment=builder.freeze(generation=0),
    +    )
    +    assert image.max_doc == 1
    +    assert image.postings["body"]["search"][0].positions == (0, 1)
    +    with pytest.raises(TypeError):
    +        image.stored_documents[0] = {"id": "changed"}
    +    with pytest.raises(TypeError):
    +        image.stored_documents[0]["id"] = "changed"
    +
    +
    +def test_segment_image_rejects_nonmonotonic_posting_ids():
    +    from minilucene.index.postings import Posting
    +
    +    with pytest.raises(ValueError, match="strictly increasing"):
    +        SegmentImage(
    +            generation=1,
    +            schema_fingerprint="abc",
    +            stored_documents={0: {}, 1: {}},
    +            postings={
    +                "body": {
    +                    "term": (
    +                        Posting(1, 1, (0,)),
    +                        Posting(0, 1, (0,)),
    +                    )
    +                }
    +            },
    +            field_lengths={"body": (1, 1)},
    +        )
    +
    +
    +def test_segment_image_rejects_wrong_field_length_count():
    +    with pytest.raises(ValueError, match="field lengths"):
    +        SegmentImage(
    +            generation=1,
    +            schema_fingerprint="abc",
    +            stored_documents={0: {}},
    +            postings={},
    +            field_lengths={"body": ()},
    +        )
    ```

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

Round-trip 与 Validation 测试构造不一致的 Doc Count、Posting、Norm 与 Stored Field。

**关键测试语句**

```python
assert image.max_doc == 1
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

SegmentImage 是完整不可变逻辑 Payload，独立于文件布局与发布协议。

### 为什么需要这个机制

内存 Segment 在交给磁盘 Codec 前，需要一个可被精确保留的 Canonical Value Object。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Builder 归一化 Map 与 Tuple，校验跨表 Count 与 Doc ID，再向 Codec 暴露唯一确定 Image。

### 机制板块

#### 不可变 Segment Image机制

Builder 归一化 Map 与 Tuple，校验跨表 Count 与 Doc ID，再向 Codec 暴露唯一确定 Image。

??? note "文件差异：src/minilucene/storage/image.py"
    ```diff
    diff --git a/src/minilucene/storage/image.py b/src/minilucene/storage/image.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..7ef65e5bf05149773a77f527d88164afdd44da10
    --- /dev/null
    +++ b/src/minilucene/storage/image.py
    @@ -0,0 +1,115 @@
    +from collections.abc import Mapping
    +from dataclasses import dataclass
    +from itertools import pairwise
    +from types import MappingProxyType
    +
    +from minilucene.index.postings import MemorySegment, Posting
    +
    +
    +def _freeze_string_mapping(
    +    values: Mapping[str, str],
    +) -> Mapping[str, str]:
    +    return MappingProxyType(dict(sorted(values.items())))
    +
    +
    +@dataclass(frozen=True, slots=True)
    +class SegmentImage:
    +    generation: int
    +    schema_fingerprint: str
    +    stored_documents: Mapping[int, Mapping[str, str]]
    +    postings: Mapping[str, Mapping[str, tuple[Posting, ...]]]
    +    field_lengths: Mapping[str, tuple[int, ...]]
    +
    +    def __post_init__(self) -> None:
    +        if self.generation <= 0:
    +            raise ValueError("segment generation must be positive")
    +        if not self.schema_fingerprint:
    +            raise ValueError("schema fingerprint must be non-empty")
    +
    +        stored = {
    +            doc_id: _freeze_string_mapping(document)
    +            for doc_id, document in sorted(self.stored_documents.items())
    +        }
    +        if tuple(stored) != tuple(range(len(stored))):
    +            raise ValueError("stored document IDs must be dense")
    +        max_doc = len(stored)
    +
    +        frozen_postings: dict[
    +            str, Mapping[str, tuple[Posting, ...]]
    +        ] = {}
    +        for field, terms in sorted(self.postings.items()):
    +            frozen_terms: dict[str, tuple[Posting, ...]] = {}
    +            for term, term_postings in sorted(terms.items()):
    +                term_postings = tuple(term_postings)
    +                doc_ids = tuple(
    +                    posting.doc_id for posting in term_postings
    +                )
    +                if any(
    +                    right <= left for left, right in pairwise(doc_ids)
    +                ):
    +                    raise ValueError(
    +                        "posting doc IDs must be strictly increasing"
    +                    )
    +                for posting in term_postings:
    +                    if not 0 <= posting.doc_id < max_doc:
    +                        raise ValueError("posting doc ID outside segment")
    +                    if posting.term_frequency <= 0:
    +                        raise ValueError("term frequency must be positive")
    +                    if posting.positions:
    +                        if posting.term_frequency != len(posting.positions):
    +                            raise ValueError(
    +                                "term frequency must equal position count"
    +                            )
    +                        if any(
    +                            right <= left
    +                            for left, right in pairwise(posting.positions)
    +                        ):
    +                            raise ValueError(
    +                                "positions must be strictly increasing"
    +                            )
    +                frozen_terms[term] = term_postings
    +            frozen_postings[field] = MappingProxyType(frozen_terms)
    +
    +        lengths: dict[str, tuple[int, ...]] = {}
    +        for field, values in sorted(self.field_lengths.items()):
    +            values = tuple(values)
    +            if len(values) != max_doc or any(value < 0 for value in values):
    +                raise ValueError(
    +                    "field lengths must match documents and be non-negative"
    +                )
    +            lengths[field] = values
    +
    +        object.__setattr__(
    +            self, "stored_documents", MappingProxyType(stored)
    +        )
    +        object.__setattr__(
    +            self, "postings", MappingProxyType(frozen_postings)
    +        )
    +        object.__setattr__(
    +            self, "field_lengths", MappingProxyType(lengths)
    +        )
    +
    +    @property
    +    def max_doc(self) -> int:
    +        return len(self.stored_documents)
    +
    +    @classmethod
    +    def from_memory_segment(
    +        cls,
    +        *,
    +        generation: int,
    +        schema_fingerprint: str,
    +        segment: MemorySegment,
    +    ) -> "SegmentImage":
    +        return cls(
    +            generation=generation,
    +            schema_fingerprint=schema_fingerprint,
    +            stored_documents={
    +                doc_id: document
    +                for doc_id, document in enumerate(
    +                    segment.stored_documents
    +                )
    +            },
    +            postings=segment.postings,
    +            field_lengths=segment.field_lengths,
    +        )
    ```

**是什么，为什么现在需要**

SegmentImage 是完整不可变逻辑 Payload，独立于文件布局与发布协议。

**在运行时做什么**

Builder 归一化 Map 与 Tuple，校验跨表 Count 与 Doc ID，再向 Codec 暴露唯一确定 Image。

**关键语句理解**

把逻辑 Image 与字节分离，让格式校验和文件系统原子性可以演进而不改变 Search 语义。

#### 包、Fixture 与工程支撑

保持包导出、测试语料、依赖与运行环境可复现。

??? note "支撑文件差异（1 个文件）"
    **`src/minilucene/storage/__init__.py`**

    ```diff
    diff --git a/src/minilucene/storage/__init__.py b/src/minilucene/storage/__init__.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..0257b60f52bad1b096decc92d5633870c6a220de
    --- /dev/null
    +++ b/src/minilucene/storage/__init__.py
    @@ -0,0 +1,3 @@
    +from minilucene.storage.image import SegmentImage
    +
    +__all__ = ["SegmentImage"]
    ```


### 验证证据

运行 `uv run pytest -q $(cat journey/stages/08-segment-images/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

把逻辑 Image 与字节分离，让格式校验和文件系统原子性可以演进而不改变 Search 语义。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 4 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/04-codec.md)

[Complete reference patch / 完整参考补丁](https://github.com/system-in-miniature/mini-lucene/blob/main/journey/stages/08-segment-images/stage.patch)

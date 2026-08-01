# Stage 05 · 快照级语料统计

### 目标

实现快照级语料统计，并能从可执行反例、运行时状态与关键语句解释其边界。

??? note "交付文件"
    - `src/minilucene/query/match.py`
    - `src/minilucene/search/__init__.py`
    - `src/minilucene/search/reader.py`
    - `src/minilucene/search/stats.py`
    - `tests/helpers/corpus.py`
    - `tests/unit/search/test_corpus_stats.py`

### 当前遇到的问题

用 Segment 局部统计评分，会让多 Segment 索引中的相同 Term 不可比较。

### 测试契约

#### 先看会坏在哪里

反例把 Document 不均匀分布在多个 Segment，并检查整个 Snapshot 上的 DF 与平均 Field Length。

??? note "文件差异：tests/helpers/corpus.py"
    ```diff
    diff --git a/tests/helpers/corpus.py b/tests/helpers/corpus.py
    index c71d8d795733402ad8f48eac1faa618aecd324cc..57b0ab8156b73bb0e7efd798e32cdd41377d5d21 100644
    --- a/tests/helpers/corpus.py
    +++ b/tests/helpers/corpus.py
    @@ -6,6 +6,7 @@ class SingleSegmentReader:
         def __init__(self, segment):
             self.segment = segment
             self.max_doc = segment.max_doc
    +        self.live_doc_ids = frozenset(range(segment.max_doc))
             self.max_prefix_expansions = 1_024

         def postings(self, field, term):
    @@ -53,3 +54,22 @@ def build_memory_reader(documents):
         for document in documents:
             builder.add_document({"body": document})
         return SingleSegmentReader(builder.freeze(generation=0))
    +
    +
    +def build_multi_segment_reader(*, segments, deleted):
    +    from minilucene.search.reader import ReaderView
    +
    +    built = []
    +    live_docs = []
    +    for generation, (documents, removed) in enumerate(
    +        zip(segments, deleted, strict=True),
    +        start=1,
    +    ):
    +        builder = RamIndexBuilder(Schema(body=TextField(stored=True)))
    +        for document in documents:
    +            builder.add_document({"body": document})
    +        segment = builder.freeze(generation=generation)
    +        built.append(segment)
    +        live_docs.append(frozenset(range(segment.max_doc)) - frozenset(removed))
    +    schema = Schema(body=TextField(stored=True))
    +    return ReaderView(schema, tuple(built), tuple(live_docs))
    ```

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

反例把 Document 不均匀分布在多个 Segment，并检查整个 Snapshot 上的 DF 与平均 Field Length。

**关键测试语句**

```python
assert stats.live_doc_count == 2
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

??? note "文件差异：tests/unit/search/test_corpus_stats.py"
    ```diff
    diff --git a/tests/unit/search/test_corpus_stats.py b/tests/unit/search/test_corpus_stats.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..afc60e0487c488b190daebe3a90199830eb32901
    --- /dev/null
    +++ b/tests/unit/search/test_corpus_stats.py
    @@ -0,0 +1,46 @@
    +from minilucene.query import MatchAllQuery, TermQuery
    +from tests.helpers.corpus import build_multi_segment_reader
    +
    +
    +def test_corpus_stats_span_segments_and_only_live_documents():
    +    reader = build_multi_segment_reader(
    +        segments=(("kafka kafka", "rabbit"), ("kafka replicas",)),
    +        deleted=((1,), ()),
    +    )
    +    stats = reader.corpus_stats
    +    assert stats.live_doc_count == 2
    +    assert stats.doc_frequency("body", "kafka") == 2
    +    assert stats.average_length("body") == 2.0
    +
    +
    +def test_reader_translates_segment_local_ids_to_snapshot_ids_and_addresses():
    +    reader = build_multi_segment_reader(
    +        segments=(("alpha", "deleted"), ("alpha",)),
    +        deleted=((1,), ()),
    +    )
    +    assert [posting.doc_id for posting in reader.postings("body", "alpha")] == [
    +        0,
    +        2,
    +    ]
    +    assert reader.address(0).segment_generation == 1
    +    assert reader.address(2).segment_generation == 2
    +    assert reader.address(2).local_doc_id == 0
    +
    +
    +def test_match_all_and_term_queries_exclude_deleted_documents():
    +    reader = build_multi_segment_reader(
    +        segments=(("alpha", "alpha"),),
    +        deleted=((0,),),
    +    )
    +    assert reader.match(MatchAllQuery()) == {1}
    +    assert reader.match(TermQuery("body", "alpha")) == {1}
    +
    +
    +def test_stored_fields_and_lengths_resolve_through_snapshot_address():
    +    reader = build_multi_segment_reader(
    +        segments=(("one two",), ("three",)),
    +        deleted=((), ()),
    +    )
    +    assert reader.stored_fields(1) == {"body": "three"}
    +    assert reader.field_length("body", 0) == 2
    +    assert reader.field_length("body", 1) == 1
    ```

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

反例把 Document 不均匀分布在多个 Segment，并检查整个 Snapshot 上的 DF 与平均 Field Length。

**关键测试语句**

```python
assert stats.live_doc_count == 2
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Corpus Statistic 属于 Reader Snapshot：Live Document Count、各 Field Length Total 与 Term DF。

### 为什么需要这个机制

用 Segment 局部统计评分，会让多 Segment 索引中的相同 Term 不可比较。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

打开 Search Reader 时遍历全部可见 Segment View，并把聚合统计与它们一起冻结。

### 机制板块

#### 快照级语料统计机制

打开 Search Reader 时遍历全部可见 Segment View，并把聚合统计与它们一起冻结。

??? note "文件差异：src/minilucene/query/match.py"
    ```diff
    diff --git a/src/minilucene/query/match.py b/src/minilucene/query/match.py
    index 914d4dc16beb10f3ea714a436d5fc72a479db417..5f4c52524477ea97a73cb12c0b4085a8355eee64 100644
    --- a/src/minilucene/query/match.py
    +++ b/src/minilucene/query/match.py
    @@ -18,6 +18,7 @@ from minilucene.query.model import (
     class MatchReader(Protocol):
         max_doc: int
         max_prefix_expansions: int
    +    live_doc_ids: frozenset[int]

         def postings(self, field: str, term: str) -> Iterable[Posting]: ...

    @@ -104,7 +105,7 @@ def match_query(reader: MatchReader, query: Query) -> set[int]:
                     for term in terms
                 )
             case MatchAllQuery():
    -            return set(range(reader.max_doc))
    +            return set(reader.live_doc_ids)
             case BooleanQuery(clauses):
                 return match_boolean(reader, clauses)
         raise QueryError(f"unsupported query: {type(query).__name__}")
    ```

??? note "文件差异：src/minilucene/search/reader.py"
    ```diff
    diff --git a/src/minilucene/search/reader.py b/src/minilucene/search/reader.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..97cd1d7f6bbf5f8dee41f0c891a0b9564d31e5e7
    --- /dev/null
    +++ b/src/minilucene/search/reader.py
    @@ -0,0 +1,180 @@
    +from collections.abc import Mapping
    +from dataclasses import dataclass
    +
    +from minilucene.index.postings import MemorySegment, Posting
    +from minilucene.query.match import match_query
    +from minilucene.query.model import Query
    +from minilucene.schema import Schema
    +from minilucene.search.stats import CorpusStats, freeze_corpus_stats
    +
    +
    +@dataclass(frozen=True, slots=True)
    +class DocAddress:
    +    segment_generation: int
    +    local_doc_id: int
    +
    +
    +class ReaderView:
    +    def __init__(
    +        self,
    +        schema: Schema,
    +        segments: tuple[MemorySegment, ...],
    +        live_docs: tuple[frozenset[int], ...] | None = None,
    +        *,
    +        max_prefix_expansions: int = 1_024,
    +    ) -> None:
    +        self.schema = schema
    +        self.segments = segments
    +        self.max_prefix_expansions = max_prefix_expansions
    +        if live_docs is None:
    +            live_docs = tuple(
    +                frozenset(range(segment.max_doc)) for segment in segments
    +            )
    +        if len(live_docs) != len(segments):
    +            raise ValueError("live-doc masks must match segments")
    +        for segment, mask in zip(segments, live_docs, strict=True):
    +            if any(doc_id < 0 or doc_id >= segment.max_doc for doc_id in mask):
    +                raise ValueError("live-doc ID outside segment")
    +        self._live_docs = live_docs
    +        bases: list[int] = []
    +        next_base = 0
    +        for segment in segments:
    +            bases.append(next_base)
    +            next_base += segment.max_doc
    +        self._bases = tuple(bases)
    +        self.max_doc = next_base
    +        self.live_doc_ids = frozenset(
    +            base + local_doc_id
    +            for base, mask in zip(self._bases, live_docs, strict=True)
    +            for local_doc_id in mask
    +        )
    +        self.corpus_stats = self._build_corpus_stats()
    +
    +    def _resolve(self, doc_id: int) -> tuple[int, MemorySegment, int]:
    +        if doc_id < 0 or doc_id >= self.max_doc:
    +            raise IndexError(f"document ID outside reader: {doc_id}")
    +        for index in range(len(self.segments) - 1, -1, -1):
    +            base = self._bases[index]
    +            if doc_id >= base:
    +                return index, self.segments[index], doc_id - base
    +        raise IndexError(f"document ID outside reader: {doc_id}")
    +
    +    def address(self, doc_id: int) -> DocAddress:
    +        _, segment, local_doc_id = self._resolve(doc_id)
    +        return DocAddress(segment.generation, local_doc_id)
    +
    +    def postings(self, field: str, term: str) -> tuple[Posting, ...]:
    +        result: list[Posting] = []
    +        for base, segment, live in zip(
    +            self._bases, self.segments, self._live_docs, strict=True
    +        ):
    +            for posting in segment.postings.get(field, {}).get(term, ()):
    +                if posting.doc_id in live:
    +                    result.append(
    +                        Posting(
    +                            doc_id=base + posting.doc_id,
    +                            term_frequency=posting.term_frequency,
    +                            positions=posting.positions,
    +                        )
    +                    )
    +        return tuple(result)
    +
    +    def terms_with_prefix(
    +        self, field: str, prefix: str
    +    ) -> tuple[str, ...]:
    +        return tuple(
    +            sorted(
    +                {
    +                    term
    +                    for segment in self.segments
    +                    for term in segment.postings.get(field, {})
    +                    if term.startswith(prefix)
    +                }
    +            )
    +        )
    +
    +    def has_phrase(
    +        self,
    +        field: str,
    +        terms: tuple[str, ...],
    +        query_positions: tuple[int, ...],
    +        doc_id: int,
    +    ) -> bool:
    +        segment_index, segment, local_doc_id = self._resolve(doc_id)
    +        if local_doc_id not in self._live_docs[segment_index]:
    +            return False
    +        term_positions: list[set[int]] = []
    +        for term in terms:
    +            posting = next(
    +                (
    +                    item
    +                    for item in segment.postings.get(field, {}).get(term, ())
    +                    if item.doc_id == local_doc_id
    +                ),
    +                None,
    +            )
    +            if posting is None:
    +                return False
    +            term_positions.append(set(posting.positions))
    +        return any(
    +            all(
    +                start + query_position in positions
    +                for query_position, positions in zip(
    +                    query_positions, term_positions, strict=True
    +                )
    +            )
    +            for start in term_positions[0]
    +        )
    +
    +    def stored_fields(self, doc_id: int) -> Mapping[str, str]:
    +        index, segment, local_doc_id = self._resolve(doc_id)
    +        if local_doc_id not in self._live_docs[index]:
    +            raise KeyError(f"document is deleted: {doc_id}")
    +        return segment.stored_documents[local_doc_id]
    +
    +    def field_length(self, field: str, doc_id: int) -> int:
    +        index, segment, local_doc_id = self._resolve(doc_id)
    +        if local_doc_id not in self._live_docs[index]:
    +            raise KeyError(f"document is deleted: {doc_id}")
    +        return segment.field_lengths.get(
    +            field, (0,) * segment.max_doc
    +        )[local_doc_id]
    +
    +    def match(self, query: Query) -> set[int]:
    +        return match_query(self, query)
    +
    +    def _build_corpus_stats(self) -> CorpusStats:
    +        doc_frequencies: dict[tuple[str, str], int] = {}
    +        for segment, live in zip(
    +            self.segments, self._live_docs, strict=True
    +        ):
    +            for field, terms in segment.postings.items():
    +                for term, postings in terms.items():
    +                    frequency = sum(
    +                        posting.doc_id in live for posting in postings
    +                    )
    +                    key = (field, term)
    +                    doc_frequencies[key] = (
    +                        doc_frequencies.get(key, 0) + frequency
    +                    )
    +
    +        length_sums: dict[str, int] = {}
    +        length_counts: dict[str, int] = {}
    +        for segment, live in zip(
    +            self.segments, self._live_docs, strict=True
    +        ):
    +            for field, lengths in segment.field_lengths.items():
    +                for local_doc_id in live:
    +                    length = lengths[local_doc_id]
    +                    if length > 0:
    +                        length_sums[field] = length_sums.get(field, 0) + length
    +                        length_counts[field] = length_counts.get(field, 0) + 1
    +        averages = {
    +            field: length_sums[field] / count
    +            for field, count in length_counts.items()
    +        }
    +        return freeze_corpus_stats(
    +            live_doc_count=len(self.live_doc_ids),
    +            doc_frequencies=doc_frequencies,
    +            average_field_lengths=averages,
    +        )
    ```

??? note "文件差异：src/minilucene/search/stats.py"
    ```diff
    diff --git a/src/minilucene/search/stats.py b/src/minilucene/search/stats.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..f7ccd82d285a0a8c28159bb35998ffe1fbb1e119
    --- /dev/null
    +++ b/src/minilucene/search/stats.py
    @@ -0,0 +1,31 @@
    +from collections.abc import Mapping
    +from dataclasses import dataclass
    +from types import MappingProxyType
    +
    +
    +@dataclass(frozen=True, slots=True)
    +class CorpusStats:
    +    live_doc_count: int
    +    doc_frequencies: Mapping[tuple[str, str], int]
    +    average_field_lengths: Mapping[str, float]
    +
    +    def doc_frequency(self, field: str, term: str) -> int:
    +        return self.doc_frequencies.get((field, term), 0)
    +
    +    def average_length(self, field: str) -> float:
    +        return self.average_field_lengths.get(field, 0.0)
    +
    +
    +def freeze_corpus_stats(
    +    *,
    +    live_doc_count: int,
    +    doc_frequencies: dict[tuple[str, str], int],
    +    average_field_lengths: dict[str, float],
    +) -> CorpusStats:
    +    return CorpusStats(
    +        live_doc_count=live_doc_count,
    +        doc_frequencies=MappingProxyType(dict(doc_frequencies)),
    +        average_field_lengths=MappingProxyType(
    +            dict(average_field_lengths)
    +        ),
    +    )
    ```

**是什么，为什么现在需要**

Corpus Statistic 属于 Reader Snapshot：Live Document Count、各 Field Length Total 与 Term DF。

**在运行时做什么**

打开 Search Reader 时遍历全部可见 Segment View，并把聚合统计与它们一起冻结。

**关键语句理解**

统计与 Matching 使用的 Segment Set 一起冻结，避免 Score 混合两个可见性代次。

#### 包、Fixture 与工程支撑

保持包导出、测试语料、依赖与运行环境可复现。

??? note "支撑文件差异（1 个文件）"
    **`src/minilucene/search/__init__.py`**

    ```diff
    diff --git a/src/minilucene/search/__init__.py b/src/minilucene/search/__init__.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..e7896ba128e109797bb2852a4a0914eb03446089
    --- /dev/null
    +++ b/src/minilucene/search/__init__.py
    @@ -0,0 +1,4 @@
    +from minilucene.search.reader import DocAddress, ReaderView
    +from minilucene.search.stats import CorpusStats
    +
    +__all__ = ["CorpusStats", "DocAddress", "ReaderView"]
    ```


### 验证证据

运行 `uv run pytest -q $(cat journey/stages/05-corpus-statistics/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

统计与 Matching 使用的 Segment Set 一起冻结，避免 Score 混合两个可见性代次。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 8 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/08-scoring.md)

[Complete reference patch / 完整参考补丁](https://github.com/system-in-miniature/mini-lucene/blob/main/journey/stages/05-corpus-statistics/stage.patch)

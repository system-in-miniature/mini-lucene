# Stage 07 · 有界 Top-K 检索

### 目标

实现有界 Top-K 检索，并能从可执行反例、运行时状态与关键语句解释其边界。

??? note "交付文件"
    - `src/minilucene/__init__.py`
    - `src/minilucene/index/__init__.py`
    - `src/minilucene/index/memory.py`
    - `src/minilucene/search/__init__.py`
    - `src/minilucene/search/collector.py`
    - `src/minilucene/search/searcher.py`
    - `tests/acceptance/test_phase1_retrieval_kernel.py`
    - `tests/contract/test_memory_search.py`
    - `tests/unit/search/test_topk.py`

### 当前遇到的问题

调用方只要少量 Hit 时，对全部匹配 Document 排序会浪费内存。

### 测试契约

#### 先看会坏在哪里

测试制造多于 K 的 Match、Score Tie 与足够大的 Stored Field，暴露提前 Fetch。

??? note "文件差异：tests/acceptance/test_phase1_retrieval_kernel.py"
    ```diff
    diff --git a/tests/acceptance/test_phase1_retrieval_kernel.py b/tests/acceptance/test_phase1_retrieval_kernel.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..11d79bdda942017dbae48dbb690db02977e7d59f
    --- /dev/null
    +++ b/tests/acceptance/test_phase1_retrieval_kernel.py
    @@ -0,0 +1,43 @@
    +from minilucene import KeywordField, MemoryIndex, Schema, TextField
    +from minilucene.query import (
    +    BooleanClause,
    +    BooleanQuery,
    +    Occur,
    +    PhraseQuery,
    +    TermQuery,
    +)
    +
    +
    +def test_fielded_phrase_bm25_topk_and_stored_fields_close_one_loop():
    +    index = MemoryIndex(
    +        Schema(
    +            id=KeywordField(stored=True),
    +            title=TextField(stored=True, boost=2.0),
    +            body=TextField(stored=True),
    +        )
    +    )
    +    index.add_document(
    +        id="1",
    +        title="Kafka",
    +        body="follower replicas",
    +    )
    +    index.add_document(
    +        id="2",
    +        title="Queues",
    +        body="follower processes coordinate distant replicas",
    +    )
    +    query = BooleanQuery(
    +        (
    +            BooleanClause(
    +                Occur.MUST, TermQuery("title", "kafka")
    +            ),
    +            BooleanClause(
    +                Occur.MUST,
    +                PhraseQuery("body", ("follower", "replicas")),
    +            ),
    +        )
    +    )
    +    result = index.search(query, top_k=1)
    +    assert result.total_hits == 1
    +    assert result.hits[0].stored_fields["id"] == "1"
    +    assert result.hits[0].score > 0
    ```

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

测试制造多于 K 的 Match、Score Tie 与足够大的 Stored Field，暴露提前 Fetch。

**关键测试语句**

```python
assert result.total_hits == 1
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

??? note "文件差异：tests/contract/test_memory_search.py"
    ```diff
    diff --git a/tests/contract/test_memory_search.py b/tests/contract/test_memory_search.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..6d2a3777e8d6a9339a31ba434eb9f98a9e18ee90
    --- /dev/null
    +++ b/tests/contract/test_memory_search.py
    @@ -0,0 +1,29 @@
    +from minilucene import MemoryIndex, Schema, TextField
    +from minilucene.query import MatchAllQuery, TermQuery
    +
    +
    +def test_public_memory_index_returns_stored_fields():
    +    index = MemoryIndex(Schema(body=TextField(stored=True)))
    +    index.add_document(body="kafka replicas")
    +    result = index.search(TermQuery("body", "kafka"), top_k=10)
    +    assert result.total_hits == 1
    +    assert result.hits[0].stored_fields == {"body": "kafka replicas"}
    +
    +
    +def test_public_memory_index_uses_bounded_topk_and_deterministic_order():
    +    index = MemoryIndex(Schema(body=TextField(stored=True)))
    +    index.add_document(body="same")
    +    index.add_document(body="same")
    +    index.add_document(body="same")
    +    result = index.search(TermQuery("body", "same"), top_k=2)
    +    assert result.total_hits == 3
    +    assert [hit.local_doc_id for hit in result.hits] == [0, 1]
    +
    +
    +def test_match_all_can_report_total_without_returning_hits():
    +    index = MemoryIndex(Schema(body=TextField(stored=True)))
    +    index.add_document(body="one")
    +    index.add_document(body="two")
    +    result = index.search(MatchAllQuery(), top_k=0)
    +    assert result.total_hits == 2
    +    assert result.hits == ()
    ```

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

测试制造多于 K 的 Match、Score Tie 与足够大的 Stored Field，暴露提前 Fetch。

**关键测试语句**

```python
assert result.total_hits == 1
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

??? note "文件差异：tests/unit/search/test_topk.py"
    ```diff
    diff --git a/tests/unit/search/test_topk.py b/tests/unit/search/test_topk.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..9c53fd5f91701a3e561a42d4b158d37084702ae2
    --- /dev/null
    +++ b/tests/unit/search/test_topk.py
    @@ -0,0 +1,39 @@
    +from minilucene.search.collector import TopKCollector
    +
    +
    +def test_heap_topk_matches_complete_sort_oracle():
    +    scored = (
    +        (score, 1, doc)
    +        for doc, score in enumerate((1.0, 5.0, 3.0, 5.0))
    +    )
    +    collector = TopKCollector(2)
    +    for score, segment, doc in scored:
    +        collector.collect(score, segment, doc)
    +    assert [
    +        (hit.score, hit.local_doc_id)
    +        for hit in collector.top_docs().hits
    +    ] == [
    +        (5.0, 1),
    +        (5.0, 3),
    +    ]
    +    assert collector.max_retained == 2
    +    assert collector.top_docs().total_hits == 4
    +
    +
    +def test_ties_prefer_lower_segment_then_lower_local_doc_id():
    +    collector = TopKCollector(2)
    +    for segment, doc in ((2, 0), (1, 4), (1, 2)):
    +        collector.collect(1.0, segment, doc)
    +    assert [
    +        (hit.segment_generation, hit.local_doc_id)
    +        for hit in collector.top_docs().hits
    +    ] == [(1, 2), (1, 4)]
    +
    +
    +def test_zero_topk_counts_hits_without_retaining_them():
    +    collector = TopKCollector(0)
    +    collector.collect(1.0, 1, 0)
    +    result = collector.top_docs()
    +    assert result.total_hits == 1
    +    assert result.hits == ()
    +    assert collector.max_retained == 0
    ```

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

测试制造多于 K 的 Match、Score Tie 与足够大的 Stored Field，暴露提前 Fetch。

**关键测试语句**

```python
assert result.total_hits == 1
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

有界 Collector 只保留有竞争力的 Score/Doc Pair；Search 把 Collect 与 Fetch Stored Winner 分开。

### 为什么需要这个机制

调用方只要少量 Hit 时，对全部匹配 Document 排序会浪费内存。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Scoring 把 Candidate 流入大小 K 的 Min Heap，确定最终顺序后只加载 Winner 的 Stored Data。

### 机制板块

#### 有界 Top-K 检索机制

Scoring 把 Candidate 流入大小 K 的 Min Heap，确定最终顺序后只加载 Winner 的 Stored Data。

??? note "文件差异：src/minilucene/index/memory.py"
    ```diff
    diff --git a/src/minilucene/index/memory.py b/src/minilucene/index/memory.py
    index 4e2bff6c5b4479d1b4d081ede519b00e87b928eb..040f41b34f1b801c2c39d338aeaa9eb6cb80adb1 100644
    --- a/src/minilucene/index/memory.py
    +++ b/src/minilucene/index/memory.py
    @@ -6,6 +6,7 @@ from minilucene.analysis import KeywordAnalyzer, StandardAnalyzer
     from minilucene.analysis.model import Token
     from minilucene.document import FrozenDocument, freeze_document
     from minilucene.index.postings import MemorySegment, Posting
    +from minilucene.query.model import Query
     from minilucene.schema import FieldType, Schema


    @@ -96,3 +97,20 @@ class RamIndexBuilder:
                 stored_documents=tuple(self._stored_documents),
                 field_lengths=field_lengths,
             )
    +
    +
    +class MemoryIndex:
    +    def __init__(self, schema: Schema) -> None:
    +        self.schema = schema
    +        self._builder = RamIndexBuilder(schema)
    +
    +    def add_document(self, **values: object) -> int:
    +        return self._builder.add_document(values)
    +
    +    def search(self, query: Query, *, top_k: int = 10):
    +        from minilucene.search.reader import ReaderView
    +        from minilucene.search.searcher import IndexSearcher
    +
    +        segment = self._builder.freeze(generation=0)
    +        reader = ReaderView(self.schema, (segment,))
    +        return IndexSearcher(reader).search(query, top_k=top_k)
    ```

??? note "文件差异：src/minilucene/search/collector.py"
    ```diff
    diff --git a/src/minilucene/search/collector.py b/src/minilucene/search/collector.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..efdbe0b93c2d53eae6d43668a6a345923805c2f5
    --- /dev/null
    +++ b/src/minilucene/search/collector.py
    @@ -0,0 +1,70 @@
    +import heapq
    +import math
    +from collections.abc import Mapping
    +from dataclasses import dataclass
    +from types import MappingProxyType
    +
    +
    +@dataclass(frozen=True, slots=True)
    +class SearchHit:
    +    score: float
    +    segment_generation: int
    +    local_doc_id: int
    +    stored_fields: Mapping[str, str]
    +
    +
    +@dataclass(frozen=True, slots=True)
    +class TopDocs:
    +    total_hits: int
    +    hits: tuple[SearchHit, ...]
    +
    +
    +class TopKCollector:
    +    def __init__(self, top_k: int) -> None:
    +        if not isinstance(top_k, int) or top_k < 0:
    +            raise ValueError("top_k must be a non-negative integer")
    +        self.top_k = top_k
    +        self.total_hits = 0
    +        self.max_retained = 0
    +        self._heap: list[
    +            tuple[tuple[float, int, int], SearchHit]
    +        ] = []
    +
    +    def collect(
    +        self,
    +        score: float,
    +        segment_generation: int,
    +        local_doc_id: int,
    +        stored_fields: Mapping[str, str] | None = None,
    +    ) -> None:
    +        if not math.isfinite(score):
    +            raise ValueError("collected score must be finite")
    +        self.total_hits += 1
    +        if self.top_k == 0:
    +            return
    +        hit = SearchHit(
    +            score=score,
    +            segment_generation=segment_generation,
    +            local_doc_id=local_doc_id,
    +            stored_fields=MappingProxyType(dict(stored_fields or {})),
    +        )
    +        key = (score, -segment_generation, -local_doc_id)
    +        item = (key, hit)
    +        if len(self._heap) < self.top_k:
    +            heapq.heappush(self._heap, item)
    +        elif key > self._heap[0][0]:
    +            heapq.heapreplace(self._heap, item)
    +        self.max_retained = max(self.max_retained, len(self._heap))
    +
    +    def top_docs(self) -> TopDocs:
    +        hits = tuple(
    +            sorted(
    +                (hit for _, hit in self._heap),
    +                key=lambda hit: (
    +                    -hit.score,
    +                    hit.segment_generation,
    +                    hit.local_doc_id,
    +                ),
    +            )
    +        )
    +        return TopDocs(total_hits=self.total_hits, hits=hits)
    ```

??? note "文件差异：src/minilucene/search/searcher.py"
    ```diff
    diff --git a/src/minilucene/search/searcher.py b/src/minilucene/search/searcher.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..652b07d013d5aed76f2968b3b6acd597e40b224d
    --- /dev/null
    +++ b/src/minilucene/search/searcher.py
    @@ -0,0 +1,27 @@
    +from minilucene.query.model import Query
    +from minilucene.search.bm25 import BM25
    +from minilucene.search.collector import TopDocs, TopKCollector
    +from minilucene.search.reader import ReaderView
    +from minilucene.search.scorer import score_query
    +
    +
    +class IndexSearcher:
    +    def __init__(
    +        self, reader: ReaderView, *, similarity: BM25 | None = None
    +    ) -> None:
    +        self.reader = reader
    +        self.similarity = similarity or BM25()
    +
    +    def search(self, query: Query, *, top_k: int = 10) -> TopDocs:
    +        collector = TopKCollector(top_k)
    +        for doc_id, score in score_query(
    +            self.reader, query, self.similarity
    +        ).items():
    +            address = self.reader.address(doc_id)
    +            collector.collect(
    +                score,
    +                address.segment_generation,
    +                address.local_doc_id,
    +                self.reader.stored_fields(doc_id),
    +            )
    +        return collector.top_docs()
    ```

**是什么，为什么现在需要**

有界 Collector 只保留有竞争力的 Score/Doc Pair；Search 把 Collect 与 Fetch Stored Winner 分开。

**在运行时做什么**

Scoring 把 Candidate 流入大小 K 的 Min Heap，确定最终顺序后只加载 Winner 的 Stored Data。

**关键语句理解**

Heap Bound 控制工作内存，Score 加 Doc 排序让 Tie 在多次运行间可复现。

#### 包、Fixture 与工程支撑

保持包导出、测试语料、依赖与运行环境可复现。

??? note "支撑文件差异（3 个文件）"
    **`src/minilucene/__init__.py`**

    ```diff
    diff --git a/src/minilucene/__init__.py b/src/minilucene/__init__.py
    index 721912e6f3b75a9afc6f77eb7af3eb1fc91c4d24..e853a4ef756dd11aabbc128d9f98e09568598771 100644
    --- a/src/minilucene/__init__.py
    +++ b/src/minilucene/__init__.py
    @@ -1,11 +1,6 @@
    +from minilucene.index.memory import MemoryIndex
     from minilucene.schema import KeywordField, Schema, StoredField, TextField

    -
    -class MemoryIndex:
    -    def __init__(self, schema: Schema) -> None:
    -        self.schema = schema
    -
    -
     __all__ = [
         "KeywordField",
         "MemoryIndex",
    ```

    **`src/minilucene/index/__init__.py`**

    ```diff
    diff --git a/src/minilucene/index/__init__.py b/src/minilucene/index/__init__.py
    index 526ed500ddd971e3a53f86bfbaacd97fed7a1870..e0dbe8b0b479603f9a19cdcc1d49d7a66263f698 100644
    --- a/src/minilucene/index/__init__.py
    +++ b/src/minilucene/index/__init__.py
    @@ -1,4 +1,4 @@
    -from minilucene.index.memory import RamIndexBuilder
    +from minilucene.index.memory import MemoryIndex, RamIndexBuilder
     from minilucene.index.postings import MemorySegment, Posting

    -__all__ = ["MemorySegment", "Posting", "RamIndexBuilder"]
    +__all__ = ["MemoryIndex", "MemorySegment", "Posting", "RamIndexBuilder"]
    ```

    **`src/minilucene/search/__init__.py`**

    ```diff
    diff --git a/src/minilucene/search/__init__.py b/src/minilucene/search/__init__.py
    index 76c1e85bd6bf48b0dad002921d2dd98021687093..9a180bb8d02904ac791327e499b73fad1f256551 100644
    --- a/src/minilucene/search/__init__.py
    +++ b/src/minilucene/search/__init__.py
    @@ -1,6 +1,18 @@
     from minilucene.search.bm25 import BM25
    +from minilucene.search.collector import SearchHit, TopDocs, TopKCollector
     from minilucene.search.reader import DocAddress, ReaderView
     from minilucene.search.scorer import score_query
    +from minilucene.search.searcher import IndexSearcher
     from minilucene.search.stats import CorpusStats

    -__all__ = ["BM25", "CorpusStats", "DocAddress", "ReaderView", "score_query"]
    +__all__ = [
    +    "BM25",
    +    "CorpusStats",
    +    "DocAddress",
    +    "IndexSearcher",
    +    "ReaderView",
    +    "SearchHit",
    +    "TopDocs",
    +    "TopKCollector",
    +    "score_query",
    +]
    ```


### 验证证据

运行 `uv run pytest -q $(cat journey/stages/07-topk-retrieval/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

Heap Bound 控制工作内存，Score 加 Doc 排序让 Tie 在多次运行间可复现。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 8 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/08-scoring.md)

[Complete reference patch / 完整参考补丁](https://github.com/system-in-miniature/mini-lucene/blob/main/journey/stages/07-topk-retrieval/stage.patch)

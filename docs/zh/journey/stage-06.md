# Stage 06 · 全局 BM25 排名

### 目标

实现全局 BM25 排名，并能从可执行反例、运行时状态与关键语句解释其边界。

??? note "交付文件"
    - `src/minilucene/search/__init__.py`
    - `src/minilucene/search/bm25.py`
    - `src/minilucene/search/scorer.py`
    - `tests/contract/test_ranking.py`
    - `tests/helpers/corpus.py`
    - `tests/unit/search/test_bm25.py`

### 当前遇到的问题

Matching 只说明哪些 Document 合格，却不说明有限结果槽位如何排序。

### 测试契约

#### 先看会坏在哪里

测试改变 TF、Document Length、零平均长度与 Field Boost，暴露不稳定或除零评分。

??? note "文件差异：tests/contract/test_ranking.py"
    ```diff
    diff --git a/tests/contract/test_ranking.py b/tests/contract/test_ranking.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..d84ba3d0fd4bbd090d1a56cee51672bb103b7b29
    --- /dev/null
    +++ b/tests/contract/test_ranking.py
    @@ -0,0 +1,58 @@
    +from minilucene.query import (
    +    BooleanClause,
    +    BooleanQuery,
    +    Occur,
    +    PhraseQuery,
    +    TermQuery,
    +)
    +from tests.helpers.corpus import search_memory
    +
    +
    +def test_title_boost_changes_ranking():
    +    hits = search_memory(
    +        documents=(
    +            {"title": "kafka", "body": "nothing"},
    +            {"title": "nothing", "body": "kafka kafka"},
    +        ),
    +        query=BooleanQuery(
    +            (
    +                BooleanClause(
    +                    Occur.SHOULD, TermQuery("title", "kafka")
    +                ),
    +                BooleanClause(Occur.SHOULD, TermQuery("body", "kafka")),
    +            )
    +        ),
    +        title_boost=3.0,
    +    )
    +    assert hits[0].stored_fields["id"] == "0"
    +
    +
    +def test_phrase_scores_only_documents_that_match_positions():
    +    hits = search_memory(
    +        documents=(
    +            {"title": "", "body": "follower replicas"},
    +            {"title": "", "body": "follower distant replicas"},
    +        ),
    +        query=PhraseQuery("body", ("follower", "replicas")),
    +    )
    +    assert [hit.stored_fields["id"] for hit in hits] == ["0"]
    +
    +
    +def test_must_not_filters_without_contributing_score():
    +    positive = TermQuery("body", "kafka")
    +    filtered = BooleanQuery(
    +        (
    +            BooleanClause(Occur.MUST, positive),
    +            BooleanClause(
    +                Occur.MUST_NOT, TermQuery("body", "excluded")
    +            ),
    +        )
    +    )
    +    documents = (
    +        {"title": "", "body": "kafka"},
    +        {"title": "", "body": "kafka excluded"},
    +    )
    +    positive_hits = search_memory(documents=documents, query=positive)
    +    filtered_hits = search_memory(documents=documents, query=filtered)
    +    assert len(filtered_hits) == 1
    +    assert filtered_hits[0].score == positive_hits[0].score
    ```

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

测试改变 TF、Document Length、零平均长度与 Field Boost，暴露不稳定或除零评分。

**关键测试语句**

```python
assert hits[0].stored_fields["id"] == "0"
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

??? note "文件差异：tests/helpers/corpus.py"
    ```diff
    diff --git a/tests/helpers/corpus.py b/tests/helpers/corpus.py
    index 57b0ab8156b73bb0e7efd798e32cdd41377d5d21..d46946224d0ae42c4df8983a4d5c841281a09e4b 100644
    --- a/tests/helpers/corpus.py
    +++ b/tests/helpers/corpus.py
    @@ -1,5 +1,7 @@
    +from dataclasses import dataclass
    +
     from minilucene.index.memory import RamIndexBuilder
    -from minilucene.schema import Schema, TextField
    +from minilucene.schema import KeywordField, Schema, TextField


     class SingleSegmentReader:
    @@ -73,3 +75,44 @@ def build_multi_segment_reader(*, segments, deleted):
             live_docs.append(frozenset(range(segment.max_doc)) - frozenset(removed))
         schema = Schema(body=TextField(stored=True))
         return ReaderView(schema, tuple(built), tuple(live_docs))
    +
    +
    +@dataclass(frozen=True)
    +class OracleHit:
    +    score: float
    +    stored_fields: object
    +    segment_generation: int
    +    local_doc_id: int
    +
    +
    +def search_memory(*, documents, query, title_boost=1.0):
    +    from minilucene.search.reader import ReaderView
    +    from minilucene.search.scorer import score_query
    +
    +    schema = Schema(
    +        id=KeywordField(stored=True),
    +        title=TextField(stored=True, boost=title_boost),
    +        body=TextField(stored=True),
    +    )
    +    builder = RamIndexBuilder(schema)
    +    for index, document in enumerate(documents):
    +        builder.add_document({"id": str(index), **document})
    +    reader = ReaderView(schema, (builder.freeze(generation=0),))
    +    scores = score_query(reader, query)
    +    hits = [
    +        OracleHit(
    +            score=score,
    +            stored_fields=reader.stored_fields(doc_id),
    +            segment_generation=reader.address(doc_id).segment_generation,
    +            local_doc_id=reader.address(doc_id).local_doc_id,
    +        )
    +        for doc_id, score in scores.items()
    +    ]
    +    return sorted(
    +        hits,
    +        key=lambda hit: (
    +            -hit.score,
    +            hit.segment_generation,
    +            hit.local_doc_id,
    +        ),
    +    )
    ```

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

测试改变 TF、Document Length、零平均长度与 Field Boost，暴露不稳定或除零评分。

**关键测试语句**

```python
assert hits[0].stored_fields["id"] == "0"
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

??? note "文件差异：tests/unit/search/test_bm25.py"
    ```diff
    diff --git a/tests/unit/search/test_bm25.py b/tests/unit/search/test_bm25.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..5b4e63cf0f68cf47d8dab61658e16d6a8d8ae345
    --- /dev/null
    +++ b/tests/unit/search/test_bm25.py
    @@ -0,0 +1,32 @@
    +import pytest
    +
    +from minilucene.search.bm25 import BM25
    +
    +
    +def test_bm25_tf_saturates():
    +    bm25 = BM25(k1=1.2, b=0.75)
    +    one = bm25.term_score(tf=1, df=1, n=10, dl=10, avgdl=10)
    +    ten = bm25.term_score(tf=10, df=1, n=10, dl=10, avgdl=10)
    +    hundred = bm25.term_score(tf=100, df=1, n=10, dl=10, avgdl=10)
    +    assert ten > one
    +    assert hundred - ten < ten - one
    +
    +
    +def test_bm25_longer_document_is_normalized_down():
    +    bm25 = BM25()
    +    short = bm25.term_score(tf=2, df=2, n=10, dl=5, avgdl=10)
    +    long = bm25.term_score(tf=2, df=2, n=10, dl=20, avgdl=10)
    +    assert short > long
    +
    +
    +@pytest.mark.parametrize(
    +    ("k1", "b"),
    +    [(0.0, 0.75), (-1.0, 0.75), (1.2, -0.1), (1.2, 1.1)],
    +)
    +def test_bm25_rejects_invalid_parameters(k1, b):
    +    with pytest.raises(ValueError):
    +        BM25(k1=k1, b=b)
    +
    +
    +def test_bm25_returns_zero_for_non_match():
    +    assert BM25().term_score(tf=0, df=1, n=10, dl=1, avgdl=1) == 0.0
    ```

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

测试改变 TF、Document Length、零平均长度与 Field Boost，暴露不稳定或除零评分。

**关键测试语句**

```python
assert hits[0].stored_fields["id"] == "0"
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

BM25 把全局 IDF、饱和 TF 与 Length Normalization 组合起来；Boost 表达显式字段或 Query 权重。

### 为什么需要这个机制

Matching 只说明哪些 Document 合格，却不说明有限结果槽位如何排序。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Scorer 遍历匹配 Term，读取 Snapshot Statistic 与 Document Norm，累积子分数，再应用确定性 Tie Break。

### 机制板块

#### 全局 BM25 排名机制

Scorer 遍历匹配 Term，读取 Snapshot Statistic 与 Document Norm，累积子分数，再应用确定性 Tie Break。

??? note "文件差异：src/minilucene/search/bm25.py"
    ```diff
    diff --git a/src/minilucene/search/bm25.py b/src/minilucene/search/bm25.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..f1449d80578641b446272b1d2f753ff612071789
    --- /dev/null
    +++ b/src/minilucene/search/bm25.py
    @@ -0,0 +1,34 @@
    +import math
    +from dataclasses import dataclass
    +
    +
    +@dataclass(frozen=True, slots=True)
    +class BM25:
    +    k1: float = 1.2
    +    b: float = 0.75
    +
    +    def __post_init__(self) -> None:
    +        if not math.isfinite(self.k1) or self.k1 <= 0:
    +            raise ValueError("BM25 k1 must be finite and positive")
    +        if not math.isfinite(self.b) or not 0.0 <= self.b <= 1.0:
    +            raise ValueError("BM25 b must be finite and between zero and one")
    +
    +    def term_score(
    +        self,
    +        *,
    +        tf: int,
    +        df: int,
    +        n: int,
    +        dl: int,
    +        avgdl: float,
    +    ) -> float:
    +        if tf <= 0 or df <= 0 or n <= 0:
    +            return 0.0
    +        idf = math.log(1.0 + (n - df + 0.5) / (df + 0.5))
    +        normalized_length = dl / avgdl if avgdl else 0.0
    +        norm = 1.0 - self.b + self.b * normalized_length
    +        return (
    +            idf
    +            * (tf * (self.k1 + 1.0))
    +            / (tf + self.k1 * norm)
    +        )
    ```

??? note "文件差异：src/minilucene/search/scorer.py"
    ```diff
    diff --git a/src/minilucene/search/scorer.py b/src/minilucene/search/scorer.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..f56cf9473c99a6be16e4d878dcc40cdf8e2fb053
    --- /dev/null
    +++ b/src/minilucene/search/scorer.py
    @@ -0,0 +1,92 @@
    +from minilucene.query.match import match_query
    +from minilucene.query.model import (
    +    BooleanQuery,
    +    MatchAllQuery,
    +    Occur,
    +    PhraseQuery,
    +    PrefixQuery,
    +    Query,
    +    TermQuery,
    +)
    +from minilucene.search.bm25 import BM25
    +from minilucene.search.reader import ReaderView
    +
    +
    +def _term_scores(
    +    reader: ReaderView,
    +    query: TermQuery,
    +    bm25: BM25,
    +    eligible: set[int] | None = None,
    +) -> dict[int, float]:
    +    stats = reader.corpus_stats
    +    field = reader.schema[query.field]
    +    df = stats.doc_frequency(query.field, query.term)
    +    average_length = stats.average_length(query.field)
    +    scores: dict[int, float] = {}
    +    for posting in reader.postings(query.field, query.term):
    +        if eligible is not None and posting.doc_id not in eligible:
    +            continue
    +        scores[posting.doc_id] = field.boost * bm25.term_score(
    +            tf=posting.term_frequency,
    +            df=df,
    +            n=stats.live_doc_count,
    +            dl=reader.field_length(query.field, posting.doc_id),
    +            avgdl=average_length,
    +        )
    +    return scores
    +
    +
    +def _merge_scores(
    +    target: dict[int, float],
    +    source: dict[int, float],
    +    eligible: set[int],
    +) -> None:
    +    for doc_id, score in source.items():
    +        if doc_id in eligible:
    +            target[doc_id] = target.get(doc_id, 0.0) + score
    +
    +
    +def score_query(
    +    reader: ReaderView, query: Query, bm25: BM25 | None = None
    +) -> dict[int, float]:
    +    bm25 = bm25 or BM25()
    +    candidates = match_query(reader, query)
    +    match query:
    +        case TermQuery():
    +            return _term_scores(reader, query, bm25, candidates)
    +        case PhraseQuery(field, terms):
    +            scores: dict[int, float] = {}
    +            for term in terms:
    +                _merge_scores(
    +                    scores,
    +                    _term_scores(
    +                        reader, TermQuery(field, term), bm25, candidates
    +                    ),
    +                    candidates,
    +                )
    +            return scores
    +        case PrefixQuery(field, prefix):
    +            scores = {}
    +            for term in reader.terms_with_prefix(field, prefix):
    +                _merge_scores(
    +                    scores,
    +                    _term_scores(
    +                        reader, TermQuery(field, term), bm25, candidates
    +                    ),
    +                    candidates,
    +                )
    +            return scores
    +        case MatchAllQuery():
    +            return {doc_id: 0.0 for doc_id in candidates}
    +        case BooleanQuery(clauses):
    +            scores = {doc_id: 0.0 for doc_id in candidates}
    +            for clause in clauses:
    +                if clause.occur is Occur.MUST_NOT:
    +                    continue
    +                _merge_scores(
    +                    scores,
    +                    score_query(reader, clause.query, bm25),
    +                    candidates,
    +                )
    +            return scores
    +    return {}
    ```

**是什么，为什么现在需要**

BM25 把全局 IDF、饱和 TF 与 Length Normalization 组合起来；Boost 表达显式字段或 Query 权重。

**在运行时做什么**

Scorer 遍历匹配 Term，读取 Snapshot Statistic 与 Document Norm，累积子分数，再应用确定性 Tie Break。

**关键语句理解**

零平均值保护建立有限归一化基线，避免空 Field 污染所有 Score。

#### 包、Fixture 与工程支撑

保持包导出、测试语料、依赖与运行环境可复现。

??? note "支撑文件差异（1 个文件）"
    **`src/minilucene/search/__init__.py`**

    ```diff
    diff --git a/src/minilucene/search/__init__.py b/src/minilucene/search/__init__.py
    index e7896ba128e109797bb2852a4a0914eb03446089..76c1e85bd6bf48b0dad002921d2dd98021687093 100644
    --- a/src/minilucene/search/__init__.py
    +++ b/src/minilucene/search/__init__.py
    @@ -1,4 +1,6 @@
    +from minilucene.search.bm25 import BM25
     from minilucene.search.reader import DocAddress, ReaderView
    +from minilucene.search.scorer import score_query
     from minilucene.search.stats import CorpusStats

    -__all__ = ["CorpusStats", "DocAddress", "ReaderView"]
    +__all__ = ["BM25", "CorpusStats", "DocAddress", "ReaderView", "score_query"]
    ```


### 验证证据

运行 `uv run pytest -q $(cat journey/stages/06-bm25-ranking/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

零平均值保护建立有限归一化基线，避免空 Field 污染所有 Score。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 8 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/08-scoring.md)

[Complete reference patch / 完整参考补丁](https://github.com/system-in-miniature/mini-lucene/blob/main/journey/stages/06-bm25-ranking/stage.patch)

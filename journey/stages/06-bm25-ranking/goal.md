# Stage 06 · Global BM25 ranking / 全局 BM25 排名

<!-- journey: chapter=8 tests_added=3 -->

## English

### Goal

Build global bm25 ranking and explain its boundary from an executable counterexample, runtime state, and the critical statement.

### Deliverable files

- `src/minilucene/search/__init__.py`
- `src/minilucene/search/bm25.py`
- `src/minilucene/search/scorer.py`
- `tests/contract/test_ranking.py`
- `tests/helpers/corpus.py`
- `tests/unit/search/test_bm25.py`

### The problem at this point

Matching says which documents qualify but not how limited result slots should be ordered.

### Test contract

#### See the failure first

Tests vary term frequency, document length, zero average length, and field boosts to expose unstable or divided-by-zero scoring.

<!-- journey-file: tests/contract/test_ranking.py -->
<!-- journey-file: tests/helpers/corpus.py -->
<!-- journey-file: tests/unit/search/test_bm25.py -->
#### Global BM25 ranking test evidence

##### What this test locks

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

##### How it constructs the counterexample

Tests vary term frequency, document length, zero average length, and field boosts to expose unstable or divided-by-zero scoring.

##### Key test statement

```python
assert hits[0].stored_fields["id"] == "0"
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

##### What a failure means

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

BM25 combines global IDF with saturating term frequency and length normalization; boosts express explicit field/query weight.

### Why this mechanism is necessary

Matching says which documents qualify but not how limited result slots should be ordered. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

The scorer visits matching terms, reads snapshot statistics and per-document norms, accumulates child scores, then applies deterministic tie-breaking.

### Mechanism blocks

<!-- journey-file: src/minilucene/search/bm25.py -->
<!-- journey-file: src/minilucene/search/scorer.py -->
#### Global BM25 ranking mechanism

##### What it is and why it appears

BM25 combines global IDF with saturating term frequency and length normalization; boosts express explicit field/query weight.

##### Runtime role

The scorer visits matching terms, reads snapshot statistics and per-document norms, accumulates child scores, then applies deterministic tie-breaking.

##### Statement understanding

The zero-average guard preserves a finite normalization baseline instead of letting an empty field poison every score.

<!-- journey-file: src/minilucene/search/__init__.py -->
#### Package, fixture, and project support

These files only keep exports, test corpora, dependencies, and the runtime environment reproducible; they are supporting wiring rather than Lucene mechanism logic.

### Verification evidence

Run `uv run pytest -q $(cat journey/stages/06-bm25-ranking/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

The zero-average guard preserves a finite normalization baseline instead of letting an empty field poison every score.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 8](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/08-scoring.md)

## 中文

### 目标

实现全局 BM25 排名，并能从可执行反例、运行时状态与关键语句解释其边界。

### 交付文件

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

<!-- journey-file: tests/contract/test_ranking.py -->
<!-- journey-file: tests/helpers/corpus.py -->
<!-- journey-file: tests/unit/search/test_bm25.py -->
#### 全局 BM25 排名测试证据

##### 测试锁定什么

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

##### 如何构造反例

测试改变 TF、Document Length、零平均长度与 Field Boost，暴露不稳定或除零评分。

##### 关键测试语句

```python
assert hits[0].stored_fields["id"] == "0"
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

##### 失败意味着什么

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

BM25 把全局 IDF、饱和 TF 与 Length Normalization 组合起来；Boost 表达显式字段或 Query 权重。

### 为什么需要这个机制

Matching 只说明哪些 Document 合格，却不说明有限结果槽位如何排序。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Scorer 遍历匹配 Term，读取 Snapshot Statistic 与 Document Norm，累积子分数，再应用确定性 Tie Break。

### 机制板块

<!-- journey-file: src/minilucene/search/bm25.py -->
<!-- journey-file: src/minilucene/search/scorer.py -->
#### 全局 BM25 排名机制

##### 是什么，为什么现在需要

BM25 把全局 IDF、饱和 TF 与 Length Normalization 组合起来；Boost 表达显式字段或 Query 权重。

##### 在运行时做什么

Scorer 遍历匹配 Term，读取 Snapshot Statistic 与 Document Norm，累积子分数，再应用确定性 Tie Break。

##### 关键语句理解

零平均值保护建立有限归一化基线，避免空 Field 污染所有 Score。

<!-- journey-file: src/minilucene/search/__init__.py -->
#### 包、Fixture 与工程支撑

这些文件只保持包导出、测试语料、依赖与运行环境可复现，不把支撑接线误讲成 Lucene 机制。

### 验证证据

运行 `uv run pytest -q $(cat journey/stages/06-bm25-ranking/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

零平均值保护建立有限归一化基线，避免空 Field 污染所有 Score。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 8 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/08-scoring.md)

# Stage 05 · Snapshot corpus statistics / 快照级语料统计

<!-- journey: chapter=8 tests_added=2 -->

## English

### Goal

Build snapshot corpus statistics and explain its boundary from an executable counterexample, runtime state, and the critical statement.

### Deliverable files

- `src/minilucene/query/match.py`
- `src/minilucene/search/__init__.py`
- `src/minilucene/search/reader.py`
- `src/minilucene/search/stats.py`
- `tests/helpers/corpus.py`
- `tests/unit/search/test_corpus_stats.py`

### The problem at this point

Scoring each segment with local statistics makes identical terms incomparable across a multi-segment index.

### Test contract

#### See the failure first

The counterexample distributes documents unevenly across segments and checks document frequency and average field length over the whole snapshot.

<!-- journey-file: tests/helpers/corpus.py -->
<!-- journey-file: tests/unit/search/test_corpus_stats.py -->
#### Snapshot corpus statistics test evidence

##### What this test locks

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

##### How it constructs the counterexample

The counterexample distributes documents unevenly across segments and checks document frequency and average field length over the whole snapshot.

##### Key test statement

```python
assert stats.live_doc_count == 2
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

##### What a failure means

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

Corpus statistics belong to a reader snapshot: live document count, per-field length totals, and term document frequency.

### Why this mechanism is necessary

Scoring each segment with local statistics makes identical terms incomparable across a multi-segment index. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

Opening a search reader walks all visible segment views once and freezes aggregate statistics beside them.

### Mechanism blocks

<!-- journey-file: src/minilucene/query/match.py -->
<!-- journey-file: src/minilucene/search/reader.py -->
<!-- journey-file: src/minilucene/search/stats.py -->
#### Snapshot corpus statistics mechanism

##### What it is and why it appears

Corpus statistics belong to a reader snapshot: live document count, per-field length totals, and term document frequency.

##### Runtime role

Opening a search reader walks all visible segment views once and freezes aggregate statistics beside them.

##### Statement understanding

Freezing statistics with the same segment set used for matching prevents scores from mixing two visibility generations.

<!-- journey-file: src/minilucene/search/__init__.py -->
#### Package, fixture, and project support

These files only keep exports, test corpora, dependencies, and the runtime environment reproducible; they are supporting wiring rather than Lucene mechanism logic.

### Verification evidence

Run `uv run pytest -q $(cat journey/stages/05-corpus-statistics/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Freezing statistics with the same segment set used for matching prevents scores from mixing two visibility generations.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 8](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/08-scoring.md)

## 中文

### 目标

实现快照级语料统计，并能从可执行反例、运行时状态与关键语句解释其边界。

### 交付文件

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

<!-- journey-file: tests/helpers/corpus.py -->
<!-- journey-file: tests/unit/search/test_corpus_stats.py -->
#### 快照级语料统计测试证据

##### 测试锁定什么

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

##### 如何构造反例

反例把 Document 不均匀分布在多个 Segment，并检查整个 Snapshot 上的 DF 与平均 Field Length。

##### 关键测试语句

```python
assert stats.live_doc_count == 2
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

##### 失败意味着什么

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Corpus Statistic 属于 Reader Snapshot：Live Document Count、各 Field Length Total 与 Term DF。

### 为什么需要这个机制

用 Segment 局部统计评分，会让多 Segment 索引中的相同 Term 不可比较。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

打开 Search Reader 时遍历全部可见 Segment View，并把聚合统计与它们一起冻结。

### 机制板块

<!-- journey-file: src/minilucene/query/match.py -->
<!-- journey-file: src/minilucene/search/reader.py -->
<!-- journey-file: src/minilucene/search/stats.py -->
#### 快照级语料统计机制

##### 是什么，为什么现在需要

Corpus Statistic 属于 Reader Snapshot：Live Document Count、各 Field Length Total 与 Term DF。

##### 在运行时做什么

打开 Search Reader 时遍历全部可见 Segment View，并把聚合统计与它们一起冻结。

##### 关键语句理解

统计与 Matching 使用的 Segment Set 一起冻结，避免 Score 混合两个可见性代次。

<!-- journey-file: src/minilucene/search/__init__.py -->
#### 包、Fixture 与工程支撑

这些文件只保持包导出、测试语料、依赖与运行环境可复现，不把支撑接线误讲成 Lucene 机制。

### 验证证据

运行 `uv run pytest -q $(cat journey/stages/05-corpus-statistics/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

统计与 Matching 使用的 Segment Set 一起冻结，避免 Score 混合两个可见性代次。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 8 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/08-scoring.md)

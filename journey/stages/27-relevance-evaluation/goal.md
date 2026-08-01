# Stage 27 · Deterministic relevance evaluation / 确定性相关性评估

<!-- journey: chapter=8 tests_added=4 -->

## English

### Goal

Build deterministic relevance evaluation and explain its boundary from an executable counterexample, runtime state, and the critical statement.

### Deliverable files

- `src/minilucene/evaluation.py`
- `tests/evaluation/test_metrics.py`
- `tests/evaluation/test_reference_corpus.py`
- `tests/fixtures/corpus.json`
- `tests/fixtures/qrels.json`
- `tests/fixtures/queries.json`
- `tests/support/__init__.py`
- `tests/support/reference_corpus.py`

### The problem at this point

A few hand-inspected hits cannot show whether ranking changes improve or regress a fixed retrieval task.

### Test contract

#### See the failure first

Metric tests cover ties, missing judgments, empty relevant sets, cutoffs, and a frozen corpus with expected per-query results.

<!-- journey-file: tests/evaluation/test_metrics.py -->
<!-- journey-file: tests/evaluation/test_reference_corpus.py -->
<!-- journey-file: tests/support/__init__.py -->
<!-- journey-file: tests/support/reference_corpus.py -->
#### Deterministic relevance evaluation test evidence

##### What this test locks

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

##### How it constructs the counterexample

Metric tests cover ties, missing judgments, empty relevant sets, cutoffs, and a frozen corpus with expected per-query results.

##### Key test statement

```python
assert precision_at_k(ranked, relevant, 2) == 0.5
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

##### What a failure means

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

Precision, recall, average precision, reciprocal rank, and nDCG are deterministic functions of ranked IDs and qrels; fixtures freeze the evaluation world.

### Why this mechanism is necessary

A few hand-inspected hits cannot show whether ranking changes improve or regress a fixed retrieval task. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

The harness builds the reference index, runs declared queries, computes metrics at fixed cutoffs, and compares stable aggregates.

### Mechanism blocks

<!-- journey-file: src/minilucene/evaluation.py -->
#### Deterministic relevance evaluation mechanism

##### What it is and why it appears

Precision, recall, average precision, reciprocal rank, and nDCG are deterministic functions of ranked IDs and qrels; fixtures freeze the evaluation world.

##### Runtime role

The harness builds the reference index, runs declared queries, computes metrics at fixed cutoffs, and compares stable aggregates.

##### Statement understanding

Explicit tie ordering and fixed fixtures make a score change observable as evidence rather than an anecdotal ranking impression.

<!-- journey-file: tests/fixtures/corpus.json -->
<!-- journey-file: tests/fixtures/qrels.json -->
<!-- journey-file: tests/fixtures/queries.json -->
#### Package, fixture, and project support

These files only keep exports, test corpora, dependencies, and the runtime environment reproducible; they are supporting wiring rather than Lucene mechanism logic.

### Verification evidence

Run `uv run pytest -q $(cat journey/stages/27-relevance-evaluation/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Explicit tie ordering and fixed fixtures make a score change observable as evidence rather than an anecdotal ranking impression.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 8](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/08-scoring.md)

## 中文

### 目标

实现确定性相关性评估，并能从可执行反例、运行时状态与关键语句解释其边界。

### 交付文件

- `src/minilucene/evaluation.py`
- `tests/evaluation/test_metrics.py`
- `tests/evaluation/test_reference_corpus.py`
- `tests/fixtures/corpus.json`
- `tests/fixtures/qrels.json`
- `tests/fixtures/queries.json`
- `tests/support/__init__.py`
- `tests/support/reference_corpus.py`

### 当前遇到的问题

少量人工查看 Hit 无法说明 Ranking 变化是在改进还是回归固定 Retrieval Task。

### 测试契约

#### 先看会坏在哪里

Metric 测试覆盖 Tie、缺失 Judgment、空 Relevant Set、Cutoff 与带预期 Query Result 的冻结 Corpus。

<!-- journey-file: tests/evaluation/test_metrics.py -->
<!-- journey-file: tests/evaluation/test_reference_corpus.py -->
<!-- journey-file: tests/support/__init__.py -->
<!-- journey-file: tests/support/reference_corpus.py -->
#### 确定性相关性评估测试证据

##### 测试锁定什么

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

##### 如何构造反例

Metric 测试覆盖 Tie、缺失 Judgment、空 Relevant Set、Cutoff 与带预期 Query Result 的冻结 Corpus。

##### 关键测试语句

```python
assert precision_at_k(ranked, relevant, 2) == 0.5
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

##### 失败意味着什么

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Precision、Recall、AP、RR 与 nDCG 是 Ranked ID 与 Qrel 的确定函数；Fixture 冻结评估世界。

### 为什么需要这个机制

少量人工查看 Hit 无法说明 Ranking 变化是在改进还是回归固定 Retrieval Task。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Harness 构建 Reference Index、运行声明 Query、在固定 Cutoff 计算 Metric，并比较稳定 Aggregate。

### 机制板块

<!-- journey-file: src/minilucene/evaluation.py -->
#### 确定性相关性评估机制

##### 是什么，为什么现在需要

Precision、Recall、AP、RR 与 nDCG 是 Ranked ID 与 Qrel 的确定函数；Fixture 冻结评估世界。

##### 在运行时做什么

Harness 构建 Reference Index、运行声明 Query、在固定 Cutoff 计算 Metric，并比较稳定 Aggregate。

##### 关键语句理解

显式 Tie Ordering 与固定 Fixture，让 Score 变化成为可观察证据而非主观 Ranking 印象。

<!-- journey-file: tests/fixtures/corpus.json -->
<!-- journey-file: tests/fixtures/qrels.json -->
<!-- journey-file: tests/fixtures/queries.json -->
#### 包、Fixture 与工程支撑

这些文件只保持包导出、测试语料、依赖与运行环境可复现，不把支撑接线误讲成 Lucene 机制。

### 验证证据

运行 `uv run pytest -q $(cat journey/stages/27-relevance-evaluation/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

显式 Tie Ordering 与固定 Fixture，让 Score 变化成为可观察证据而非主观 Ranking 印象。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 8 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/08-scoring.md)

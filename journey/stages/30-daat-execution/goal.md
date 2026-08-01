# Stage 30 · Document-at-a-time execution / Document-at-a-time 执行

<!-- journey: chapter=11 tests_added=4 -->

## English

### Goal

Build document-at-a-time execution and explain its boundary from an executable counterexample, runtime state, and the critical statement.

### Deliverable files

- `pyproject.toml`
- `src/minilucene/search/__init__.py`
- `src/minilucene/search/collector.py`
- `src/minilucene/search/iterators.py`
- `src/minilucene/search/scorer.py`
- `src/minilucene/search/searcher.py`
- `tests/contract/test_collect_then_fetch.py`
- `tests/unit/search/test_daat_scorer.py`
- `tests/unit/search/test_iterators.py`
- `tests/unit/search/test_topk.py`
- `uv.lock`

### The problem at this point

Materializing full result sets for every query node hides streaming behavior and scales with all matches before Top-K can discard most of them.

### Test contract

#### See the failure first

Differential tests generate nested boolean queries and require DAAT hits and scores to equal the existing set-based oracle, including fallback cases.

<!-- journey-file: tests/contract/test_collect_then_fetch.py -->
<!-- journey-file: tests/unit/search/test_daat_scorer.py -->
<!-- journey-file: tests/unit/search/test_iterators.py -->
<!-- journey-file: tests/unit/search/test_topk.py -->
#### Document-at-a-time execution test evidence

##### What this test locks

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

##### How it constructs the counterexample

Differential tests generate nested boolean queries and require DAAT hits and scores to equal the existing set-based oracle, including fallback cases.

##### Key test statement

```python
assert results.total_hits == 10
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

##### What a failure means

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

A doc iterator exposes current doc ID and monotonic advance; conjunction aligns cursors, disjunction heap-merges them, exclusion filters a required stream, and streaming scorers retain BM25 evidence.

### Why this mechanism is necessary

Materializing full result sets for every query node hides streaming behavior and scales with all matches before Top-K can discard most of them. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

The planner builds iterator/scorer trees from rewritten queries, collectors consume candidates without stored fields, and a second phase fetches only winners.

### Mechanism blocks

<!-- journey-file: src/minilucene/search/collector.py -->
<!-- journey-file: src/minilucene/search/iterators.py -->
<!-- journey-file: src/minilucene/search/scorer.py -->
<!-- journey-file: src/minilucene/search/searcher.py -->
#### Document-at-a-time execution mechanism

##### What it is and why it appears

A doc iterator exposes current doc ID and monotonic advance; conjunction aligns cursors, disjunction heap-merges them, exclusion filters a required stream, and streaming scorers retain BM25 evidence.

##### Runtime role

The planner builds iterator/scorer trees from rewritten queries, collectors consume candidates without stored fields, and a second phase fetches only winners.

##### Statement understanding

Differential equality makes the old executor an oracle while the new iterator contract changes cost and control flow without silently changing semantics.

<!-- journey-file: pyproject.toml -->
<!-- journey-file: src/minilucene/search/__init__.py -->
<!-- journey-file: uv.lock -->
#### Package, fixture, and project support

These files only keep exports, test corpora, dependencies, and the runtime environment reproducible; they are supporting wiring rather than Lucene mechanism logic.

### Verification evidence

Run `uv run pytest -q $(cat journey/stages/30-daat-execution/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Differential equality makes the old executor an oracle while the new iterator contract changes cost and control flow without silently changing semantics.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 11](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/11-daat.md)

## 中文

### 目标

实现Document-at-a-time 执行，并能从可执行反例、运行时状态与关键语句解释其边界。

### 交付文件

- `pyproject.toml`
- `src/minilucene/search/__init__.py`
- `src/minilucene/search/collector.py`
- `src/minilucene/search/iterators.py`
- `src/minilucene/search/scorer.py`
- `src/minilucene/search/searcher.py`
- `tests/contract/test_collect_then_fetch.py`
- `tests/unit/search/test_daat_scorer.py`
- `tests/unit/search/test_iterators.py`
- `tests/unit/search/test_topk.py`
- `uv.lock`

### 当前遇到的问题

为每个 Query Node 物化完整 Result Set 会隐藏流式行为，并在 Top-K 丢弃多数结果前就按全部 Match 扩张。

### 测试契约

#### 先看会坏在哪里

差分测试生成嵌套 Boolean Query，并要求 DAAT Hit 与 Score 等于既有 Set-based Oracle，包含 Fallback Case。

<!-- journey-file: tests/contract/test_collect_then_fetch.py -->
<!-- journey-file: tests/unit/search/test_daat_scorer.py -->
<!-- journey-file: tests/unit/search/test_iterators.py -->
<!-- journey-file: tests/unit/search/test_topk.py -->
#### Document-at-a-time 执行测试证据

##### 测试锁定什么

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

##### 如何构造反例

差分测试生成嵌套 Boolean Query，并要求 DAAT Hit 与 Score 等于既有 Set-based Oracle，包含 Fallback Case。

##### 关键测试语句

```python
assert results.total_hits == 10
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

##### 失败意味着什么

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Doc Iterator 暴露 Current Doc ID 与单调 Advance；Conjunction 对齐 Cursor，Disjunction 用 Heap Merge，Exclusion 过滤 Required Stream，Streaming Scorer 保留 BM25 Evidence。

### 为什么需要这个机制

为每个 Query Node 物化完整 Result Set 会隐藏流式行为，并在 Top-K 丢弃多数结果前就按全部 Match 扩张。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Planner 从 Rewritten Query 构建 Iterator/Scorer Tree，Collector 在不取 Stored Field 的情况下消费 Candidate，第二阶段只 Fetch Winner。

### 机制板块

<!-- journey-file: src/minilucene/search/collector.py -->
<!-- journey-file: src/minilucene/search/iterators.py -->
<!-- journey-file: src/minilucene/search/scorer.py -->
<!-- journey-file: src/minilucene/search/searcher.py -->
#### Document-at-a-time 执行机制

##### 是什么，为什么现在需要

Doc Iterator 暴露 Current Doc ID 与单调 Advance；Conjunction 对齐 Cursor，Disjunction 用 Heap Merge，Exclusion 过滤 Required Stream，Streaming Scorer 保留 BM25 Evidence。

##### 在运行时做什么

Planner 从 Rewritten Query 构建 Iterator/Scorer Tree，Collector 在不取 Stored Field 的情况下消费 Candidate，第二阶段只 Fetch Winner。

##### 关键语句理解

差分相等让旧 Executor 成为 Oracle，使新 Iterator Contract 改变成本与控制流而不悄悄改变语义。

<!-- journey-file: pyproject.toml -->
<!-- journey-file: src/minilucene/search/__init__.py -->
<!-- journey-file: uv.lock -->
#### 包、Fixture 与工程支撑

这些文件只保持包导出、测试语料、依赖与运行环境可复现，不把支撑接线误讲成 Lucene 机制。

### 验证证据

运行 `uv run pytest -q $(cat journey/stages/30-daat-execution/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

差分相等让旧 Executor 成为 Oracle，使新 Iterator Contract 改变成本与控制流而不悄悄改变语义。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 11 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/11-daat.md)

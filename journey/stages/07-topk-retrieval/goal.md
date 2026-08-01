# Stage 07 · Bounded Top-K retrieval / 有界 Top-K 检索

<!-- journey: chapter=8 tests_added=3 -->

## English

### Goal

Build bounded top-k retrieval and explain its boundary from an executable counterexample, runtime state, and the critical statement.

### Deliverable files

- `src/minilucene/__init__.py`
- `src/minilucene/index/__init__.py`
- `src/minilucene/index/memory.py`
- `src/minilucene/search/__init__.py`
- `src/minilucene/search/collector.py`
- `src/minilucene/search/searcher.py`
- `tests/acceptance/test_phase1_retrieval_kernel.py`
- `tests/contract/test_memory_search.py`
- `tests/unit/search/test_topk.py`

### The problem at this point

Sorting every matching document wastes memory when a caller requests only a small number of hits.

### Test contract

#### See the failure first

The tests create more matches than K, score ties, and stored fields large enough to expose eager fetching.

<!-- journey-file: tests/acceptance/test_phase1_retrieval_kernel.py -->
<!-- journey-file: tests/contract/test_memory_search.py -->
<!-- journey-file: tests/unit/search/test_topk.py -->
#### Bounded Top-K retrieval test evidence

##### What this test locks

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

##### How it constructs the counterexample

The tests create more matches than K, score ties, and stored fields large enough to expose eager fetching.

##### Key test statement

```python
assert result.total_hits == 1
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

##### What a failure means

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

A bounded collector retains only competitive score/doc pairs; search separates collect from fetching stored winners.

### Why this mechanism is necessary

Sorting every matching document wastes memory when a caller requests only a small number of hits. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

Scoring streams candidates into a min-heap of size K, finalizes deterministic order, then loads stored data only for winners.

### Mechanism blocks

<!-- journey-file: src/minilucene/index/memory.py -->
<!-- journey-file: src/minilucene/search/collector.py -->
<!-- journey-file: src/minilucene/search/searcher.py -->
#### Bounded Top-K retrieval mechanism

##### What it is and why it appears

A bounded collector retains only competitive score/doc pairs; search separates collect from fetching stored winners.

##### Runtime role

Scoring streams candidates into a min-heap of size K, finalizes deterministic order, then loads stored data only for winners.

##### Statement understanding

The heap bound controls working memory, and score-plus-doc ordering makes ties reproducible across runs.

<!-- journey-file: src/minilucene/__init__.py -->
<!-- journey-file: src/minilucene/index/__init__.py -->
<!-- journey-file: src/minilucene/search/__init__.py -->
#### Package, fixture, and project support

These files only keep exports, test corpora, dependencies, and the runtime environment reproducible; they are supporting wiring rather than Lucene mechanism logic.

### Verification evidence

Run `uv run pytest -q $(cat journey/stages/07-topk-retrieval/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

The heap bound controls working memory, and score-plus-doc ordering makes ties reproducible across runs.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 8](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/08-scoring.md)

## 中文

### 目标

实现有界 Top-K 检索，并能从可执行反例、运行时状态与关键语句解释其边界。

### 交付文件

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

<!-- journey-file: tests/acceptance/test_phase1_retrieval_kernel.py -->
<!-- journey-file: tests/contract/test_memory_search.py -->
<!-- journey-file: tests/unit/search/test_topk.py -->
#### 有界 Top-K 检索测试证据

##### 测试锁定什么

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

##### 如何构造反例

测试制造多于 K 的 Match、Score Tie 与足够大的 Stored Field，暴露提前 Fetch。

##### 关键测试语句

```python
assert result.total_hits == 1
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

##### 失败意味着什么

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

有界 Collector 只保留有竞争力的 Score/Doc Pair；Search 把 Collect 与 Fetch Stored Winner 分开。

### 为什么需要这个机制

调用方只要少量 Hit 时，对全部匹配 Document 排序会浪费内存。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Scoring 把 Candidate 流入大小 K 的 Min Heap，确定最终顺序后只加载 Winner 的 Stored Data。

### 机制板块

<!-- journey-file: src/minilucene/index/memory.py -->
<!-- journey-file: src/minilucene/search/collector.py -->
<!-- journey-file: src/minilucene/search/searcher.py -->
#### 有界 Top-K 检索机制

##### 是什么，为什么现在需要

有界 Collector 只保留有竞争力的 Score/Doc Pair；Search 把 Collect 与 Fetch Stored Winner 分开。

##### 在运行时做什么

Scoring 把 Candidate 流入大小 K 的 Min Heap，确定最终顺序后只加载 Winner 的 Stored Data。

##### 关键语句理解

Heap Bound 控制工作内存，Score 加 Doc 排序让 Tie 在多次运行间可复现。

<!-- journey-file: src/minilucene/__init__.py -->
<!-- journey-file: src/minilucene/index/__init__.py -->
<!-- journey-file: src/minilucene/search/__init__.py -->
#### 包、Fixture 与工程支撑

这些文件只保持包导出、测试语料、依赖与运行环境可复现，不把支撑接线误讲成 Lucene 机制。

### 验证证据

运行 `uv run pytest -q $(cat journey/stages/07-topk-retrieval/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

Heap Bound 控制工作内存，Score 加 Doc 排序让 Tie 在多次运行间可复现。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 8 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/08-scoring.md)

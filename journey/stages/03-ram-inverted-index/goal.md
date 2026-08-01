# Stage 03 · Immutable RAM inverted index / 不可变 RAM 倒排索引

<!-- journey: chapter=3 tests_added=1 -->

## English

### Goal

Build immutable ram inverted index and explain its boundary from an executable counterexample, runtime state, and the critical statement.

### Deliverable files

- `src/minilucene/index/__init__.py`
- `src/minilucene/index/memory.py`
- `src/minilucene/index/postings.py`
- `tests/contract/test_memory_index.py`

### The problem at this point

Validated documents still require a structure that answers which documents contain a term and where it occurs.

### Test contract

#### See the failure first

Tests index repeated terms and multiple fields, then mutate source inputs to prove the built segment does not change.

<!-- journey-file: tests/contract/test_memory_index.py -->
#### Immutable RAM inverted index test evidence

##### What this test locks

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

##### How it constructs the counterexample

Tests index repeated terms and multiple fields, then mutate source inputs to prove the built segment does not change.

##### Key test statement

```python
assert (posting.doc_id, posting.term_frequency, posting.positions) == (
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

##### What a failure means

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

A posting binds term, doc ID, frequency, and positions; norms store per-field length; an immutable segment freezes one indexing generation.

### Why this mechanism is necessary

Validated documents still require a structure that answers which documents contain a term and where it occurs. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

The builder analyzes indexed fields, assigns local doc IDs, accumulates ordered postings and norms, then publishes immutable mappings.

### Mechanism blocks

<!-- journey-file: src/minilucene/index/memory.py -->
<!-- journey-file: src/minilucene/index/postings.py -->
#### Immutable RAM inverted index mechanism

##### What it is and why it appears

A posting binds term, doc ID, frequency, and positions; norms store per-field length; an immutable segment freezes one indexing generation.

##### Runtime role

The builder analyzes indexed fields, assigns local doc IDs, accumulates ordered postings and norms, then publishes immutable mappings.

##### Statement understanding

Sorting terms, documents, and positions makes the segment deterministic and safe to share without mutation locks.

<!-- journey-file: src/minilucene/index/__init__.py -->
#### Package, fixture, and project support

These files only keep exports, test corpora, dependencies, and the runtime environment reproducible; they are supporting wiring rather than Lucene mechanism logic.

### Verification evidence

Run `uv run pytest -q $(cat journey/stages/03-ram-inverted-index/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Sorting terms, documents, and positions makes the segment deterministic and safe to share without mutation locks.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 3](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/03-inverted-index.md)

## 中文

### 目标

实现不可变 RAM 倒排索引，并能从可执行反例、运行时状态与关键语句解释其边界。

### 交付文件

- `src/minilucene/index/__init__.py`
- `src/minilucene/index/memory.py`
- `src/minilucene/index/postings.py`
- `tests/contract/test_memory_index.py`

### 当前遇到的问题

校验后的 Document 仍需要一种结构回答某 Term 出现在哪些 Document、哪些位置。

### 测试契约

#### 先看会坏在哪里

测试索引重复 Term 与多 Field，再修改源输入以证明已构建 Segment 不会变化。

<!-- journey-file: tests/contract/test_memory_index.py -->
#### 不可变 RAM 倒排索引测试证据

##### 测试锁定什么

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

##### 如何构造反例

测试索引重复 Term 与多 Field，再修改源输入以证明已构建 Segment 不会变化。

##### 关键测试语句

```python
assert (posting.doc_id, posting.term_frequency, posting.positions) == (
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

##### 失败意味着什么

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Posting 绑定 Term、Doc ID、Frequency 与 Position；Norm 保存 Field Length；不可变 Segment 冻结一次索引代次。

### 为什么需要这个机制

校验后的 Document 仍需要一种结构回答某 Term 出现在哪些 Document、哪些位置。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Builder 分析可索引字段、分配 Local Doc ID、累积有序 Posting 与 Norm，最后发布不可变 Mapping。

### 机制板块

<!-- journey-file: src/minilucene/index/memory.py -->
<!-- journey-file: src/minilucene/index/postings.py -->
#### 不可变 RAM 倒排索引机制

##### 是什么，为什么现在需要

Posting 绑定 Term、Doc ID、Frequency 与 Position；Norm 保存 Field Length；不可变 Segment 冻结一次索引代次。

##### 在运行时做什么

Builder 分析可索引字段、分配 Local Doc ID、累积有序 Posting 与 Norm，最后发布不可变 Mapping。

##### 关键语句理解

对 Term、Document 与 Position 排序，使 Segment 确定且可无锁共享。

<!-- journey-file: src/minilucene/index/__init__.py -->
#### 包、Fixture 与工程支撑

这些文件只保持包导出、测试语料、依赖与运行环境可复现，不把支撑接线误讲成 Lucene 机制。

### 验证证据

运行 `uv run pytest -q $(cat journey/stages/03-ram-inverted-index/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

对 Term、Document 与 Position 排序，使 Segment 确定且可无锁共享。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 3 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/03-inverted-index.md)

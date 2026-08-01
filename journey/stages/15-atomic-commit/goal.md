# Stage 15 · Atomic commit and reopen / 原子 Commit 与重开

<!-- journey: chapter=7 tests_added=3 -->

## English

### Goal

Build atomic commit and reopen and explain its boundary from an executable counterexample, runtime state, and the critical statement.

### Deliverable files

- `src/minilucene/__init__.py`
- `src/minilucene/index/directory.py`
- `src/minilucene/reader.py`
- `src/minilucene/writer.py`
- `tests/acceptance/test_phase2_storage_commit.py`
- `tests/contract/test_disk_search.py`
- `tests/storage/test_commit_recovery.py`

### The problem at this point

Flushed segments survive on disk but remain invisible after restart until the manifest root publishes them.

### Test contract

#### See the failure first

Commit tests fail before and during root replacement, reopen repeatedly, and require either the complete previous generation or the complete next one.

<!-- journey-file: tests/acceptance/test_phase2_storage_commit.py -->
<!-- journey-file: tests/contract/test_disk_search.py -->
<!-- journey-file: tests/storage/test_commit_recovery.py -->
#### Atomic commit and reopen test evidence

##### What this test locks

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

##### How it constructs the counterexample

Commit tests fail before and during root replacement, reopen repeatedly, and require either the complete previous generation or the complete next one.

##### Key test statement

```python
assert manifest.segment_generations == (1, 2)
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

##### What a failure means

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

Commit is a publication protocol over already durable segment children; reopen reconstructs an index strictly from the current manifest.

### Why this mechanism is necessary

Flushed segments survive on disk but remain invisible after restart until the manifest root publishes them. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

The writer flushes, prepares all referenced children, writes the next manifest, atomically swaps the root, and advances committed generation only after success.

### Mechanism blocks

<!-- journey-file: src/minilucene/index/directory.py -->
<!-- journey-file: src/minilucene/reader.py -->
<!-- journey-file: src/minilucene/writer.py -->
#### Atomic commit and reopen mechanism

##### What it is and why it appears

Commit is a publication protocol over already durable segment children; reopen reconstructs an index strictly from the current manifest.

##### Runtime role

The writer flushes, prepares all referenced children, writes the next manifest, atomically swaps the root, and advances committed generation only after success.

##### Statement understanding

Fsyncing children before the root and the directory after replacement establishes the crash-ordering proof.

<!-- journey-file: src/minilucene/__init__.py -->
#### Package, fixture, and project support

These files only keep exports, test corpora, dependencies, and the runtime environment reproducible; they are supporting wiring rather than Lucene mechanism logic.

### Verification evidence

Run `uv run pytest -q $(cat journey/stages/15-atomic-commit/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Fsyncing children before the root and the directory after replacement establishes the crash-ordering proof.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 7](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/07-commit-atomicity.md)

## 中文

### 目标

实现原子 Commit 与重开，并能从可执行反例、运行时状态与关键语句解释其边界。

### 交付文件

- `src/minilucene/__init__.py`
- `src/minilucene/index/directory.py`
- `src/minilucene/reader.py`
- `src/minilucene/writer.py`
- `tests/acceptance/test_phase2_storage_commit.py`
- `tests/contract/test_disk_search.py`
- `tests/storage/test_commit_recovery.py`

### 当前遇到的问题

Flushed Segment 虽已在磁盘，却要等 Manifest Root 发布后才能在 Restart 后可见。

### 测试契约

#### 先看会坏在哪里

Commit 测试在 Root Replacement 前和过程中失败、反复重开，并要求只看到完整上一代或下一代。

<!-- journey-file: tests/acceptance/test_phase2_storage_commit.py -->
<!-- journey-file: tests/contract/test_disk_search.py -->
<!-- journey-file: tests/storage/test_commit_recovery.py -->
#### 原子 Commit 与重开测试证据

##### 测试锁定什么

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

##### 如何构造反例

Commit 测试在 Root Replacement 前和过程中失败、反复重开，并要求只看到完整上一代或下一代。

##### 关键测试语句

```python
assert manifest.segment_generations == (1, 2)
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

##### 失败意味着什么

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Commit 是已持久 Segment Child 之上的发布协议；Reopen 严格从当前 Manifest 重建 Index。

### 为什么需要这个机制

Flushed Segment 虽已在磁盘，却要等 Manifest Root 发布后才能在 Restart 后可见。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Writer 先 Flush、准备全部引用 Child、写下一 Manifest、原子 Swap Root，并只在成功后推进 Committed Generation。

### 机制板块

<!-- journey-file: src/minilucene/index/directory.py -->
<!-- journey-file: src/minilucene/reader.py -->
<!-- journey-file: src/minilucene/writer.py -->
#### 原子 Commit 与重开机制

##### 是什么，为什么现在需要

Commit 是已持久 Segment Child 之上的发布协议；Reopen 严格从当前 Manifest 重建 Index。

##### 在运行时做什么

Writer 先 Flush、准备全部引用 Child、写下一 Manifest、原子 Swap Root，并只在成功后推进 Committed Generation。

##### 关键语句理解

Root 前 Fsync Child、Replacement 后 Fsync Directory，建立 Crash Ordering 证明。

<!-- journey-file: src/minilucene/__init__.py -->
#### 包、Fixture 与工程支撑

这些文件只保持包导出、测试语料、依赖与运行环境可复现，不把支撑接线误讲成 Lucene 机制。

### 验证证据

运行 `uv run pytest -q $(cat journey/stages/15-atomic-commit/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

Root 前 Fsync Child、Replacement 后 Fsync Directory，建立 Crash Ordering 证明。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 7 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/07-commit-atomicity.md)

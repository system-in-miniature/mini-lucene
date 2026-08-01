# Stage 14 · Writer flush / Writer Flush

<!-- journey: chapter=5 tests_added=1 -->

## English

### Goal

Build writer flush and explain its boundary from an executable counterexample, runtime state, and the critical statement.

### Deliverable files

- `src/minilucene/index/directory.py`
- `src/minilucene/index/memory.py`
- `src/minilucene/writer.py`
- `tests/storage/test_writer_flush.py`

### The problem at this point

Buffered documents are searchable nowhere and durable nowhere until one operation freezes them into a segment.

### Test contract

#### See the failure first

Tests cross document and byte thresholds, inject publication failure, and verify a failed flush keeps the buffer retryable.

<!-- journey-file: tests/storage/test_writer_flush.py -->
#### Writer flush test evidence

##### What this test locks

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

##### How it constructs the counterexample

Tests cross document and byte thresholds, inject publication failure, and verify a failed flush keeps the buffer retryable.

##### Key test statement

```python
assert segment.generation == 1
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

##### What a failure means

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

Flush converts the current mutable RAM buffer into one immutable segment without publishing a commit or a new reader view.

### Why this mechanism is necessary

Buffered documents are searchable nowhere and durable nowhere until one operation freezes them into a segment. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

The writer swaps or snapshots its buffer, builds an image, publishes the segment, then records it as uncommitted only after success.

### Mechanism blocks

<!-- journey-file: src/minilucene/index/directory.py -->
<!-- journey-file: src/minilucene/index/memory.py -->
<!-- journey-file: src/minilucene/writer.py -->
#### Writer flush mechanism

##### What it is and why it appears

Flush converts the current mutable RAM buffer into one immutable segment without publishing a commit or a new reader view.

##### Runtime role

The writer swaps or snapshots its buffer, builds an image, publishes the segment, then records it as uncommitted only after success.

##### Statement understanding

Clearing the buffer after publication preserves retry safety: failure leaves the same documents available for another flush.



### Verification evidence

Run `uv run pytest -q $(cat journey/stages/14-writer-flush/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Clearing the buffer after publication preserves retry safety: failure leaves the same documents available for another flush.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 5](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/05-segments-nrt.md)

## 中文

### 目标

实现Writer Flush，并能从可执行反例、运行时状态与关键语句解释其边界。

### 交付文件

- `src/minilucene/index/directory.py`
- `src/minilucene/index/memory.py`
- `src/minilucene/writer.py`
- `tests/storage/test_writer_flush.py`

### 当前遇到的问题

Buffered Document 在被一次操作冻结成 Segment 前，既不可搜索也不持久。

### 测试契约

#### 先看会坏在哪里

测试跨越 Document/Byte Threshold、注入 Publication Failure，并验证失败 Flush 保持 Buffer 可重试。

<!-- journey-file: tests/storage/test_writer_flush.py -->
#### Writer Flush测试证据

##### 测试锁定什么

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

##### 如何构造反例

测试跨越 Document/Byte Threshold、注入 Publication Failure，并验证失败 Flush 保持 Buffer 可重试。

##### 关键测试语句

```python
assert segment.generation == 1
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

##### 失败意味着什么

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Flush 把当前 Mutable RAM Buffer 转成一个 Immutable Segment，但不发布 Commit 或新 Reader View。

### 为什么需要这个机制

Buffered Document 在被一次操作冻结成 Segment 前，既不可搜索也不持久。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Writer Swap 或 Snapshot 当前 Buffer、构建 Image、发布 Segment，并且只在成功后记录为 Uncommitted。

### 机制板块

<!-- journey-file: src/minilucene/index/directory.py -->
<!-- journey-file: src/minilucene/index/memory.py -->
<!-- journey-file: src/minilucene/writer.py -->
#### Writer Flush机制

##### 是什么，为什么现在需要

Flush 把当前 Mutable RAM Buffer 转成一个 Immutable Segment，但不发布 Commit 或新 Reader View。

##### 在运行时做什么

Writer Swap 或 Snapshot 当前 Buffer、构建 Image、发布 Segment，并且只在成功后记录为 Uncommitted。

##### 关键语句理解

只在发布后清空 Buffer 保持 Retry Safety：失败时同一批 Document 仍可再次 Flush。



### 验证证据

运行 `uv run pytest -q $(cat journey/stages/14-writer-flush/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

只在发布后清空 Buffer 保持 Retry Safety：失败时同一批 Document 仍可再次 Flush。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 5 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/05-segments-nrt.md)

# Stage 10 · Educational segment codec / 教学用 Segment Codec

<!-- journey: chapter=4 tests_added=1 -->

## English

### Goal

Build educational segment codec and explain its boundary from an executable counterexample, runtime state, and the critical statement.

### Deliverable files

- `src/minilucene/storage/codec.py`
- `tests/unit/storage/test_segment_codec.py`

### The problem at this point

A logical image is not durable until every table has an explicit binary layout and cross-file consistency checks.

### Test contract

#### See the failure first

Codec tests corrupt lengths, term order, doc deltas, positions, and trailing bytes across the four segment files.

<!-- journey-file: tests/unit/storage/test_segment_codec.py -->
#### Educational segment codec test evidence

##### What this test locks

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

##### How it constructs the counterexample

Codec tests corrupt lengths, term order, doc deltas, positions, and trailing bytes across the four segment files.

##### Key test statement

```python
assert first == second
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

##### What a failure means

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

The codec splits terms, postings, stored fields, and norms into bounded canonical frames while preserving one shared document space.

### Why this mechanism is necessary

A logical image is not durable until every table has an explicit binary layout and cross-file consistency checks. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

Encode orders tables and delta-encodes monotonic IDs; decode validates headers, counts, bounds, ordering, and full input consumption.

### Mechanism blocks

<!-- journey-file: src/minilucene/storage/codec.py -->
#### Educational segment codec mechanism

##### What it is and why it appears

The codec splits terms, postings, stored fields, and norms into bounded canonical frames while preserving one shared document space.

##### Runtime role

Encode orders tables and delta-encodes monotonic IDs; decode validates headers, counts, bounds, ordering, and full input consumption.

##### Statement understanding

Rejecting trailing or non-canonical bytes makes one logical image map to one accepted representation, simplifying integrity evidence.



### Verification evidence

Run `uv run pytest -q $(cat journey/stages/10-segment-codec/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Rejecting trailing or non-canonical bytes makes one logical image map to one accepted representation, simplifying integrity evidence.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 4](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/04-codec.md)

## 中文

### 目标

实现教学用 Segment Codec，并能从可执行反例、运行时状态与关键语句解释其边界。

### 交付文件

- `src/minilucene/storage/codec.py`
- `tests/unit/storage/test_segment_codec.py`

### 当前遇到的问题

逻辑 Image 只有在每张表具备显式二进制布局与跨文件一致性检查后才可持久。

### 测试契约

#### 先看会坏在哪里

Codec 测试破坏四个 Segment File 中的 Length、Term Order、Doc Delta、Position 与尾随字节。

<!-- journey-file: tests/unit/storage/test_segment_codec.py -->
#### 教学用 Segment Codec测试证据

##### 测试锁定什么

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

##### 如何构造反例

Codec 测试破坏四个 Segment File 中的 Length、Term Order、Doc Delta、Position 与尾随字节。

##### 关键测试语句

```python
assert first == second
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

##### 失败意味着什么

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Codec 把 Term、Posting、Stored Field 与 Norm 拆成有界 Canonical Frame，同时保留共享 Document Space。

### 为什么需要这个机制

逻辑 Image 只有在每张表具备显式二进制布局与跨文件一致性检查后才可持久。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Encode 排序 Table 并 Delta Encode 单调 ID；Decode 校验 Header、Count、Bound、Order 与完整输入消费。

### 机制板块

<!-- journey-file: src/minilucene/storage/codec.py -->
#### 教学用 Segment Codec机制

##### 是什么，为什么现在需要

Codec 把 Term、Posting、Stored Field 与 Norm 拆成有界 Canonical Frame，同时保留共享 Document Space。

##### 在运行时做什么

Encode 排序 Table 并 Delta Encode 单调 ID；Decode 校验 Header、Count、Bound、Order 与完整输入消费。

##### 关键语句理解

拒绝尾随或非 Canonical Byte，使一个逻辑 Image 只对应一种可接受表示，简化 Integrity Evidence。



### 验证证据

运行 `uv run pytest -q $(cat journey/stages/10-segment-codec/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

拒绝尾随或非 Canonical Byte，使一个逻辑 Image 只对应一种可接受表示，简化 Integrity Evidence。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 4 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/04-codec.md)

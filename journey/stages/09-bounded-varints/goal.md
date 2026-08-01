# Stage 09 · Bounded varint primitives / 有界 Varint 原语

<!-- journey: chapter=4 tests_added=1 -->

## English

### Goal

Build bounded varint primitives and explain its boundary from an executable counterexample, runtime state, and the critical statement.

### Deliverable files

- `src/minilucene/storage/varint.py`
- `tests/unit/storage/test_varint.py`

### The problem at this point

A compact integer encoding becomes unsafe if truncation, overflow, signedness, or non-canonical forms are implicit.

### Test contract

#### See the failure first

The suite feeds truncated, overlong, negative, and non-canonical encodings, including boolean values that masquerade as integers.

<!-- journey-file: tests/unit/storage/test_varint.py -->
#### Bounded varint primitives test evidence

##### What this test locks

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

##### How it constructs the counterexample

The suite feeds truncated, overlong, negative, and non-canonical encodings, including boolean values that masquerade as integers.

##### Key test statement

```python
assert decode_uvarint(encoded, 0) == (value, len(encoded))
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

##### What a failure means

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

Unsigned varints encode small non-negative integers in continuation bytes under an explicit maximum bit width.

### Why this mechanism is necessary

A compact integer encoding becomes unsafe if truncation, overflow, signedness, or non-canonical forms are implicit. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

Encoding rejects invalid Python values and emits a canonical byte sequence; decoding counts bytes and bits before returning a value.

### Mechanism blocks

<!-- journey-file: src/minilucene/storage/varint.py -->
#### Bounded varint primitives mechanism

##### What it is and why it appears

Unsigned varints encode small non-negative integers in continuation bytes under an explicit maximum bit width.

##### Runtime role

Encoding rejects invalid Python values and emits a canonical byte sequence; decoding counts bytes and bits before returning a value.

##### Statement understanding

The byte-count bound turns malicious continuation bytes into a typed failure instead of an unbounded loop or oversized integer.



### Verification evidence

Run `uv run pytest -q $(cat journey/stages/09-bounded-varints/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

The byte-count bound turns malicious continuation bytes into a typed failure instead of an unbounded loop or oversized integer.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 4](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/04-codec.md)

## 中文

### 目标

实现有界 Varint 原语，并能从可执行反例、运行时状态与关键语句解释其边界。

### 交付文件

- `src/minilucene/storage/varint.py`
- `tests/unit/storage/test_varint.py`

### 当前遇到的问题

若截断、Overflow、Signedness 或非 Canonical Form 隐含不明，紧凑整数编码就不安全。

### 测试契约

#### 先看会坏在哪里

测试输入截断、过长、负数与非 Canonical Encoding，并包含伪装成 Integer 的 Boolean。

<!-- journey-file: tests/unit/storage/test_varint.py -->
#### 有界 Varint 原语测试证据

##### 测试锁定什么

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

##### 如何构造反例

测试输入截断、过长、负数与非 Canonical Encoding，并包含伪装成 Integer 的 Boolean。

##### 关键测试语句

```python
assert decode_uvarint(encoded, 0) == (value, len(encoded))
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

##### 失败意味着什么

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Unsigned Varint 在显式最大 Bit Width 下，用 Continuation Byte 编码小型非负整数。

### 为什么需要这个机制

若截断、Overflow、Signedness 或非 Canonical Form 隐含不明，紧凑整数编码就不安全。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Encoding 拒绝非法 Python Value 并输出 Canonical Byte Sequence；Decoding 在返回前统计 Byte 与 Bit。

### 机制板块

<!-- journey-file: src/minilucene/storage/varint.py -->
#### 有界 Varint 原语机制

##### 是什么，为什么现在需要

Unsigned Varint 在显式最大 Bit Width 下，用 Continuation Byte 编码小型非负整数。

##### 在运行时做什么

Encoding 拒绝非法 Python Value 并输出 Canonical Byte Sequence；Decoding 在返回前统计 Byte 与 Bit。

##### 关键语句理解

Byte Count Bound 把恶意 Continuation Byte 变成类型化失败，而非无限循环或超大整数。



### 验证证据

运行 `uv run pytest -q $(cat journey/stages/09-bounded-varints/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

Byte Count Bound 把恶意 Continuation Byte 变成类型化失败，而非无限循环或超大整数。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 4 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/04-codec.md)

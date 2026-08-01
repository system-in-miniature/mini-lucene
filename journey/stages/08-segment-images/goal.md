# Stage 08 · Immutable segment images / 不可变 Segment Image

<!-- journey: chapter=4 tests_added=1 -->

## English

### Goal

Build immutable segment images and explain its boundary from an executable counterexample, runtime state, and the critical statement.

### Deliverable files

- `src/minilucene/storage/__init__.py`
- `src/minilucene/storage/image.py`
- `tests/unit/storage/test_segment_image.py`

### The problem at this point

The in-memory segment needs a canonical value object before a disk codec can preserve it exactly.

### Test contract

#### See the failure first

Round-trip and validation tests construct mismatched doc counts, postings, norms, and stored fields.

<!-- journey-file: tests/unit/storage/test_segment_image.py -->
#### Immutable segment images test evidence

##### What this test locks

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

##### How it constructs the counterexample

Round-trip and validation tests construct mismatched doc counts, postings, norms, and stored fields.

##### Key test statement

```python
assert image.max_doc == 1
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

##### What a failure means

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

A SegmentImage is the complete immutable logical payload, independent of file layout and publication protocol.

### Why this mechanism is necessary

The in-memory segment needs a canonical value object before a disk codec can preserve it exactly. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

Builders normalize maps and tuples, validate cross-table counts and doc IDs, and expose one deterministic image to codecs.

### Mechanism blocks

<!-- journey-file: src/minilucene/storage/image.py -->
#### Immutable segment images mechanism

##### What it is and why it appears

A SegmentImage is the complete immutable logical payload, independent of file layout and publication protocol.

##### Runtime role

Builders normalize maps and tuples, validate cross-table counts and doc IDs, and expose one deterministic image to codecs.

##### Statement understanding

Separating logical image from bytes lets format validation and filesystem atomicity evolve without changing search semantics.

<!-- journey-file: src/minilucene/storage/__init__.py -->
#### Package, fixture, and project support

These files only keep exports, test corpora, dependencies, and the runtime environment reproducible; they are supporting wiring rather than Lucene mechanism logic.

### Verification evidence

Run `uv run pytest -q $(cat journey/stages/08-segment-images/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Separating logical image from bytes lets format validation and filesystem atomicity evolve without changing search semantics.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 4](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/04-codec.md)

## 中文

### 目标

实现不可变 Segment Image，并能从可执行反例、运行时状态与关键语句解释其边界。

### 交付文件

- `src/minilucene/storage/__init__.py`
- `src/minilucene/storage/image.py`
- `tests/unit/storage/test_segment_image.py`

### 当前遇到的问题

内存 Segment 在交给磁盘 Codec 前，需要一个可被精确保留的 Canonical Value Object。

### 测试契约

#### 先看会坏在哪里

Round-trip 与 Validation 测试构造不一致的 Doc Count、Posting、Norm 与 Stored Field。

<!-- journey-file: tests/unit/storage/test_segment_image.py -->
#### 不可变 Segment Image测试证据

##### 测试锁定什么

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

##### 如何构造反例

Round-trip 与 Validation 测试构造不一致的 Doc Count、Posting、Norm 与 Stored Field。

##### 关键测试语句

```python
assert image.max_doc == 1
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

##### 失败意味着什么

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

SegmentImage 是完整不可变逻辑 Payload，独立于文件布局与发布协议。

### 为什么需要这个机制

内存 Segment 在交给磁盘 Codec 前，需要一个可被精确保留的 Canonical Value Object。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Builder 归一化 Map 与 Tuple，校验跨表 Count 与 Doc ID，再向 Codec 暴露唯一确定 Image。

### 机制板块

<!-- journey-file: src/minilucene/storage/image.py -->
#### 不可变 Segment Image机制

##### 是什么，为什么现在需要

SegmentImage 是完整不可变逻辑 Payload，独立于文件布局与发布协议。

##### 在运行时做什么

Builder 归一化 Map 与 Tuple，校验跨表 Count 与 Doc ID，再向 Codec 暴露唯一确定 Image。

##### 关键语句理解

把逻辑 Image 与字节分离，让格式校验和文件系统原子性可以演进而不改变 Search 语义。

<!-- journey-file: src/minilucene/storage/__init__.py -->
#### 包、Fixture 与工程支撑

这些文件只保持包导出、测试语料、依赖与运行环境可复现，不把支撑接线误讲成 Lucene 机制。

### 验证证据

运行 `uv run pytest -q $(cat journey/stages/08-segment-images/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

把逻辑 Image 与字节分离，让格式校验和文件系统原子性可以演进而不改变 Search 语义。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 4 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/04-codec.md)

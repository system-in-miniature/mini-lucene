# Stage 16 · Point-in-time reader snapshots / 时间点 Reader Snapshot

<!-- journey: chapter=5 tests_added=1 -->

## English

### Goal

Build point-in-time reader snapshots and explain its boundary from an executable counterexample, runtime state, and the critical statement.

### Deliverable files

- `src/minilucene/errors.py`
- `src/minilucene/index/directory.py`
- `src/minilucene/reader.py`
- `src/minilucene/snapshot.py`
- `tests/nrt/test_reader_snapshot.py`

### The problem at this point

A reader that follows writer mutation in place cannot offer stable results across refresh, delete, or merge.

### Test contract

#### See the failure first

Tests open an old reader, publish newer state, and prove the old reader's segments, live docs, statistics, and hits do not change.

<!-- journey-file: tests/nrt/test_reader_snapshot.py -->
#### Point-in-time reader snapshots test evidence

##### What this test locks

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

##### How it constructs the counterexample

Tests open an old reader, publish newer state, and prove the old reader's segments, live docs, statistics, and hits do not change.

##### Key test statement

```python
assert old_reader.max_doc == 1
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

##### What a failure means

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

A reader snapshot freezes segment identities and visibility metadata at open time and owns references to those immutable resources.

### Why this mechanism is necessary

A reader that follows writer mutation in place cannot offer stable results across refresh, delete, or merge. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

Opening captures the current publication view; search reads only captured objects; closing releases ownership without consulting later writer state.

### Mechanism blocks

<!-- journey-file: src/minilucene/errors.py -->
<!-- journey-file: src/minilucene/index/directory.py -->
<!-- journey-file: src/minilucene/reader.py -->
<!-- journey-file: src/minilucene/snapshot.py -->
#### Point-in-time reader snapshots mechanism

##### What it is and why it appears

A reader snapshot freezes segment identities and visibility metadata at open time and owns references to those immutable resources.

##### Runtime role

Opening captures the current publication view; search reads only captured objects; closing releases ownership without consulting later writer state.

##### Statement understanding

Copying the reference set, not mutable contents, is enough because segments are immutable and visibility overlays are versioned.



### Verification evidence

Run `uv run pytest -q $(cat journey/stages/16-reader-snapshots/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Copying the reference set, not mutable contents, is enough because segments are immutable and visibility overlays are versioned.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 5](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/05-segments-nrt.md)

## 中文

### 目标

实现时间点 Reader Snapshot，并能从可执行反例、运行时状态与关键语句解释其边界。

### 交付文件

- `src/minilucene/errors.py`
- `src/minilucene/index/directory.py`
- `src/minilucene/reader.py`
- `src/minilucene/snapshot.py`
- `tests/nrt/test_reader_snapshot.py`

### 当前遇到的问题

若 Reader 原地跟随 Writer Mutation，就无法在 Refresh、Delete 或 Merge 间提供稳定结果。

### 测试契约

#### 先看会坏在哪里

测试打开旧 Reader、发布新状态，并证明旧 Reader 的 Segment、Live Docs、Statistic 与 Hit 不变。

<!-- journey-file: tests/nrt/test_reader_snapshot.py -->
#### 时间点 Reader Snapshot测试证据

##### 测试锁定什么

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

##### 如何构造反例

测试打开旧 Reader、发布新状态，并证明旧 Reader 的 Segment、Live Docs、Statistic 与 Hit 不变。

##### 关键测试语句

```python
assert old_reader.max_doc == 1
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

##### 失败意味着什么

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Reader Snapshot 在 Open 时冻结 Segment Identity 与 Visibility Metadata，并拥有这些不可变资源的引用。

### 为什么需要这个机制

若 Reader 原地跟随 Writer Mutation，就无法在 Refresh、Delete 或 Merge 间提供稳定结果。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Open 捕获当前 Publication View；Search 只读取捕获对象；Close 释放 Ownership 且不查询后续 Writer State。

### 机制板块

<!-- journey-file: src/minilucene/errors.py -->
<!-- journey-file: src/minilucene/index/directory.py -->
<!-- journey-file: src/minilucene/reader.py -->
<!-- journey-file: src/minilucene/snapshot.py -->
#### 时间点 Reader Snapshot机制

##### 是什么，为什么现在需要

Reader Snapshot 在 Open 时冻结 Segment Identity 与 Visibility Metadata，并拥有这些不可变资源的引用。

##### 在运行时做什么

Open 捕获当前 Publication View；Search 只读取捕获对象；Close 释放 Ownership 且不查询后续 Writer State。

##### 关键语句理解

因为 Segment 不可变且 Visibility Overlay 有版本，只复制 Reference Set 而非内容就足够。



### 验证证据

运行 `uv run pytest -q $(cat journey/stages/16-reader-snapshots/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

因为 Segment 不可变且 Visibility Overlay 有版本，只复制 Reference Set 而非内容就足够。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 5 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/05-segments-nrt.md)

# Stage 18 · Immutable live-doc masks / 不可变 Live-doc Mask

<!-- journey: chapter=6 tests_added=2 -->

## English

### Goal

Build immutable live-doc masks and explain its boundary from an executable counterexample, runtime state, and the critical statement.

### Deliverable files

- `src/minilucene/storage/filesystem.py`
- `src/minilucene/storage/live_docs.py`
- `tests/storage/test_live_docs_commit.py`
- `tests/unit/storage/test_live_docs.py`

### The problem at this point

Immutable segment files cannot erase deleted documents in place without breaking old readers and checksums.

### Test contract

#### See the failure first

Tests flip bits across boundaries, corrupt generations, and retain old masks while new readers observe a newer deletion view.

<!-- journey-file: tests/storage/test_live_docs_commit.py -->
<!-- journey-file: tests/unit/storage/test_live_docs.py -->
#### Immutable live-doc masks test evidence

##### What this test locks

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

##### How it constructs the counterexample

Tests flip bits across boundaries, corrupt generations, and retain old masks while new readers observe a newer deletion view.

##### Key test statement

```python
assert published.path.name == "live_000001.bin"
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

##### What a failure means

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

A live-doc mask is a versioned immutable visibility overlay; stored/posting data stays unchanged while a bit decides whether a local doc is visible.

### Why this mechanism is necessary

Immutable segment files cannot erase deleted documents in place without breaking old readers and checksums. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

Mutation derives a new mask from the previous generation, writes and checksums it atomically, and publishes its generation in writer state.

### Mechanism blocks

<!-- journey-file: src/minilucene/storage/filesystem.py -->
<!-- journey-file: src/minilucene/storage/live_docs.py -->
#### Immutable live-doc masks mechanism

##### What it is and why it appears

A live-doc mask is a versioned immutable visibility overlay; stored/posting data stays unchanged while a bit decides whether a local doc is visible.

##### Runtime role

Mutation derives a new mask from the previous generation, writes and checksums it atomically, and publishes its generation in writer state.

##### Statement understanding

Publishing a new generation instead of editing bytes lets old snapshots retain their exact deletion view.



### Verification evidence

Run `uv run pytest -q $(cat journey/stages/18-live-doc-masks/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Publishing a new generation instead of editing bytes lets old snapshots retain their exact deletion view.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 6](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/06-deletes-updates.md)

## 中文

### 目标

实现不可变 Live-doc Mask，并能从可执行反例、运行时状态与关键语句解释其边界。

### 交付文件

- `src/minilucene/storage/filesystem.py`
- `src/minilucene/storage/live_docs.py`
- `tests/storage/test_live_docs_commit.py`
- `tests/unit/storage/test_live_docs.py`

### 当前遇到的问题

不可变 Segment File 无法原地擦除删除 Document，否则会破坏旧 Reader 与 Checksum。

### 测试契约

#### 先看会坏在哪里

测试跨边界翻转 Bit、损坏 Generation，并让旧 Mask 保留而新 Reader 观察更新删除视图。

<!-- journey-file: tests/storage/test_live_docs_commit.py -->
<!-- journey-file: tests/unit/storage/test_live_docs.py -->
#### 不可变 Live-doc Mask测试证据

##### 测试锁定什么

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

##### 如何构造反例

测试跨边界翻转 Bit、损坏 Generation，并让旧 Mask 保留而新 Reader 观察更新删除视图。

##### 关键测试语句

```python
assert published.path.name == "live_000001.bin"
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

##### 失败意味着什么

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Live-doc Mask 是有版本的不可变 Visibility Overlay；Stored/Posting Data 不变，由 Bit 决定 Local Doc 是否可见。

### 为什么需要这个机制

不可变 Segment File 无法原地擦除删除 Document，否则会破坏旧 Reader 与 Checksum。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Mutation 从前一代派生新 Mask、原子写入并校验，再在 Writer State 发布其 Generation。

### 机制板块

<!-- journey-file: src/minilucene/storage/filesystem.py -->
<!-- journey-file: src/minilucene/storage/live_docs.py -->
#### 不可变 Live-doc Mask机制

##### 是什么，为什么现在需要

Live-doc Mask 是有版本的不可变 Visibility Overlay；Stored/Posting Data 不变，由 Bit 决定 Local Doc 是否可见。

##### 在运行时做什么

Mutation 从前一代派生新 Mask、原子写入并校验，再在 Writer State 发布其 Generation。

##### 关键语句理解

发布新 Generation 而非修改字节，让旧 Snapshot 保留准确的删除视图。



### 验证证据

运行 `uv run pytest -q $(cat journey/stages/18-live-doc-masks/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

发布新 Generation 而非修改字节，让旧 Snapshot 保留准确的删除视图。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 6 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/06-deletes-updates.md)

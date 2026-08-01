# Stage 22 · Segment ownership and close / Segment 所有权与 Close

<!-- journey: chapter=10 tests_added=3 -->

## English

### Goal

Build segment ownership and close and explain its boundary from an executable counterexample, runtime state, and the critical statement.

### Deliverable files

- `src/minilucene/errors.py`
- `src/minilucene/index/directory.py`
- `src/minilucene/reader.py`
- `src/minilucene/storage/registry.py`
- `src/minilucene/writer.py`
- `tests/acceptance/test_phase3_nrt_mutation.py`
- `tests/nrt/test_close_lifecycle.py`
- `tests/nrt/test_segment_ownership.py`

### The problem at this point

Obsolete files cannot be deleted merely because the writer stopped referencing them; readers may still own snapshots.

### Test contract

#### See the failure first

The suite keeps readers across merge and close, opens owner zero, repeats cleanup, and exercises calls after writer or reader close.

<!-- journey-file: tests/acceptance/test_phase3_nrt_mutation.py -->
<!-- journey-file: tests/nrt/test_close_lifecycle.py -->
<!-- journey-file: tests/nrt/test_segment_ownership.py -->
#### Segment ownership and close test evidence

##### What this test locks

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

##### How it constructs the counterexample

The suite keeps readers across merge and close, opens owner zero, repeats cleanup, and exercises calls after writer or reader close.

##### Key test statement

```python
assert ids(old_reader, "gamma") == ()
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

##### What a failure means

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

An ownership registry tracks explicit reader/writer references. Obsolete means not current; collectible means obsolete with owner count zero.

### Why this mechanism is necessary

Obsolete files cannot be deleted merely because the writer stopped referencing them; readers may still own snapshots. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

Opening and closing readers acquire/release segment generations; writer swaps mark inputs obsolete; cleanup deletes only registry-approved generations.

### Mechanism blocks

<!-- journey-file: src/minilucene/errors.py -->
<!-- journey-file: src/minilucene/index/directory.py -->
<!-- journey-file: src/minilucene/reader.py -->
<!-- journey-file: src/minilucene/storage/registry.py -->
<!-- journey-file: src/minilucene/writer.py -->
#### Segment ownership and close mechanism

##### What it is and why it appears

An ownership registry tracks explicit reader/writer references. Obsolete means not current; collectible means obsolete with owner count zero.

##### Runtime role

Opening and closing readers acquire/release segment generations; writer swaps mark inputs obsolete; cleanup deletes only registry-approved generations.

##### Statement understanding

The zero-owner transition, not writer preference, is the safe deletion boundary; close must release each ownership exactly once.



### Verification evidence

Run `uv run pytest -q $(cat journey/stages/22-ownership-close/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

The zero-owner transition, not writer preference, is the safe deletion boundary; close must release each ownership exactly once.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 10](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/10-merge-and-beyond.md)

## 中文

### 目标

实现Segment 所有权与 Close，并能从可执行反例、运行时状态与关键语句解释其边界。

### 交付文件

- `src/minilucene/errors.py`
- `src/minilucene/index/directory.py`
- `src/minilucene/reader.py`
- `src/minilucene/storage/registry.py`
- `src/minilucene/writer.py`
- `tests/acceptance/test_phase3_nrt_mutation.py`
- `tests/nrt/test_close_lifecycle.py`
- `tests/nrt/test_segment_ownership.py`

### 当前遇到的问题

不能因为 Writer 不再引用就删除 Obsolete File；Reader 可能仍拥有 Snapshot。

### 测试契约

#### 先看会坏在哪里

测试让 Reader 跨 Merge 与 Close 存活、打开 Owner Zero、重复 Cleanup，并在 Writer/Reader Close 后调用操作。

<!-- journey-file: tests/acceptance/test_phase3_nrt_mutation.py -->
<!-- journey-file: tests/nrt/test_close_lifecycle.py -->
<!-- journey-file: tests/nrt/test_segment_ownership.py -->
#### Segment 所有权与 Close测试证据

##### 测试锁定什么

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

##### 如何构造反例

测试让 Reader 跨 Merge 与 Close 存活、打开 Owner Zero、重复 Cleanup，并在 Writer/Reader Close 后调用操作。

##### 关键测试语句

```python
assert ids(old_reader, "gamma") == ()
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

##### 失败意味着什么

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Ownership Registry 跟踪显式 Reader/Writer Reference。Obsolete 表示非当前；Collectible 表示 Obsolete 且 Owner Count 为零。

### 为什么需要这个机制

不能因为 Writer 不再引用就删除 Obsolete File；Reader 可能仍拥有 Snapshot。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Reader Open/Close 获取或释放 Segment Generation；Writer Swap 标记 Input Obsolete；Cleanup 只删除 Registry 批准的 Generation。

### 机制板块

<!-- journey-file: src/minilucene/errors.py -->
<!-- journey-file: src/minilucene/index/directory.py -->
<!-- journey-file: src/minilucene/reader.py -->
<!-- journey-file: src/minilucene/storage/registry.py -->
<!-- journey-file: src/minilucene/writer.py -->
#### Segment 所有权与 Close机制

##### 是什么，为什么现在需要

Ownership Registry 跟踪显式 Reader/Writer Reference。Obsolete 表示非当前；Collectible 表示 Obsolete 且 Owner Count 为零。

##### 在运行时做什么

Reader Open/Close 获取或释放 Segment Generation；Writer Swap 标记 Input Obsolete；Cleanup 只删除 Registry 批准的 Generation。

##### 关键语句理解

Owner Count 归零而非 Writer 偏好才是安全删除边界；Close 必须恰好释放每份 Ownership 一次。



### 验证证据

运行 `uv run pytest -q $(cat journey/stages/22-ownership-close/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

Owner Count 归零而非 Writer 偏好才是安全删除边界；Close 必须恰好释放每份 Ownership 一次。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 10 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/10-merge-and-beyond.md)

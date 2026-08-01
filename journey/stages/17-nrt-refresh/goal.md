# Stage 17 · Near-real-time refresh / Near-real-time Refresh

<!-- journey: chapter=5 tests_added=1 -->

## English

### Goal

Build near-real-time refresh and explain its boundary from an executable counterexample, runtime state, and the critical statement.

### Deliverable files

- `src/minilucene/storage/segment_store.py`
- `src/minilucene/writer.py`
- `tests/nrt/test_refresh_visibility.py`

### The problem at this point

Waiting for a durable commit before every search makes newly flushed data unnecessarily invisible in the running process.

### Test contract

#### See the failure first

The contract distinguishes buffered, flushed, refreshed, committed, and reopened views across one document timeline.

<!-- journey-file: tests/nrt/test_refresh_visibility.py -->
#### Near-real-time refresh test evidence

##### What this test locks

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

##### How it constructs the counterexample

The contract distinguishes buffered, flushed, refreshed, committed, and reopened views across one document timeline.

##### Key test statement

```python
assert nrt.search(TermQuery("body", "visible"), top_k=10).total_hits == 1
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

##### What a failure means

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

Refresh publishes a new in-process snapshot from current segments; commit publishes the restart root. Near-real-time describes visibility, not weaker indexing.

### Why this mechanism is necessary

Waiting for a durable commit before every search makes newly flushed data unnecessarily invisible in the running process. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

Refresh flushes if needed, captures current segment/live-doc generations, and returns a reader without replacing the durable manifest.

### Mechanism blocks

<!-- journey-file: src/minilucene/storage/segment_store.py -->
<!-- journey-file: src/minilucene/writer.py -->
#### Near-real-time refresh mechanism

##### What it is and why it appears

Refresh publishes a new in-process snapshot from current segments; commit publishes the restart root. Near-real-time describes visibility, not weaker indexing.

##### Runtime role

Refresh flushes if needed, captures current segment/live-doc generations, and returns a reader without replacing the durable manifest.

##### Statement understanding

Keeping refresh and commit separate explains why a document can be searchable now yet absent after a crash and reopen.



### Verification evidence

Run `uv run pytest -q $(cat journey/stages/17-nrt-refresh/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Keeping refresh and commit separate explains why a document can be searchable now yet absent after a crash and reopen.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 5](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/05-segments-nrt.md)

## 中文

### 目标

实现Near-real-time Refresh，并能从可执行反例、运行时状态与关键语句解释其边界。

### 交付文件

- `src/minilucene/storage/segment_store.py`
- `src/minilucene/writer.py`
- `tests/nrt/test_refresh_visibility.py`

### 当前遇到的问题

每次搜索都等待 Durable Commit，会让已 Flush 新数据在进程内不必要地不可见。

### 测试契约

#### 先看会坏在哪里

契约沿一条 Document Timeline 区分 Buffered、Flushed、Refreshed、Committed 与 Reopened View。

<!-- journey-file: tests/nrt/test_refresh_visibility.py -->
#### Near-real-time Refresh测试证据

##### 测试锁定什么

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

##### 如何构造反例

契约沿一条 Document Timeline 区分 Buffered、Flushed、Refreshed、Committed 与 Reopened View。

##### 关键测试语句

```python
assert nrt.search(TermQuery("body", "visible"), top_k=10).total_hits == 1
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

##### 失败意味着什么

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Refresh 从当前 Segment 发布新的进程内 Snapshot；Commit 发布 Restart Root。Near-real-time 描述可见性而非较弱索引。

### 为什么需要这个机制

每次搜索都等待 Durable Commit，会让已 Flush 新数据在进程内不必要地不可见。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Refresh 必要时 Flush、捕获当前 Segment/Live-doc Generation，并返回 Reader，但不替换 Durable Manifest。

### 机制板块

<!-- journey-file: src/minilucene/storage/segment_store.py -->
<!-- journey-file: src/minilucene/writer.py -->
#### Near-real-time Refresh机制

##### 是什么，为什么现在需要

Refresh 从当前 Segment 发布新的进程内 Snapshot；Commit 发布 Restart Root。Near-real-time 描述可见性而非较弱索引。

##### 在运行时做什么

Refresh 必要时 Flush、捕获当前 Segment/Live-doc Generation，并返回 Reader，但不替换 Durable Manifest。

##### 关键语句理解

把 Refresh 与 Commit 分开，解释了 Document 为何现在可搜索，却可能在 Crash/Reopen 后消失。



### 验证证据

运行 `uv run pytest -q $(cat journey/stages/17-nrt-refresh/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

把 Refresh 与 Commit 分开，解释了 Document 为何现在可搜索，却可能在 Crash/Reopen 后消失。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 5 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/05-segments-nrt.md)

# Stage 19 · Delete by exact term / 按精确 Term 删除

<!-- journey: chapter=6 tests_added=1 -->

## English

### Goal

Build delete by exact term and explain its boundary from an executable counterexample, runtime state, and the critical statement.

### Deliverable files

- `src/minilucene/index/directory.py`
- `src/minilucene/index/memory.py`
- `src/minilucene/search/reader.py`
- `src/minilucene/storage/live_docs.py`
- `src/minilucene/writer.py`
- `tests/nrt/test_delete_by_term.py`

### The problem at this point

A deletion request must find matching live documents and publish visibility changes without mutating segment postings.

### Test contract

#### See the failure first

Tests delete across RAM and disk segments, repeat deletion, refresh old/new readers, and commit/reopen the result.

<!-- journey-file: tests/nrt/test_delete_by_term.py -->
#### Delete by exact term test evidence

##### What this test locks

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

##### How it constructs the counterexample

Tests delete across RAM and disk segments, repeat deletion, refresh old/new readers, and commit/reopen the result.

##### Key test statement

```python
assert writer.delete_by_term("id", "same") == 2
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

##### What a failure means

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

Delete-by-term is derive-then-swap: evaluate one exact indexed term against each current segment, then publish new live-doc generations.

### Why this mechanism is necessary

A deletion request must find matching live documents and publish visibility changes without mutating segment postings. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

The writer flushes pending additions when necessary, resolves matching local doc IDs, derives masks, and updates only successful segment generations.

### Mechanism blocks

<!-- journey-file: src/minilucene/index/directory.py -->
<!-- journey-file: src/minilucene/index/memory.py -->
<!-- journey-file: src/minilucene/search/reader.py -->
<!-- journey-file: src/minilucene/storage/live_docs.py -->
<!-- journey-file: src/minilucene/writer.py -->
#### Delete by exact term mechanism

##### What it is and why it appears

Delete-by-term is derive-then-swap: evaluate one exact indexed term against each current segment, then publish new live-doc generations.

##### Runtime role

The writer flushes pending additions when necessary, resolves matching local doc IDs, derives masks, and updates only successful segment generations.

##### Statement understanding

Exact-term deletion intentionally bypasses query parsing and analysis so the mutation key has one unambiguous indexed representation.



### Verification evidence

Run `uv run pytest -q $(cat journey/stages/19-delete-by-term/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Exact-term deletion intentionally bypasses query parsing and analysis so the mutation key has one unambiguous indexed representation.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 6](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/06-deletes-updates.md)

## 中文

### 目标

实现按精确 Term 删除，并能从可执行反例、运行时状态与关键语句解释其边界。

### 交付文件

- `src/minilucene/index/directory.py`
- `src/minilucene/index/memory.py`
- `src/minilucene/search/reader.py`
- `src/minilucene/storage/live_docs.py`
- `src/minilucene/writer.py`
- `tests/nrt/test_delete_by_term.py`

### 当前遇到的问题

删除请求必须找到匹配的 Live Document 并发布可见性变化，而不能修改 Segment Posting。

### 测试契约

#### 先看会坏在哪里

测试跨 RAM 与 Disk Segment 删除、重复删除、Refresh 新旧 Reader，并 Commit/Reopen 结果。

<!-- journey-file: tests/nrt/test_delete_by_term.py -->
#### 按精确 Term 删除测试证据

##### 测试锁定什么

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

##### 如何构造反例

测试跨 RAM 与 Disk Segment 删除、重复删除、Refresh 新旧 Reader，并 Commit/Reopen 结果。

##### 关键测试语句

```python
assert writer.delete_by_term("id", "same") == 2
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

##### 失败意味着什么

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Delete-by-term 是 Derive-then-swap：在每个当前 Segment 上求值一个精确 Indexed Term，再发布新 Live-doc Generation。

### 为什么需要这个机制

删除请求必须找到匹配的 Live Document 并发布可见性变化，而不能修改 Segment Posting。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Writer 必要时 Flush Pending Add、解析匹配 Local Doc ID、派生 Mask，并只更新成功的 Segment Generation。

### 机制板块

<!-- journey-file: src/minilucene/index/directory.py -->
<!-- journey-file: src/minilucene/index/memory.py -->
<!-- journey-file: src/minilucene/search/reader.py -->
<!-- journey-file: src/minilucene/storage/live_docs.py -->
<!-- journey-file: src/minilucene/writer.py -->
#### 按精确 Term 删除机制

##### 是什么，为什么现在需要

Delete-by-term 是 Derive-then-swap：在每个当前 Segment 上求值一个精确 Indexed Term，再发布新 Live-doc Generation。

##### 在运行时做什么

Writer 必要时 Flush Pending Add、解析匹配 Local Doc ID、派生 Mask，并只更新成功的 Segment Generation。

##### 关键语句理解

Exact-term Delete 有意绕过 Query Parsing 与 Analysis，使 Mutation Key 只有一种明确 Indexed Representation。



### 验证证据

运行 `uv run pytest -q $(cat journey/stages/19-delete-by-term/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

Exact-term Delete 有意绕过 Query Parsing 与 Analysis，使 Mutation Key 只有一种明确 Indexed Representation。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 6 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/06-deletes-updates.md)

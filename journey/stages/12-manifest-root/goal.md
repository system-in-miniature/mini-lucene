# Stage 12 · Manifest commit root / Manifest 提交根

<!-- journey: chapter=7 tests_added=1 -->

## English

### Goal

Build manifest commit root and explain its boundary from an executable counterexample, runtime state, and the critical statement.

### Deliverable files

- `src/minilucene/storage/manifest.py`
- `tests/storage/test_manifest_store.py`

### The problem at this point

A durable segment is not necessarily part of the committed index; restart needs one authoritative root.

### Test contract

#### See the failure first

Tests create orphan segments, corrupt candidate manifests, and interrupt root replacement to require old-root-or-new-root recovery.

<!-- journey-file: tests/storage/test_manifest_store.py -->
#### Manifest commit root test evidence

##### What this test locks

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

##### How it constructs the counterexample

Tests create orphan segments, corrupt candidate manifests, and interrupt root replacement to require old-root-or-new-root recovery.

##### Key test statement

```python
assert store.read() == created
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

##### What a failure means

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

The manifest names the committed segment generation and schema fingerprint. Its atomic replacement publishes the index root.

### Why this mechanism is necessary

A durable segment is not necessarily part of the committed index; restart needs one authoritative root. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

Commit writes and fsyncs a candidate manifest, replaces the root file, fsyncs the directory, and validates referenced children on reopen.

### Mechanism blocks

<!-- journey-file: src/minilucene/storage/manifest.py -->
#### Manifest commit root mechanism

##### What it is and why it appears

The manifest names the committed segment generation and schema fingerprint. Its atomic replacement publishes the index root.

##### Runtime role

Commit writes and fsyncs a candidate manifest, replaces the root file, fsyncs the directory, and validates referenced children on reopen.

##### Statement understanding

Readers follow only the published root, so unreferenced durable files remain orphans rather than becoming synthesized commits.



### Verification evidence

Run `uv run pytest -q $(cat journey/stages/12-manifest-root/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Readers follow only the published root, so unreferenced durable files remain orphans rather than becoming synthesized commits.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 7](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/07-commit-atomicity.md)

## 中文

### 目标

实现Manifest 提交根，并能从可执行反例、运行时状态与关键语句解释其边界。

### 交付文件

- `src/minilucene/storage/manifest.py`
- `tests/storage/test_manifest_store.py`

### 当前遇到的问题

已持久 Segment 不一定属于已提交 Index；Restart 需要唯一权威 Root。

### 测试契约

#### 先看会坏在哪里

测试创建 Orphan Segment、损坏 Candidate Manifest，并中断 Root Replacement，要求恢复结果只能是旧 Root 或新 Root。

<!-- journey-file: tests/storage/test_manifest_store.py -->
#### Manifest 提交根测试证据

##### 测试锁定什么

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

##### 如何构造反例

测试创建 Orphan Segment、损坏 Candidate Manifest，并中断 Root Replacement，要求恢复结果只能是旧 Root 或新 Root。

##### 关键测试语句

```python
assert store.read() == created
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

##### 失败意味着什么

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Manifest 命名已提交 Segment Generation 与 Schema Fingerprint；其原子替换发布 Index Root。

### 为什么需要这个机制

已持久 Segment 不一定属于已提交 Index；Restart 需要唯一权威 Root。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Commit 写并 Fsync Candidate Manifest、替换 Root File、Fsync Directory，并在重开时验证引用的 Child。

### 机制板块

<!-- journey-file: src/minilucene/storage/manifest.py -->
#### Manifest 提交根机制

##### 是什么，为什么现在需要

Manifest 命名已提交 Segment Generation 与 Schema Fingerprint；其原子替换发布 Index Root。

##### 在运行时做什么

Commit 写并 Fsync Candidate Manifest、替换 Root File、Fsync Directory，并在重开时验证引用的 Child。

##### 关键语句理解

Reader 只跟随已发布 Root，因此未引用的持久文件仍是 Orphan，不会变成拼接出的 Commit。



### 验证证据

运行 `uv run pytest -q $(cat journey/stages/12-manifest-root/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

Reader 只跟随已发布 Root，因此未引用的持久文件仍是 Orphan，不会变成拼接出的 Commit。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 7 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/07-commit-atomicity.md)

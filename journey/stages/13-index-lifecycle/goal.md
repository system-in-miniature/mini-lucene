# Stage 13 · Index lifecycle ownership / Index 生命周期所有权

<!-- journey: chapter=5 tests_added=1 -->

## English

### Goal

Build index lifecycle ownership and explain its boundary from an executable counterexample, runtime state, and the critical statement.

### Deliverable files

- `src/minilucene/__init__.py`
- `src/minilucene/errors.py`
- `src/minilucene/index/__init__.py`
- `src/minilucene/index/directory.py`
- `src/minilucene/schema.py`
- `src/minilucene/writer.py`
- `tests/contract/test_index_lifecycle.py`

### The problem at this point

Storage components exist, but no object yet owns schema identity, writer exclusivity, open/close state, and directory resources.

### Test contract

#### See the failure first

The contract opens conflicting writers, crosses schema fingerprints, uses closed handles, and repeats close operations.

<!-- journey-file: tests/contract/test_index_lifecycle.py -->
#### Index lifecycle ownership test evidence

##### What this test locks

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

##### How it constructs the counterexample

The contract opens conflicting writers, crosses schema fingerprints, uses closed handles, and repeats close operations.

##### Key test statement

```python
assert reopened.schema == schema
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

##### What a failure means

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

An IndexDirectory owns durable stores and writer leases; an IndexWriter owns buffered mutation and publication lifecycle.

### Why this mechanism is necessary

Storage components exist, but no object yet owns schema identity, writer exclusivity, open/close state, and directory resources. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

Open validates or establishes schema identity, grants one writer lease, and every public operation checks lifecycle state before mutation.

### Mechanism blocks

<!-- journey-file: src/minilucene/errors.py -->
<!-- journey-file: src/minilucene/index/directory.py -->
<!-- journey-file: src/minilucene/schema.py -->
<!-- journey-file: src/minilucene/writer.py -->
#### Index lifecycle ownership mechanism

##### What it is and why it appears

An IndexDirectory owns durable stores and writer leases; an IndexWriter owns buffered mutation and publication lifecycle.

##### Runtime role

Open validates or establishes schema identity, grants one writer lease, and every public operation checks lifecycle state before mutation.

##### Statement understanding

Central ownership turns use-after-close and competing writers into immediate typed errors rather than delayed disk corruption.

<!-- journey-file: src/minilucene/__init__.py -->
<!-- journey-file: src/minilucene/index/__init__.py -->
#### Package, fixture, and project support

These files only keep exports, test corpora, dependencies, and the runtime environment reproducible; they are supporting wiring rather than Lucene mechanism logic.

### Verification evidence

Run `uv run pytest -q $(cat journey/stages/13-index-lifecycle/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Central ownership turns use-after-close and competing writers into immediate typed errors rather than delayed disk corruption.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 5](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/05-segments-nrt.md)

## 中文

### 目标

实现Index 生命周期所有权，并能从可执行反例、运行时状态与关键语句解释其边界。

### 交付文件

- `src/minilucene/__init__.py`
- `src/minilucene/errors.py`
- `src/minilucene/index/__init__.py`
- `src/minilucene/index/directory.py`
- `src/minilucene/schema.py`
- `src/minilucene/writer.py`
- `tests/contract/test_index_lifecycle.py`

### 当前遇到的问题

存储组件已存在，但尚无对象统一拥有 Schema Identity、Writer Exclusivity、Open/Close State 与 Directory Resource。

### 测试契约

#### 先看会坏在哪里

契约打开冲突 Writer、跨 Schema Fingerprint、使用已关闭 Handle，并重复 Close。

<!-- journey-file: tests/contract/test_index_lifecycle.py -->
#### Index 生命周期所有权测试证据

##### 测试锁定什么

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

##### 如何构造反例

契约打开冲突 Writer、跨 Schema Fingerprint、使用已关闭 Handle，并重复 Close。

##### 关键测试语句

```python
assert reopened.schema == schema
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

##### 失败意味着什么

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

IndexDirectory 拥有 Durable Store 与 Writer Lease；IndexWriter 拥有 Buffered Mutation 与 Publication Lifecycle。

### 为什么需要这个机制

存储组件已存在，但尚无对象统一拥有 Schema Identity、Writer Exclusivity、Open/Close State 与 Directory Resource。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Open 校验或建立 Schema Identity、授予唯一 Writer Lease，并让每个 Public Operation 在 Mutation 前检查 Lifecycle State。

### 机制板块

<!-- journey-file: src/minilucene/errors.py -->
<!-- journey-file: src/minilucene/index/directory.py -->
<!-- journey-file: src/minilucene/schema.py -->
<!-- journey-file: src/minilucene/writer.py -->
#### Index 生命周期所有权机制

##### 是什么，为什么现在需要

IndexDirectory 拥有 Durable Store 与 Writer Lease；IndexWriter 拥有 Buffered Mutation 与 Publication Lifecycle。

##### 在运行时做什么

Open 校验或建立 Schema Identity、授予唯一 Writer Lease，并让每个 Public Operation 在 Mutation 前检查 Lifecycle State。

##### 关键语句理解

集中所有权把 Use-after-close 与竞争 Writer 变成立即类型错误，而非延迟磁盘损坏。

<!-- journey-file: src/minilucene/__init__.py -->
<!-- journey-file: src/minilucene/index/__init__.py -->
#### 包、Fixture 与工程支撑

这些文件只保持包导出、测试语料、依赖与运行环境可复现，不把支撑接线误讲成 Lucene 机制。

### 验证证据

运行 `uv run pytest -q $(cat journey/stages/13-index-lifecycle/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

集中所有权把 Use-after-close 与竞争 Writer 变成立即类型错误，而非延迟磁盘损坏。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 5 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/05-segments-nrt.md)

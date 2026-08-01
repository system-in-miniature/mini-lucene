# Stage 28 · CLI and domain closure / CLI 与领域闭环

<!-- journey: chapter=1 tests_added=5 -->

## English

### Goal

Build cli and domain closure and explain its boundary from an executable counterexample, runtime state, and the critical statement.

### Deliverable files

- `pyproject.toml`
- `src/minilucene/__init__.py`
- `src/minilucene/cli.py`
- `tests/acceptance/test_end_to_end.py`
- `tests/acceptance/test_failure_matrix.py`
- `tests/acceptance/test_owner_zero.py`
- `tests/contract/test_cli.py`
- `tests/test_public_surface.py`

### The problem at this point

The core mechanisms need one thin user path and combined failure evidence without duplicating indexing or search semantics.

### Test contract

#### See the failure first

End-to-end and failure matrices combine commit, reopen, delete, merge, bad input, closed handles, and CLI process behavior.

<!-- journey-file: tests/acceptance/test_end_to_end.py -->
<!-- journey-file: tests/acceptance/test_failure_matrix.py -->
<!-- journey-file: tests/acceptance/test_owner_zero.py -->
<!-- journey-file: tests/contract/test_cli.py -->
<!-- journey-file: tests/test_public_surface.py -->
#### CLI and domain closure test evidence

##### What this test locks

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

##### How it constructs the counterexample

End-to-end and failure matrices combine commit, reopen, delete, merge, bad input, closed handles, and CLI process behavior.

##### Key test statement

```python
assert _ids(initial) == ("1",)
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

##### What a failure means

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

The CLI is an adapter over the public API; domain closure means lifecycle, persistence, ranking, and failure contracts survive composition.

### Why this mechanism is necessary

The core mechanisms need one thin user path and combined failure evidence without duplicating indexing or search semantics. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

Commands parse bounded JSON arguments, open the same directory/writer/reader objects, call existing operations, serialize results, and preserve typed error exits.

### Mechanism blocks

<!-- journey-file: src/minilucene/cli.py -->
#### CLI and domain closure mechanism

##### What it is and why it appears

The CLI is an adapter over the public API; domain closure means lifecycle, persistence, ranking, and failure contracts survive composition.

##### Runtime role

Commands parse bounded JSON arguments, open the same directory/writer/reader objects, call existing operations, serialize results, and preserve typed error exits.

##### Statement understanding

An adapter may translate input and output but must not own alternate commit, query, scoring, or lifecycle rules.

<!-- journey-file: pyproject.toml -->
<!-- journey-file: src/minilucene/__init__.py -->
#### Package, fixture, and project support

These files only keep exports, test corpora, dependencies, and the runtime environment reproducible; they are supporting wiring rather than Lucene mechanism logic.

### Verification evidence

Run `uv run pytest -q $(cat journey/stages/28-cli-domain-closure/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

An adapter may translate input and output but must not own alternate commit, query, scoring, or lifecycle rules.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 1](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/01-getting-started.md)

## 中文

### 目标

实现CLI 与领域闭环，并能从可执行反例、运行时状态与关键语句解释其边界。

### 交付文件

- `pyproject.toml`
- `src/minilucene/__init__.py`
- `src/minilucene/cli.py`
- `tests/acceptance/test_end_to_end.py`
- `tests/acceptance/test_failure_matrix.py`
- `tests/acceptance/test_owner_zero.py`
- `tests/contract/test_cli.py`
- `tests/test_public_surface.py`

### 当前遇到的问题

核心机制需要一条轻量用户路径与组合失败证据，同时不能复制 Index/Search 语义。

### 测试契约

#### 先看会坏在哪里

End-to-end 与 Failure Matrix 组合 Commit、Reopen、Delete、Merge、Bad Input、Closed Handle 与 CLI Process 行为。

<!-- journey-file: tests/acceptance/test_end_to_end.py -->
<!-- journey-file: tests/acceptance/test_failure_matrix.py -->
<!-- journey-file: tests/acceptance/test_owner_zero.py -->
<!-- journey-file: tests/contract/test_cli.py -->
<!-- journey-file: tests/test_public_surface.py -->
#### CLI 与领域闭环测试证据

##### 测试锁定什么

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

##### 如何构造反例

End-to-end 与 Failure Matrix 组合 Commit、Reopen、Delete、Merge、Bad Input、Closed Handle 与 CLI Process 行为。

##### 关键测试语句

```python
assert _ids(initial) == ("1",)
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

##### 失败意味着什么

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

CLI 是 Public API 上的 Adapter；领域闭环意味着 Lifecycle、Persistence、Ranking 与 Failure Contract 经组合后仍成立。

### 为什么需要这个机制

核心机制需要一条轻量用户路径与组合失败证据，同时不能复制 Index/Search 语义。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Command 解析有界 JSON Argument、打开同一 Directory/Writer/Reader Object、调用已有 Operation、序列化结果并保留类型化错误退出。

### 机制板块

<!-- journey-file: src/minilucene/cli.py -->
#### CLI 与领域闭环机制

##### 是什么，为什么现在需要

CLI 是 Public API 上的 Adapter；领域闭环意味着 Lifecycle、Persistence、Ranking 与 Failure Contract 经组合后仍成立。

##### 在运行时做什么

Command 解析有界 JSON Argument、打开同一 Directory/Writer/Reader Object、调用已有 Operation、序列化结果并保留类型化错误退出。

##### 关键语句理解

Adapter 可以翻译 Input/Output，但不得拥有另一套 Commit、Query、Scoring 或 Lifecycle Rule。

<!-- journey-file: pyproject.toml -->
<!-- journey-file: src/minilucene/__init__.py -->
#### 包、Fixture 与工程支撑

这些文件只保持包导出、测试语料、依赖与运行环境可复现，不把支撑接线误讲成 Lucene 机制。

### 验证证据

运行 `uv run pytest -q $(cat journey/stages/28-cli-domain-closure/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

Adapter 可以翻译 Input/Output，但不得拥有另一套 Commit、Query、Scoring 或 Lifecycle Rule。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 1 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/01-getting-started.md)

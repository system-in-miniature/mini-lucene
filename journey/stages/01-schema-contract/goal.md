# Stage 01 · Field and document contract / 字段与文档契约

<!-- journey: chapter=1 tests_added=2 -->

## English

### Goal

Build field and document contract and explain its boundary from an executable counterexample, runtime state, and the critical statement.

### Deliverable files

- `pyproject.toml`
- `src/minilucene/__init__.py`
- `src/minilucene/document.py`
- `src/minilucene/schema.py`
- `tests/contract/test_schema.py`
- `tests/test_public_surface.py`
- `uv.lock`

### The problem at this point

An index cannot interpret arbitrary dictionaries without fixing field type, storage, indexing, and analyzer rules.

### Test contract

#### See the failure first

The contracts submit unknown fields, duplicate names, missing required values, and values of the wrong Python type.

<!-- journey-file: tests/contract/test_schema.py -->
<!-- journey-file: tests/test_public_surface.py -->
#### Field and document contract test evidence

##### What this test locks

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

##### How it constructs the counterexample

The contracts submit unknown fields, duplicate names, missing required values, and values of the wrong Python type.

##### Key test statement

```python
assert schema["id"].indexed and not schema["id"].tokenized
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

##### What a failure means

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

A schema is the closed interpretation contract; a Document is validated input, not yet an indexed representation.

### Why this mechanism is necessary

An index cannot interpret arbitrary dictionaries without fixing field type, storage, indexing, and analyzer rules. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

Validation resolves every field definition before analysis or storage and returns typed failures before state changes.

### Mechanism blocks

<!-- journey-file: src/minilucene/document.py -->
<!-- journey-file: src/minilucene/schema.py -->
#### Field and document contract mechanism

##### What it is and why it appears

A schema is the closed interpretation contract; a Document is validated input, not yet an indexed representation.

##### Runtime role

Validation resolves every field definition before analysis or storage and returns typed failures before state changes.

##### Statement understanding

Rejecting unknown and ill-typed values at the boundary prevents later codecs and scorers from guessing semantics.

<!-- journey-file: pyproject.toml -->
<!-- journey-file: src/minilucene/__init__.py -->
<!-- journey-file: uv.lock -->
#### Package, fixture, and project support

These files only keep exports, test corpora, dependencies, and the runtime environment reproducible; they are supporting wiring rather than Lucene mechanism logic.

### Verification evidence

Run `uv run pytest -q $(cat journey/stages/01-schema-contract/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Rejecting unknown and ill-typed values at the boundary prevents later codecs and scorers from guessing semantics.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 1](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/01-getting-started.md)

## 中文

### 目标

实现字段与文档契约，并能从可执行反例、运行时状态与关键语句解释其边界。

### 交付文件

- `pyproject.toml`
- `src/minilucene/__init__.py`
- `src/minilucene/document.py`
- `src/minilucene/schema.py`
- `tests/contract/test_schema.py`
- `tests/test_public_surface.py`
- `uv.lock`

### 当前遇到的问题

索引若不固定字段类型、存储、索引与 Analyzer 规则，就无法解释任意字典。

### 测试契约

#### 先看会坏在哪里

契约提交未知字段、重名字段、缺失必填值与错误 Python 类型。

<!-- journey-file: tests/contract/test_schema.py -->
<!-- journey-file: tests/test_public_surface.py -->
#### 字段与文档契约测试证据

##### 测试锁定什么

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

##### 如何构造反例

契约提交未知字段、重名字段、缺失必填值与错误 Python 类型。

##### 关键测试语句

```python
assert schema["id"].indexed and not schema["id"].tokenized
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

##### 失败意味着什么

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Schema 是封闭的解释契约；Document 是校验后的输入，还不是索引表示。

### 为什么需要这个机制

索引若不固定字段类型、存储、索引与 Analyzer 规则，就无法解释任意字典。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Validation 在 Analysis 或 Storage 前解析每个 Field Definition，并在状态变化前返回类型化失败。

### 机制板块

<!-- journey-file: src/minilucene/document.py -->
<!-- journey-file: src/minilucene/schema.py -->
#### 字段与文档契约机制

##### 是什么，为什么现在需要

Schema 是封闭的解释契约；Document 是校验后的输入，还不是索引表示。

##### 在运行时做什么

Validation 在 Analysis 或 Storage 前解析每个 Field Definition，并在状态变化前返回类型化失败。

##### 关键语句理解

在边界拒绝未知与错类型值，防止后续 Codec 与 Scorer 猜测语义。

<!-- journey-file: pyproject.toml -->
<!-- journey-file: src/minilucene/__init__.py -->
<!-- journey-file: uv.lock -->
#### 包、Fixture 与工程支撑

这些文件只保持包导出、测试语料、依赖与运行环境可复现，不把支撑接线误讲成 Lucene 机制。

### 验证证据

运行 `uv run pytest -q $(cat journey/stages/01-schema-contract/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

在边界拒绝未知与错类型值，防止后续 Codec 与 Scorer 猜测语义。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 1 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/01-getting-started.md)

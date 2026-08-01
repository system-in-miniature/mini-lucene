# Stage 02 · Positional analysis / 位置化文本分析

<!-- journey: chapter=2 tests_added=1 -->

## English

### Goal

Build positional analysis and explain its boundary from an executable counterexample, runtime state, and the critical statement.

### Deliverable files

- `src/minilucene/analysis/__init__.py`
- `src/minilucene/analysis/model.py`
- `src/minilucene/analysis/pipeline.py`
- `src/minilucene/analysis/standard.py`
- `tests/unit/analysis/test_pipeline.py`

### The problem at this point

Raw text cannot support term, phrase, or highlighting semantics until token attributes are stable.

### Test contract

#### See the failure first

The suite uses punctuation, stop words, position gaps, offsets, and invalid token ranges to expose lossy analyzers.

<!-- journey-file: tests/unit/analysis/test_pipeline.py -->
#### Positional analysis test evidence

##### What this test locks

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

##### How it constructs the counterexample

The suite uses punctuation, stop words, position gaps, offsets, and invalid token ranges to expose lossy analyzers.

##### Key test statement

```python
assert analyzer.analyze("Kafka AND Replicas") == (
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

##### What a failure means

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

A Token carries term text, position, and source offsets; an Analyzer is a deterministic pipeline over those attributes.

### Why this mechanism is necessary

Raw text cannot support term, phrase, or highlighting semantics until token attributes are stable. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

Character filtering and tokenization create evidence; filters normalize or remove tokens while preserving position and offset meaning.

### Mechanism blocks

<!-- journey-file: src/minilucene/analysis/model.py -->
<!-- journey-file: src/minilucene/analysis/pipeline.py -->
<!-- journey-file: src/minilucene/analysis/standard.py -->
#### Positional analysis mechanism

##### What it is and why it appears

A Token carries term text, position, and source offsets; an Analyzer is a deterministic pipeline over those attributes.

##### Runtime role

Character filtering and tokenization create evidence; filters normalize or remove tokens while preserving position and offset meaning.

##### Statement understanding

Position increments preserve phrase distance across removed tokens, while offsets preserve the original text span for highlighting.

<!-- journey-file: src/minilucene/analysis/__init__.py -->
#### Package, fixture, and project support

These files only keep exports, test corpora, dependencies, and the runtime environment reproducible; they are supporting wiring rather than Lucene mechanism logic.

### Verification evidence

Run `uv run pytest -q $(cat journey/stages/02-positional-analysis/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Position increments preserve phrase distance across removed tokens, while offsets preserve the original text span for highlighting.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 2](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/02-analysis.md)

## 中文

### 目标

实现位置化文本分析，并能从可执行反例、运行时状态与关键语句解释其边界。

### 交付文件

- `src/minilucene/analysis/__init__.py`
- `src/minilucene/analysis/model.py`
- `src/minilucene/analysis/pipeline.py`
- `src/minilucene/analysis/standard.py`
- `tests/unit/analysis/test_pipeline.py`

### 当前遇到的问题

原始文本只有形成稳定 Token 属性后，才能支持 Term、Phrase 与 Highlight 语义。

### 测试契约

#### 先看会坏在哪里

测试用标点、Stop Word、Position Gap、Offset 与非法 Token Range 暴露有损 Analyzer。

<!-- journey-file: tests/unit/analysis/test_pipeline.py -->
#### 位置化文本分析测试证据

##### 测试锁定什么

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

##### 如何构造反例

测试用标点、Stop Word、Position Gap、Offset 与非法 Token Range 暴露有损 Analyzer。

##### 关键测试语句

```python
assert analyzer.analyze("Kafka AND Replicas") == (
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

##### 失败意味着什么

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Token 携带 Term、Position 与源 Offset；Analyzer 是这些属性上的确定性 Pipeline。

### 为什么需要这个机制

原始文本只有形成稳定 Token 属性后，才能支持 Term、Phrase 与 Highlight 语义。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

字符过滤与 Tokenization 产生证据；Filter 在保留 Position 与 Offset 含义的前提下归一化或移除 Token。

### 机制板块

<!-- journey-file: src/minilucene/analysis/model.py -->
<!-- journey-file: src/minilucene/analysis/pipeline.py -->
<!-- journey-file: src/minilucene/analysis/standard.py -->
#### 位置化文本分析机制

##### 是什么，为什么现在需要

Token 携带 Term、Position 与源 Offset；Analyzer 是这些属性上的确定性 Pipeline。

##### 在运行时做什么

字符过滤与 Tokenization 产生证据；Filter 在保留 Position 与 Offset 含义的前提下归一化或移除 Token。

##### 关键语句理解

Position Increment 保留被移除 Token 造成的 Phrase 距离，Offset 保留 Highlight 所需的原文范围。

<!-- journey-file: src/minilucene/analysis/__init__.py -->
#### 包、Fixture 与工程支撑

这些文件只保持包导出、测试语料、依赖与运行环境可复现，不把支撑接线误讲成 Lucene 机制。

### 验证证据

运行 `uv run pytest -q $(cat journey/stages/02-positional-analysis/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

Position Increment 保留被移除 Token 造成的 Phrase 距离，Offset 保留 Highlight 所需的原文范围。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 2 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/02-analysis.md)

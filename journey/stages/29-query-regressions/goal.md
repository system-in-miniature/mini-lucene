# Stage 29 · Query and token regressions / Query 与 Token 回归

<!-- journey: chapter=9 tests_added=4 -->

## English

### Goal

Build query and token regressions and explain its boundary from an executable counterexample, runtime state, and the critical statement.

### Deliverable files

- `src/minilucene/analysis/__init__.py`
- `src/minilucene/analysis/model.py`
- `src/minilucene/analysis/pipeline.py`
- `src/minilucene/analysis/standard.py`
- `src/minilucene/query_parser/lexer.py`
- `src/minilucene/query_parser/parser.py`
- `src/minilucene/reader.py`
- `src/minilucene/search/reader.py`
- `src/minilucene/storage/codec.py`
- `src/minilucene/storage/manifest.py`
- `src/minilucene/writer.py`
- `tests/acceptance/test_phase1_retrieval_kernel.py`
- `tests/unit/analysis/test_pipeline.py`
- `tests/unit/query_parser/test_lexer.py`
- `tests/unit/query_parser/test_parser.py`

### The problem at this point

Single-token quoted queries, hyphenated terms, invalid token attributes, zero-length statistics, and boolean varints expose gaps between documented and executable contracts.

### Test contract

#### See the failure first

Regression tests preserve exact strings that the earlier lexer/parser accepted incorrectly and construct invalid Token and primitive values directly.

<!-- journey-file: tests/acceptance/test_phase1_retrieval_kernel.py -->
<!-- journey-file: tests/unit/analysis/test_pipeline.py -->
<!-- journey-file: tests/unit/query_parser/test_lexer.py -->
<!-- journey-file: tests/unit/query_parser/test_parser.py -->
#### Query and token regressions test evidence

##### What this test locks

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

##### How it constructs the counterexample

Regression tests preserve exact strings that the earlier lexer/parser accepted incorrectly and construct invalid Token and primitive values directly.

##### Key test statement

```python
assert result.total_hits == 1
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

##### What a failure means

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

A regression Stage turns discovered counterexamples into permanent boundaries across parsing, analysis, scoring, and codec primitives.

### Why this mechanism is necessary

Single-token quoted queries, hyphenated terms, invalid token attributes, zero-length statistics, and boolean varints expose gaps between documented and executable contracts. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

The parser recognizes one-term phrases without collapsing quote evidence; the lexer keeps hyphens inside terms; constructors and primitives validate values at creation.

### Mechanism blocks

<!-- journey-file: src/minilucene/analysis/model.py -->
<!-- journey-file: src/minilucene/analysis/pipeline.py -->
<!-- journey-file: src/minilucene/analysis/standard.py -->
<!-- journey-file: src/minilucene/query_parser/lexer.py -->
<!-- journey-file: src/minilucene/query_parser/parser.py -->
<!-- journey-file: src/minilucene/reader.py -->
<!-- journey-file: src/minilucene/search/reader.py -->
<!-- journey-file: src/minilucene/storage/codec.py -->
<!-- journey-file: src/minilucene/storage/manifest.py -->
<!-- journey-file: src/minilucene/writer.py -->
#### Query and token regressions mechanism

##### What it is and why it appears

A regression Stage turns discovered counterexamples into permanent boundaries across parsing, analysis, scoring, and codec primitives.

##### Runtime role

The parser recognizes one-term phrases without collapsing quote evidence; the lexer keeps hyphens inside terms; constructors and primitives validate values at creation.

##### Statement understanding

Validation must live at the earliest owning boundary, so every downstream caller receives an already-valid Token, score denominator, or integer.

<!-- journey-file: src/minilucene/analysis/__init__.py -->
#### Package, fixture, and project support

These files only keep exports, test corpora, dependencies, and the runtime environment reproducible; they are supporting wiring rather than Lucene mechanism logic.

### Verification evidence

Run `uv run pytest -q $(cat journey/stages/29-query-regressions/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Validation must live at the earliest owning boundary, so every downstream caller receives an already-valid Token, score denominator, or integer.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 9](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/09-query-language.md)

## 中文

### 目标

实现Query 与 Token 回归，并能从可执行反例、运行时状态与关键语句解释其边界。

### 交付文件

- `src/minilucene/analysis/__init__.py`
- `src/minilucene/analysis/model.py`
- `src/minilucene/analysis/pipeline.py`
- `src/minilucene/analysis/standard.py`
- `src/minilucene/query_parser/lexer.py`
- `src/minilucene/query_parser/parser.py`
- `src/minilucene/reader.py`
- `src/minilucene/search/reader.py`
- `src/minilucene/storage/codec.py`
- `src/minilucene/storage/manifest.py`
- `src/minilucene/writer.py`
- `tests/acceptance/test_phase1_retrieval_kernel.py`
- `tests/unit/analysis/test_pipeline.py`
- `tests/unit/query_parser/test_lexer.py`
- `tests/unit/query_parser/test_parser.py`

### 当前遇到的问题

单 Token Quote、Hyphenated Term、非法 Token Attribute、零长度统计与 Boolean Varint 暴露文档契约与可执行契约间缺口。

### 测试契约

#### 先看会坏在哪里

回归测试保留早期 Lexer/Parser 错误处理的精确字符串，并直接构造非法 Token 与 Primitive Value。

<!-- journey-file: tests/acceptance/test_phase1_retrieval_kernel.py -->
<!-- journey-file: tests/unit/analysis/test_pipeline.py -->
<!-- journey-file: tests/unit/query_parser/test_lexer.py -->
<!-- journey-file: tests/unit/query_parser/test_parser.py -->
#### Query 与 Token 回归测试证据

##### 测试锁定什么

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

##### 如何构造反例

回归测试保留早期 Lexer/Parser 错误处理的精确字符串，并直接构造非法 Token 与 Primitive Value。

##### 关键测试语句

```python
assert result.total_hits == 1
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

##### 失败意味着什么

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Regression Stage 把已发现反例变成 Parsing、Analysis、Scoring 与 Codec Primitive 的永久边界。

### 为什么需要这个机制

单 Token Quote、Hyphenated Term、非法 Token Attribute、零长度统计与 Boolean Varint 暴露文档契约与可执行契约间缺口。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Parser 识别单 Term Phrase 而不丢 Quote Evidence；Lexer 保留 Term 内 Hyphen；Constructor 与 Primitive 在创建时校验 Value。

### 机制板块

<!-- journey-file: src/minilucene/analysis/model.py -->
<!-- journey-file: src/minilucene/analysis/pipeline.py -->
<!-- journey-file: src/minilucene/analysis/standard.py -->
<!-- journey-file: src/minilucene/query_parser/lexer.py -->
<!-- journey-file: src/minilucene/query_parser/parser.py -->
<!-- journey-file: src/minilucene/reader.py -->
<!-- journey-file: src/minilucene/search/reader.py -->
<!-- journey-file: src/minilucene/storage/codec.py -->
<!-- journey-file: src/minilucene/storage/manifest.py -->
<!-- journey-file: src/minilucene/writer.py -->
#### Query 与 Token 回归机制

##### 是什么，为什么现在需要

Regression Stage 把已发现反例变成 Parsing、Analysis、Scoring 与 Codec Primitive 的永久边界。

##### 在运行时做什么

Parser 识别单 Term Phrase 而不丢 Quote Evidence；Lexer 保留 Term 内 Hyphen；Constructor 与 Primitive 在创建时校验 Value。

##### 关键语句理解

Validation 必须位于最早的所有权边界，使每个下游调用方收到的 Token、Score Denominator 或 Integer 已经有效。

<!-- journey-file: src/minilucene/analysis/__init__.py -->
#### 包、Fixture 与工程支撑

这些文件只保持包导出、测试语料、依赖与运行环境可复现，不把支撑接线误讲成 Lucene 机制。

### 验证证据

运行 `uv run pytest -q $(cat journey/stages/29-query-regressions/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

Validation 必须位于最早的所有权边界，使每个下游调用方收到的 Token、Score Denominator 或 Integer 已经有效。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 9 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/09-query-language.md)

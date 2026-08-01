# Stage 23 · Closed query lexer / 封闭 Query Lexer

<!-- journey: chapter=9 tests_added=1 -->

## English

### Goal

Build closed query lexer and explain its boundary from an executable counterexample, runtime state, and the critical statement.

### Deliverable files

- `src/minilucene/query_parser/__init__.py`
- `src/minilucene/query_parser/errors.py`
- `src/minilucene/query_parser/lexer.py`
- `tests/unit/query_parser/test_lexer.py`

### The problem at this point

User query text needs tokens that preserve source spans and distinguish operators, phrases, prefixes, fields, and errors.

### Test contract

#### See the failure first

Lexer tests include escapes, unmatched quotes, illegal stars, hyphenated text, and exact error offsets.

<!-- journey-file: tests/unit/query_parser/test_lexer.py -->
#### Closed query lexer test evidence

##### What this test locks

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

##### How it constructs the counterexample

Lexer tests include escapes, unmatched quotes, illegal stars, hyphenated text, and exact error offsets.

##### Key test statement

```python
assert [(token.kind, token.text, token.start) for token in tokens] == [
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

##### What a failure means

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

The lexer is evidence-preserving translation from characters to a finite token vocabulary; it does not decide precedence or index meaning.

### Why this mechanism is necessary

User query text needs tokens that preserve source spans and distinguish operators, phrases, prefixes, fields, and errors. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

A cursor consumes characters, records start/end spans, recognizes reserved syntax, and emits typed lexical failures at the first impossible byte.

### Mechanism blocks

<!-- journey-file: src/minilucene/query_parser/errors.py -->
<!-- journey-file: src/minilucene/query_parser/lexer.py -->
#### Closed query lexer mechanism

##### What it is and why it appears

The lexer is evidence-preserving translation from characters to a finite token vocabulary; it does not decide precedence or index meaning.

##### Runtime role

A cursor consumes characters, records start/end spans, recognizes reserved syntax, and emits typed lexical failures at the first impossible byte.

##### Statement understanding

Keeping spans through tokenization lets later parser errors point to the user's original text rather than a normalized reconstruction.

<!-- journey-file: src/minilucene/query_parser/__init__.py -->
#### Package, fixture, and project support

These files only keep exports, test corpora, dependencies, and the runtime environment reproducible; they are supporting wiring rather than Lucene mechanism logic.

### Verification evidence

Run `uv run pytest -q $(cat journey/stages/23-query-lexer/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Keeping spans through tokenization lets later parser errors point to the user's original text rather than a normalized reconstruction.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 9](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/09-query-language.md)

## 中文

### 目标

实现封闭 Query Lexer，并能从可执行反例、运行时状态与关键语句解释其边界。

### 交付文件

- `src/minilucene/query_parser/__init__.py`
- `src/minilucene/query_parser/errors.py`
- `src/minilucene/query_parser/lexer.py`
- `tests/unit/query_parser/test_lexer.py`

### 当前遇到的问题

用户 Query Text 需要保留 Source Span，并区分 Operator、Phrase、Prefix、Field 与 Error 的 Token。

### 测试契约

#### 先看会坏在哪里

Lexer 测试包含 Escape、未闭 Quote、非法 Star、Hyphenated Text 与精确 Error Offset。

<!-- journey-file: tests/unit/query_parser/test_lexer.py -->
#### 封闭 Query Lexer测试证据

##### 测试锁定什么

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

##### 如何构造反例

Lexer 测试包含 Escape、未闭 Quote、非法 Star、Hyphenated Text 与精确 Error Offset。

##### 关键测试语句

```python
assert [(token.kind, token.text, token.start) for token in tokens] == [
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

##### 失败意味着什么

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Lexer 是从 Character 到有限 Token Vocabulary 的保留证据翻译；它不决定 Precedence 或 Index Meaning。

### 为什么需要这个机制

用户 Query Text 需要保留 Source Span，并区分 Operator、Phrase、Prefix、Field 与 Error 的 Token。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Cursor 消费 Character、记录 Start/End Span、识别 Reserved Syntax，并在第一个不可能 Byte 发出类型化 Lexical Failure。

### 机制板块

<!-- journey-file: src/minilucene/query_parser/errors.py -->
<!-- journey-file: src/minilucene/query_parser/lexer.py -->
#### 封闭 Query Lexer机制

##### 是什么，为什么现在需要

Lexer 是从 Character 到有限 Token Vocabulary 的保留证据翻译；它不决定 Precedence 或 Index Meaning。

##### 在运行时做什么

Cursor 消费 Character、记录 Start/End Span、识别 Reserved Syntax，并在第一个不可能 Byte 发出类型化 Lexical Failure。

##### 关键语句理解

Tokenization 全程保留 Span，让后续 Parser Error 指向用户原文而非归一化重建文本。

<!-- journey-file: src/minilucene/query_parser/__init__.py -->
#### 包、Fixture 与工程支撑

这些文件只保持包导出、测试语料、依赖与运行环境可复现，不把支撑接线误讲成 Lucene 机制。

### 验证证据

运行 `uv run pytest -q $(cat journey/stages/23-query-lexer/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

Tokenization 全程保留 Span，让后续 Parser Error 指向用户原文而非归一化重建文本。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 9 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/09-query-language.md)

# Stage 24 · Recursive-descent query parser / 递归下降 Query Parser

<!-- journey: chapter=9 tests_added=1 -->

## English

### Goal

Build recursive-descent query parser and explain its boundary from an executable counterexample, runtime state, and the critical statement.

### Deliverable files

- `src/minilucene/analysis/standard.py`
- `src/minilucene/query_parser/__init__.py`
- `src/minilucene/query_parser/parser.py`
- `tests/unit/query_parser/test_parser.py`

### The problem at this point

Tokens remain ambiguous until precedence, grouping, field scope, unary operators, and implicit composition are explicit.

### Test contract

#### See the failure first

Tests compare ASTs for mixed AND/OR/NOT, nested groups, fields, phrases, prefixes, and incomplete expressions.

<!-- journey-file: tests/unit/query_parser/test_parser.py -->
#### Recursive-descent query parser test evidence

##### What this test locks

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

##### How it constructs the counterexample

Tests compare ASTs for mixed AND/OR/NOT, nested groups, fields, phrases, prefixes, and incomplete expressions.

##### Key test statement

```python
assert parse_query("a OR b AND c", schema, "body") == BooleanQuery(
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

##### What a failure means

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

A recursive-descent layer per precedence level turns the closed token stream into the same closed query AST used by execution.

### Why this mechanism is necessary

Tokens remain ambiguous until precedence, grouping, field scope, unary operators, and implicit composition are explicit. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

Parsing advances tokens through OR, AND, unary, and primary functions, applies field scope deliberately, and requires full input consumption.

### Mechanism blocks

<!-- journey-file: src/minilucene/analysis/standard.py -->
<!-- journey-file: src/minilucene/query_parser/parser.py -->
#### Recursive-descent query parser mechanism

##### What it is and why it appears

A recursive-descent layer per precedence level turns the closed token stream into the same closed query AST used by execution.

##### Runtime role

Parsing advances tokens through OR, AND, unary, and primary functions, applies field scope deliberately, and requires full input consumption.

##### Statement understanding

Full consumption rejects valid prefixes followed by garbage; separate precedence functions make grouping rules visible in code.

<!-- journey-file: src/minilucene/query_parser/__init__.py -->
#### Package, fixture, and project support

These files only keep exports, test corpora, dependencies, and the runtime environment reproducible; they are supporting wiring rather than Lucene mechanism logic.

### Verification evidence

Run `uv run pytest -q $(cat journey/stages/24-query-parser/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Full consumption rejects valid prefixes followed by garbage; separate precedence functions make grouping rules visible in code.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 9](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/09-query-language.md)

## 中文

### 目标

实现递归下降 Query Parser，并能从可执行反例、运行时状态与关键语句解释其边界。

### 交付文件

- `src/minilucene/analysis/standard.py`
- `src/minilucene/query_parser/__init__.py`
- `src/minilucene/query_parser/parser.py`
- `tests/unit/query_parser/test_parser.py`

### 当前遇到的问题

Token 在 Precedence、Grouping、Field Scope、Unary Operator 与隐式组合明确前仍有歧义。

### 测试契约

#### 先看会坏在哪里

测试比较混合 AND/OR/NOT、嵌套 Group、Field、Phrase、Prefix 与不完整表达式的 AST。

<!-- journey-file: tests/unit/query_parser/test_parser.py -->
#### 递归下降 Query Parser测试证据

##### 测试锁定什么

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

##### 如何构造反例

测试比较混合 AND/OR/NOT、嵌套 Group、Field、Phrase、Prefix 与不完整表达式的 AST。

##### 关键测试语句

```python
assert parse_query("a OR b AND c", schema, "body") == BooleanQuery(
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

##### 失败意味着什么

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

每个 Precedence Level 一层递归下降，把封闭 Token Stream 转成执行使用的同一封闭 Query AST。

### 为什么需要这个机制

Token 在 Precedence、Grouping、Field Scope、Unary Operator 与隐式组合明确前仍有歧义。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Parsing 通过 OR、AND、Unary 与 Primary Function 推进 Token，有意应用 Field Scope，并要求完整消费输入。

### 机制板块

<!-- journey-file: src/minilucene/analysis/standard.py -->
<!-- journey-file: src/minilucene/query_parser/parser.py -->
#### 递归下降 Query Parser机制

##### 是什么，为什么现在需要

每个 Precedence Level 一层递归下降，把封闭 Token Stream 转成执行使用的同一封闭 Query AST。

##### 在运行时做什么

Parsing 通过 OR、AND、Unary 与 Primary Function 推进 Token，有意应用 Field Scope，并要求完整消费输入。

##### 关键语句理解

完整消费拒绝后接垃圾的有效前缀；分离的 Precedence Function 让 Grouping Rule 在代码中可见。

<!-- journey-file: src/minilucene/query_parser/__init__.py -->
#### 包、Fixture 与工程支撑

这些文件只保持包导出、测试语料、依赖与运行环境可复现，不把支撑接线误讲成 Lucene 机制。

### 验证证据

运行 `uv run pytest -q $(cat journey/stages/24-query-parser/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

完整消费拒绝后接垃圾的有效前缀；分离的 Precedence Function 让 Grouping Rule 在代码中可见。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 9 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/09-query-language.md)

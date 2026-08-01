# Stage 04 · Closed query matching / 封闭 Query 匹配

<!-- journey: chapter=3 tests_added=3 -->

## English

### Goal

Build closed query matching and explain its boundary from an executable counterexample, runtime state, and the critical statement.

### Deliverable files

- `src/minilucene/query/__init__.py`
- `src/minilucene/query/match.py`
- `src/minilucene/query/model.py`
- `tests/contract/test_query_matching.py`
- `tests/helpers/__init__.py`
- `tests/helpers/corpus.py`

### The problem at this point

An index has postings but no explicit language for composing term, phrase, and boolean predicates.

### Test contract

#### See the failure first

The tests build nested AND, OR, NOT, and phrase queries whose positional or set behavior differs under naive evaluation.

<!-- journey-file: tests/contract/test_query_matching.py -->
<!-- journey-file: tests/helpers/__init__.py -->
<!-- journey-file: tests/helpers/corpus.py -->
#### Closed query matching test evidence

##### What this test locks

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

##### How it constructs the counterexample

The tests build nested AND, OR, NOT, and phrase queries whose positional or set behavior differs under naive evaluation.

##### Key test statement

```python
assert reader.match(PhraseQuery("body", ("distributed", "system"))) == {0}
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

##### What a failure means

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

A closed AST enumerates supported query forms; matching is a pure operation over a reader snapshot and returns document evidence.

### Why this mechanism is necessary

An index has postings but no explicit language for composing term, phrase, and boolean predicates. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

Leaf queries read postings, phrase matching aligns positions, and boolean nodes combine child results under explicit occurrence rules.

### Mechanism blocks

<!-- journey-file: src/minilucene/query/match.py -->
<!-- journey-file: src/minilucene/query/model.py -->
#### Closed query matching mechanism

##### What it is and why it appears

A closed AST enumerates supported query forms; matching is a pure operation over a reader snapshot and returns document evidence.

##### Runtime role

Leaf queries read postings, phrase matching aligns positions, and boolean nodes combine child results under explicit occurrence rules.

##### Statement understanding

Keeping the AST closed makes unsupported syntax impossible to smuggle into runtime matching as an unvalidated string.

<!-- journey-file: src/minilucene/query/__init__.py -->
#### Package, fixture, and project support

These files only keep exports, test corpora, dependencies, and the runtime environment reproducible; they are supporting wiring rather than Lucene mechanism logic.

### Verification evidence

Run `uv run pytest -q $(cat journey/stages/04-query-matching/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Keeping the AST closed makes unsupported syntax impossible to smuggle into runtime matching as an unvalidated string.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 3](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/03-inverted-index.md)

## 中文

### 目标

实现封闭 Query 匹配，并能从可执行反例、运行时状态与关键语句解释其边界。

### 交付文件

- `src/minilucene/query/__init__.py`
- `src/minilucene/query/match.py`
- `src/minilucene/query/model.py`
- `tests/contract/test_query_matching.py`
- `tests/helpers/__init__.py`
- `tests/helpers/corpus.py`

### 当前遇到的问题

索引已有 Posting，却没有显式语言组合 Term、Phrase 与 Boolean Predicate。

### 测试契约

#### 先看会坏在哪里

测试构造嵌套 AND、OR、NOT 与 Phrase Query，使朴素求值暴露 Position 或集合语义错误。

<!-- journey-file: tests/contract/test_query_matching.py -->
<!-- journey-file: tests/helpers/__init__.py -->
<!-- journey-file: tests/helpers/corpus.py -->
#### 封闭 Query 匹配测试证据

##### 测试锁定什么

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

##### 如何构造反例

测试构造嵌套 AND、OR、NOT 与 Phrase Query，使朴素求值暴露 Position 或集合语义错误。

##### 关键测试语句

```python
assert reader.match(PhraseQuery("body", ("distributed", "system"))) == {0}
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

##### 失败意味着什么

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

封闭 AST 枚举支持的 Query 形式；Matching 是 Reader Snapshot 上的纯操作并返回 Document Evidence。

### 为什么需要这个机制

索引已有 Posting，却没有显式语言组合 Term、Phrase 与 Boolean Predicate。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Leaf Query 读取 Posting，Phrase Matching 对齐 Position，Boolean Node 按显式 Occur Rule 组合子结果。

### 机制板块

<!-- journey-file: src/minilucene/query/match.py -->
<!-- journey-file: src/minilucene/query/model.py -->
#### 封闭 Query 匹配机制

##### 是什么，为什么现在需要

封闭 AST 枚举支持的 Query 形式；Matching 是 Reader Snapshot 上的纯操作并返回 Document Evidence。

##### 在运行时做什么

Leaf Query 读取 Posting，Phrase Matching 对齐 Position，Boolean Node 按显式 Occur Rule 组合子结果。

##### 关键语句理解

保持 AST 封闭，避免不受支持的语法以未校验字符串混入运行时 Matching。

<!-- journey-file: src/minilucene/query/__init__.py -->
#### 包、Fixture 与工程支撑

这些文件只保持包导出、测试语料、依赖与运行环境可复现，不把支撑接线误讲成 Lucene 机制。

### 验证证据

运行 `uv run pytest -q $(cat journey/stages/04-query-matching/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

保持 AST 封闭，避免不受支持的语法以未校验字符串混入运行时 Matching。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 3 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/03-inverted-index.md)

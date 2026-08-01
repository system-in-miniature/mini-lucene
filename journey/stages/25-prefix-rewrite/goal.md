# Stage 25 · Bounded prefix rewrite / 有界 Prefix Rewrite

<!-- journey: chapter=9 tests_added=1 -->

## English

### Goal

Build bounded prefix rewrite and explain its boundary from an executable counterexample, runtime state, and the critical statement.

### Deliverable files

- `src/minilucene/errors.py`
- `src/minilucene/reader.py`
- `src/minilucene/search/reader.py`
- `src/minilucene/search/rewrite.py`
- `tests/contract/test_prefix_rewrite.py`

### The problem at this point

A prefix query cannot execute directly against exact-term postings, and unbounded expansion can turn one query into exhaustive work.

### Test contract

#### See the failure first

Tests create more matching terms than the limit, vary default fields, and ensure deterministic expansion or a typed too-many-clauses failure.

<!-- journey-file: tests/contract/test_prefix_rewrite.py -->
#### Bounded prefix rewrite test evidence

##### What this test locks

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

##### How it constructs the counterexample

Tests create more matching terms than the limit, vary default fields, and ensure deterministic expansion or a typed too-many-clauses failure.

##### Key test statement

```python
assert reader.rewrite(
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

##### What a failure means

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

Rewrite translates a high-level prefix node into a bounded OR of exact TermQuery nodes using the current reader vocabulary.

### Why this mechanism is necessary

A prefix query cannot execute directly against exact-term postings, and unbounded expansion can turn one query into exhaustive work. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

It resolves field context, enumerates sorted matching terms, stops after limit plus one, and recursively rewrites composite children.

### Mechanism blocks

<!-- journey-file: src/minilucene/errors.py -->
<!-- journey-file: src/minilucene/reader.py -->
<!-- journey-file: src/minilucene/search/reader.py -->
<!-- journey-file: src/minilucene/search/rewrite.py -->
#### Bounded prefix rewrite mechanism

##### What it is and why it appears

Rewrite translates a high-level prefix node into a bounded OR of exact TermQuery nodes using the current reader vocabulary.

##### Runtime role

It resolves field context, enumerates sorted matching terms, stops after limit plus one, and recursively rewrites composite children.

##### Statement understanding

Checking one term beyond the limit distinguishes an exactly-full valid rewrite from silent truncation that would lose matches.



### Verification evidence

Run `uv run pytest -q $(cat journey/stages/25-prefix-rewrite/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Checking one term beyond the limit distinguishes an exactly-full valid rewrite from silent truncation that would lose matches.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 9](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/09-query-language.md)

## 中文

### 目标

实现有界 Prefix Rewrite，并能从可执行反例、运行时状态与关键语句解释其边界。

### 交付文件

- `src/minilucene/errors.py`
- `src/minilucene/reader.py`
- `src/minilucene/search/reader.py`
- `src/minilucene/search/rewrite.py`
- `tests/contract/test_prefix_rewrite.py`

### 当前遇到的问题

Prefix Query 无法直接执行 Exact-term Posting，且无界展开会把一次 Query 变成穷举工作。

### 测试契约

#### 先看会坏在哪里

测试创建超过 Limit 的匹配 Term、改变 Default Field，并要求确定性 Expansion 或类型化 Too-many-clauses Failure。

<!-- journey-file: tests/contract/test_prefix_rewrite.py -->
#### 有界 Prefix Rewrite测试证据

##### 测试锁定什么

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

##### 如何构造反例

测试创建超过 Limit 的匹配 Term、改变 Default Field，并要求确定性 Expansion 或类型化 Too-many-clauses Failure。

##### 关键测试语句

```python
assert reader.rewrite(
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

##### 失败意味着什么

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Rewrite 使用当前 Reader Vocabulary，把高层 Prefix Node 翻译成有界 Exact TermQuery OR。

### 为什么需要这个机制

Prefix Query 无法直接执行 Exact-term Posting，且无界展开会把一次 Query 变成穷举工作。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

它解析 Field Context、枚举有序匹配 Term、在 Limit+1 停止，并递归 Rewrite Composite Child。

### 机制板块

<!-- journey-file: src/minilucene/errors.py -->
<!-- journey-file: src/minilucene/reader.py -->
<!-- journey-file: src/minilucene/search/reader.py -->
<!-- journey-file: src/minilucene/search/rewrite.py -->
#### 有界 Prefix Rewrite机制

##### 是什么，为什么现在需要

Rewrite 使用当前 Reader Vocabulary，把高层 Prefix Node 翻译成有界 Exact TermQuery OR。

##### 在运行时做什么

它解析 Field Context、枚举有序匹配 Term、在 Limit+1 停止，并递归 Rewrite Composite Child。

##### 关键语句理解

检查 Limit 之外一个 Term，区分恰好填满的合法 Rewrite 与会丢 Match 的静默截断。



### 验证证据

运行 `uv run pytest -q $(cat journey/stages/25-prefix-rewrite/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

检查 Limit 之外一个 Term，区分恰好填满的合法 Rewrite 与会丢 Match 的静默截断。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 9 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/09-query-language.md)

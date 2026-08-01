# Stage 26 · Offset-based highlighting / 基于 Offset 的 Highlight

<!-- journey: chapter=9 tests_added=1 -->

## English

### Goal

Build offset-based highlighting and explain its boundary from an executable counterexample, runtime state, and the critical statement.

### Deliverable files

- `src/minilucene/highlight.py`
- `src/minilucene/reader.py`
- `src/minilucene/search/collector.py`
- `src/minilucene/search/searcher.py`
- `tests/contract/test_highlighting.py`

### The problem at this point

Highlighting normalized query terms by searching raw strings fails under case folding, punctuation, repeated terms, and phrase boundaries.

### Test contract

#### See the failure first

Tests use mixed case, repeated tokens, overlapping clauses, stored/non-stored fields, and fragment limits.

<!-- journey-file: tests/contract/test_highlighting.py -->
#### Offset-based highlighting test evidence

##### What this test locks

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

##### How it constructs the counterexample

Tests use mixed case, repeated tokens, overlapping clauses, stored/non-stored fields, and fragment limits.

##### Key test statement

```python
assert result.hits[0].highlights["body"] == (
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

##### What a failure means

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

Highlighting reuses analyzer offsets as the mapping from indexed evidence back to stored source text.

### Why this mechanism is necessary

Highlighting normalized query terms by searching raw strings fails under case folding, punctuation, repeated terms, and phrase boundaries. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

The highlighter analyzes stored text with the field analyzer, selects token spans matched by rewritten query terms, merges overlaps, and builds bounded fragments.

### Mechanism blocks

<!-- journey-file: src/minilucene/highlight.py -->
<!-- journey-file: src/minilucene/reader.py -->
<!-- journey-file: src/minilucene/search/collector.py -->
<!-- journey-file: src/minilucene/search/searcher.py -->
#### Offset-based highlighting mechanism

##### What it is and why it appears

Highlighting reuses analyzer offsets as the mapping from indexed evidence back to stored source text.

##### Runtime role

The highlighter analyzes stored text with the field analyzer, selects token spans matched by rewritten query terms, merges overlaps, and builds bounded fragments.

##### Statement understanding

Offsets, not normalized token strings, preserve the exact original casing and punctuation inserted between highlight tags.



### Verification evidence

Run `uv run pytest -q $(cat journey/stages/26-highlighting/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Offsets, not normalized token strings, preserve the exact original casing and punctuation inserted between highlight tags.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 9](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/09-query-language.md)

## 中文

### 目标

实现基于 Offset 的 Highlight，并能从可执行反例、运行时状态与关键语句解释其边界。

### 交付文件

- `src/minilucene/highlight.py`
- `src/minilucene/reader.py`
- `src/minilucene/search/collector.py`
- `src/minilucene/search/searcher.py`
- `tests/contract/test_highlighting.py`

### 当前遇到的问题

用字符串搜索在原文中 Highlight 归一化 Query Term，会在大小写、标点、重复 Term 与 Phrase Boundary 下失败。

### 测试契约

#### 先看会坏在哪里

测试使用混合大小写、重复 Token、重叠 Clause、Stored/Non-stored Field 与 Fragment Limit。

<!-- journey-file: tests/contract/test_highlighting.py -->
#### 基于 Offset 的 Highlight测试证据

##### 测试锁定什么

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

##### 如何构造反例

测试使用混合大小写、重复 Token、重叠 Clause、Stored/Non-stored Field 与 Fragment Limit。

##### 关键测试语句

```python
assert result.hits[0].highlights["body"] == (
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

##### 失败意味着什么

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Highlight 复用 Analyzer Offset，把索引证据映射回 Stored Source Text。

### 为什么需要这个机制

用字符串搜索在原文中 Highlight 归一化 Query Term，会在大小写、标点、重复 Term 与 Phrase Boundary 下失败。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Highlighter 用 Field Analyzer 分析 Stored Text、选择 Rewritten Query Term 匹配的 Token Span、合并重叠并构建有界 Fragment。

### 机制板块

<!-- journey-file: src/minilucene/highlight.py -->
<!-- journey-file: src/minilucene/reader.py -->
<!-- journey-file: src/minilucene/search/collector.py -->
<!-- journey-file: src/minilucene/search/searcher.py -->
#### 基于 Offset 的 Highlight机制

##### 是什么，为什么现在需要

Highlight 复用 Analyzer Offset，把索引证据映射回 Stored Source Text。

##### 在运行时做什么

Highlighter 用 Field Analyzer 分析 Stored Text、选择 Rewritten Query Term 匹配的 Token Span、合并重叠并构建有界 Fragment。

##### 关键语句理解

Offset 而非归一化 Token String，保留 Highlight Tag 之间准确的原始大小写与标点。



### 验证证据

运行 `uv run pytest -q $(cat journey/stages/26-highlighting/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

Offset 而非归一化 Token String，保留 Highlight Tag 之间准确的原始大小写与标点。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 9 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/09-query-language.md)

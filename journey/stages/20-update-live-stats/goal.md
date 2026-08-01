# Stage 20 · Update and live-only statistics / Update 与仅 Live 统计

<!-- journey: chapter=6 tests_added=2 -->

## English

### Goal

Build update and live-only statistics and explain its boundary from an executable counterexample, runtime state, and the critical statement.

### Deliverable files

- `src/minilucene/writer.py`
- `tests/nrt/test_live_bm25_stats.py`
- `tests/nrt/test_update_document.py`

### The problem at this point

Implementing update as add-then-delete can delete the replacement, and deleted documents must stop influencing ranking.

### Test contract

#### See the failure first

The counterexample updates multiple matches, injects add failure, and compares BM25 before and after deletions across snapshots.

<!-- journey-file: tests/nrt/test_live_bm25_stats.py -->
<!-- journey-file: tests/nrt/test_update_document.py -->
#### Update and live-only statistics test evidence

##### What this test locks

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

##### How it constructs the counterexample

The counterexample updates multiple matches, injects add failure, and compares BM25 before and after deletions across snapshots.

##### Key test statement

```python
assert stats.live_doc_count == 2
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

##### What a failure means

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

Update is delete-all matching old identity plus one validated add under one writer operation; corpus statistics count only live documents.

### Why this mechanism is necessary

Implementing update as add-then-delete can delete the replacement, and deleted documents must stop influencing ranking. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

The writer validates replacement first, derives deletion masks from the pre-update view, then buffers the new document; readers aggregate only live postings and norms.

### Mechanism blocks

<!-- journey-file: src/minilucene/writer.py -->
#### Update and live-only statistics mechanism

##### What it is and why it appears

Update is delete-all matching old identity plus one validated add under one writer operation; corpus statistics count only live documents.

##### Runtime role

The writer validates replacement first, derives deletion masks from the pre-update view, then buffers the new document; readers aggregate only live postings and norms.

##### Statement understanding

Validating before deletion prevents a bad replacement from destroying old data; live filtering keeps ranking consistent with visible hits.



### Verification evidence

Run `uv run pytest -q $(cat journey/stages/20-update-live-stats/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Validating before deletion prevents a bad replacement from destroying old data; live filtering keeps ranking consistent with visible hits.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 6](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/06-deletes-updates.md)

## 中文

### 目标

实现Update 与仅 Live 统计，并能从可执行反例、运行时状态与关键语句解释其边界。

### 交付文件

- `src/minilucene/writer.py`
- `tests/nrt/test_live_bm25_stats.py`
- `tests/nrt/test_update_document.py`

### 当前遇到的问题

把 Update 实现为先 Add 后 Delete 会删掉替代 Document，且已删除 Document 不应继续影响 Ranking。

### 测试契约

#### 先看会坏在哪里

反例 Update 多个 Match、注入 Add Failure，并比较多个 Snapshot 中删除前后的 BM25。

<!-- journey-file: tests/nrt/test_live_bm25_stats.py -->
<!-- journey-file: tests/nrt/test_update_document.py -->
#### Update 与仅 Live 统计测试证据

##### 测试锁定什么

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

##### 如何构造反例

反例 Update 多个 Match、注入 Add Failure，并比较多个 Snapshot 中删除前后的 BM25。

##### 关键测试语句

```python
assert stats.live_doc_count == 2
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

##### 失败意味着什么

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Update 是在一次 Writer Operation 中删除全部旧身份匹配并加入一个已校验新 Document；Corpus Statistic 只统计 Live Document。

### 为什么需要这个机制

把 Update 实现为先 Add 后 Delete 会删掉替代 Document，且已删除 Document 不应继续影响 Ranking。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Writer 先校验 Replacement、从更新前 View 派生 Delete Mask，再 Buffer 新 Document；Reader 只聚合 Live Posting 与 Norm。

### 机制板块

<!-- journey-file: src/minilucene/writer.py -->
#### Update 与仅 Live 统计机制

##### 是什么，为什么现在需要

Update 是在一次 Writer Operation 中删除全部旧身份匹配并加入一个已校验新 Document；Corpus Statistic 只统计 Live Document。

##### 在运行时做什么

Writer 先校验 Replacement、从更新前 View 派生 Delete Mask，再 Buffer 新 Document；Reader 只聚合 Live Posting 与 Norm。

##### 关键语句理解

删除前校验防止错误 Replacement 摧毁旧数据；Live Filtering 让 Ranking 与可见 Hit 一致。



### 验证证据

运行 `uv run pytest -q $(cat journey/stages/20-update-live-stats/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

删除前校验防止错误 Replacement 摧毁旧数据；Live Filtering 让 Ranking 与可见 Hit 一致。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 6 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/06-deletes-updates.md)

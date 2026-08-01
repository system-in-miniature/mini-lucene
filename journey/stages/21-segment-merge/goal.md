# Stage 21 · Explicit segment merge / 显式 Segment Merge

<!-- journey: chapter=10 tests_added=1 -->

## English

### Goal

Build explicit segment merge and explain its boundary from an executable counterexample, runtime state, and the critical statement.

### Deliverable files

- `src/minilucene/merge.py`
- `src/minilucene/writer.py`
- `tests/nrt/test_segment_merge.py`

### The problem at this point

Many immutable segments increase lookup and file overhead, but merging must not resurrect deleted documents or renumber visible history incorrectly.

### Test contract

#### See the failure first

Tests merge segments containing deletions, retain an old reader, inject output failure, and compare results before and after publication.

<!-- journey-file: tests/nrt/test_segment_merge.py -->
#### Explicit segment merge test evidence

##### What this test locks

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

##### How it constructs the counterexample

Tests merge segments containing deletions, retain an old reader, inject output failure, and compare results before and after publication.

##### Key test statement

```python
assert merged.max_doc == before.num_live_docs
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

##### What a failure means

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

Merge captures immutable inputs, copies only live documents into a new dense segment, and swaps writer ownership after output publication.

### Why this mechanism is necessary

Many immutable segments increase lookup and file overhead, but merging must not resurrect deleted documents or renumber visible history incorrectly. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

The writer pins input generations, builds a doc-ID remap and output image, publishes it, then replaces current segment references and retires inputs.

### Mechanism blocks

<!-- journey-file: src/minilucene/merge.py -->
<!-- journey-file: src/minilucene/writer.py -->
#### Explicit segment merge mechanism

##### What it is and why it appears

Merge captures immutable inputs, copies only live documents into a new dense segment, and swaps writer ownership after output publication.

##### Runtime role

The writer pins input generations, builds a doc-ID remap and output image, publishes it, then replaces current segment references and retires inputs.

##### Statement understanding

Publishing output before swapping state makes failure leave the old segment set authoritative and old readers valid.



### Verification evidence

Run `uv run pytest -q $(cat journey/stages/21-segment-merge/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Publishing output before swapping state makes failure leave the old segment set authoritative and old readers valid.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 10](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/10-merge-and-beyond.md)

## 中文

### 目标

实现显式 Segment Merge，并能从可执行反例、运行时状态与关键语句解释其边界。

### 交付文件

- `src/minilucene/merge.py`
- `src/minilucene/writer.py`
- `tests/nrt/test_segment_merge.py`

### 当前遇到的问题

大量 Immutable Segment 增加 Lookup 与文件开销，但 Merge 不能复活已删 Document 或错误重编号可见历史。

### 测试契约

#### 先看会坏在哪里

测试合并含删除的 Segment、保留旧 Reader、注入 Output Failure，并比较发布前后结果。

<!-- journey-file: tests/nrt/test_segment_merge.py -->
#### 显式 Segment Merge测试证据

##### 测试锁定什么

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

##### 如何构造反例

测试合并含删除的 Segment、保留旧 Reader、注入 Output Failure，并比较发布前后结果。

##### 关键测试语句

```python
assert merged.max_doc == before.num_live_docs
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

##### 失败意味着什么

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Merge 捕获不可变 Input，只把 Live Document 复制到新的 Dense Segment，并在 Output Publication 后交换 Writer Ownership。

### 为什么需要这个机制

大量 Immutable Segment 增加 Lookup 与文件开销，但 Merge 不能复活已删 Document 或错误重编号可见历史。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Writer Pin 输入 Generation、构建 Doc-ID Remap 与 Output Image、发布后替换当前 Segment Reference 并 Retire Input。

### 机制板块

<!-- journey-file: src/minilucene/merge.py -->
<!-- journey-file: src/minilucene/writer.py -->
#### 显式 Segment Merge机制

##### 是什么，为什么现在需要

Merge 捕获不可变 Input，只把 Live Document 复制到新的 Dense Segment，并在 Output Publication 后交换 Writer Ownership。

##### 在运行时做什么

Writer Pin 输入 Generation、构建 Doc-ID Remap 与 Output Image、发布后替换当前 Segment Reference 并 Retire Input。

##### 关键语句理解

先发布 Output 再 Swap State，使失败时旧 Segment Set 仍权威且旧 Reader 有效。



### 验证证据

运行 `uv run pytest -q $(cat journey/stages/21-segment-merge/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

先发布 Output 再 Swap State，使失败时旧 Segment Set 仍权威且旧 Reader 有效。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 10 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/10-merge-and-beyond.md)

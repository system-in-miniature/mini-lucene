# Stage 11 · Checksummed segment publication / 带校验和的 Segment 发布

<!-- journey: chapter=4 tests_added=1 -->

## English

### Goal

Build checksummed segment publication and explain its boundary from an executable counterexample, runtime state, and the critical statement.

### Deliverable files

- `src/minilucene/storage/filesystem.py`
- `src/minilucene/storage/segment_store.py`
- `tests/storage/test_segment_store.py`

### The problem at this point

Several correctly encoded files can still be partially written or mixed across generations.

### Test contract

#### See the failure first

Failure injection stops publication between temporary writes, checksums, fsync, and rename, then reopens the directory.

<!-- journey-file: tests/storage/test_segment_store.py -->
#### Checksummed segment publication test evidence

##### What this test locks

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

##### How it constructs the counterexample

Failure injection stops publication between temporary writes, checksums, fsync, and rename, then reopens the directory.

##### Key test statement

```python
assert fs.writes[-1].name == "segment.json"
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

##### What a failure means

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

A segment store publishes an immutable directory only after every file and metadata digest is complete and durable.

### Why this mechanism is necessary

Several correctly encoded files can still be partially written or mixed across generations. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

It writes a temporary sibling, fsyncs files and directory, records SHA-256 metadata, atomically renames, and verifies on read.

### Mechanism blocks

<!-- journey-file: src/minilucene/storage/filesystem.py -->
<!-- journey-file: src/minilucene/storage/segment_store.py -->
#### Checksummed segment publication mechanism

##### What it is and why it appears

A segment store publishes an immutable directory only after every file and metadata digest is complete and durable.

##### Runtime role

It writes a temporary sibling, fsyncs files and directory, records SHA-256 metadata, atomically renames, and verifies on read.

##### Statement understanding

The final rename is the visibility boundary; checksummed children prepared beforehand ensure readers never accept a mixed segment.



### Verification evidence

Run `uv run pytest -q $(cat journey/stages/11-segment-publication/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

The final rename is the visibility boundary; checksummed children prepared beforehand ensure readers never accept a mixed segment.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 4](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/04-codec.md)

## 中文

### 目标

实现带校验和的 Segment 发布，并能从可执行反例、运行时状态与关键语句解释其边界。

### 交付文件

- `src/minilucene/storage/filesystem.py`
- `src/minilucene/storage/segment_store.py`
- `tests/storage/test_segment_store.py`

### 当前遇到的问题

多个正确编码文件仍可能被部分写入，或混合不同代次。

### 测试契约

#### 先看会坏在哪里

Failure Injection 在临时写、Checksum、Fsync 与 Rename 之间停止发布，再重开目录。

<!-- journey-file: tests/storage/test_segment_store.py -->
#### 带校验和的 Segment 发布测试证据

##### 测试锁定什么

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

##### 如何构造反例

Failure Injection 在临时写、Checksum、Fsync 与 Rename 之间停止发布，再重开目录。

##### 关键测试语句

```python
assert fs.writes[-1].name == "segment.json"
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

##### 失败意味着什么

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Segment Store 只有在每个文件与 Metadata Digest 完整持久后，才发布不可变目录。

### 为什么需要这个机制

多个正确编码文件仍可能被部分写入，或混合不同代次。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

它写临时 Sibling、Fsync 文件与目录、记录 SHA-256 Metadata、原子 Rename，并在读取时验证。

### 机制板块

<!-- journey-file: src/minilucene/storage/filesystem.py -->
<!-- journey-file: src/minilucene/storage/segment_store.py -->
#### 带校验和的 Segment 发布机制

##### 是什么，为什么现在需要

Segment Store 只有在每个文件与 Metadata Digest 完整持久后，才发布不可变目录。

##### 在运行时做什么

它写临时 Sibling、Fsync 文件与目录、记录 SHA-256 Metadata、原子 Rename，并在读取时验证。

##### 关键语句理解

最终 Rename 是可见性边界；预先准备好的带校验 Child 确保 Reader 不接受混合 Segment。



### 验证证据

运行 `uv run pytest -q $(cat journey/stages/11-segment-publication/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

最终 Rename 是可见性边界；预先准备好的带校验 Child 确保 Reader 不接受混合 Segment。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 4 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/04-codec.md)

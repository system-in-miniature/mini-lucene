# 阶段 3：NRT 变更与合并验收

> **语言**: [English](../phase3-nrt-mutation.md) | 简体中文

## 已验收的可见性模型

MiniLucene 现在具有三个可执行且彼此不同的边界：

```text
flush
  creates an immutable segment in writer state

refresh
  returns a new in-process point-in-time reader

commit
  atomically replaces the recoverable manifest
```

通过刷新可见的数据如果没有提交，会在模拟进程重新打开后消失。既有读取器在之后的
任何刷新、删除、更新、提交或合并后都绝不改变。

## 已验收的变更行为

- 每个 `IndexReader` 拥有一个冻结的 `ReaderSnapshot`。
- 关闭读取器是幂等的，并且只释放该读取器的分段引用。
- 活跃文档（live docs）是不可变位集合世代，具有最大文档数验证和 SHA-256 清单引用。
- 按词项删除会先派生每个缓冲区和分段掩码，再交换写入器状态。
- 重复删除只统计新删除的活跃文档。
- 更新会先验证并准备替换文档，再以原子方式交换
  `删除所有精确词项匹配项 + 添加一个替换文档`。
- 已删除文档既不贡献命中、文档频率、平均字段长度，也不贡献 BM25 分数。
- 显式合并直接复制活跃的倒排记录和位置，因此已索引但未存储的文本仍可搜索。
- 合并会将本地文档 ID 稠密地重新映射，并保留范数和存储字段。
- 在写入器集合交换前发生合并失败时，旧分段集合仍具权威性。
- 世代分配会跳过发布失败前创建的完整孤儿分段和活跃文档文件。

## 所有权与清理

一个进程内注册表按分段世代跟踪相互独立的读取器与写入器所有者。仅当分段满足以下
条件时，垃圾回收才会移除它：

```text
absent from manifest
AND absent from every reader owner
AND absent from the writer owner
AND a recognized complete segment directory
```

格式错误或未知的目录会保留以供诊断。`Index.close()` 会停止接纳新操作，并报告外部
读取器，而不是使它们失效。写入器关闭依次经过 `OPEN → CLOSING → CLOSED`，先释放
分段所有权，再释放其锁。

## 已验收命令

执行于 2026-07-27：

```text
uv run pytest tests/acceptance/test_phase3_nrt_mutation.py -q
1 passed

uv run ruff check src tests tools
All checks passed

uv run pytest -q
149 passed

uv run python -m compileall -q src tests tools
exit 0

git diff --check
exit 0
```

## 按阶段边界推迟的内容

阶段 3 不包含查询字符串解析器、高亮、评估语料库、CLI、网络适配器、分布式协调、
自动合并调度器或向量检索。

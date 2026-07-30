# 阶段 2：不可变存储与提交验收

> **语言**: [English](../phase2-storage-commit.md) | 简体中文

## 已验收的持久化闭环

```text
RamIndexBuilder
→ immutable SegmentImage
→ deterministic term/posting/stored/norm codecs
→ checksummed temporary segment directory
→ atomic segment rename
→ writer segment set
→ atomic manifest replacement
→ fresh committed IndexReader
```

`manifest.json` 是唯一可恢复根（recoverable root）。未被清单引用的完整分段目录是孤儿，
重新打开后仍不可见。

## 固定的存储行为

- 分段世代为正数，文档 ID 稠密且只在本地有效。
- 无符号 varint 以 uint64 为界；文档 ID 和位置在第一个值之后使用正增量。
- 词项按字段和词项排序；其偏移量连续覆盖 `postings.bin`。
- 存储字段采用长度分帧的规范 UTF-8 JSON。
- 范数（norms）为每个本地文档携带一个经过分析的字段长度。
- `segment.json` 记录魔数、版本、编解码器、模式指纹、长度和 SHA-256 校验和。
- 分段数据文件先于 `segment.json` 同步；元数据先于分段目录的原子重命名同步。
- 模式 JSON 单独持久化，并依据其 SHA-256 指纹和已提交清单进行验证。
- 每个索引路径只允许存在一个 `IndexWriter` 锁。
- 刷新到磁盘（flush）会向写入器状态发布不可变分段，但不会修改清单。
- 提交会执行 flush，重新打开并验证每个被引用分段，然后以原子方式替换清单。
- 清单替换失败时，先前的提交仍具权威性。
- `Index.open_reader()` 严格按有序的清单引用加载，并计算全局读取器统计信息。
- 磁盘结果和分数与单分段内存预言机（oracle）一致。

## 故障证据

可执行测试覆盖：

- 最终目录重命名前的数据文件写入失败；
- 文件长度或校验和损坏；
- 模式不匹配；
- 清单格式错误与未知版本；
- 完整孤儿分段；
- 清单替换失败；
- 成功提交后全新重新打开。

分段字节布局记录在
[`segment-format.md`](segment-format.md) 中。

## 已验收命令

执行于 2026-07-27：

```text
uv run pytest tests/acceptance/test_phase2_storage_commit.py -q
1 passed

uv run ruff check src tests tools
All checks passed

uv run pytest -q
108 passed

uv run python -m compileall -q src tests tools
exit 0

git diff --check
exit 0
```

## 按阶段边界推迟的内容

阶段 2 不包含近实时刷新（NRT refresh）、活跃文档文件、删除、更新、合并、引用所有权
清理、查询字符串解析器、高亮、网络适配器、分布式协调或向量检索。

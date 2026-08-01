# 自主重建

每个 Stage 都是一节可独立浏览的完整课：先理解当前问题、基本概念与必要性，再按机制板块连接相关文件和关键语句，最后用验证证据和自己的话完成理解闭环。

这是三种学习模式中的浏览器自主学习路径。按主题学习请进入[机制教程](../index.md)；需要 CLI 互动请查看 [Agent 带教使用教程](../agent-guide.md)。

如果希望在编辑器里聚焦当前增量，运行 `python -m journey.tools.build_journey study N`，再打开 `../MiniLucene-journey-workspace`。

| Stage | 主题 | 新增测试 | 教材章节 |
|---:|---|---:|---:|
| [01](stage-01.md) | 字段与文档契约 | 2 | [1](../tutorial/01-getting-started.md) |
| [02](stage-02.md) | 位置化文本分析 | 1 | [2](../tutorial/02-analysis.md) |
| [03](stage-03.md) | 不可变 RAM 倒排索引 | 1 | [3](../tutorial/03-inverted-index.md) |
| [04](stage-04.md) | 封闭 Query 匹配 | 3 | [3](../tutorial/03-inverted-index.md) |
| [05](stage-05.md) | 快照级语料统计 | 2 | [8](../tutorial/08-scoring.md) |
| [06](stage-06.md) | 全局 BM25 排名 | 3 | [8](../tutorial/08-scoring.md) |
| [07](stage-07.md) | 有界 Top-K 检索 | 3 | [8](../tutorial/08-scoring.md) |
| [08](stage-08.md) | 不可变 Segment Image | 1 | [4](../tutorial/04-codec.md) |
| [09](stage-09.md) | 有界 Varint 原语 | 1 | [4](../tutorial/04-codec.md) |
| [10](stage-10.md) | 教学用 Segment Codec | 1 | [4](../tutorial/04-codec.md) |
| [11](stage-11.md) | 带校验和的 Segment 发布 | 1 | [4](../tutorial/04-codec.md) |
| [12](stage-12.md) | Manifest 提交根 | 1 | [7](../tutorial/07-commit-atomicity.md) |
| [13](stage-13.md) | Index 生命周期所有权 | 1 | [5](../tutorial/05-segments-nrt.md) |
| [14](stage-14.md) | Writer Flush | 1 | [5](../tutorial/05-segments-nrt.md) |
| [15](stage-15.md) | 原子 Commit 与重开 | 3 | [7](../tutorial/07-commit-atomicity.md) |
| [16](stage-16.md) | 时间点 Reader Snapshot | 1 | [5](../tutorial/05-segments-nrt.md) |
| [17](stage-17.md) | Near-real-time Refresh | 1 | [5](../tutorial/05-segments-nrt.md) |
| [18](stage-18.md) | 不可变 Live-doc Mask | 2 | [6](../tutorial/06-deletes-updates.md) |
| [19](stage-19.md) | 按精确 Term 删除 | 1 | [6](../tutorial/06-deletes-updates.md) |
| [20](stage-20.md) | Update 与仅 Live 统计 | 2 | [6](../tutorial/06-deletes-updates.md) |
| [21](stage-21.md) | 显式 Segment Merge | 1 | [10](../tutorial/10-merge-and-beyond.md) |
| [22](stage-22.md) | Segment 所有权与 Close | 3 | [10](../tutorial/10-merge-and-beyond.md) |
| [23](stage-23.md) | 封闭 Query Lexer | 1 | [9](../tutorial/09-query-language.md) |
| [24](stage-24.md) | 递归下降 Query Parser | 1 | [9](../tutorial/09-query-language.md) |
| [25](stage-25.md) | 有界 Prefix Rewrite | 1 | [9](../tutorial/09-query-language.md) |
| [26](stage-26.md) | 基于 Offset 的 Highlight | 1 | [9](../tutorial/09-query-language.md) |
| [27](stage-27.md) | 确定性相关性评估 | 4 | [8](../tutorial/08-scoring.md) |
| [28](stage-28.md) | CLI 与领域闭环 | 5 | [1](../tutorial/01-getting-started.md) |
| [29](stage-29.md) | Query 与 Token 回归 | 4 | [9](../tutorial/09-query-language.md) |
| [30](stage-30.md) | Document-at-a-time 执行 | 4 | [11](../tutorial/11-daat.md) |

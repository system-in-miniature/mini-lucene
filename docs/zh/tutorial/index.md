# MiniLucene 教程

这套十一章教材沿一套词法检索系统，从文本分析一路讲到不可变存储、NRT 可见性、
打分、查询解析与 merge。建议按顺序阅读；每章都包含源码锚点、实测实验、与真实
Lucene 的差异，以及带折叠参考答案的练习。

1. [认识 MiniLucene](01-getting-started.md)
2. [分析链](02-analysis.md)
3. [倒排索引](03-inverted-index.md)
4. [磁盘编码](04-codec.md)
5. [段与近实时](05-segments-nrt.md)
6. [删除与更新](06-deletes-updates.md)
7. [提交原子性](07-commit-atomicity.md)
8. [打分与 Top-K](08-scoring.md)
9. [查询语言](09-query-language.md)
10. [合并与方法论](10-merge-and-beyond.md)
11. [文档一次查询执行（DAAT）](11-daat.md)

[行为矩阵](../../behavior-matrix.md)是可执行契约；
[MiniLucene → Lucene 映射](../../lucene-mapping.md)用于对照教学内核与真实系统。

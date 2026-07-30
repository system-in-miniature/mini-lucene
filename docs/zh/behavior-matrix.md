# MiniLucene V1 可执行行为矩阵

> **语言**: [English](../behavior-matrix.md) | 简体中文

下列每项受支持行为和明确非目标都绑定到一个稳定的 pytest 节点。公共 API 列给出用户
接触的边界；它不声明与 Apache Lucene API 或文件格式兼容。

| 功能（Feature） | 公共 API | 语义边界 | 可执行测试节点 ID |
|---|---|---|---|
| 字段模式（Field schema） | `Schema`, `TextField`, `KeywordField`, `StoredField` | 存储、索引、分词、位置和加权彼此独立 | `tests/contract/test_schema.py::test_stored_indexed_and_tokenized_are_independent` |
| 索引生命周期 | `Index.create`, `Index.open` | 持久化不可变模式指纹定义一个索引 | `tests/contract/test_index_lifecycle.py::test_create_open_and_schema_fingerprint` |
| 单一写入器 | `Index.writer` | 同一索引无法再打开第二个变更所有者 | `tests/contract/test_index_lifecycle.py::test_only_one_writer_can_be_open` |
| 位置分析器 | `StandardAnalyzer.analyze` | 转为小写和过滤停用词时保留原始偏移量与位置间隙 | `tests/unit/analysis/test_pipeline.py::test_standard_analysis_preserves_offsets_and_stopword_gap` |
| 精确关键字分析 | `KeywordField` | 一个完整值变为一个不带位置的精确词项 | `tests/contract/test_memory_index.py::test_keyword_field_indexes_one_exact_term_without_positions` |
| 不可变 RAM 分段 | `RamIndexBuilder.freeze` | 倒排记录、位置、长度和存储值一同冻结 | `tests/contract/test_memory_index.py::test_ram_segment_contains_positions_lengths_and_only_stored_values` |
| 词项查询与存储字段 | `TermQuery`, `MemoryIndex.search` | 精确词项匹配只返回声明为存储的值 | `tests/contract/test_memory_search.py::test_public_memory_index_returns_stored_fields` |
| 短语查询 | `PhraseQuery` | 精确短语匹配依赖位置，而非仅依赖词项共同出现 | `tests/contract/test_query_matching.py::test_phrase_requires_consecutive_positions` |
| 布尔查询 | `BooleanQuery` | MUST、SHOULD 和 MUST_NOT 使用固定的集合语义 | `tests/contract/test_query_matching.py::test_should_is_required_without_must_and_optional_with_must` |
| 全匹配查询 | `MatchAllQuery` | 无需保留结果对象即可统计总命中数 | `tests/contract/test_memory_search.py::test_match_all_can_report_total_without_returning_hits` |
| 全局 BM25 | `MemoryIndex.search`, `IndexReader.search` | TF 饱和度、IDF、长度归一化和字段加权使用同一个活跃语料库视图 | `tests/evaluation/test_reference_corpus.py::test_bm25_term_frequency_saturates_instead_of_growing_linearly` |
| 有界 Top-K | `search(..., top_k=K)` | 收集器在统计所有匹配项的同时最多保留 K 个命中 | `tests/unit/search/test_topk.py::test_heap_topk_matches_complete_sort_oracle` |
| 教学分段编解码器 | `IndexWriter.flush` | 确定性不可变文件可往返还原倒排记录与存储数据 | `tests/storage/test_segment_store.py::test_segment_store_open_round_trips_image` |
| Flush 可见性 | `IndexWriter.flush` | flush 创建分段，但不改变已提交清单 | `tests/storage/test_writer_flush.py::test_flush_creates_segment_but_does_not_change_manifest` |
| 原子提交 | `IndexWriter.commit` | 清单替换在新旧已提交根之间二选一 | `tests/storage/test_commit_recovery.py::test_manifest_replace_failure_preserves_previous_commit` |
| NRT 刷新 | `IndexWriter.refresh` | 已 flush 的状态对读取器可见，但不具备重启持久性 | `tests/nrt/test_refresh_visibility.py::test_uncommitted_refresh_state_disappears_after_process_reopen` |
| 读取器快照 | `Index.open_reader` | 既有读取器在后续提交后仍保持时间点视图 | `tests/nrt/test_reader_snapshot.py::test_reader_snapshot_never_changes_after_later_commit` |
| 精确词项删除 | `IndexWriter.delete_by_term` | 不可变倒排记录保持不变，活跃文档掩码隐藏匹配项 | `tests/nrt/test_delete_by_term.py::test_old_reader_keeps_deleted_document_and_new_stats_exclude_it` |
| 原子更新 | `IndexWriter.update_document` | 更新等于删除所有匹配项，再添加一份经过验证的文档 | `tests/nrt/test_update_document.py::test_invalid_replacement_leaves_delete_state_unchanged` |
| 显式合并 | `IndexWriter.merge` | 压实选中的不可变分段，同时保持结果和分数不变 | `tests/nrt/test_segment_merge.py::test_merge_skips_deletes_and_preserves_search_results` |
| 分段所有权 | `Index.collect_garbage`, `Index.lifecycle_diagnostics` | 过时文件等待每个读取器和写入器所有者释放后才移除 | `tests/nrt/test_segment_ownership.py::test_obsolete_segments_wait_for_old_reader_close` |
| 查询词法分析器 | `lex` | 封闭语法保留偏移量和带引号文本 | `tests/unit/query_parser/test_lexer.py::test_lexer_preserves_offsets_and_quoted_text` |
| 查询解析器 | `parse_query` | 括号、一元运算、AND、OR 和隐式 OR 映射到封闭 AST | `tests/unit/query_parser/test_parser.py::test_and_binds_tighter_than_or` |
| 前缀改写 | `IndexReader.rewrite` | 有序词项展开具有严格的快速失败上限 | `tests/contract/test_prefix_rewrite.py::test_prefix_expansion_fails_instead_of_truncating` |
| 安全高亮 | `search_text(..., highlight_fields=...)` | 按偏移量重新分析存储文本，并对所有输出进行 HTML 转义 | `tests/contract/test_highlighting.py::test_highlight_uses_original_offsets_and_escapes_text` |
| 相关性指标 | `precision_at_k`, `recall_at_k`, `mean_reciprocal_rank`, `ndcg_at_k` | 纯函数消费排名，不导入索引内部实现 | `tests/evaluation/test_metrics.py::test_binary_metrics` |
| 分级排名指标 | `ndcg_at_k` | 分级增益按排名折损，并以理想顺序归一化 | `tests/evaluation/test_metrics.py::test_ndcg_uses_graded_relevance` |
| 参考相关性语料库 | 测试夹具 API | 排名与近似分数在提交、重开和合并后保持不变 | `tests/evaluation/test_reference_corpus.py::test_rankings_survive_commit_reopen_and_merge` |
| 本地 CLI 适配器 | `minilucene` | 创建、添加、搜索、删除和合并只调用公共 Python API | `tests/contract/test_cli.py::test_cli_create_add_search_delete_and_merge` |
| 验证失败原子性 | `IndexWriter.add_document` | 无效输入在 RAM 构建器发生变更前失败 | `tests/contract/test_memory_index.py::test_failed_document_validation_does_not_mutate_builder` |
| 分段发布失败 | `IndexWriter.flush` | 数据写入失败既不留下最终分段，也不留下临时目录 | `tests/storage/test_segment_store.py::test_failed_publish_never_creates_final_directory` |
| 完整孤儿恢复 | `Index.open` | 清单中不存在的完整分段在重启后不可见 | `tests/storage/test_commit_recovery.py::test_complete_segment_without_manifest_is_ignored_after_reopen` |
| 校验和损坏 | `Index.open_reader` | 搜索前，变更过的分段字节会使系统安全拒绝继续 | `tests/storage/test_segment_store.py::test_segment_store_rejects_checksum_corruption` |
| 变更后的过时读取器 | `IndexReader` | 旧读取器在 NRT 变更和合并过程中保留原始文档 | `tests/acceptance/test_phase3_nrt_mutation.py::test_nrt_mutation_merge_recovery_and_owner_zero` |
| 合并发布失败 | `IndexWriter.merge` | 输出发布失败不会交换写入器分段集合 | `tests/acceptance/test_failure_matrix.py::test_merge_publish_failure_preserves_writer_set` |
| 关闭故障聚合 | `IndexWriter.close` | 清理尝试会聚合故障，重复关闭是安全的 | `tests/acceptance/test_failure_matrix.py::test_repeated_close_aggregates_cleanup_failures` |
| 所有者归零收尾 | `Index.lifecycle_diagnostics` | 显式关闭释放每个读取器、写入器、分段、锁和临时作业 | `tests/acceptance/test_owner_zero.py::test_every_explicit_owner_and_temporary_job_reaches_zero` |
| 公共端到端闭环 | 文档记录的 Python API | 索引、查询、排名、高亮、刷新、变更、合并、重开与评估可以组合 | `tests/acceptance/test_end_to_end.py::test_documented_public_api_closes_the_v1_product_loop` |
| 无 TCP 或 HTTP 适配器 | 无 | V1 仅公开直接 Python 调用与本地 CLI 边界 | `tests/contract/test_behavior_matrix.py::test_v1_source_excludes_tcp_and_http_adapters` |
| 无分布式协调 | 无 | 复制、心跳、选举和集群均在 V1 范围之外 | `tests/contract/test_behavior_matrix.py::test_v1_source_excludes_distributed_coordination` |
| 无向量检索 | 无 | 向量字段、ANN 和混合检索仍属于 V2 工作 | `tests/contract/test_behavior_matrix.py::test_v1_source_excludes_vector_retrieval` |
| 不兼容 Lucene 编解码器 | 无 | 文件为 MiniLucene 教学分段文件 | `tests/contract/test_behavior_matrix.py::test_v1_segment_format_disclaims_lucene_codec_compatibility` |
| 无自动合并调度器 | 仅 `IndexWriter.merge` | 合并选择是显式且确定性的 | `tests/contract/test_behavior_matrix.py::test_v1_has_no_automatic_merge_scheduler` |
| 课程保持独立 | 无 | 此仓库是已完成的参考项目，不是课程内容 | `tests/contract/test_behavior_matrix.py::test_v1_repository_separates_course_material` |

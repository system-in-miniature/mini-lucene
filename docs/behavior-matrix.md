# MiniLucene V1 Executable Behavior Matrix

> **Language**: English | [简体中文](zh/behavior-matrix.md)

Every supported behavior and explicit non-goal below is bound to one stable
pytest node. The public API column names the boundary a user touches; it does
not claim Apache Lucene API or file-format compatibility.

| Feature | Public API | Semantic boundary | Executable test node ID |
|---|---|---|---|
| Field schema | `Schema`, `TextField`, `KeywordField`, `StoredField` | stored, indexed, tokenized, positions, and boost stay independent | `tests/contract/test_schema.py::test_stored_indexed_and_tokenized_are_independent` |
| Index lifecycle | `Index.create`, `Index.open` | persisted immutable schema fingerprints define one index | `tests/contract/test_index_lifecycle.py::test_create_open_and_schema_fingerprint` |
| Single writer | `Index.writer` | a second mutation owner cannot open for the same index | `tests/contract/test_index_lifecycle.py::test_only_one_writer_can_be_open` |
| Positional analyzer | `StandardAnalyzer.analyze` | lowercase and stopword filtering preserve original offsets and position gaps | `tests/unit/analysis/test_pipeline.py::test_standard_analysis_preserves_offsets_and_stopword_gap` |
| Exact keyword analysis | `KeywordField` | one complete value becomes one exact term without positions | `tests/contract/test_memory_index.py::test_keyword_field_indexes_one_exact_term_without_positions` |
| Immutable RAM segment | `RamIndexBuilder.freeze` | postings, positions, lengths, and stored values freeze together | `tests/contract/test_memory_index.py::test_ram_segment_contains_positions_lengths_and_only_stored_values` |
| Term query and stored fields | `TermQuery`, `MemoryIndex.search` | exact term matches return only declared stored values | `tests/contract/test_memory_search.py::test_public_memory_index_returns_stored_fields` |
| Phrase query | `PhraseQuery` | exact phrase matching depends on positions rather than term co-occurrence | `tests/contract/test_query_matching.py::test_phrase_requires_consecutive_positions` |
| Boolean query | `BooleanQuery` | MUST, SHOULD, and MUST_NOT use the frozen set semantics | `tests/contract/test_query_matching.py::test_should_is_required_without_must_and_optional_with_must` |
| Match-all query | `MatchAllQuery` | total hits can be counted without retaining result objects | `tests/contract/test_memory_search.py::test_match_all_can_report_total_without_returning_hits` |
| Global BM25 | `MemoryIndex.search`, `IndexReader.search` | TF saturation, IDF, length norm, and field boost use one live corpus view | `tests/evaluation/test_reference_corpus.py::test_bm25_term_frequency_saturates_instead_of_growing_linearly` |
| DAAT Boolean execution | `iter_scored_docs` | nested MUST, SHOULD, and MUST_NOT hits and scores match the preserved set oracle | `tests/unit/search/test_daat_scorer.py::test_daat_matches_set_oracle_for_seeded_random_corpora_and_queries` |
| Bounded Top-K | `search(..., top_k=K)` | collector retains at most K hits while counting all matches | `tests/unit/search/test_topk.py::test_heap_topk_matches_complete_sort_oracle` |
| Collect then fetch | `IndexSearcher.search` | stored fields and highlights are materialized only for final Top-K winners | `tests/contract/test_collect_then_fetch.py::test_search_fetches_stored_fields_only_for_final_top_k` |
| Educational segment codec | `IndexWriter.flush` | deterministic immutable files round-trip postings and stored data | `tests/storage/test_segment_store.py::test_segment_store_open_round_trips_image` |
| Flush visibility | `IndexWriter.flush` | flush creates a segment without changing the committed manifest | `tests/storage/test_writer_flush.py::test_flush_creates_segment_but_does_not_change_manifest` |
| Atomic commit | `IndexWriter.commit` | manifest replacement chooses the old or new committed root | `tests/storage/test_commit_recovery.py::test_manifest_replace_failure_preserves_previous_commit` |
| NRT refresh | `IndexWriter.refresh` | flushed state becomes reader-visible without becoming restart-durable | `tests/nrt/test_refresh_visibility.py::test_uncommitted_refresh_state_disappears_after_process_reopen` |
| Reader snapshot | `Index.open_reader` | an existing reader remains a point-in-time view after later commits | `tests/nrt/test_reader_snapshot.py::test_reader_snapshot_never_changes_after_later_commit` |
| Exact-term delete | `IndexWriter.delete_by_term` | immutable postings stay unchanged while live-doc masks hide matches | `tests/nrt/test_delete_by_term.py::test_old_reader_keeps_deleted_document_and_new_stats_exclude_it` |
| Atomic update | `IndexWriter.update_document` | update is delete-all-matches plus one validated add | `tests/nrt/test_update_document.py::test_invalid_replacement_leaves_delete_state_unchanged` |
| Explicit merge | `IndexWriter.merge` | selected immutable segments compact while preserving results and scores | `tests/nrt/test_segment_merge.py::test_merge_skips_deletes_and_preserves_search_results` |
| Segment ownership | `Index.collect_garbage`, `Index.lifecycle_diagnostics` | obsolete files wait for every reader and writer owner to release | `tests/nrt/test_segment_ownership.py::test_obsolete_segments_wait_for_old_reader_close` |
| Query lexer | `lex` | closed syntax preserves offsets and quoted text | `tests/unit/query_parser/test_lexer.py::test_lexer_preserves_offsets_and_quoted_text` |
| Query parser | `parse_query` | parentheses, unary, AND, OR, and implicit OR map to the closed AST | `tests/unit/query_parser/test_parser.py::test_and_binds_tighter_than_or` |
| Prefix rewrite | `IndexReader.rewrite` | sorted term expansion has a hard fail-fast cap | `tests/contract/test_prefix_rewrite.py::test_prefix_expansion_fails_instead_of_truncating` |
| Safe highlighting | `search_text(..., highlight_fields=...)` | stored text is re-analyzed by offset and all output is HTML-escaped | `tests/contract/test_highlighting.py::test_highlight_uses_original_offsets_and_escapes_text` |
| Relevance metrics | `precision_at_k`, `recall_at_k`, `mean_reciprocal_rank`, `ndcg_at_k` | pure functions consume rankings without importing index internals | `tests/evaluation/test_metrics.py::test_binary_metrics` |
| Graded ranking metric | `ndcg_at_k` | graded gains are discounted by rank and normalized by the ideal order | `tests/evaluation/test_metrics.py::test_ndcg_uses_graded_relevance` |
| Reference relevance corpus | test fixture API | rankings and approximate scores survive commit, reopen, and merge | `tests/evaluation/test_reference_corpus.py::test_rankings_survive_commit_reopen_and_merge` |
| Local CLI adapter | `minilucene` | create, add, search, delete, and merge call only public Python APIs | `tests/contract/test_cli.py::test_cli_create_add_search_delete_and_merge` |
| Validation failure atomicity | `IndexWriter.add_document` | invalid input fails before the RAM builder mutates | `tests/contract/test_memory_index.py::test_failed_document_validation_does_not_mutate_builder` |
| Segment publish failure | `IndexWriter.flush` | failed data writes leave neither a final segment nor a temporary directory | `tests/storage/test_segment_store.py::test_failed_publish_never_creates_final_directory` |
| Complete orphan recovery | `Index.open` | a complete segment absent from the manifest is not restart-visible | `tests/storage/test_commit_recovery.py::test_complete_segment_without_manifest_is_ignored_after_reopen` |
| Checksum corruption | `Index.open_reader` | changed segment bytes fail closed before search | `tests/storage/test_segment_store.py::test_segment_store_rejects_checksum_corruption` |
| Stale reader after mutation | `IndexReader` | old readers retain their original documents across NRT mutation and merge | `tests/acceptance/test_phase3_nrt_mutation.py::test_nrt_mutation_merge_recovery_and_owner_zero` |
| Merge publish failure | `IndexWriter.merge` | failed output publication does not swap the writer segment set | `tests/acceptance/test_failure_matrix.py::test_merge_publish_failure_preserves_writer_set` |
| Close failure aggregation | `IndexWriter.close` | cleanup attempts aggregate failures and repeated close is safe | `tests/acceptance/test_failure_matrix.py::test_repeated_close_aggregates_cleanup_failures` |
| Owner-zero closeout | `Index.lifecycle_diagnostics` | explicit close releases every reader, writer, segment, lock, and temporary job | `tests/acceptance/test_owner_zero.py::test_every_explicit_owner_and_temporary_job_reaches_zero` |
| Public end-to-end loop | documented Python API | index, query, rank, highlight, refresh, mutate, merge, reopen, and evaluate compose | `tests/acceptance/test_end_to_end.py::test_documented_public_api_closes_the_v1_product_loop` |
| No TCP or HTTP adapter | none | V1 exposes direct Python and local CLI boundaries only | `tests/contract/test_behavior_matrix.py::test_v1_source_excludes_tcp_and_http_adapters` |
| No distributed coordination | none | replication, heartbeat, election, and clustering are outside V1 | `tests/contract/test_behavior_matrix.py::test_v1_source_excludes_distributed_coordination` |
| No vector retrieval | none | vector fields, ANN, and hybrid retrieval remain V2 work | `tests/contract/test_behavior_matrix.py::test_v1_source_excludes_vector_retrieval` |
| No Lucene codec compatibility | none | files are MiniLucene educational segment files | `tests/contract/test_behavior_matrix.py::test_v1_segment_format_disclaims_lucene_codec_compatibility` |
| No automatic merge scheduler | `IndexWriter.merge` only | merge selection is explicit and deterministic | `tests/contract/test_behavior_matrix.py::test_v1_has_no_automatic_merge_scheduler` |
| Tutorial/runtime separation | `docs/tutorial/` | lessons stay in documentation rather than a `course/` or `chapters/` runtime tree | `tests/contract/test_behavior_matrix.py::test_v1_repository_separates_course_material` |

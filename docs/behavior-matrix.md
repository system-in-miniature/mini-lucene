# MiniLucene V1 Executable Behavior Matrix

Every supported behavior and explicit non-goal below is bound to one stable
pytest node. The public API column names the boundary a user touches; it does
not claim Apache Lucene API or file-format compatibility.

| Feature | Public API | Semantic boundary | Executable test node ID |
|---|---|---|---|
| Field schema | `Schema`, `TextField`, `KeywordField`, `StoredField` | stored, indexed, tokenized, positions, and boost stay independent | `tests/contract/test_schema.py::test_stored_indexed_and_tokenized_are_independent` |
| Positional analyzer | `StandardAnalyzer.analyze` | lowercase and stopword filtering preserve original offsets and position gaps | `tests/unit/analysis/test_pipeline.py::test_standard_analysis_preserves_offsets_and_stopword_gap` |
| Immutable RAM segment | `RamIndexBuilder.freeze` | postings, positions, lengths, and stored values freeze together | `tests/contract/test_memory_index.py::test_ram_segment_contains_positions_lengths_and_only_stored_values` |
| Phrase query | `PhraseQuery` | exact phrase matching depends on positions rather than term co-occurrence | `tests/contract/test_query_matching.py::test_phrase_requires_consecutive_positions` |
| Boolean query | `BooleanQuery` | MUST, SHOULD, and MUST_NOT use the frozen set semantics | `tests/contract/test_query_matching.py::test_should_is_required_without_must_and_optional_with_must` |
| Global BM25 | `MemoryIndex.search`, `IndexReader.search` | TF saturation, IDF, length norm, and field boost use one live corpus view | `tests/evaluation/test_reference_corpus.py::test_bm25_term_frequency_saturates_instead_of_growing_linearly` |
| Bounded Top-K | `search(..., top_k=K)` | collector retains at most K hits while counting all matches | `tests/unit/search/test_topk.py::test_heap_topk_matches_complete_sort_oracle` |
| Educational segment codec | `IndexWriter.flush` | deterministic immutable files round-trip postings and stored data | `tests/storage/test_segment_store.py::test_segment_store_open_round_trips_image` |
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
| Reference relevance corpus | test fixture API | rankings and approximate scores survive commit, reopen, and merge | `tests/evaluation/test_reference_corpus.py::test_rankings_survive_commit_reopen_and_merge` |
| Local CLI adapter | `minilucene` | create, add, search, delete, and merge call only public Python APIs | `tests/contract/test_cli.py::test_cli_create_add_search_delete_and_merge` |
| No TCP or HTTP adapter | none | V1 exposes direct Python and local CLI boundaries only | `tests/contract/test_behavior_matrix.py::test_v1_source_excludes_tcp_and_http_adapters` |
| No distributed coordination | none | replication, heartbeat, election, and clustering are outside V1 | `tests/contract/test_behavior_matrix.py::test_v1_source_excludes_distributed_coordination` |
| No vector retrieval | none | vector fields, ANN, and hybrid retrieval remain V2 work | `tests/contract/test_behavior_matrix.py::test_v1_source_excludes_vector_retrieval` |
| No Lucene codec compatibility | none | files are MiniLucene educational segment files | `tests/contract/test_behavior_matrix.py::test_v1_segment_format_disclaims_lucene_codec_compatibility` |
| No automatic merge scheduler | `IndexWriter.merge` only | merge selection is explicit and deterministic | `tests/contract/test_behavior_matrix.py::test_v1_has_no_automatic_merge_scheduler` |
| Course remains separate | none | this repository is the completed reference project, not course content | `tests/contract/test_behavior_matrix.py::test_v1_repository_separates_course_material` |

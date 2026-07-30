> **Language**: English | [简体中文](zh/lucene-mapping.md)

# MiniLucene → Apache Lucene mapping

MiniLucene is a teaching implementation, not an Apache Lucene-compatible
codec or API. This guide maps the small Python modules to the production
concepts they are meant to expose and calls out places where copying the
MiniLucene mental model into real Lucene would be wrong.

## How to read the labels

- **Equivalent**: the same conceptual invariant is being taught. Names, APIs,
  concurrency guarantees, and bytes on disk can still differ.
- **Intentionally simplified**: the production concept is recognizable, but
  important machinery or query types are omitted.
- **Semantics reversed**: MiniLucene deliberately or accidentally makes a
  choice opposite to current Lucene. Treat these rows as warnings, not as a
  smaller implementation of the same behavior.

## Module and format mapping

| Level | MiniLucene module or format | Apache Lucene counterpart | What carries over, and what does not |
|---|---|---|---|
| **Equivalent** | `manifest.json` (`storage/manifest.py`) | `SegmentInfos` and the latest `segments_N` commit file | Both are the atomically published root that names the segment generations belonging to one durable commit. The JSON layout is custom and is not a Lucene file format. |
| **Equivalent** | `live_*.bin` (`storage/live_docs.py`) | `LiveDocsFormat`, `.liv` files, and `Bits` live-doc views | Postings stay immutable while a generation-stamped bitset hides deleted local doc IDs. The encoding and naming are MiniLucene-specific. |
| **Intentionally simplified** | `storage/codec.py`, `storage/segment_store.py`, `terms.bin`, `postings.bin`, `stored.bin`, `norms.bin` | `Codec` plus `PostingsFormat`, `StoredFieldsFormat`, `NormsFormat`, and related per-segment files | The split teaches format ownership, delta encoding, checksums, and strict decoding. It omits Lucene codecs such as BlockTree terms, skip data, packed blocks, compound files, and format compatibility. |
| **Equivalent** | `analysis/pipeline.py` | `Analyzer`, `TokenStream`, `Tokenizer`, and `TokenFilter` | A tokenizer produces tokens and filters transform the stream while attributes such as term, position, and offsets survive the pipeline. Python tuples replace Lucene's reusable attribute stream. |
| **Equivalent** | `analysis/standard.py` position and offset handling | `PositionIncrementAttribute` and `OffsetAttribute` | Removing a stopword does not renumber later tokens, so a phrase cannot jump across the removed source position. Tokenization and the one-word default stop set are only educational. |
| **Intentionally simplified** | `writer.py` | `IndexWriter` | It owns buffering, immutable segment publication, deletion generations, refresh, commit, and explicit merge, but has no rollback or `prepareCommit`. |
| **Intentionally simplified** | one `RamIndexBuilder` in `writer.py` | `DocumentsWriterPerThread` (DWPT), flush control, and indexing chains | MiniLucene has a single-threaded RAM buffer. There is no per-thread indexing, concurrent flush, reader pool, or Lucene-style writer concurrency model. |
| **Equivalent** | `storage/registry.py` | `IndexDeletionPolicy`, `IndexFileDeleter`, and reader/file reference counting | Obsolete segments are reclaimed only after the durable commit and all process-local owners stop referencing them. Unlike Lucene, ownership here is an in-process registry and does not protect readers in another process. |
| **Intentionally simplified** | `reader.py` (`IndexReader`) and `snapshot.py` | `DirectoryReader`, leaf readers, and point-in-time reader snapshots | A reader freezes a segment/live-doc view and remains unchanged after later refreshes. MiniLucene eagerly materializes segment images and has no shared `SegmentReader`/core cache. |
| **Intentionally simplified** | `search/reader.py` (`ReaderView`) | low-level leaf/composite reader access used by search | It translates global doc IDs, exposes postings/stored fields, and builds corpus statistics, but it is an internal query-facing view rather than a public lifecycle owner. |
| **Semantics reversed** | live-only corpus statistics in `search/reader.py` | Lucene term statistics before merge | MiniLucene excludes deleted documents from `docFreq`, document count, and average lengths immediately. Lucene's segment statistics still include deleted documents until merge, so merge can change scores in real Lucene; MiniLucene erases that phenomenon. |
| **Intentionally simplified** | `query/match.py` and `search/scorer.py` | `PostingsEnum`, `DocIdSetIterator`, `Scorer`, `ConjunctionScorer`, `DisjunctionScorer`, and two-phase iteration | MiniLucene materializes complete `set[int]` matches and `dict[int, float]` scores. It has no doc-at-a-time cursors, postings skipping, conjunction/disjunction merge, or two-phase iterator. |
| **Semantics reversed** | `search/searcher.py` plus `search/collector.py` | `IndexSearcher`, `Collector`/`LeafCollector`, `TopScoreDocCollector`, then stored-field/highlight fetch | MiniLucene loads stored fields and computes highlights for every match before offering it to the Top-K heap. Lucene normally collects doc ID/score first and fetches expensive hit content only for the winners. MiniLucene retains only O(K) hit objects, but its stored-field I/O and highlighting work remain O(total hits). |
| **Semantics reversed** | phrase branch in `search/scorer.py` | `PhraseQuery`, phrase matcher, phrase frequency, and similarity scoring | MiniLucene first verifies adjacency, then sums BM25 contributions of the component terms. Lucene scores using phrase frequency; repeated phrases and scattered term frequency therefore rank differently. |
| **Intentionally simplified** | `query/model.py`, `query_parser/`, and `search/rewrite.py` | Lucene `Query` subclasses, query parser, and multi-term query rewrite | Term, boolean, exact phrase, prefix, and match-all queries form a closed teaching AST. Phrase slop, fuzzy/wildcard/regex queries, numeric/range queries, and most rewrite strategies are absent. |
| **Semantics reversed** | `boost` on `FieldType` in `schema.py` | query-time boosts such as `BoostQuery` | MiniLucene fixes boost in the schema and applies it while scoring every query. Lucene 7.0 removed index-time field boosts and retains query-time boost, so the supported direction is the opposite. |
| **Intentionally simplified** | string-only `schema.py` and `document.py` | `FieldType`, point fields/BKD trees, doc values, stored fields, and term vectors | MiniLucene has only text/keyword/stored strings. It has no numeric or date fields, range query, doc values, field sorting, aggregation/faceting, term vectors, payloads, or multi-valued fields. |
| **Intentionally simplified** | explicit `merge()` and `merge.py` | `MergePolicy`, `MergeScheduler`, and `IndexWriter` merge execution | Live documents are copied into one immutable segment with dense local doc IDs, but there is no automatic or tiered merge policy and no background scheduling. |
| **Intentionally simplified** | `highlight.py` | Lucene highlighters using postings offsets, term vectors, or re-analysis | MiniLucene re-analyzes stored text. Consequently an indexed-but-not-stored field cannot be highlighted, even though real Lucene can be configured with offsets or term vectors for highlighting. |
| **Intentionally simplified** | `.writer.lock` in `writer.py` | Lucene `LockFactory`/`NativeFSLockFactory` and `IndexWriter` write lock | `O_EXCL` prevents two writers, but a crash leaves the file behind permanently. The PID is informational only; there is no stale-lock validation or force-unlock API. |

## Query-execution warning

The most important gap is not merely the absence of WAND or SIMD. MiniLucene
does not contain a doc-at-a-time execution path at all:

```text
MiniLucene: postings → complete sets → complete score dictionary
Lucene:     postings cursors → scorer iteration → collector → top doc IDs
                                                       ↓
                                            stored fields/highlighting
```

`TopKCollector` does bound the number of retained hit objects to K. It does
not make the current search path O(K): `IndexSearcher.search` reads stored
fields and highlights every matching document before the heap can discard it.

## Other boundaries readers should know

- Phrase matching preserves analyzer position gaps, but phrase scoring is the
  sum of term BM25 scores rather than BM25 over phrase frequency.
- BM25 statistics use only live documents. Real Lucene retains deleted
  documents in segment statistics until merge, which is why production merge
  can change scores.
- Boost belongs to the MiniLucene schema. Current Lucene supports query-time
  boost instead; the directions are opposite.
- Numeric/date fields, doc values, range queries, field sorting, aggregation,
  and faceting are outside the implementation.
- A process crash can strand `.writer.lock`; closing normally removes it, but
  the project has no recovery or unlock API.
- Highlighting requires a stored `TextField`, because MiniLucene re-analyzes
  stored text instead of reading index offsets or term vectors.

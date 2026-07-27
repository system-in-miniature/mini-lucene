# MiniLucene Reference Project Design

**Date:** 2026-07-27  
**Status:** Approved by delegated final-acceptance authority  
**Repository:** `~/MiniLucene-workspace/MiniLucene`

## 1. Goal

MiniLucene is a compact, usable Python full-text search engine whose code maps
directly to the mechanisms that make Lucene useful:

```text
fielded documents
→ analysis with positions and offsets
→ positional inverted index
→ Query AST
→ BM25 scoring
→ bounded Top-K collection
→ immutable disk segments
→ reader snapshots and refresh
→ delete/update overlays
→ segment merge
```

The project exists to explain search behavior and storage semantics. It is not
a file-format-compatible or performance-compatible Lucene implementation.

The finished repository is the reference project. Course material will be
designed later in a separate repository and will not be generated during this
implementation.

## 2. Design principles inherited from MiniRedis

1. **Domain mechanism first.** Search behavior, index visibility, and segment
   ownership dominate the design.
2. **Direct-first.** The Python API is the primary boundary. A CLI may be a
   final thin adapter; TCP, HTTP, authentication, and deployment are absent.
3. **One semantic owner per transition.** `IndexWriter` serializes mutations;
   `IndexReader` owns an immutable point-in-time view.
4. **Stable domain values cross boundaries.** An analyzer emits immutable
   `Token` values, flush emits immutable `SegmentImage` metadata, and readers
   consume immutable segment snapshots.
5. **Errors do not partially publish state.** Failed analysis, flush, commit,
   delete publication, or merge cannot produce a half-visible index.
6. **Behavior before optimization.** Positions, corpus statistics, global
   scoring, visibility, and live-doc semantics are required. BlockTree, FST,
   WAND, SIMD, mmap tuning, and production codecs are not.
7. **Failure experiments are executable.** Crash boundaries and stale-reader
   behavior are proved by tests, not only described.
8. **Project and course remain separate.** Chapter count is not a project
   architecture constraint.

## 3. Version boundary

### V1: complete lexical-search loop

V1 includes:

- fielded documents and a frozen schema;
- `TextField`, `KeywordField`, and stored-only fields;
- composable analyzers with term, position, and source offsets;
- an in-memory positional inverted index;
- term, boolean, phrase, prefix, and match-all queries;
- BM25 with field boosts and global live-document statistics;
- bounded Top-K collection and deterministic tie-breaking;
- stored-field retrieval and simple offset-based highlighting;
- immutable checksummed disk segments;
- RAM buffering, flush, atomic commit, and recovery;
- point-in-time readers and explicit near-real-time refresh;
- delete-by-term, update as delete-plus-add, and live-doc overlays;
- segment merge with doc-ID remapping;
- a deliberately small query parser;
- a small relevance-evaluation toolkit and accepted corpus.

### V2: optional retrieval extensions

V2 may add a brute-force `VectorField`, cosine Top-K, and RRF or weighted
lexical/vector fusion. V1 contains no placeholder vector implementation and no
vector-specific storage branch.

### Explicit non-goals

V1 does not implement:

- Lucene index-file compatibility;
- Java API compatibility;
- full Lucene query syntax;
- fuzzy queries, regex queries, span queries, facets, joins, or aggregations;
- FST, BlockTree, BKD, HNSW, WAND, Block-Max WAND, skip lists, or SIMD;
- production compression, mmap tuning, parallel segment search, or distributed
  search;
- index replication, sharding, cluster membership, election, or failover;
- HTTP, TCP, authentication, ACL, TLS, or a hosted service;
- automatic background merge scheduling;
- vector or hybrid retrieval in V1.

## 4. Public API and product behavior

The public API is a local Python library:

```python
schema = Schema(
    id=KeywordField(stored=True),
    title=TextField(stored=True, boost=2.0),
    body=TextField(stored=True),
    author=KeywordField(stored=True),
)

index = Index.create(path, schema)

with index.writer() as writer:
    writer.add_document(
        id="doc-1",
        title="Understanding Kafka Replication",
        body="Kafka uses partition leaders and follower replicas.",
        author="jonah",
    )
    writer.commit()

reader = index.open_reader()
searcher = IndexSearcher(reader)
result = searcher.search(
    parse_query('title:kafka AND body:"follower replicas"', schema),
    top_k=10,
    highlight_fields=("body",),
)
reader.close()
```

Binary document values are outside V1. Input and stored values are Unicode
strings; term bytes on disk use strict UTF-8. Invalid field names, missing
values, and schema mismatches fail before the writer mutates its RAM buffer.

The schema is persisted when the index is created and is immutable for that
index. Opening with a different schema fails with a schema-fingerprint error.

## 5. Domain model

### 5.1 Fields and schema

Each field freezes these properties:

```python
FieldType(
    indexed: bool,
    tokenized: bool,
    stored: bool,
    store_positions: bool,
    boost: float,
    analyzer_name: str | None,
)
```

- `TextField` is indexed, tokenized, and positional.
- `KeywordField` is indexed as exactly one term and is not tokenized.
- `StoredField` is stored but not indexed.
- Stored and indexed are independent.
- Field boost must be finite and positive.
- Unknown fields and values that are not strings are rejected.

Documents are frozen mappings from field name to string. A document may omit a
field, but it may not contain an undeclared field.

V1 does not enforce a unique primary key. Lucene-style update is explicit:

```python
writer.update_document(Term("id", "doc-1"), replacement)
```

It deletes every live document matching the exact term in the writer's current
view and then adds the replacement document.

### 5.2 Analysis

The analysis pipeline has explicit, independently testable units:

```text
text
→ optional CharacterFilter
→ Tokenizer
→ zero or more TokenFilter values
→ immutable Token stream
```

Every token contains:

```python
Token(
    term: str,
    position: int,
    start_offset: int,
    end_offset: int,
)
```

Required built-ins:

- `StandardTokenizer`: deterministic Unicode word tokenization;
- `KeywordTokenizer`: the whole input as one token;
- `LowercaseFilter`;
- `StopwordFilter`.

Removing a stop word preserves the positional gap. Offsets always refer to the
original input string. V1 character filters may only perform
length-preserving transformations, avoiding offset-correction machinery.

Index-time and query-time analysis call the same field analyzer. Phrase and
prefix syntax parse structure first, then analyze applicable text.

### 5.3 In-memory index

The RAM buffer owns:

```text
postings[field][term] -> ordered postings
stored_documents[local_doc_id]
field_lengths[field][local_doc_id]
term_document_frequency[field][term]
```

A posting contains:

```python
Posting(
    doc_id: int,
    term_frequency: int,
    positions: tuple[int, ...],
)
```

Document IDs inside a RAM buffer or segment are dense, zero-based, and local to
that owner. They are never stable application identifiers.

Posting lists are strictly ordered by local doc ID. Positions are strictly
increasing. Term frequency equals the number of positions for positional
fields.

## 6. Query and scoring model

### 6.1 Query AST

The closed V1 query union is:

- `TermQuery(field, term)`;
- `PhraseQuery(field, terms, positions=None, slop=0)`, where `None` means
  consecutive normalized positions;
- `PrefixQuery(field, prefix)`;
- `BooleanQuery(clauses)`;
- `MatchAllQuery()`.

Boolean occurrences are `MUST`, `SHOULD`, and `MUST_NOT`.

Boolean semantics are fixed:

- every `MUST` clause must match;
- every `MUST_NOT` clause removes a candidate;
- if there is no `MUST`, at least one `SHOULD` must match;
- if there is a `MUST`, `SHOULD` is optional and contributes score;
- a query containing only `MUST_NOT` matches nothing.

Phrase queries require their normalized query positions at `slop=0`. Stopword
gaps remain visible, so phrase construction subtracts the first surviving
token position but does not renumber later tokens. For example, analyzing
`"distributed the system"` may produce positions `(0, 2)`, which does not
match adjacent `"distributed system"`.

Prefix queries expand against the sorted per-field term dictionary. Expansion
has a configured hard cap and fails explicitly when exceeded; it never scans
stored documents.

### 6.2 Global BM25

BM25 defaults match Lucene's common values:

```text
k1 = 1.2
b = 0.75
```

Scoring uses live documents only:

```text
N                    global live-document count
df(field, term)      global live-document frequency across segments
tf(field, term, doc) term frequency
dl(field, doc)       analyzed field length
avgdl(field)         global average live field length
```

Term scores use BM25 term-frequency saturation and length normalization, then
multiply by the schema field boost. Boolean scores sum matching positive
clauses. Phrase matching is a filter plus the sum of its component term scores;
V1 adds no hidden phrase bonus. `MUST_NOT` never contributes score.

All segment scorers receive one immutable global `CorpusStats` snapshot. A
segment must not compute local IDF.

### 6.3 Scorer and Top-K collector

Matching and scoring are separate:

```text
Query
→ rewrite
→ Weight with CorpusStats
→ per-segment Scorer
→ TopKCollector
→ TopDocs
```

`TopKCollector` keeps at most K hits in a min-heap. It does not materialize and
sort every hit.

Final order is:

1. score descending;
2. segment generation ascending;
3. local doc ID ascending.

This tie-break is deterministic but is not a relevance promise.

## 7. Disk segment format

Segments are immutable directories:

```text
segments/
└── seg_000001/
    ├── segment.json
    ├── terms.bin
    ├── postings.bin
    ├── stored.bin
    └── norms.bin
```

`segment.json` contains:

- format magic and version;
- segment generation;
- schema fingerprint;
- max doc count;
- file lengths and SHA-256 checksums;
- codec identifiers.

The implementation uses simple, documented codecs:

- sorted UTF-8 field/term dictionary with offsets into `postings.bin`;
- unsigned varints;
- delta-encoded doc IDs and positions;
- length-framed canonical UTF-8 JSON for stored fields;
- per-field integer document lengths in `norms.bin`.

The codec is educational, deterministic, and checksum-validated. It is not
Lucene's codec.

Segment creation is:

```text
build complete immutable SegmentImage in memory
→ write files into a unique temporary directory
→ fsync every file
→ write and fsync segment.json last
→ fsync temporary directory
→ atomic rename to final segment directory
→ fsync segments directory
```

A reader rejects unknown versions, checksum mismatches, invalid offsets,
non-monotonic postings, and schema mismatches.

## 8. Writer, commit, and recovery

`IndexWriter` is the only mutation owner. It owns:

- one RAM buffer;
- the writer's ordered segment set;
- pending delete terms;
- live-doc overlays;
- the next segment and commit generations;
- one lifecycle state.

The public writer API is not thread-safe. Concurrent callers must serialize
access outside the writer; tests prove a second writer lock cannot open for the
same index.

### 8.1 Flush

Flush converts the current RAM buffer into a new immutable segment and clears
the buffer. Flush does not update the committed manifest and is not, by itself,
recoverable or visible to an existing reader.

Automatic flush is driven by a deterministic logical threshold measured in
buffered documents and token/posting counts, not RSS.

### 8.2 Commit

The manifest is the only committed root:

```text
manifest.json
```

It contains:

- format version and schema fingerprint;
- commit generation;
- ordered segment generations;
- live-doc generation and checksum for every segment;
- next generation counters.

Commit performs:

```text
flush RAM buffer
→ materialize new immutable live-doc files
→ fsync all referenced files/directories
→ write manifest.tmp
→ fsync manifest.tmp
→ atomic rename to manifest.json
→ fsync index directory
```

After a crash, opening the index sees either the old manifest or the new
manifest. Unreferenced complete segments and temporary files are orphans and
are ignored. Recovery never guesses that an orphan should be committed.

## 9. Reader snapshots and near-real-time visibility

`IndexReader` owns an immutable snapshot of:

- the ordered segment handles;
- one immutable live-doc mask per segment;
- the corpus statistics derived from those live docs;
- the schema fingerprint.

An existing reader never changes.

The three boundaries are distinct:

- **flush:** creates an immutable segment;
- **refresh:** publishes a new in-process reader snapshot from the writer's
  current flushed segments and delete overlays;
- **commit:** publishes a recoverable manifest.

`writer.refresh()` flushes pending documents and returns a new reader. It does
not commit. A process crash may therefore lose data that was visible to an NRT
reader.

`index.open_reader()` reads only the committed manifest. Old readers remain
usable after refresh, commit, delete, update, and merge until explicitly
closed.

Segment handles are reference-counted by the index directory owner. Obsolete
segment directories are deleted only after they are absent from the committed
manifest and no live reader or writer snapshot references them.

## 10. Delete, update, and merge

Segments and postings never mutate in place.

Delete-by-term creates a new immutable live-doc mask generation. It applies to
all documents visible in the writer's current view, including buffered
documents.

Update is exactly:

```text
delete_by_term(term)
→ add_document(replacement)
```

Delete and replacement become visible together at the next refresh and
recoverable together at the next commit.

Merge is explicit in V1:

```python
writer.merge(segment_ids)
```

It:

1. captures the selected segments and live-doc masks;
2. skips deleted documents;
3. assigns dense new local doc IDs;
4. merges term dictionaries, postings, positions, stored fields, and norms;
5. writes one new immutable segment;
6. swaps the writer's segment set atomically;
7. publishes only on refresh or commit.

Merge failure leaves the old segment set authoritative. Merge output becomes
an ignored orphan until safely removed. V1 has no background merge scheduler
and therefore no concurrent merge/write race.

## 11. Query parser and highlighting

The parser accepts this closed syntax:

```text
kafka
title:kafka
"kafka replication"
kafka AND replication
kafka OR rabbitmq
NOT kafka
-kafka
title:kaf*
(kafka OR rabbitmq) AND replication
```

Precedence is:

```text
parentheses > unary NOT/- > AND > OR
```

Adjacent expressions use implicit `OR`. Bare terms and phrases use the
configured default field. A prefix wildcard is allowed only as the final
character of one term. Invalid syntax reports an offset and never silently
rewrites to a different query.

Highlighting is deliberately simple:

- it works only on stored `TextField` values;
- it re-analyzes the stored value with the field's analyzer;
- it derives matching token offsets from the rewritten query;
- it returns escaped text fragments with `<em>...</em>`;
- phrase highlighting uses the matched positional sequence;
- it does not attempt sentence scoring or multi-fragment optimization.

Because highlighting re-analyzes stored text, postings do not store offsets in
V1. Token offsets remain a first-class analyzer contract.

## 12. Evaluation

`minilucene.evaluation` provides:

- `precision_at_k`;
- `recall_at_k`;
- `mean_reciprocal_rank`;
- `ndcg_at_k`.

The accepted project includes a small deterministic corpus, queries, and
relevance labels. Evaluation is a read-only consumer of `TopDocs`; metrics do
not influence scoring or index state.

The acceptance corpus proves:

- field boosts change ranking;
- BM25 term frequency saturates;
- phrase queries change recall relative to boolean conjunction;
- deleted documents contribute neither hits nor corpus statistics;
- rankings are equal before and after flush/commit/reopen/merge.

## 13. Failure and lifecycle semantics

Every owner is explicit:

- `IndexWriter`;
- RAM buffer;
- temporary segment job;
- committed manifest;
- `IndexReader`;
- segment handle/reference;
- optional CLI adapter.

Required failure experiments:

1. analysis or validation fails before buffer mutation;
2. segment file write fails before directory rename;
3. segment completes but manifest replacement never happens;
4. manifest replacement succeeds while old files remain;
5. checksum corruption fails open without partial index publication;
6. refresh-visible but uncommitted documents disappear after simulated crash;
7. old reader retains its old snapshot after refresh;
8. merge fails before writer segment-set swap;
9. close is idempotent and leaves no writer lock, temporary job, reader, or
   segment handle.

Close order is:

```text
stop writer admission
→ finish or fail current owned mutation
→ close unpublished reader snapshots owned by writer
→ release segment handles
→ release writer lock
```

Closing one reader does not invalidate another reader. Closing the index waits
for no external reader; it reports retained reader owners instead of forcibly
invalidating them.

## 14. Testing strategy

Tests are Direct-first and grouped by evidence:

```text
tests/unit/          analyzers, codecs, varints, parser, BM25 math
tests/contract/      public schema/index/writer/reader/search behavior
tests/storage/       flush, commit, recovery, corruption, orphan handling
tests/nrt/           refresh, stale readers, delete/update, merge
tests/evaluation/    ranking counterexamples and metrics
tests/acceptance/    full lifecycle and owner-zero checks
```

Core test rules:

- use injected filesystem operations at crash boundaries;
- use frozen small corpora with hand-computed postings and scores;
- compare heap Top-K with a complete-sort oracle;
- compare multi-segment scoring with a one-segment equivalent index;
- compare pre-merge and post-merge logical hits and scores;
- reject tests that inspect only internal dictionaries without exercising a
  public behavior;
- no network adapter becomes a semantic oracle;
- no skipped or xfailed core test is used for acceptance.

## 15. Architecture and phase plan

The implementation will be planned as four independently accepted phases:

### Phase 1: retrieval kernel

```text
Schema/Document
→ Analyzer/Token
→ RAM positional postings
→ Query AST and execution
→ global BM25
→ bounded Top-K
```

Acceptance: an in-memory fielded search engine supports exact, boolean, phrase,
prefix, ranked Top-K, stored fields, and deterministic counterexamples.

### Phase 2: immutable storage and commit

```text
SegmentImage
→ term/postings/stored/norm codecs
→ checksummed segment directory
→ IndexWriter flush
→ atomic manifest commit
→ committed reader recovery
```

Acceptance: restart sees only a complete old or new commit, and disk search is
equivalent to the in-memory oracle.

### Phase 3: NRT mutation and merge

```text
reader snapshot
→ refresh
→ live-doc masks
→ delete/update
→ explicit merge
→ reference-owned cleanup
```

Acceptance: old/new readers have deterministic visibility, refresh differs
from commit, crash loses only uncommitted NRT state, and merge preserves
logical search behavior.

### Phase 4: product closure and final acceptance

```text
query parser
→ highlighting
→ evaluation metrics/corpus
→ optional thin CLI
→ behavior matrix
→ owner-zero lifecycle acceptance
```

Acceptance: the public API performs realistic local search, all documented
features link to executable evidence, all owners settle, and the worktree is
clean.

## 16. Success criteria

The project is accepted only when:

- a realistic fielded corpus can be indexed, committed, reopened, refreshed,
  updated, deleted, merged, searched, ranked, and highlighted;
- phrase matching demonstrably depends on positions;
- BM25 uses global live-document statistics and bounded Top-K;
- stored/indexed/tokenized semantics are independently visible;
- flush, refresh, and commit have distinct executable behavior;
- old readers remain point-in-time snapshots;
- delete and update never rewrite postings in place;
- crash tests prove atomic manifest publication and orphan tolerance;
- pre-merge and post-merge results are logically equivalent;
- every public feature is mapped to a named test in a behavior matrix;
- the full suite, static checks, compile checks, and repository cleanliness
  pass;
- no course directory or course chapters are created.

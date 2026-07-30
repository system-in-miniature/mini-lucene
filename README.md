> **Language**: English | [简体中文](README.zh-CN.md)

# MiniLucene

MiniLucene is a direct-first Python reference implementation of the mechanisms
that make lexical search work. It connects field schemas, analysis, positional
inverted indexes, BM25, bounded Top-K collection, immutable disk segments,
point-in-time readers, near-real-time refresh, deletion, update, and merge in
one small system.

The project is intentionally not a clone of Apache Lucene. It does not promise
Lucene API or file-format compatibility, production performance, network
serving, distributed coordination, or vector retrieval.

## Quickstart

```python
from pathlib import Path

from minilucene import Index, KeywordField, Schema, TextField

schema = Schema(
    id=KeywordField(stored=True),
    title=TextField(stored=True, boost=2.0),
    body=TextField(stored=True),
)

index = Index.create(Path("./example-index"), schema)
with index.writer() as writer:
    writer.add_document(
        id="doc-1",
        title="Understanding Kafka Replication",
        body="Kafka uses partition leaders and follower replicas.",
    )
    writer.commit()

with index.open_reader() as reader:
    results = reader.search_text(
        'title:kafka OR body:"follower replicas"',
        default_field="body",
        top_k=10,
        highlight_fields=("title", "body"),
    )
    for hit in results.hits:
        print(hit.score, dict(hit.stored_fields), dict(hit.highlights))

index.close()
```

The same public boundary is available through a thin local CLI:

```text
minilucene create INDEX --schema SCHEMA_JSON
minilucene add INDEX DOCUMENT_JSON...
minilucene search INDEX QUERY --default-field body --top-k 10
minilucene delete INDEX FIELD TERM
minilucene merge INDEX SEGMENT...
```

## Mental model

```text
Document + Schema
        ↓
field Analyzer → tokens + positions + offsets
        ↓
RAM inverted index
        ↓ flush
immutable Segment
        ↓ refresh
new point-in-time Reader
        ↓ commit
atomically published restart root

query text → lexer → parser → Query AST → prefix rewrite
                                          ↓
                          matching → global BM25
                                          ↓
                         stored fields + highlighting
                           for every matching document
                                          ↓
                                      Top-K heap
```

`TextField` is tokenized and positional. `KeywordField` indexes the complete
value as one exact term. `StoredField` is returned with hits but cannot be
searched. Stored and indexed are independent properties.

The standard analyzer lowercases tokens and preserves source offsets and
position gaps. Phrase queries therefore distinguish adjacent terms from terms
separated in the original text. Highlighting re-analyzes stored `TextField`
values, uses those offsets, and HTML-escapes all original text.

BM25 statistics are global to one reader snapshot and include only live
documents. The Top-K collector retains only K hit objects while still
reporting the complete hit count. This is an in-memory bound, not an O(K)
search pipeline: the current searcher reads stored fields and computes
highlights for every match before collection.

## Flush, refresh, and commit

- `flush` turns the writer's RAM buffer into an immutable segment. It is not
  yet a durable index root.
- `refresh` returns a new reader that sees the writer's flushed state. Older
  readers remain unchanged.
- `commit` atomically replaces the manifest. Reopening after a process exit
  sees only this committed root.

Segments are immutable. Delete publishes a live-document mask. Update validates
the replacement, deletes all exact-term matches, then adds one replacement.
Merge explicitly combines selected segments, skips deleted documents, remaps
local document IDs, and atomically updates the writer's segment set. It is not
automatically scheduled.

Readers and writers register segment ownership. Garbage collection removes a
complete obsolete segment only after it is absent from the committed manifest
and every process-local owner has released it.

## Scope

V1 supports:

- fielded Unicode documents and stored-field retrieval;
- standard and keyword analysis;
- term, boolean, phrase, prefix, and match-all queries;
- global BM25, field boost, deterministic bounded Top-K;
- deterministic educational segment files with checksums;
- atomic commit, restart recovery, NRT refresh, delete, update, and merge;
- query parsing, safe highlighting, relevance metrics, fixtures, and local CLI.

V1 deliberately excludes:

- TCP, HTTP, RESP, or remote-client compatibility;
- replication, heartbeats, elections, clustering, and sharding;
- Apache Lucene codecs, FST/BlockTree, WAND, SIMD, or production tuning;
- doc-at-a-time iterators (`PostingsEnum`, conjunction/disjunction scorers,
  and two-phase iteration); matching and scoring materialize full sets/maps;
- numeric/date fields, doc values, range queries, field sorting, aggregation,
  and faceting;
- vector fields, HNSW, hybrid retrieval, and automatic merge scheduling;
- course chapters or lesson content.

## Important differences from Apache Lucene

Several boundaries are more than missing optimizations:

- **Intentionally simplified:** Search is full-set algebra, not doc-at-a-time
  iteration. `PostingsEnum`,
  `ConjunctionScorer`, and related cursor/skip machinery do not exist.
- **Semantics reversed:** Stored fields and highlights are produced for every
  match before Top-K
  collection. Lucene normally collects doc IDs/scores first and fetches only
  the winning hits.
- **Semantics reversed:** Phrase matches are scored as the sum of their terms'
  BM25 scores, not from phrase frequency.
- **Semantics reversed:** BM25 statistics exclude deleted documents
  immediately. Lucene segment
  statistics include them until merge, so MiniLucene does not demonstrate the
  production phenomenon where merge can change scores.
- **Semantics reversed:** Boost is fixed in the schema. Lucene 7.0 removed
  index-time field boost and retains query-time boost, making the supported
  direction the opposite.
- **Intentionally simplified:** There are no numeric fields, doc values, or
  range queries.
- **Intentionally simplified:** A crashed process can leave `.writer.lock`
  behind permanently; there is no stale-lock recovery or force-unlock API.
- **Intentionally simplified:** Highlighting re-analyzes stored text, so an
  indexed-but-not-stored field cannot be highlighted.

See [MiniLucene → Apache Lucene mapping](docs/lucene-mapping.md) for the
module-by-module **Equivalent / Intentionally simplified / Semantics
reversed** table.

The course will be designed separately after this reference project is
accepted.

## Development

```bash
uv sync --dev
uv run ruff check src tests tools
uv run pytest -q
uv run python -m compileall -q src tests tools
git diff --check
```

Architecture and evidence:

- [Frozen design](docs/superpowers/specs/2026-07-27-minilucene-reference-project-design.md)
- [Implementation plans](docs/superpowers/plans/2026-07-27-minilucene-reference-project.md)
- [Segment format](docs/segment-format.md)
- [MiniLucene → Apache Lucene mapping](docs/lucene-mapping.md)
- [Phase 1: retrieval kernel](docs/phase1-retrieval-kernel.md)
- [Phase 2: storage and commit](docs/phase2-storage-commit.md)
- [Phase 3: NRT mutation and merge](docs/phase3-nrt-mutation.md)
- [Executable behavior matrix](docs/behavior-matrix.md)

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
                          matching → global BM25 → Top-K
                                          ↓
                              stored fields + highlighting
```

`TextField` is tokenized and positional. `KeywordField` indexes the complete
value as one exact term. `StoredField` is returned with hits but cannot be
searched. Stored and indexed are independent properties.

The standard analyzer lowercases tokens and preserves source offsets and
position gaps. Phrase queries therefore distinguish adjacent terms from terms
separated in the original text. Highlighting re-analyzes stored `TextField`
values, uses those offsets, and HTML-escapes all original text.

BM25 statistics are global to one reader snapshot and include only live
documents. Matching, scoring, and collecting are separate stages; the Top-K
collector retains only K hits while still reporting the complete hit count.

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
- vector fields, HNSW, hybrid retrieval, and automatic merge scheduling;
- course chapters or lesson content.

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
- [Phase 1: retrieval kernel](docs/phase1-retrieval-kernel.md)
- [Phase 2: storage and commit](docs/phase2-storage-commit.md)
- [Phase 3: NRT mutation and merge](docs/phase3-nrt-mutation.md)
- [Executable behavior matrix](docs/behavior-matrix.md)

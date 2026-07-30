# MiniLucene Tutorial

[中文版](zh/index.md)

MiniLucene is a compact Python reference implementation for learning how
lexical search connects schemas, analyzers, positional inverted indexes, BM25,
immutable segments, point-in-time readers, and near-real-time mutation. It is
an inspectable teaching system, not an Apache Lucene API or file-format clone.

## Install

You need Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/system-in-miniature/MiniLucene.git
cd MiniLucene
uv sync --dev
```

## First experiment

Run the CLI experiment from Chapter 4:

```bash
uv run minilucene create demo-index --schema schema.json
uv run minilucene add demo-index doc-1.json doc-2.json
uv run minilucene search demo-index '"follower replicas"' \
  --default-field body --top-k 10 --highlight body
```

The result should contain one hit, document `1`, with
`<em>follower replicas</em>` highlighted. Chapter 4 supplies the complete JSON
fixtures and explains what to inspect.

## Reading path

Read the retrieval, persistence, and NRT acceptance chapters as an architecture
tour; then use the mapping and behavior matrix to separate this miniature's
mechanisms from production Lucene behavior.

For the complete feature scope, mental model, and public API example, see the
[English README](https://github.com/system-in-miniature/MiniLucene#readme).
The [design history archive](superpowers/README.md) records construction-time
plans; current docs and executable tests remain the source of truth.

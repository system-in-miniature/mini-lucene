# Chapter 4: Hands-on CLI Experiment

[中文版](zh/labs-guide.md)

MiniLucene does not currently have a `labs/` directory. A dedicated lab suite
is planned; for now, this chapter uses the supported CLI to exercise the same
create → commit → reopen → query path.

## Prepare the fixtures

Create `schema.json`:

```json
{"fields":{"id":{"indexed":true,"tokenized":false,"stored":true,"store_positions":false,"boost":1.0,"analyzer_name":"keyword"},"title":{"indexed":true,"tokenized":true,"stored":true,"store_positions":true,"boost":2.0,"analyzer_name":"standard"},"body":{"indexed":true,"tokenized":true,"stored":true,"store_positions":true,"boost":1.0,"analyzer_name":"standard"}}}
```

Create `doc-1.json` and `doc-2.json`:

```json
{"id":"1","title":"Kafka Replication","body":"Kafka uses follower replicas."}
```

```json
{"id":"2","title":"Rabbit","body":"Rabbit queues messages."}
```

## Run

From the repository root:

```bash
uv sync --dev
uv run minilucene create demo-index --schema schema.json
uv run minilucene add demo-index doc-1.json doc-2.json
uv run minilucene search demo-index '"follower replicas"' \
  --default-field body --top-k 10 --highlight body
```

Use a new `demo-index` path when repeating the experiment.

## Expected observation

The create and add commands report `created`, two added documents, and commit
generation `1`. Search returns `total_hits: 1`; the hit has stored field
`id: "1"` and this highlight:

```html
Kafka uses <em>follower replicas</em>.
```

Watch how schema field choices control analysis and storage, how `add` publishes
an immutable segment through a commit, and how the phrase query uses positions
while highlighting uses source offsets. Continue with the
[retrieval kernel](phase1-retrieval-kernel.md) and
[segment format](segment-format.md).

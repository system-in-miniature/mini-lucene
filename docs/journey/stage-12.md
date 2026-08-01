# Stage 12 · Manifest commit root

### Goal

Build manifest commit root and explain its boundary from an executable counterexample, runtime state, and the critical statement.

??? note "Deliverable files"
    - `src/minilucene/storage/manifest.py`
    - `tests/storage/test_manifest_store.py`

### The problem at this point

A durable segment is not necessarily part of the committed index; restart needs one authoritative root.

### Test contract

#### See the failure first

Tests create orphan segments, corrupt candidate manifests, and interrupt root replacement to require old-root-or-new-root recovery.

??? note "File diff: tests/storage/test_manifest_store.py"
    ```diff
    diff --git a/tests/storage/test_manifest_store.py b/tests/storage/test_manifest_store.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..667d49e6961e546db242d991f6bb8deab34863ac
    --- /dev/null
    +++ b/tests/storage/test_manifest_store.py
    @@ -0,0 +1,86 @@
    +from pathlib import Path
    +
    +import pytest
    +
    +from minilucene.storage.filesystem import FileSystemOps
    +from minilucene.storage.manifest import (
    +    Manifest,
    +    ManifestStore,
    +    SegmentCommit,
    +)
    +
    +
    +class ReplaceFailingFileSystem(FileSystemOps):
    +    def replace(self, source, destination):
    +        raise OSError("injected manifest replace failure")
    +
    +
    +def test_create_and_read_generation_zero_manifest(tmp_path):
    +    store = ManifestStore(tmp_path)
    +    created = store.create(schema_fingerprint="schema")
    +    assert store.read() == created
    +    assert created.commit_generation == 0
    +    assert created.segment_generations == ()
    +    assert created.next_segment_generation == 1
    +    assert created.next_commit_generation == 1
    +
    +
    +def test_open_ignores_complete_orphan_segment(tmp_path):
    +    orphan = tmp_path / "segments" / "seg_000001"
    +    orphan.mkdir(parents=True)
    +    (orphan / "segment.json").write_text("{}", encoding="utf-8")
    +    store = ManifestStore(tmp_path)
    +    store.create(schema_fingerprint="schema")
    +    assert store.read().segment_generations == ()
    +
    +
    +def test_replace_failure_preserves_old_manifest(tmp_path):
    +    stable_store = ManifestStore(tmp_path)
    +    old = stable_store.create(schema_fingerprint="schema")
    +    updated = Manifest.next_from(
    +        old,
    +        segments=(SegmentCommit(segment_generation=1),),
    +    )
    +    failing_store = ManifestStore(
    +        tmp_path,
    +        fs=ReplaceFailingFileSystem(),
    +    )
    +    with pytest.raises(OSError, match="injected"):
    +        failing_store.write_atomic(updated)
    +    assert stable_store.read() == old
    +
    +
    +def test_manifest_round_trips_live_doc_metadata(tmp_path):
    +    store = ManifestStore(tmp_path)
    +    old = store.create(schema_fingerprint="schema")
    +    updated = Manifest.next_from(
    +        old,
    +        segments=(
    +            SegmentCommit(
    +                segment_generation=7,
    +                live_docs_generation=2,
    +                live_docs_checksum="abc",
    +            ),
    +        ),
    +    )
    +    store.write_atomic(updated)
    +    assert store.read() == updated
    +
    +
    +def test_manifest_rejects_unknown_format_version(tmp_path):
    +    store = ManifestStore(tmp_path)
    +    store.create(schema_fingerprint="schema")
    +    manifest_path = tmp_path / "manifest.json"
    +    text = manifest_path.read_text(encoding="utf-8")
    +    manifest_path.write_text(
    +        text.replace('"format_version":1', '"format_version":2'),
    +        encoding="utf-8",
    +    )
    +    with pytest.raises(ValueError, match="format version"):
    +        store.read()
    +
    +
    +def test_manifest_path_is_the_only_root_file(tmp_path):
    +    store = ManifestStore(tmp_path)
    +    store.create(schema_fingerprint="schema")
    +    assert Path("manifest.json") == store.path.relative_to(tmp_path)
    ```

**What this test locks**

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

**How it constructs the counterexample**

Tests create orphan segments, corrupt candidate manifests, and interrupt root replacement to require old-root-or-new-root recovery.

**Key test statement**

```python
assert store.read() == created
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

**What a failure means**

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

The manifest names the committed segment generation and schema fingerprint. Its atomic replacement publishes the index root.

### Why this mechanism is necessary

A durable segment is not necessarily part of the committed index; restart needs one authoritative root. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

Commit writes and fsyncs a candidate manifest, replaces the root file, fsyncs the directory, and validates referenced children on reopen.

### Mechanism blocks

#### Manifest commit root mechanism

Commit writes and fsyncs a candidate manifest, replaces the root file, fsyncs the directory, and validates referenced children on reopen.

??? note "File diff: src/minilucene/storage/manifest.py"
    ```diff
    diff --git a/src/minilucene/storage/manifest.py b/src/minilucene/storage/manifest.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..ae6451ebd86da3135ef5515a692a13453606bd4e
    --- /dev/null
    +++ b/src/minilucene/storage/manifest.py
    @@ -0,0 +1,188 @@
    +import json
    +from dataclasses import asdict, dataclass
    +from pathlib import Path
    +
    +from minilucene.storage.filesystem import FileSystemOps
    +
    +_FORMAT_VERSION = 1
    +
    +
    +@dataclass(frozen=True, slots=True)
    +class SegmentCommit:
    +    segment_generation: int
    +    live_docs_generation: int | None = None
    +    live_docs_checksum: str | None = None
    +
    +    def __post_init__(self) -> None:
    +        if self.segment_generation <= 0:
    +            raise ValueError("segment generation must be positive")
    +        if (self.live_docs_generation is None) != (
    +            self.live_docs_checksum is None
    +        ):
    +            raise ValueError(
    +                "live-doc generation and checksum must appear together"
    +            )
    +        if (
    +            self.live_docs_generation is not None
    +            and self.live_docs_generation <= 0
    +        ):
    +            raise ValueError("live-doc generation must be positive")
    +        if self.live_docs_checksum == "":
    +            raise ValueError("live-doc checksum must be non-empty")
    +
    +
    +@dataclass(frozen=True, slots=True)
    +class Manifest:
    +    format_version: int
    +    schema_fingerprint: str
    +    commit_generation: int
    +    segments: tuple[SegmentCommit, ...]
    +    next_segment_generation: int
    +    next_commit_generation: int
    +
    +    def __post_init__(self) -> None:
    +        if self.format_version != _FORMAT_VERSION:
    +            raise ValueError("unknown manifest format version")
    +        if not self.schema_fingerprint:
    +            raise ValueError("manifest schema fingerprint must be non-empty")
    +        if self.commit_generation < 0:
    +            raise ValueError("commit generation must be non-negative")
    +        if self.next_commit_generation <= self.commit_generation:
    +            raise ValueError(
    +                "next commit generation must exceed current generation"
    +            )
    +        generations = self.segment_generations
    +        if len(set(generations)) != len(generations):
    +            raise ValueError("manifest segment generations must be unique")
    +        if self.next_segment_generation <= max(generations, default=0):
    +            raise ValueError(
    +                "next segment generation must exceed referenced segments"
    +            )
    +
    +    @property
    +    def segment_generations(self) -> tuple[int, ...]:
    +        return tuple(
    +            segment.segment_generation for segment in self.segments
    +        )
    +
    +    @classmethod
    +    def initial(cls, schema_fingerprint: str) -> "Manifest":
    +        return cls(
    +            format_version=_FORMAT_VERSION,
    +            schema_fingerprint=schema_fingerprint,
    +            commit_generation=0,
    +            segments=(),
    +            next_segment_generation=1,
    +            next_commit_generation=1,
    +        )
    +
    +    @classmethod
    +    def next_from(
    +        cls,
    +        current: "Manifest",
    +        *,
    +        segments: tuple[SegmentCommit, ...],
    +        next_segment_generation: int | None = None,
    +    ) -> "Manifest":
    +        minimum_next_segment = max(
    +            (
    +                segment.segment_generation
    +                for segment in segments
    +            ),
    +            default=0,
    +        ) + 1
    +        return cls(
    +            format_version=_FORMAT_VERSION,
    +            schema_fingerprint=current.schema_fingerprint,
    +            commit_generation=current.next_commit_generation,
    +            segments=tuple(segments),
    +            next_segment_generation=max(
    +                current.next_segment_generation,
    +                minimum_next_segment,
    +                next_segment_generation or 1,
    +            ),
    +            next_commit_generation=current.next_commit_generation + 1,
    +        )
    +
    +
    +class ManifestStore:
    +    def __init__(
    +        self, root: Path, *, fs: FileSystemOps | None = None
    +    ) -> None:
    +        self.root = Path(root)
    +        self.fs = fs or FileSystemOps()
    +        self.fs.mkdir(self.root, parents=True, exist_ok=True)
    +        self.path = self.root / "manifest.json"
    +        self.temporary_path = self.root / "manifest.tmp"
    +
    +    def create(self, *, schema_fingerprint: str) -> Manifest:
    +        if self.fs.exists(self.path):
    +            raise FileExistsError(f"manifest already exists: {self.path}")
    +        manifest = Manifest.initial(schema_fingerprint)
    +        self.write_atomic(manifest)
    +        return manifest
    +
    +    def write_atomic(self, manifest: Manifest) -> None:
    +        data = json.dumps(
    +            {
    +                "format_version": manifest.format_version,
    +                "schema_fingerprint": manifest.schema_fingerprint,
    +                "commit_generation": manifest.commit_generation,
    +                "segments": [
    +                    asdict(segment) for segment in manifest.segments
    +                ],
    +                "next_segment_generation": (
    +                    manifest.next_segment_generation
    +                ),
    +                "next_commit_generation": manifest.next_commit_generation,
    +            },
    +            sort_keys=True,
    +            separators=(",", ":"),
    +        ).encode("utf-8")
    +        self.fs.write_bytes(self.temporary_path, data)
    +        self.fs.fsync_file(self.temporary_path)
    +        self.fs.replace(self.temporary_path, self.path)
    +        self.fs.fsync_directory(self.root)
    +
    +    def read(self) -> Manifest:
    +        try:
    +            value = json.loads(
    +                self.fs.read_bytes(self.path).decode(
    +                    "utf-8", errors="strict"
    +                )
    +            )
    +        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
    +            raise ValueError(f"invalid manifest: {error}") from error
    +        if not isinstance(value, dict):
    +            raise TypeError("manifest must be a JSON object")
    +        expected_keys = {
    +            "format_version",
    +            "schema_fingerprint",
    +            "commit_generation",
    +            "segments",
    +            "next_segment_generation",
    +            "next_commit_generation",
    +        }
    +        if set(value) != expected_keys:
    +            raise ValueError("manifest fields do not match format")
    +        raw_segments = value["segments"]
    +        if not isinstance(raw_segments, list):
    +            raise TypeError("manifest segments must be a list")
    +        try:
    +            segments = tuple(
    +                SegmentCommit(**segment) for segment in raw_segments
    +            )
    +            return Manifest(
    +                format_version=value["format_version"],
    +                schema_fingerprint=value["schema_fingerprint"],
    +                commit_generation=value["commit_generation"],
    +                segments=segments,
    +                next_segment_generation=value[
    +                    "next_segment_generation"
    +                ],
    +                next_commit_generation=value[
    +                    "next_commit_generation"
    +                ],
    +            )
    +        except (TypeError, KeyError, ValueError) as error:
    +            raise ValueError(f"invalid manifest fields: {error}") from error
    ```

**What it is and why it appears**

The manifest names the committed segment generation and schema fingerprint. Its atomic replacement publishes the index root.

**Runtime role**

Commit writes and fsyncs a candidate manifest, replaces the root file, fsyncs the directory, and validates referenced children on reopen.

**Statement understanding**

Readers follow only the published root, so unreferenced durable files remain orphans rather than becoming synthesized commits.

### Verification evidence

Run `uv run pytest -q $(cat journey/stages/12-manifest-root/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

Readers follow only the published root, so unreferenced durable files remain orphans rather than becoming synthesized commits.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 7](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/07-commit-atomicity.md)

[Complete reference patch / 完整参考补丁](https://github.com/system-in-miniature/mini-lucene/blob/main/journey/stages/12-manifest-root/stage.patch)

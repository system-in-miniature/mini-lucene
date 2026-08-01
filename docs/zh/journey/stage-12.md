# Stage 12 · Manifest 提交根

### 目标

实现Manifest 提交根，并能从可执行反例、运行时状态与关键语句解释其边界。

??? note "交付文件"
    - `src/minilucene/storage/manifest.py`
    - `tests/storage/test_manifest_store.py`

### 当前遇到的问题

已持久 Segment 不一定属于已提交 Index；Restart 需要唯一权威 Root。

### 测试契约

#### 先看会坏在哪里

测试创建 Orphan Segment、损坏 Candidate Manifest，并中断 Root Replacement，要求恢复结果只能是旧 Root 或新 Root。

??? note "文件差异：tests/storage/test_manifest_store.py"
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

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

测试创建 Orphan Segment、损坏 Candidate Manifest，并中断 Root Replacement，要求恢复结果只能是旧 Root 或新 Root。

**关键测试语句**

```python
assert store.read() == created
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Manifest 命名已提交 Segment Generation 与 Schema Fingerprint；其原子替换发布 Index Root。

### 为什么需要这个机制

已持久 Segment 不一定属于已提交 Index；Restart 需要唯一权威 Root。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Commit 写并 Fsync Candidate Manifest、替换 Root File、Fsync Directory，并在重开时验证引用的 Child。

### 机制板块

#### Manifest 提交根机制

Commit 写并 Fsync Candidate Manifest、替换 Root File、Fsync Directory，并在重开时验证引用的 Child。

??? note "文件差异：src/minilucene/storage/manifest.py"
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

**是什么，为什么现在需要**

Manifest 命名已提交 Segment Generation 与 Schema Fingerprint；其原子替换发布 Index Root。

**在运行时做什么**

Commit 写并 Fsync Candidate Manifest、替换 Root File、Fsync Directory，并在重开时验证引用的 Child。

**关键语句理解**

Reader 只跟随已发布 Root，因此未引用的持久文件仍是 Orphan，不会变成拼接出的 Commit。

### 验证证据

运行 `uv run pytest -q $(cat journey/stages/12-manifest-root/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

Reader 只跟随已发布 Root，因此未引用的持久文件仍是 Orphan，不会变成拼接出的 Commit。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 7 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/07-commit-atomicity.md)

[Complete reference patch / 完整参考补丁](https://github.com/system-in-miniature/mini-lucene/blob/main/journey/stages/12-manifest-root/stage.patch)

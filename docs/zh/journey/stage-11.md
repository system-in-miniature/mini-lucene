# Stage 11 · 带校验和的 Segment 发布

### 目标

实现带校验和的 Segment 发布，并能从可执行反例、运行时状态与关键语句解释其边界。

??? note "交付文件"
    - `src/minilucene/storage/filesystem.py`
    - `src/minilucene/storage/segment_store.py`
    - `tests/storage/test_segment_store.py`

### 当前遇到的问题

多个正确编码文件仍可能被部分写入，或混合不同代次。

### 测试契约

#### 先看会坏在哪里

Failure Injection 在临时写、Checksum、Fsync 与 Rename 之间停止发布，再重开目录。

??? note "文件差异：tests/storage/test_segment_store.py"
    ```diff
    diff --git a/tests/storage/test_segment_store.py b/tests/storage/test_segment_store.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..31e70bb9cd0df9ca1c3dd97eccfd4d94d913b59d
    --- /dev/null
    +++ b/tests/storage/test_segment_store.py
    @@ -0,0 +1,98 @@
    +from pathlib import Path
    +
    +import pytest
    +
    +from minilucene.index.memory import RamIndexBuilder
    +from minilucene.schema import Schema, TextField
    +from minilucene.storage.filesystem import FileSystemOps
    +from minilucene.storage.image import SegmentImage
    +from minilucene.storage.segment_store import (
    +    CorruptIndexError,
    +    SegmentStore,
    +)
    +
    +
    +def build_image():
    +    schema = Schema(body=TextField(stored=True))
    +    builder = RamIndexBuilder(schema)
    +    builder.add_document({"body": "immutable segment"})
    +    return SegmentImage.from_memory_segment(
    +        generation=1,
    +        schema_fingerprint=schema.fingerprint,
    +        segment=builder.freeze(generation=0),
    +    )
    +
    +
    +class RecordingFileSystem(FileSystemOps):
    +    def __init__(self):
    +        self.writes = []
    +        self.file_syncs = []
    +        self.directory_syncs = []
    +
    +    def write_bytes(self, path, data):
    +        self.writes.append(Path(path))
    +        super().write_bytes(path, data)
    +
    +    def fsync_file(self, path):
    +        self.file_syncs.append(Path(path))
    +        super().fsync_file(path)
    +
    +    def fsync_directory(self, path):
    +        self.directory_syncs.append(Path(path))
    +        super().fsync_directory(path)
    +
    +
    +class FailingFileSystem(FileSystemOps):
    +    def __init__(self, filename):
    +        self.filename = filename
    +
    +    def write_bytes(self, path, data):
    +        if Path(path).name == self.filename:
    +            raise OSError(f"injected write failure: {self.filename}")
    +        super().write_bytes(path, data)
    +
    +
    +def test_segment_store_writes_metadata_last(tmp_path):
    +    fs = RecordingFileSystem()
    +    store = SegmentStore(tmp_path, fs=fs)
    +    descriptor = store.publish(build_image())
    +    assert fs.writes[-1].name == "segment.json"
    +    assert fs.file_syncs[-1].name == "segment.json"
    +    assert descriptor.path == Path("segments/seg_000001")
    +    assert not list((tmp_path / "segments").glob(".tmp-*"))
    +
    +
    +def test_failed_publish_never_creates_final_directory(tmp_path):
    +    store = SegmentStore(
    +        tmp_path,
    +        fs=FailingFileSystem("postings.bin"),
    +    )
    +    with pytest.raises(OSError, match="injected"):
    +        store.publish(build_image())
    +    assert not (tmp_path / "segments" / "seg_000001").exists()
    +    assert not list((tmp_path / "segments").glob(".tmp-*"))
    +
    +
    +def test_segment_store_open_round_trips_image(tmp_path):
    +    image = build_image()
    +    store = SegmentStore(tmp_path)
    +    store.publish(image)
    +    assert store.open(1, image.schema_fingerprint) == image
    +
    +
    +def test_segment_store_rejects_checksum_corruption(tmp_path):
    +    image = build_image()
    +    store = SegmentStore(tmp_path)
    +    descriptor = store.publish(image)
    +    postings = tmp_path / descriptor.path / "postings.bin"
    +    postings.write_bytes(postings.read_bytes() + b"\x00")
    +    with pytest.raises(CorruptIndexError, match="length|checksum"):
    +        store.open(1, image.schema_fingerprint)
    +
    +
    +def test_segment_store_rejects_schema_mismatch(tmp_path):
    +    image = build_image()
    +    store = SegmentStore(tmp_path)
    +    store.publish(image)
    +    with pytest.raises(CorruptIndexError, match="schema"):
    +        store.open(1, "different")
    ```

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

Failure Injection 在临时写、Checksum、Fsync 与 Rename 之间停止发布，再重开目录。

**关键测试语句**

```python
assert fs.writes[-1].name == "segment.json"
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Segment Store 只有在每个文件与 Metadata Digest 完整持久后，才发布不可变目录。

### 为什么需要这个机制

多个正确编码文件仍可能被部分写入，或混合不同代次。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

它写临时 Sibling、Fsync 文件与目录、记录 SHA-256 Metadata、原子 Rename，并在读取时验证。

### 机制板块

#### 带校验和的 Segment 发布机制

它写临时 Sibling、Fsync 文件与目录、记录 SHA-256 Metadata、原子 Rename，并在读取时验证。

??? note "文件差异：src/minilucene/storage/filesystem.py"
    ```diff
    diff --git a/src/minilucene/storage/filesystem.py b/src/minilucene/storage/filesystem.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..9c4f1fb3b5cea652a591ef82d3eb5082666a1333
    --- /dev/null
    +++ b/src/minilucene/storage/filesystem.py
    @@ -0,0 +1,45 @@
    +import os
    +import shutil
    +from pathlib import Path
    +
    +
    +class FileSystemOps:
    +    def mkdir(
    +        self, path: Path, *, parents: bool = False, exist_ok: bool = False
    +    ) -> None:
    +        Path(path).mkdir(parents=parents, exist_ok=exist_ok)
    +
    +    def write_bytes(self, path: Path, data: bytes) -> None:
    +        with Path(path).open("wb") as stream:
    +            stream.write(data)
    +
    +    def read_bytes(self, path: Path) -> bytes:
    +        return Path(path).read_bytes()
    +
    +    def fsync_file(self, path: Path) -> None:
    +        descriptor = os.open(Path(path), os.O_RDONLY)
    +        try:
    +            os.fsync(descriptor)
    +        finally:
    +            os.close(descriptor)
    +
    +    def fsync_directory(self, path: Path) -> None:
    +        descriptor = os.open(
    +            Path(path), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    +        )
    +        try:
    +            os.fsync(descriptor)
    +        finally:
    +            os.close(descriptor)
    +
    +    def replace(self, source: Path, destination: Path) -> None:
    +        os.replace(source, destination)
    +
    +    def exists(self, path: Path) -> bool:
    +        return Path(path).exists()
    +
    +    def remove_tree(self, path: Path) -> None:
    +        shutil.rmtree(path)
    +
    +    def list_directory(self, path: Path) -> tuple[Path, ...]:
    +        return tuple(Path(path).iterdir())
    ```

??? note "文件差异：src/minilucene/storage/segment_store.py"
    ```diff
    diff --git a/src/minilucene/storage/segment_store.py b/src/minilucene/storage/segment_store.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..b809a9b48390f86ebe211aa9ffa5d0937b52b28b
    --- /dev/null
    +++ b/src/minilucene/storage/segment_store.py
    @@ -0,0 +1,192 @@
    +import hashlib
    +import json
    +import uuid
    +from dataclasses import dataclass
    +from pathlib import Path
    +
    +from minilucene.storage.codec import SegmentDataCodec
    +from minilucene.storage.filesystem import FileSystemOps
    +from minilucene.storage.image import SegmentImage
    +
    +_MAGIC = "MINILUCENE_SEGMENT"
    +_FORMAT_VERSION = 1
    +_CODEC = "educational-v1"
    +_DATA_FILE_ORDER = (
    +    "terms.bin",
    +    "postings.bin",
    +    "stored.bin",
    +    "norms.bin",
    +)
    +
    +
    +class CorruptIndexError(ValueError):
    +    """Raised when persisted index bytes fail strict validation."""
    +
    +
    +@dataclass(frozen=True, slots=True)
    +class SegmentDescriptor:
    +    generation: int
    +    schema_fingerprint: str
    +    max_doc: int
    +    path: Path
    +
    +
    +class SegmentStore:
    +    def __init__(
    +        self, root: Path, *, fs: FileSystemOps | None = None
    +    ) -> None:
    +        self.root = Path(root)
    +        self.fs = fs or FileSystemOps()
    +        self.segments_path = self.root / "segments"
    +        self.fs.mkdir(self.segments_path, parents=True, exist_ok=True)
    +
    +    @staticmethod
    +    def _directory_name(generation: int) -> str:
    +        return f"seg_{generation:06d}"
    +
    +    def publish(self, image: SegmentImage) -> SegmentDescriptor:
    +        relative_path = Path("segments") / self._directory_name(
    +            image.generation
    +        )
    +        final_path = self.root / relative_path
    +        if self.fs.exists(final_path):
    +            raise FileExistsError(f"segment already exists: {final_path}")
    +        temporary_path = self.segments_path / (
    +            f".tmp-{self._directory_name(image.generation)}-"
    +            f"{uuid.uuid4().hex}"
    +        )
    +        self.fs.mkdir(temporary_path)
    +        try:
    +            files = SegmentDataCodec.encode(image)
    +            metadata_files: dict[str, dict[str, object]] = {}
    +            for filename in _DATA_FILE_ORDER:
    +                data = files[filename]
    +                path = temporary_path / filename
    +                self.fs.write_bytes(path, data)
    +                self.fs.fsync_file(path)
    +                metadata_files[filename] = {
    +                    "length": len(data),
    +                    "sha256": hashlib.sha256(data).hexdigest(),
    +                }
    +            metadata = {
    +                "magic": _MAGIC,
    +                "format_version": _FORMAT_VERSION,
    +                "generation": image.generation,
    +                "schema_fingerprint": image.schema_fingerprint,
    +                "max_doc": image.max_doc,
    +                "codec": _CODEC,
    +                "files": metadata_files,
    +            }
    +            metadata_bytes = json.dumps(
    +                metadata,
    +                sort_keys=True,
    +                separators=(",", ":"),
    +            ).encode("utf-8")
    +            metadata_path = temporary_path / "segment.json"
    +            self.fs.write_bytes(metadata_path, metadata_bytes)
    +            self.fs.fsync_file(metadata_path)
    +            self.fs.fsync_directory(temporary_path)
    +            self.fs.replace(temporary_path, final_path)
    +            self.fs.fsync_directory(self.segments_path)
    +        except BaseException:
    +            if self.fs.exists(temporary_path):
    +                try:
    +                    self.fs.remove_tree(temporary_path)
    +                except OSError:
    +                    pass
    +            raise
    +        return SegmentDescriptor(
    +            generation=image.generation,
    +            schema_fingerprint=image.schema_fingerprint,
    +            max_doc=image.max_doc,
    +            path=relative_path,
    +        )
    +
    +    def open(
    +        self, generation: int, expected_schema_fingerprint: str
    +    ) -> SegmentImage:
    +        segment_path = self.segments_path / self._directory_name(
    +            generation
    +        )
    +        try:
    +            metadata = self._read_metadata(segment_path)
    +            self._validate_metadata(
    +                metadata,
    +                generation=generation,
    +                schema_fingerprint=expected_schema_fingerprint,
    +            )
    +            files = self._read_and_validate_files(segment_path, metadata)
    +            image = SegmentDataCodec.decode(
    +                generation=generation,
    +                schema_fingerprint=expected_schema_fingerprint,
    +                files=files,
    +            )
    +            if image.max_doc != metadata["max_doc"]:
    +                raise CorruptIndexError("segment max_doc mismatch")
    +            return image
    +        except CorruptIndexError:
    +            raise
    +        except (OSError, ValueError, TypeError, KeyError) as error:
    +            raise CorruptIndexError(
    +                f"cannot open segment {generation}: {error}"
    +            ) from error
    +
    +    def _read_metadata(self, segment_path: Path) -> dict[str, object]:
    +        try:
    +            value = json.loads(
    +                self.fs.read_bytes(
    +                    segment_path / "segment.json"
    +                ).decode("utf-8", errors="strict")
    +            )
    +        except (UnicodeDecodeError, json.JSONDecodeError) as error:
    +            raise CorruptIndexError("invalid segment metadata JSON") from error
    +        if not isinstance(value, dict):
    +            raise CorruptIndexError("segment metadata must be an object")
    +        return value
    +
    +    @staticmethod
    +    def _validate_metadata(
    +        metadata: dict[str, object],
    +        *,
    +        generation: int,
    +        schema_fingerprint: str,
    +    ) -> None:
    +        if metadata.get("magic") != _MAGIC:
    +            raise CorruptIndexError("unknown segment magic")
    +        if metadata.get("format_version") != _FORMAT_VERSION:
    +            raise CorruptIndexError("unknown segment format version")
    +        if metadata.get("codec") != _CODEC:
    +            raise CorruptIndexError("unknown segment codec")
    +        if metadata.get("generation") != generation:
    +            raise CorruptIndexError("segment generation mismatch")
    +        if metadata.get("schema_fingerprint") != schema_fingerprint:
    +            raise CorruptIndexError("segment schema fingerprint mismatch")
    +        if (
    +            not isinstance(metadata.get("max_doc"), int)
    +            or metadata["max_doc"] < 0
    +        ):
    +            raise CorruptIndexError("invalid segment max_doc")
    +        files = metadata.get("files")
    +        if not isinstance(files, dict) or set(files) != set(
    +            _DATA_FILE_ORDER
    +        ):
    +            raise CorruptIndexError("invalid segment file metadata")
    +
    +    def _read_and_validate_files(
    +        self, segment_path: Path, metadata: dict[str, object]
    +    ) -> dict[str, bytes]:
    +        file_metadata = metadata["files"]
    +        if not isinstance(file_metadata, dict):
    +            raise CorruptIndexError("invalid segment file metadata")
    +        result: dict[str, bytes] = {}
    +        for filename in _DATA_FILE_ORDER:
    +            expected = file_metadata[filename]
    +            if not isinstance(expected, dict):
    +                raise CorruptIndexError("invalid file metadata entry")
    +            data = self.fs.read_bytes(segment_path / filename)
    +            if expected.get("length") != len(data):
    +                raise CorruptIndexError(f"{filename} length mismatch")
    +            if expected.get("sha256") != hashlib.sha256(data).hexdigest():
    +                raise CorruptIndexError(f"{filename} checksum mismatch")
    +            result[filename] = data
    +        return result
    ```

**是什么，为什么现在需要**

Segment Store 只有在每个文件与 Metadata Digest 完整持久后，才发布不可变目录。

**在运行时做什么**

它写临时 Sibling、Fsync 文件与目录、记录 SHA-256 Metadata、原子 Rename，并在读取时验证。

**关键语句理解**

最终 Rename 是可见性边界；预先准备好的带校验 Child 确保 Reader 不接受混合 Segment。

### 验证证据

运行 `uv run pytest -q $(cat journey/stages/11-segment-publication/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

最终 Rename 是可见性边界；预先准备好的带校验 Child 确保 Reader 不接受混合 Segment。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 4 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/04-codec.md)

[Complete reference patch / 完整参考补丁](https://github.com/system-in-miniature/mini-lucene/blob/main/journey/stages/11-segment-publication/stage.patch)

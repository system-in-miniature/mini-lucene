# Stage 18 · 不可变 Live-doc Mask

### 目标

实现不可变 Live-doc Mask，并能从可执行反例、运行时状态与关键语句解释其边界。

??? note "交付文件"
    - `src/minilucene/storage/filesystem.py`
    - `src/minilucene/storage/live_docs.py`
    - `tests/storage/test_live_docs_commit.py`
    - `tests/unit/storage/test_live_docs.py`

### 当前遇到的问题

不可变 Segment File 无法原地擦除删除 Document，否则会破坏旧 Reader 与 Checksum。

### 测试契约

#### 先看会坏在哪里

测试跨边界翻转 Bit、损坏 Generation，并让旧 Mask 保留而新 Reader 观察更新删除视图。

??? note "文件差异：tests/storage/test_live_docs_commit.py"
    ```diff
    diff --git a/tests/storage/test_live_docs_commit.py b/tests/storage/test_live_docs_commit.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..12940dbad0be51f916bbd1c87b54fc69fac14a56
    --- /dev/null
    +++ b/tests/storage/test_live_docs_commit.py
    @@ -0,0 +1,60 @@
    +import pytest
    +
    +from minilucene.storage.live_docs import LiveDocsStore
    +
    +
    +def test_live_docs_store_publishes_and_reads_immutable_generation(tmp_path):
    +    segment = tmp_path / "segments" / "seg_000001"
    +    segment.mkdir(parents=True)
    +    store = LiveDocsStore(tmp_path)
    +    published = store.publish(
    +        segment_generation=1,
    +        live_docs_generation=1,
    +        max_doc=4,
    +        live_docs=frozenset({0, 3}),
    +    )
    +    assert published.path.name == "live_000001.bin"
    +    assert store.read(
    +        segment_generation=1,
    +        live_docs_generation=1,
    +        expected_checksum=published.checksum,
    +        max_doc=4,
    +    ) == frozenset({0, 3})
    +
    +
    +def test_live_docs_store_refuses_generation_overwrite(tmp_path):
    +    segment = tmp_path / "segments" / "seg_000001"
    +    segment.mkdir(parents=True)
    +    store = LiveDocsStore(tmp_path)
    +    store.publish(
    +        segment_generation=1,
    +        live_docs_generation=1,
    +        max_doc=1,
    +        live_docs=frozenset(),
    +    )
    +    with pytest.raises(FileExistsError):
    +        store.publish(
    +            segment_generation=1,
    +            live_docs_generation=1,
    +            max_doc=1,
    +            live_docs=frozenset({0}),
    +        )
    +
    +
    +def test_live_docs_store_rejects_checksum_mismatch(tmp_path):
    +    segment = tmp_path / "segments" / "seg_000001"
    +    segment.mkdir(parents=True)
    +    store = LiveDocsStore(tmp_path)
    +    store.publish(
    +        segment_generation=1,
    +        live_docs_generation=1,
    +        max_doc=1,
    +        live_docs=frozenset({0}),
    +    )
    +    with pytest.raises(ValueError, match="checksum"):
    +        store.read(
    +            segment_generation=1,
    +            live_docs_generation=1,
    +            expected_checksum="wrong",
    +            max_doc=1,
    +        )
    ```

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

测试跨边界翻转 Bit、损坏 Generation，并让旧 Mask 保留而新 Reader 观察更新删除视图。

**关键测试语句**

```python
assert published.path.name == "live_000001.bin"
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

??? note "文件差异：tests/unit/storage/test_live_docs.py"
    ```diff
    diff --git a/tests/unit/storage/test_live_docs.py b/tests/unit/storage/test_live_docs.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..192791371055d88646711492cac697474866a36a
    --- /dev/null
    +++ b/tests/unit/storage/test_live_docs.py
    @@ -0,0 +1,48 @@
    +import pytest
    +
    +from minilucene.storage.live_docs import LiveDocsCodec
    +
    +
    +def test_live_docs_round_trip():
    +    encoded = LiveDocsCodec.encode(
    +        max_doc=5,
    +        live_docs=frozenset({0, 2, 4}),
    +    )
    +    assert LiveDocsCodec.decode(5, encoded) == frozenset({0, 2, 4})
    +
    +
    +def test_live_docs_empty_and_full_round_trip():
    +    assert LiveDocsCodec.decode(
    +        0,
    +        LiveDocsCodec.encode(max_doc=0, live_docs=frozenset()),
    +    ) == frozenset()
    +    assert LiveDocsCodec.decode(
    +        9,
    +        LiveDocsCodec.encode(
    +            max_doc=9,
    +            live_docs=frozenset(range(9)),
    +        ),
    +    ) == frozenset(range(9))
    +
    +
    +def test_live_docs_rejects_id_outside_segment():
    +    with pytest.raises(ValueError, match="outside"):
    +        LiveDocsCodec.encode(max_doc=2, live_docs=frozenset({2}))
    +
    +
    +def test_live_docs_rejects_nonzero_unused_bits():
    +    encoded = bytearray(
    +        LiveDocsCodec.encode(max_doc=5, live_docs=frozenset({0}))
    +    )
    +    encoded[-1] |= 0b1000_0000
    +    with pytest.raises(ValueError, match="unused"):
    +        LiveDocsCodec.decode(5, bytes(encoded))
    +
    +
    +def test_live_docs_rejects_wrong_expected_max_doc():
    +    encoded = LiveDocsCodec.encode(
    +        max_doc=3,
    +        live_docs=frozenset({0}),
    +    )
    +    with pytest.raises(ValueError, match="max_doc"):
    +        LiveDocsCodec.decode(4, encoded)
    ```

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

测试跨边界翻转 Bit、损坏 Generation，并让旧 Mask 保留而新 Reader 观察更新删除视图。

**关键测试语句**

```python
assert published.path.name == "live_000001.bin"
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Live-doc Mask 是有版本的不可变 Visibility Overlay；Stored/Posting Data 不变，由 Bit 决定 Local Doc 是否可见。

### 为什么需要这个机制

不可变 Segment File 无法原地擦除删除 Document，否则会破坏旧 Reader 与 Checksum。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Mutation 从前一代派生新 Mask、原子写入并校验，再在 Writer State 发布其 Generation。

### 机制板块

#### 不可变 Live-doc Mask机制

Mutation 从前一代派生新 Mask、原子写入并校验，再在 Writer State 发布其 Generation。

??? note "文件差异：src/minilucene/storage/filesystem.py"
    ```diff
    diff --git a/src/minilucene/storage/filesystem.py b/src/minilucene/storage/filesystem.py
    index 9c4f1fb3b5cea652a591ef82d3eb5082666a1333..5de712b7c7b564820d20aa2df8f5ac97b7f2a563 100644
    --- a/src/minilucene/storage/filesystem.py
    +++ b/src/minilucene/storage/filesystem.py
    @@ -41,5 +41,8 @@ class FileSystemOps:
         def remove_tree(self, path: Path) -> None:
             shutil.rmtree(path)

    +    def remove_file(self, path: Path) -> None:
    +        Path(path).unlink()
    +
         def list_directory(self, path: Path) -> tuple[Path, ...]:
             return tuple(Path(path).iterdir())
    ```

??? note "文件差异：src/minilucene/storage/live_docs.py"
    ```diff
    diff --git a/src/minilucene/storage/live_docs.py b/src/minilucene/storage/live_docs.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..7d520e8da9556aa5514f328cb983359f763154a6
    --- /dev/null
    +++ b/src/minilucene/storage/live_docs.py
    @@ -0,0 +1,146 @@
    +import hashlib
    +import uuid
    +from dataclasses import dataclass
    +from pathlib import Path
    +
    +from minilucene.storage.filesystem import FileSystemOps
    +from minilucene.storage.varint import (
    +    decode_uvarint,
    +    encode_uvarint,
    +)
    +
    +
    +class LiveDocsCodec:
    +    @staticmethod
    +    def encode(*, max_doc: int, live_docs: frozenset[int]) -> bytes:
    +        if not isinstance(max_doc, int) or max_doc < 0:
    +            raise ValueError("live-doc max_doc must be non-negative")
    +        if any(doc_id < 0 or doc_id >= max_doc for doc_id in live_docs):
    +            raise ValueError("live document ID outside segment")
    +        byte_count = (max_doc + 7) // 8
    +        bits = bytearray(byte_count)
    +        for doc_id in live_docs:
    +            bits[doc_id // 8] |= 1 << (doc_id % 8)
    +        return (
    +            encode_uvarint(max_doc)
    +            + encode_uvarint(byte_count)
    +            + bytes(bits)
    +        )
    +
    +    @staticmethod
    +    def decode(
    +        expected_max_doc: int, data: bytes
    +    ) -> frozenset[int]:
    +        max_doc, offset = decode_uvarint(data, 0)
    +        if max_doc != expected_max_doc:
    +            raise ValueError("live-doc max_doc mismatch")
    +        byte_count, offset = decode_uvarint(data, offset)
    +        expected_byte_count = (max_doc + 7) // 8
    +        if byte_count != expected_byte_count:
    +            raise ValueError("live-doc bitset length mismatch")
    +        end = offset + byte_count
    +        if end != len(data):
    +            raise ValueError("live-doc data length mismatch")
    +        bits = data[offset:end]
    +        remainder = max_doc % 8
    +        if bits and remainder:
    +            unused_mask = ~((1 << remainder) - 1) & 0xFF
    +            if bits[-1] & unused_mask:
    +                raise ValueError("unused live-doc bits must be zero")
    +        return frozenset(
    +            doc_id
    +            for doc_id in range(max_doc)
    +            if bits[doc_id // 8] & (1 << (doc_id % 8))
    +        )
    +
    +
    +@dataclass(frozen=True, slots=True)
    +class LiveDocsDescriptor:
    +    segment_generation: int
    +    live_docs_generation: int
    +    checksum: str
    +    path: Path
    +
    +
    +class LiveDocsStore:
    +    def __init__(
    +        self, root: Path, *, fs: FileSystemOps | None = None
    +    ) -> None:
    +        self.root = Path(root)
    +        self.fs = fs or FileSystemOps()
    +
    +    @staticmethod
    +    def _segment_name(generation: int) -> str:
    +        return f"seg_{generation:06d}"
    +
    +    @staticmethod
    +    def _live_name(generation: int) -> str:
    +        return f"live_{generation:06d}.bin"
    +
    +    def publish(
    +        self,
    +        *,
    +        segment_generation: int,
    +        live_docs_generation: int,
    +        max_doc: int,
    +        live_docs: frozenset[int],
    +    ) -> LiveDocsDescriptor:
    +        if segment_generation <= 0 or live_docs_generation <= 0:
    +            raise ValueError("live-doc generations must be positive")
    +        segment_path = (
    +            self.root
    +            / "segments"
    +            / self._segment_name(segment_generation)
    +        )
    +        if not self.fs.exists(segment_path):
    +            raise FileNotFoundError(
    +                f"segment does not exist: {segment_path}"
    +            )
    +        filename = self._live_name(live_docs_generation)
    +        destination = segment_path / filename
    +        if self.fs.exists(destination):
    +            raise FileExistsError(
    +                f"live-doc generation already exists: {destination}"
    +            )
    +        temporary = segment_path / f".tmp-{filename}-{uuid.uuid4().hex}"
    +        data = LiveDocsCodec.encode(
    +            max_doc=max_doc,
    +            live_docs=live_docs,
    +        )
    +        try:
    +            self.fs.write_bytes(temporary, data)
    +            self.fs.fsync_file(temporary)
    +            self.fs.replace(temporary, destination)
    +            self.fs.fsync_directory(segment_path)
    +        except BaseException:
    +            if self.fs.exists(temporary):
    +                try:
    +                    self.fs.remove_file(temporary)
    +                except OSError:
    +                    pass
    +            raise
    +        return LiveDocsDescriptor(
    +            segment_generation=segment_generation,
    +            live_docs_generation=live_docs_generation,
    +            checksum=hashlib.sha256(data).hexdigest(),
    +            path=destination.relative_to(self.root),
    +        )
    +
    +    def read(
    +        self,
    +        *,
    +        segment_generation: int,
    +        live_docs_generation: int,
    +        expected_checksum: str,
    +        max_doc: int,
    +    ) -> frozenset[int]:
    +        path = (
    +            self.root
    +            / "segments"
    +            / self._segment_name(segment_generation)
    +            / self._live_name(live_docs_generation)
    +        )
    +        data = self.fs.read_bytes(path)
    +        if hashlib.sha256(data).hexdigest() != expected_checksum:
    +            raise ValueError("live-doc checksum mismatch")
    +        return LiveDocsCodec.decode(max_doc, data)
    ```

**是什么，为什么现在需要**

Live-doc Mask 是有版本的不可变 Visibility Overlay；Stored/Posting Data 不变，由 Bit 决定 Local Doc 是否可见。

**在运行时做什么**

Mutation 从前一代派生新 Mask、原子写入并校验，再在 Writer State 发布其 Generation。

**关键语句理解**

发布新 Generation 而非修改字节，让旧 Snapshot 保留准确的删除视图。

### 验证证据

运行 `uv run pytest -q $(cat journey/stages/18-live-doc-masks/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

发布新 Generation 而非修改字节，让旧 Snapshot 保留准确的删除视图。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 6 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/06-deletes-updates.md)

[Complete reference patch / 完整参考补丁](https://github.com/system-in-miniature/mini-lucene/blob/main/journey/stages/18-live-doc-masks/stage.patch)

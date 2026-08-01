# Stage 28 · CLI 与领域闭环

### 目标

实现CLI 与领域闭环，并能从可执行反例、运行时状态与关键语句解释其边界。

??? note "交付文件"
    - `pyproject.toml`
    - `src/minilucene/__init__.py`
    - `src/minilucene/cli.py`
    - `tests/acceptance/test_end_to_end.py`
    - `tests/acceptance/test_failure_matrix.py`
    - `tests/acceptance/test_owner_zero.py`
    - `tests/contract/test_cli.py`
    - `tests/test_public_surface.py`

### 当前遇到的问题

核心机制需要一条轻量用户路径与组合失败证据，同时不能复制 Index/Search 语义。

### 测试契约

#### 先看会坏在哪里

End-to-end 与 Failure Matrix 组合 Commit、Reopen、Delete、Merge、Bad Input、Closed Handle 与 CLI Process 行为。

??? note "文件差异：tests/acceptance/test_end_to_end.py"
    ```diff
    diff --git a/tests/acceptance/test_end_to_end.py b/tests/acceptance/test_end_to_end.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..153d55aa79409faf49064b78a4cde66ee08c754f
    --- /dev/null
    +++ b/tests/acceptance/test_end_to_end.py
    @@ -0,0 +1,104 @@
    +from minilucene import Index, KeywordField, Schema, TextField
    +from minilucene.evaluation import precision_at_k
    +from minilucene.query_parser import parse_query
    +
    +
    +def _ids(results):
    +    return tuple(hit.stored_fields["id"] for hit in results.hits)
    +
    +
    +def test_documented_public_api_closes_the_v1_product_loop(tmp_path):
    +    schema = Schema(
    +        id=KeywordField(stored=True),
    +        title=TextField(stored=True, boost=2.0),
    +        body=TextField(stored=True),
    +        author=KeywordField(stored=True),
    +    )
    +    index = Index.create(tmp_path, schema)
    +    with index.writer() as writer:
    +        writer.add_document(
    +            id="1",
    +            title="Kafka Replication",
    +            body="Kafka uses follower replicas.",
    +            author="jonah",
    +        )
    +        writer.flush()
    +        writer.add_document(
    +            id="2",
    +            title="Rabbit Messaging",
    +            body="Rabbit uses durable queues.",
    +            author="sam",
    +        )
    +        writer.commit()
    +
    +    reopened = Index.open(tmp_path)
    +    old_reader = reopened.open_reader()
    +    query_text = 'title:kafka OR body:"follower replicas"'
    +    query = parse_query(query_text, schema, "body")
    +    initial = old_reader.search(
    +        query, top_k=2, highlight_fields=("title", "body")
    +    )
    +    assert _ids(initial) == ("1",)
    +    assert initial.hits[0].highlights["body"] == (
    +        "Kafka uses <em>follower replicas</em>."
    +    )
    +
    +    with reopened.writer() as writer:
    +        writer.add_document(
    +            id="3",
    +            title="Follower Operations",
    +            body="A follower replica refreshes.",
    +            author="lee",
    +        )
    +        nrt = writer.refresh()
    +        assert set(
    +            _ids(
    +                nrt.search_text(
    +                    "follower",
    +                    default_field="body",
    +                    top_k=10,
    +                )
    +            )
    +        ) == {"1", "3"}
    +        writer.update_document(
    +            field="id",
    +            term="2",
    +            id="2",
    +            title="Queue Operations",
    +            body="Queues isolate consumers.",
    +            author="sam",
    +        )
    +        writer.delete_by_term("id", "1")
    +        writer.commit()
    +        nrt.close()
    +
    +    current_reader = reopened.open_reader()
    +    assert _ids(old_reader.search(query, top_k=10)) == ("1",)
    +    assert _ids(current_reader.search(query, top_k=10)) == ()
    +
    +    with reopened.writer() as writer:
    +        writer.merge(writer.segment_generations)
    +        writer.commit()
    +    final_index = Index.open(tmp_path)
    +    final_reader = final_index.open_reader()
    +    final = final_reader.search_text(
    +        "follower OR queues",
    +        default_field="body",
    +        top_k=10,
    +        highlight_fields=("body",),
    +    )
    +    ranked = _ids(final)
    +    assert set(ranked) == {"2", "3"}
    +    assert precision_at_k(ranked, {"2", "3"}, 2) == 1.0
    +
    +    old_reader.close()
    +    current_reader.close()
    +    final_reader.close()
    +    final_index.close()
    +    reopened.collect_garbage()
    +    reopened.close()
    +    index.close()
    +    diagnostics = reopened.lifecycle_diagnostics()
    +    assert diagnostics.reader_owners == ()
    +    assert diagnostics.writer_owner is None
    +    assert diagnostics.segment_owners == {}
    ```

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

End-to-end 与 Failure Matrix 组合 Commit、Reopen、Delete、Merge、Bad Input、Closed Handle 与 CLI Process 行为。

**关键测试语句**

```python
assert _ids(initial) == ("1",)
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

??? note "文件差异：tests/acceptance/test_failure_matrix.py"
    ```diff
    diff --git a/tests/acceptance/test_failure_matrix.py b/tests/acceptance/test_failure_matrix.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..03f2b8dcef5205ef30ae1edb4ea911bc2f0d21c9
    --- /dev/null
    +++ b/tests/acceptance/test_failure_matrix.py
    @@ -0,0 +1,191 @@
    +from pathlib import Path
    +
    +import pytest
    +
    +from minilucene import Index, KeywordField, Schema, TextField
    +from minilucene.errors import CloseError
    +from minilucene.query import TermQuery
    +from minilucene.storage.filesystem import FileSystemOps
    +from minilucene.storage.manifest import ManifestStore
    +from minilucene.storage.segment_store import (
    +    CorruptIndexError,
    +    SegmentStore,
    +)
    +
    +
    +def _schema():
    +    return Schema(
    +        id=KeywordField(stored=True),
    +        body=TextField(stored=True),
    +    )
    +
    +
    +class _FailingFileSystem(FileSystemOps):
    +    def __init__(self, *, filename=None, replace_manifest=False):
    +        self.filename = filename
    +        self.replace_manifest = replace_manifest
    +
    +    def write_bytes(self, path, data):
    +        if Path(path).name == self.filename:
    +            raise OSError(f"injected write failure: {self.filename}")
    +        super().write_bytes(path, data)
    +
    +    def replace(self, source, destination):
    +        if (
    +            self.replace_manifest
    +            and Path(destination).name == "manifest.json"
    +        ):
    +            raise OSError("injected manifest replacement failure")
    +        super().replace(source, destination)
    +
    +
    +def _validation_failure_before_ram_mutation(path):
    +    index = Index.create(path, _schema())
    +    with index.writer() as writer:
    +        writer.add_document(id="1", body="stable")
    +        before = (
    +            writer.buffered_document_count,
    +            writer.buffered_posting_count,
    +        )
    +        with pytest.raises(ValueError):
    +            writer.add_document(id="2", body=object())
    +        assert (
    +            writer.buffered_document_count,
    +            writer.buffered_posting_count,
    +        ) == before
    +    index.close()
    +
    +
    +def _segment_failure_before_rename(path):
    +    index = Index.create(path, _schema())
    +    with index.writer() as writer:
    +        writer.add_document(id="1", body="will fail")
    +        writer._segment_store = SegmentStore(
    +            path, fs=_FailingFileSystem(filename="postings.bin")
    +        )
    +        with pytest.raises(OSError, match="injected"):
    +            writer.flush()
    +        assert not (path / "segments" / "seg_000001").exists()
    +        assert not list((path / "segments").glob(".tmp-*"))
    +    index.close()
    +
    +
    +def _orphan_before_manifest_replace(path):
    +    index = Index.create(path, _schema())
    +    with index.writer() as writer:
    +        writer.add_document(id="1", body="orphan")
    +        writer._manifest_store = ManifestStore(
    +            path,
    +            fs=_FailingFileSystem(replace_manifest=True),
    +        )
    +        with pytest.raises(OSError, match="manifest"):
    +            writer.commit()
    +    reopened = Index.open(path)
    +    reader = reopened.open_reader()
    +    assert reader.num_live_docs == 0
    +    reader.close()
    +    reopened.close()
    +    assert (path / "segments" / "seg_000001").is_dir()
    +    index.close()
    +
    +
    +def _successful_replace_retains_owned_old_files(path):
    +    index = Index.create(path, _schema())
    +    with index.writer() as writer:
    +        writer.add_document(id="1", body="old")
    +        writer.commit()
    +    old_reader = index.open_reader()
    +    with index.writer() as writer:
    +        writer.add_document(id="2", body="new")
    +        writer.commit()
    +    assert (path / "segments" / "seg_000001").is_dir()
    +    assert (path / "segments" / "seg_000002").is_dir()
    +    assert old_reader.search(TermQuery("body", "old")).total_hits == 1
    +    old_reader.close()
    +    index.close()
    +
    +
    +def _checksum_corruption_fails_open(path):
    +    index = Index.create(path, _schema())
    +    with index.writer() as writer:
    +        writer.add_document(id="1", body="corrupt")
    +        writer.commit()
    +    postings = path / "segments" / "seg_000001" / "postings.bin"
    +    postings.write_bytes(postings.read_bytes() + b"\x00")
    +    with pytest.raises(CorruptIndexError, match="length|checksum"):
    +        Index.open(path).open_reader()
    +    index.close()
    +
    +
    +def _refresh_state_is_not_a_restart_root(path):
    +    index = Index.create(path, _schema())
    +    with index.writer() as writer:
    +        writer.add_document(id="1", body="nrt only")
    +        nrt = writer.refresh()
    +        assert nrt.search(TermQuery("body", "nrt")).total_hits == 1
    +        nrt.close()
    +    reopened = Index.open(path)
    +    reader = reopened.open_reader()
    +    assert reader.search(TermQuery("body", "nrt")).total_hits == 0
    +    reader.close()
    +    reopened.close()
    +    index.close()
    +
    +
    +@pytest.mark.parametrize(
    +    "scenario",
    +    [
    +        _validation_failure_before_ram_mutation,
    +        _segment_failure_before_rename,
    +        _orphan_before_manifest_replace,
    +        _successful_replace_retains_owned_old_files,
    +        _checksum_corruption_fails_open,
    +        _refresh_state_is_not_a_restart_root,
    +    ],
    +    ids=lambda scenario: scenario.__name__.removeprefix("_"),
    +)
    +def test_failure_matrix(tmp_path, scenario):
    +    scenario(tmp_path)
    +
    +
    +def test_merge_publish_failure_preserves_writer_set(tmp_path):
    +    index = Index.create(tmp_path, _schema())
    +    with index.writer() as writer:
    +        writer.add_document(id="1", body="one")
    +        writer.flush()
    +        writer.add_document(id="2", body="two")
    +        writer.commit()
    +    with index.writer() as writer:
    +        before = writer.segment_generations
    +        writer._segment_store = SegmentStore(
    +            tmp_path,
    +            fs=_FailingFileSystem(filename="postings.bin"),
    +        )
    +        with pytest.raises(OSError, match="injected"):
    +            writer.merge(before)
    +        assert writer.segment_generations == before
    +        assert not list((tmp_path / "segments").glob(".tmp-*"))
    +    index.close()
    +
    +
    +class _UnlinkFailingPath:
    +    def unlink(self):
    +        raise OSError("injected unlink failure")
    +
    +
    +def test_repeated_close_aggregates_cleanup_failures(tmp_path, monkeypatch):
    +    index = Index.create(tmp_path, _schema())
    +    writer = index.writer()
    +
    +    def fail_release(_owner_id):
    +        raise RuntimeError("injected release failure")
    +
    +    monkeypatch.setattr(writer._registry, "release", fail_release)
    +    real_lock = writer._lock_path
    +    writer._lock_path = _UnlinkFailingPath()
    +    with pytest.raises(CloseError) as error:
    +        writer.close()
    +    assert len(error.value.errors) == 2
    +    writer.close()
    +    real_lock.unlink()
    +    index.close()
    ```

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

End-to-end 与 Failure Matrix 组合 Commit、Reopen、Delete、Merge、Bad Input、Closed Handle 与 CLI Process 行为。

**关键测试语句**

```python
assert _ids(initial) == ("1",)
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

??? note "文件差异：tests/acceptance/test_owner_zero.py"
    ```diff
    diff --git a/tests/acceptance/test_owner_zero.py b/tests/acceptance/test_owner_zero.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..e903acdeb57925a7b48647104741aa3feac59736
    --- /dev/null
    +++ b/tests/acceptance/test_owner_zero.py
    @@ -0,0 +1,31 @@
    +from minilucene import Index, KeywordField, Schema, TextField
    +
    +
    +def test_every_explicit_owner_and_temporary_job_reaches_zero(tmp_path):
    +    index = Index.create(
    +        tmp_path,
    +        Schema(
    +            id=KeywordField(stored=True),
    +            body=TextField(stored=True),
    +        ),
    +    )
    +    with index.writer() as writer:
    +        writer.add_document(id="1", body="first")
    +        writer.flush()
    +        first = writer.refresh()
    +        writer.add_document(id="2", body="second")
    +        second = writer.refresh()
    +        writer.merge(writer.segment_generations)
    +        writer.commit()
    +        first.close()
    +        second.close()
    +    index.collect_garbage()
    +    index.close()
    +
    +    diagnostics = index.lifecycle_diagnostics()
    +    assert diagnostics.writer_owner is None
    +    assert diagnostics.reader_owners == ()
    +    assert diagnostics.segment_owners == {}
    +    assert diagnostics.temporary_jobs == ()
    +    assert not (index.path / ".writer.lock").exists()
    +    assert not list(index.path.rglob(".tmp-*"))
    ```

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

End-to-end 与 Failure Matrix 组合 Commit、Reopen、Delete、Merge、Bad Input、Closed Handle 与 CLI Process 行为。

**关键测试语句**

```python
assert _ids(initial) == ("1",)
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

??? note "文件差异：tests/contract/test_cli.py"
    ```diff
    diff --git a/tests/contract/test_cli.py b/tests/contract/test_cli.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..1a2216b28d81c36959967db25722c041232ae348
    --- /dev/null
    +++ b/tests/contract/test_cli.py
    @@ -0,0 +1,161 @@
    +import json
    +
    +import pytest
    +
    +from minilucene import KeywordField, Schema, TextField
    +from minilucene.cli import main
    +
    +
    +@pytest.fixture
    +def schema_file(tmp_path):
    +    schema = Schema(
    +        id=KeywordField(stored=True),
    +        title=TextField(stored=True, boost=2.0),
    +        body=TextField(stored=True),
    +    )
    +    path = tmp_path / "schema-input.json"
    +    path.write_text(
    +        json.dumps({"fields": schema.to_dict()}), encoding="utf-8"
    +    )
    +    return path
    +
    +
    +def _write_json(path, payload):
    +    path.write_text(json.dumps(payload), encoding="utf-8")
    +    return path
    +
    +
    +def test_cli_create_add_search_delete_and_merge(
    +    tmp_path, schema_file, capsys
    +):
    +    index_path = tmp_path / "index"
    +    first = _write_json(
    +        tmp_path / "first.json",
    +        {
    +            "id": "1",
    +            "title": "Kafka Replication",
    +            "body": "Kafka uses follower replicas.",
    +        },
    +    )
    +    second = _write_json(
    +        tmp_path / "second.json",
    +        {
    +            "id": "2",
    +            "title": "Rabbit",
    +            "body": "Rabbit queues messages.",
    +        },
    +    )
    +
    +    assert main(
    +        ["create", str(index_path), "--schema", str(schema_file)]
    +    ) == 0
    +    assert main(["add", str(index_path), str(first)]) == 0
    +    assert main(["add", str(index_path), str(second)]) == 0
    +    capsys.readouterr()
    +
    +    assert (
    +        main(
    +            [
    +                "search",
    +                str(index_path),
    +                '"follower replicas"',
    +                "--default-field",
    +                "body",
    +                "--top-k",
    +                "10",
    +                "--highlight",
    +                "body",
    +            ]
    +        )
    +        == 0
    +    )
    +    payload = json.loads(capsys.readouterr().out)
    +    assert payload["total_hits"] == 1
    +    assert payload["hits"][0]["stored_fields"]["id"] == "1"
    +    assert payload["hits"][0]["highlights"]["body"] == (
    +        "Kafka uses <em>follower replicas</em>."
    +    )
    +
    +    assert (
    +        main(["merge", str(index_path), "1", "2"]) == 0
    +    )
    +    capsys.readouterr()
    +    assert (
    +        main(["delete", str(index_path), "id", "1"]) == 0
    +    )
    +    delete_payload = json.loads(capsys.readouterr().out)
    +    assert delete_payload["deleted"] == 1
    +    assert (
    +        main(
    +            [
    +                "search",
    +                str(index_path),
    +                "kafka",
    +                "--default-field",
    +                "body",
    +            ]
    +        )
    +        == 0
    +    )
    +    assert json.loads(capsys.readouterr().out)["total_hits"] == 0
    +
    +
    +def test_cli_emits_canonical_json(tmp_path, schema_file, capsys):
    +    index_path = tmp_path / "index"
    +    main(["create", str(index_path), "--schema", str(schema_file)])
    +    capsys.readouterr()
    +    assert (
    +        main(
    +            [
    +                "search",
    +                str(index_path),
    +                "none",
    +                "--default-field",
    +                "body",
    +                "--top-k",
    +                "0",
    +            ]
    +        )
    +        == 0
    +    )
    +    assert capsys.readouterr().out == (
    +        '{"hits":[],"total_hits":0}\n'
    +    )
    +
    +
    +def test_domain_failure_exits_two_with_one_stderr_line(
    +    tmp_path, capsys
    +):
    +    assert (
    +        main(
    +            [
    +                "search",
    +                str(tmp_path / "missing"),
    +                "query",
    +                "--default-field",
    +                "body",
    +            ]
    +        )
    +        == 2
    +    )
    +    captured = capsys.readouterr()
    +    assert captured.out == ""
    +    assert captured.err.startswith("error: ")
    +    assert captured.err.count("\n") == 1
    +
    +
    +def test_unexpected_failures_are_not_swallowed(monkeypatch, tmp_path):
    +    def explode(_path):
    +        raise RuntimeError("unexpected")
    +
    +    monkeypatch.setattr("minilucene.cli.Index.open", explode)
    +    with pytest.raises(RuntimeError, match="unexpected"):
    +        main(
    +            [
    +                "search",
    +                str(tmp_path),
    +                "query",
    +                "--default-field",
    +                "body",
    +            ]
    +        )
    ```

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

End-to-end 与 Failure Matrix 组合 Commit、Reopen、Delete、Merge、Bad Input、Closed Handle 与 CLI Process 行为。

**关键测试语句**

```python
assert _ids(initial) == ("1",)
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

??? note "文件差异：tests/test_public_surface.py"
    ```diff
    diff --git a/tests/test_public_surface.py b/tests/test_public_surface.py
    index b5365f66d33290b410c23141fb8dc55adddcf10c..e3d33a3fd26c0cb69c520f38ee07f62162e11a48 100644
    --- a/tests/test_public_surface.py
    +++ b/tests/test_public_surface.py
    @@ -1,4 +1,10 @@
    -from minilucene import KeywordField, MemoryIndex, Schema, TextField
    +from minilucene import (
    +    KeywordField,
    +    MemoryIndex,
    +    Schema,
    +    TextField,
    +    __version__,
    +)


     def test_public_surface_imports():
    @@ -7,3 +13,7 @@ def test_public_surface_imports():
             body=TextField(stored=True),
         )
         assert MemoryIndex(schema).schema == schema
    +
    +
    +def test_package_exports_its_distribution_version():
    +    assert __version__ == "0.1.0"
    ```

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

End-to-end 与 Failure Matrix 组合 Commit、Reopen、Delete、Merge、Bad Input、Closed Handle 与 CLI Process 行为。

**关键测试语句**

```python
assert _ids(initial) == ("1",)
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

CLI 是 Public API 上的 Adapter；领域闭环意味着 Lifecycle、Persistence、Ranking 与 Failure Contract 经组合后仍成立。

### 为什么需要这个机制

核心机制需要一条轻量用户路径与组合失败证据，同时不能复制 Index/Search 语义。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Command 解析有界 JSON Argument、打开同一 Directory/Writer/Reader Object、调用已有 Operation、序列化结果并保留类型化错误退出。

### 机制板块

#### CLI 与领域闭环机制

Command 解析有界 JSON Argument、打开同一 Directory/Writer/Reader Object、调用已有 Operation、序列化结果并保留类型化错误退出。

??? note "文件差异：src/minilucene/cli.py"
    ```diff
    diff --git a/src/minilucene/cli.py b/src/minilucene/cli.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..8e504a44e172ae377e1448c9c05181a4c272ef1c
    --- /dev/null
    +++ b/src/minilucene/cli.py
    @@ -0,0 +1,181 @@
    +import argparse
    +import json
    +import sys
    +from collections.abc import Mapping, Sequence
    +from pathlib import Path
    +
    +from minilucene import Index, Schema
    +from minilucene.errors import MiniLuceneError
    +
    +
    +def _parser() -> argparse.ArgumentParser:
    +    parser = argparse.ArgumentParser(
    +        prog="minilucene",
    +        description="Direct-first MiniLucene reference CLI",
    +    )
    +    commands = parser.add_subparsers(dest="command", required=True)
    +
    +    create = commands.add_parser("create")
    +    create.add_argument("index", type=Path)
    +    create.add_argument("--schema", type=Path, required=True)
    +
    +    add = commands.add_parser("add")
    +    add.add_argument("index", type=Path)
    +    add.add_argument("documents", type=Path, nargs="+")
    +
    +    search = commands.add_parser("search")
    +    search.add_argument("index", type=Path)
    +    search.add_argument("query")
    +    search.add_argument("--default-field", required=True)
    +    search.add_argument("--top-k", type=int, default=10)
    +    search.add_argument(
    +        "--highlight", action="append", default=[]
    +    )
    +
    +    delete = commands.add_parser("delete")
    +    delete.add_argument("index", type=Path)
    +    delete.add_argument("field")
    +    delete.add_argument("term")
    +
    +    merge = commands.add_parser("merge")
    +    merge.add_argument("index", type=Path)
    +    merge.add_argument("segments", type=int, nargs="+")
    +    return parser
    +
    +
    +def _read_json(path: Path) -> object:
    +    return json.loads(
    +        path.read_text(encoding="utf-8", errors="strict")
    +    )
    +
    +
    +def _require_mapping(
    +    value: object, description: str
    +) -> Mapping[str, object]:
    +    if not isinstance(value, dict) or any(
    +        not isinstance(key, str) for key in value
    +    ):
    +        raise ValueError(f"{description} must be a JSON object")
    +    return value
    +
    +
    +def _emit(payload: Mapping[str, object]) -> None:
    +    print(
    +        json.dumps(
    +            payload,
    +            sort_keys=True,
    +            separators=(",", ":"),
    +        )
    +    )
    +
    +
    +def _create(args: argparse.Namespace) -> None:
    +    payload = _require_mapping(
    +        _read_json(args.schema), "schema file"
    +    )
    +    fields = _require_mapping(
    +        payload.get("fields"), "schema fields"
    +    )
    +    schema = Schema.from_dict(
    +        {
    +            name: _require_mapping(value, f"field {name}")
    +            for name, value in fields.items()
    +        }
    +    )
    +    with Index.create(args.index, schema):
    +        pass
    +    _emit({"index": str(args.index), "status": "created"})
    +
    +
    +def _add(args: argparse.Namespace) -> None:
    +    with Index.open(args.index) as index, index.writer() as writer:
    +        for path in args.documents:
    +            document = _require_mapping(
    +                _read_json(path), f"document {path}"
    +            )
    +            writer.add_document(**document)
    +        manifest = writer.commit()
    +    _emit(
    +        {
    +            "added": len(args.documents),
    +            "commit_generation": manifest.commit_generation,
    +        }
    +    )
    +
    +
    +def _search(args: argparse.Namespace) -> None:
    +    with (
    +        Index.open(args.index) as index,
    +        index.open_reader() as reader,
    +    ):
    +        results = reader.search_text(
    +            args.query,
    +            default_field=args.default_field,
    +            top_k=args.top_k,
    +            highlight_fields=tuple(args.highlight),
    +        )
    +    _emit(
    +        {
    +            "total_hits": results.total_hits,
    +            "hits": [
    +                {
    +                    "score": hit.score,
    +                    "segment_generation": (
    +                        hit.segment_generation
    +                    ),
    +                    "local_doc_id": hit.local_doc_id,
    +                    "stored_fields": dict(hit.stored_fields),
    +                    "highlights": dict(hit.highlights),
    +                }
    +                for hit in results.hits
    +            ],
    +        }
    +    )
    +
    +
    +def _delete(args: argparse.Namespace) -> None:
    +    with Index.open(args.index) as index, index.writer() as writer:
    +        deleted = writer.delete_by_term(args.field, args.term)
    +        manifest = writer.commit()
    +    _emit(
    +        {
    +            "deleted": deleted,
    +            "commit_generation": manifest.commit_generation,
    +        }
    +    )
    +
    +
    +def _merge(args: argparse.Namespace) -> None:
    +    with Index.open(args.index) as index, index.writer() as writer:
    +        descriptor = writer.merge(tuple(args.segments))
    +        manifest = writer.commit()
    +    _emit(
    +        {
    +            "merged_segment_generation": descriptor.generation,
    +            "commit_generation": manifest.commit_generation,
    +        }
    +    )
    +
    +
    +_COMMANDS = {
    +    "create": _create,
    +    "add": _add,
    +    "search": _search,
    +    "delete": _delete,
    +    "merge": _merge,
    +}
    +
    +
    +def main(argv: Sequence[str] | None = None) -> int:
    +    args = _parser().parse_args(argv)
    +    try:
    +        _COMMANDS[args.command](args)
    +    except (
    +        MiniLuceneError,
    +        ValueError,
    +        OSError,
    +        UnicodeError,
    +    ) as error:
    +        print(f"error: {error}", file=sys.stderr)
    +        return 2
    +    return 0
    ```

**是什么，为什么现在需要**

CLI 是 Public API 上的 Adapter；领域闭环意味着 Lifecycle、Persistence、Ranking 与 Failure Contract 经组合后仍成立。

**在运行时做什么**

Command 解析有界 JSON Argument、打开同一 Directory/Writer/Reader Object、调用已有 Operation、序列化结果并保留类型化错误退出。

**关键语句理解**

Adapter 可以翻译 Input/Output，但不得拥有另一套 Commit、Query、Scoring 或 Lifecycle Rule。

#### 包、Fixture 与工程支撑

保持包导出、测试语料、依赖与运行环境可复现。

??? note "支撑文件差异（2 个文件）"
    **`pyproject.toml`**

    ```diff
    diff --git a/pyproject.toml b/pyproject.toml
    index ffdd634f061ce485ef7703c4445fc1c35f833a5e..09e9d1ce9076824ff91644b16c79b5ea03ebeab2 100644
    --- a/pyproject.toml
    +++ b/pyproject.toml
    @@ -9,6 +9,9 @@ description = "Direct-first MiniLucene reference implementation"
     requires-python = ">=3.12"
     dependencies = []

    +[project.scripts]
    +minilucene = "minilucene.cli:main"
    +
     [dependency-groups]
     dev = [
       "pytest>=9,<10",
    ```

    **`src/minilucene/__init__.py`**

    ```diff
    diff --git a/src/minilucene/__init__.py b/src/minilucene/__init__.py
    index 26578c0be111c3c4f0dbb9c9848861796ee3d2e9..d5e0568f009e5183d358f152315de75c3a13e4c5 100644
    --- a/src/minilucene/__init__.py
    +++ b/src/minilucene/__init__.py
    @@ -3,6 +3,8 @@ from minilucene.index.memory import MemoryIndex
     from minilucene.reader import IndexReader
     from minilucene.schema import KeywordField, Schema, StoredField, TextField

    +__version__ = "0.1.0"
    +
     __all__ = [
         "Index",
         "IndexReader",
    @@ -11,4 +13,5 @@ __all__ = [
         "Schema",
         "StoredField",
         "TextField",
    +    "__version__",
     ]
    ```


### 验证证据

运行 `uv run pytest -q $(cat journey/stages/28-cli-domain-closure/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

Adapter 可以翻译 Input/Output，但不得拥有另一套 Commit、Query、Scoring 或 Lifecycle Rule。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 1 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/01-getting-started.md)

[Complete reference patch / 完整参考补丁](https://github.com/system-in-miniature/mini-lucene/blob/main/journey/stages/28-cli-domain-closure/stage.patch)

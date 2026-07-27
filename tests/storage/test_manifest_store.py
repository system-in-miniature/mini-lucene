from pathlib import Path

import pytest

from minilucene.storage.filesystem import FileSystemOps
from minilucene.storage.manifest import (
    Manifest,
    ManifestStore,
    SegmentCommit,
)


class ReplaceFailingFileSystem(FileSystemOps):
    def replace(self, source, destination):
        raise OSError("injected manifest replace failure")


def test_create_and_read_generation_zero_manifest(tmp_path):
    store = ManifestStore(tmp_path)
    created = store.create(schema_fingerprint="schema")
    assert store.read() == created
    assert created.commit_generation == 0
    assert created.segment_generations == ()
    assert created.next_segment_generation == 1
    assert created.next_commit_generation == 1


def test_open_ignores_complete_orphan_segment(tmp_path):
    orphan = tmp_path / "segments" / "seg_000001"
    orphan.mkdir(parents=True)
    (orphan / "segment.json").write_text("{}", encoding="utf-8")
    store = ManifestStore(tmp_path)
    store.create(schema_fingerprint="schema")
    assert store.read().segment_generations == ()


def test_replace_failure_preserves_old_manifest(tmp_path):
    stable_store = ManifestStore(tmp_path)
    old = stable_store.create(schema_fingerprint="schema")
    updated = Manifest.next_from(
        old,
        segments=(SegmentCommit(segment_generation=1),),
    )
    failing_store = ManifestStore(
        tmp_path,
        fs=ReplaceFailingFileSystem(),
    )
    with pytest.raises(OSError, match="injected"):
        failing_store.write_atomic(updated)
    assert stable_store.read() == old


def test_manifest_round_trips_live_doc_metadata(tmp_path):
    store = ManifestStore(tmp_path)
    old = store.create(schema_fingerprint="schema")
    updated = Manifest.next_from(
        old,
        segments=(
            SegmentCommit(
                segment_generation=7,
                live_docs_generation=2,
                live_docs_checksum="abc",
            ),
        ),
    )
    store.write_atomic(updated)
    assert store.read() == updated


def test_manifest_rejects_unknown_format_version(tmp_path):
    store = ManifestStore(tmp_path)
    store.create(schema_fingerprint="schema")
    manifest_path = tmp_path / "manifest.json"
    text = manifest_path.read_text(encoding="utf-8")
    manifest_path.write_text(
        text.replace('"format_version":1', '"format_version":2'),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="format version"):
        store.read()


def test_manifest_path_is_the_only_root_file(tmp_path):
    store = ManifestStore(tmp_path)
    store.create(schema_fingerprint="schema")
    assert Path("manifest.json") == store.path.relative_to(tmp_path)

from pathlib import Path

import pytest

from minilucene import Index, KeywordField, Schema, TextField
from minilucene.errors import CloseError
from minilucene.query import TermQuery
from minilucene.storage.filesystem import FileSystemOps
from minilucene.storage.manifest import ManifestStore
from minilucene.storage.segment_store import (
    CorruptIndexError,
    SegmentStore,
)


def _schema():
    return Schema(
        id=KeywordField(stored=True),
        body=TextField(stored=True),
    )


class _FailingFileSystem(FileSystemOps):
    def __init__(self, *, filename=None, replace_manifest=False):
        self.filename = filename
        self.replace_manifest = replace_manifest

    def write_bytes(self, path, data):
        if Path(path).name == self.filename:
            raise OSError(f"injected write failure: {self.filename}")
        super().write_bytes(path, data)

    def replace(self, source, destination):
        if (
            self.replace_manifest
            and Path(destination).name == "manifest.json"
        ):
            raise OSError("injected manifest replacement failure")
        super().replace(source, destination)


def _validation_failure_before_ram_mutation(path):
    index = Index.create(path, _schema())
    with index.writer() as writer:
        writer.add_document(id="1", body="stable")
        before = (
            writer.buffered_document_count,
            writer.buffered_posting_count,
        )
        with pytest.raises(ValueError):
            writer.add_document(id="2", body=object())
        assert (
            writer.buffered_document_count,
            writer.buffered_posting_count,
        ) == before
    index.close()


def _segment_failure_before_rename(path):
    index = Index.create(path, _schema())
    with index.writer() as writer:
        writer.add_document(id="1", body="will fail")
        writer._segment_store = SegmentStore(
            path, fs=_FailingFileSystem(filename="postings.bin")
        )
        with pytest.raises(OSError, match="injected"):
            writer.flush()
        assert not (path / "segments" / "seg_000001").exists()
        assert not list((path / "segments").glob(".tmp-*"))
    index.close()


def _orphan_before_manifest_replace(path):
    index = Index.create(path, _schema())
    with index.writer() as writer:
        writer.add_document(id="1", body="orphan")
        writer._manifest_store = ManifestStore(
            path,
            fs=_FailingFileSystem(replace_manifest=True),
        )
        with pytest.raises(OSError, match="manifest"):
            writer.commit()
    reopened = Index.open(path)
    reader = reopened.open_reader()
    assert reader.num_live_docs == 0
    reader.close()
    reopened.close()
    assert (path / "segments" / "seg_000001").is_dir()
    index.close()


def _successful_replace_retains_owned_old_files(path):
    index = Index.create(path, _schema())
    with index.writer() as writer:
        writer.add_document(id="1", body="old")
        writer.commit()
    old_reader = index.open_reader()
    with index.writer() as writer:
        writer.add_document(id="2", body="new")
        writer.commit()
    assert (path / "segments" / "seg_000001").is_dir()
    assert (path / "segments" / "seg_000002").is_dir()
    assert old_reader.search(TermQuery("body", "old")).total_hits == 1
    old_reader.close()
    index.close()


def _checksum_corruption_fails_open(path):
    index = Index.create(path, _schema())
    with index.writer() as writer:
        writer.add_document(id="1", body="corrupt")
        writer.commit()
    postings = path / "segments" / "seg_000001" / "postings.bin"
    postings.write_bytes(postings.read_bytes() + b"\x00")
    with pytest.raises(CorruptIndexError, match="length|checksum"):
        Index.open(path).open_reader()
    index.close()


def _refresh_state_is_not_a_restart_root(path):
    index = Index.create(path, _schema())
    with index.writer() as writer:
        writer.add_document(id="1", body="nrt only")
        nrt = writer.refresh()
        assert nrt.search(TermQuery("body", "nrt")).total_hits == 1
        nrt.close()
    reopened = Index.open(path)
    reader = reopened.open_reader()
    assert reader.search(TermQuery("body", "nrt")).total_hits == 0
    reader.close()
    reopened.close()
    index.close()


@pytest.mark.parametrize(
    "scenario",
    [
        _validation_failure_before_ram_mutation,
        _segment_failure_before_rename,
        _orphan_before_manifest_replace,
        _successful_replace_retains_owned_old_files,
        _checksum_corruption_fails_open,
        _refresh_state_is_not_a_restart_root,
    ],
    ids=lambda scenario: scenario.__name__.removeprefix("_"),
)
def test_failure_matrix(tmp_path, scenario):
    scenario(tmp_path)


def test_merge_publish_failure_preserves_writer_set(tmp_path):
    index = Index.create(tmp_path, _schema())
    with index.writer() as writer:
        writer.add_document(id="1", body="one")
        writer.flush()
        writer.add_document(id="2", body="two")
        writer.commit()
    with index.writer() as writer:
        before = writer.segment_generations
        writer._segment_store = SegmentStore(
            tmp_path,
            fs=_FailingFileSystem(filename="postings.bin"),
        )
        with pytest.raises(OSError, match="injected"):
            writer.merge(before)
        assert writer.segment_generations == before
        assert not list((tmp_path / "segments").glob(".tmp-*"))
    index.close()


class _UnlinkFailingPath:
    def unlink(self):
        raise OSError("injected unlink failure")


def test_repeated_close_aggregates_cleanup_failures(tmp_path, monkeypatch):
    index = Index.create(tmp_path, _schema())
    writer = index.writer()

    def fail_release(_owner_id):
        raise RuntimeError("injected release failure")

    monkeypatch.setattr(writer._registry, "release", fail_release)
    real_lock = writer._lock_path
    writer._lock_path = _UnlinkFailingPath()
    with pytest.raises(CloseError) as error:
        writer.close()
    assert len(error.value.errors) == 2
    writer.close()
    real_lock.unlink()
    index.close()

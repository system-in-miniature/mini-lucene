from pathlib import Path

import pytest

from minilucene.index.memory import RamIndexBuilder
from minilucene.schema import Schema, TextField
from minilucene.storage.filesystem import FileSystemOps
from minilucene.storage.image import SegmentImage
from minilucene.storage.segment_store import (
    CorruptIndexError,
    SegmentStore,
)


def build_image():
    schema = Schema(body=TextField(stored=True))
    builder = RamIndexBuilder(schema)
    builder.add_document({"body": "immutable segment"})
    return SegmentImage.from_memory_segment(
        generation=1,
        schema_fingerprint=schema.fingerprint,
        segment=builder.freeze(generation=0),
    )


class RecordingFileSystem(FileSystemOps):
    def __init__(self):
        self.writes = []
        self.file_syncs = []
        self.directory_syncs = []

    def write_bytes(self, path, data):
        self.writes.append(Path(path))
        super().write_bytes(path, data)

    def fsync_file(self, path):
        self.file_syncs.append(Path(path))
        super().fsync_file(path)

    def fsync_directory(self, path):
        self.directory_syncs.append(Path(path))
        super().fsync_directory(path)


class FailingFileSystem(FileSystemOps):
    def __init__(self, filename):
        self.filename = filename

    def write_bytes(self, path, data):
        if Path(path).name == self.filename:
            raise OSError(f"injected write failure: {self.filename}")
        super().write_bytes(path, data)


def test_segment_store_writes_metadata_last(tmp_path):
    fs = RecordingFileSystem()
    store = SegmentStore(tmp_path, fs=fs)
    descriptor = store.publish(build_image())
    assert fs.writes[-1].name == "segment.json"
    assert fs.file_syncs[-1].name == "segment.json"
    assert descriptor.path == Path("segments/seg_000001")
    assert not list((tmp_path / "segments").glob(".tmp-*"))


def test_failed_publish_never_creates_final_directory(tmp_path):
    store = SegmentStore(
        tmp_path,
        fs=FailingFileSystem("postings.bin"),
    )
    with pytest.raises(OSError, match="injected"):
        store.publish(build_image())
    assert not (tmp_path / "segments" / "seg_000001").exists()
    assert not list((tmp_path / "segments").glob(".tmp-*"))


def test_segment_store_open_round_trips_image(tmp_path):
    image = build_image()
    store = SegmentStore(tmp_path)
    store.publish(image)
    assert store.open(1, image.schema_fingerprint) == image


def test_segment_store_rejects_checksum_corruption(tmp_path):
    image = build_image()
    store = SegmentStore(tmp_path)
    descriptor = store.publish(image)
    postings = tmp_path / descriptor.path / "postings.bin"
    postings.write_bytes(postings.read_bytes() + b"\x00")
    with pytest.raises(CorruptIndexError, match="length|checksum"):
        store.open(1, image.schema_fingerprint)


def test_segment_store_rejects_schema_mismatch(tmp_path):
    image = build_image()
    store = SegmentStore(tmp_path)
    store.publish(image)
    with pytest.raises(CorruptIndexError, match="schema"):
        store.open(1, "different")

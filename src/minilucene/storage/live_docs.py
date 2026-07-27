import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

from minilucene.storage.filesystem import FileSystemOps
from minilucene.storage.varint import (
    decode_uvarint,
    encode_uvarint,
)


class LiveDocsCodec:
    @staticmethod
    def encode(*, max_doc: int, live_docs: frozenset[int]) -> bytes:
        if not isinstance(max_doc, int) or max_doc < 0:
            raise ValueError("live-doc max_doc must be non-negative")
        if any(doc_id < 0 or doc_id >= max_doc for doc_id in live_docs):
            raise ValueError("live document ID outside segment")
        byte_count = (max_doc + 7) // 8
        bits = bytearray(byte_count)
        for doc_id in live_docs:
            bits[doc_id // 8] |= 1 << (doc_id % 8)
        return (
            encode_uvarint(max_doc)
            + encode_uvarint(byte_count)
            + bytes(bits)
        )

    @staticmethod
    def decode(
        expected_max_doc: int, data: bytes
    ) -> frozenset[int]:
        max_doc, offset = decode_uvarint(data, 0)
        if max_doc != expected_max_doc:
            raise ValueError("live-doc max_doc mismatch")
        byte_count, offset = decode_uvarint(data, offset)
        expected_byte_count = (max_doc + 7) // 8
        if byte_count != expected_byte_count:
            raise ValueError("live-doc bitset length mismatch")
        end = offset + byte_count
        if end != len(data):
            raise ValueError("live-doc data length mismatch")
        bits = data[offset:end]
        remainder = max_doc % 8
        if bits and remainder:
            unused_mask = ~((1 << remainder) - 1) & 0xFF
            if bits[-1] & unused_mask:
                raise ValueError("unused live-doc bits must be zero")
        return frozenset(
            doc_id
            for doc_id in range(max_doc)
            if bits[doc_id // 8] & (1 << (doc_id % 8))
        )


@dataclass(frozen=True, slots=True)
class LiveDocsDescriptor:
    segment_generation: int
    live_docs_generation: int
    checksum: str
    path: Path


class LiveDocsStore:
    def __init__(
        self, root: Path, *, fs: FileSystemOps | None = None
    ) -> None:
        self.root = Path(root)
        self.fs = fs or FileSystemOps()

    @staticmethod
    def _segment_name(generation: int) -> str:
        return f"seg_{generation:06d}"

    @staticmethod
    def _live_name(generation: int) -> str:
        return f"live_{generation:06d}.bin"

    def publish(
        self,
        *,
        segment_generation: int,
        live_docs_generation: int,
        max_doc: int,
        live_docs: frozenset[int],
    ) -> LiveDocsDescriptor:
        if segment_generation <= 0 or live_docs_generation <= 0:
            raise ValueError("live-doc generations must be positive")
        segment_path = (
            self.root
            / "segments"
            / self._segment_name(segment_generation)
        )
        if not self.fs.exists(segment_path):
            raise FileNotFoundError(
                f"segment does not exist: {segment_path}"
            )
        filename = self._live_name(live_docs_generation)
        destination = segment_path / filename
        if self.fs.exists(destination):
            raise FileExistsError(
                f"live-doc generation already exists: {destination}"
            )
        temporary = segment_path / f".tmp-{filename}-{uuid.uuid4().hex}"
        data = LiveDocsCodec.encode(
            max_doc=max_doc,
            live_docs=live_docs,
        )
        try:
            self.fs.write_bytes(temporary, data)
            self.fs.fsync_file(temporary)
            self.fs.replace(temporary, destination)
            self.fs.fsync_directory(segment_path)
        except BaseException:
            if self.fs.exists(temporary):
                try:
                    self.fs.remove_file(temporary)
                except OSError:
                    pass
            raise
        return LiveDocsDescriptor(
            segment_generation=segment_generation,
            live_docs_generation=live_docs_generation,
            checksum=hashlib.sha256(data).hexdigest(),
            path=destination.relative_to(self.root),
        )

    def read(
        self,
        *,
        segment_generation: int,
        live_docs_generation: int,
        expected_checksum: str,
        max_doc: int,
    ) -> frozenset[int]:
        path = (
            self.root
            / "segments"
            / self._segment_name(segment_generation)
            / self._live_name(live_docs_generation)
        )
        data = self.fs.read_bytes(path)
        if hashlib.sha256(data).hexdigest() != expected_checksum:
            raise ValueError("live-doc checksum mismatch")
        return LiveDocsCodec.decode(max_doc, data)

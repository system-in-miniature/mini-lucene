import hashlib
import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from minilucene.storage.codec import SegmentDataCodec
from minilucene.storage.filesystem import FileSystemOps
from minilucene.storage.image import SegmentImage

_MAGIC = "MINILUCENE_SEGMENT"
_FORMAT_VERSION = 1
_CODEC = "educational-v1"
_DATA_FILE_ORDER = (
    "terms.bin",
    "postings.bin",
    "stored.bin",
    "norms.bin",
)


class CorruptIndexError(ValueError):
    """Raised when persisted index bytes fail strict validation."""


@dataclass(frozen=True, slots=True)
class SegmentDescriptor:
    generation: int
    schema_fingerprint: str
    max_doc: int
    path: Path


class SegmentStore:
    def __init__(
        self, root: Path, *, fs: FileSystemOps | None = None
    ) -> None:
        self.root = Path(root)
        self.fs = fs or FileSystemOps()
        self.segments_path = self.root / "segments"
        self.fs.mkdir(self.segments_path, parents=True, exist_ok=True)

    @staticmethod
    def _directory_name(generation: int) -> str:
        return f"seg_{generation:06d}"

    def generation_exists(self, generation: int) -> bool:
        return self.fs.exists(
            self.segments_path / self._directory_name(generation)
        )

    def publish(self, image: SegmentImage) -> SegmentDescriptor:
        relative_path = Path("segments") / self._directory_name(
            image.generation
        )
        final_path = self.root / relative_path
        if self.fs.exists(final_path):
            raise FileExistsError(f"segment already exists: {final_path}")
        temporary_path = self.segments_path / (
            f".tmp-{self._directory_name(image.generation)}-"
            f"{uuid.uuid4().hex}"
        )
        self.fs.mkdir(temporary_path)
        try:
            files = SegmentDataCodec.encode(image)
            metadata_files: dict[str, dict[str, object]] = {}
            for filename in _DATA_FILE_ORDER:
                data = files[filename]
                path = temporary_path / filename
                self.fs.write_bytes(path, data)
                self.fs.fsync_file(path)
                metadata_files[filename] = {
                    "length": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            metadata = {
                "magic": _MAGIC,
                "format_version": _FORMAT_VERSION,
                "generation": image.generation,
                "schema_fingerprint": image.schema_fingerprint,
                "max_doc": image.max_doc,
                "codec": _CODEC,
                "files": metadata_files,
            }
            metadata_bytes = json.dumps(
                metadata,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            metadata_path = temporary_path / "segment.json"
            self.fs.write_bytes(metadata_path, metadata_bytes)
            self.fs.fsync_file(metadata_path)
            self.fs.fsync_directory(temporary_path)
            self.fs.replace(temporary_path, final_path)
            self.fs.fsync_directory(self.segments_path)
        except BaseException:
            if self.fs.exists(temporary_path):
                try:
                    self.fs.remove_tree(temporary_path)
                except OSError:
                    pass
            raise
        return SegmentDescriptor(
            generation=image.generation,
            schema_fingerprint=image.schema_fingerprint,
            max_doc=image.max_doc,
            path=relative_path,
        )

    def open(
        self, generation: int, expected_schema_fingerprint: str
    ) -> SegmentImage:
        segment_path = self.segments_path / self._directory_name(
            generation
        )
        try:
            metadata = self._read_metadata(segment_path)
            self._validate_metadata(
                metadata,
                generation=generation,
                schema_fingerprint=expected_schema_fingerprint,
            )
            files = self._read_and_validate_files(segment_path, metadata)
            image = SegmentDataCodec.decode(
                generation=generation,
                schema_fingerprint=expected_schema_fingerprint,
                files=files,
            )
            if image.max_doc != metadata["max_doc"]:
                raise CorruptIndexError("segment max_doc mismatch")
            return image
        except CorruptIndexError:
            raise
        except (OSError, ValueError, TypeError, KeyError) as error:
            raise CorruptIndexError(
                f"cannot open segment {generation}: {error}"
            ) from error

    def _read_metadata(self, segment_path: Path) -> dict[str, object]:
        try:
            value = json.loads(
                self.fs.read_bytes(
                    segment_path / "segment.json"
                ).decode("utf-8", errors="strict")
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise CorruptIndexError("invalid segment metadata JSON") from error
        if not isinstance(value, dict):
            raise CorruptIndexError("segment metadata must be an object")
        return value

    @staticmethod
    def _validate_metadata(
        metadata: dict[str, object],
        *,
        generation: int,
        schema_fingerprint: str,
    ) -> None:
        if metadata.get("magic") != _MAGIC:
            raise CorruptIndexError("unknown segment magic")
        if metadata.get("format_version") != _FORMAT_VERSION:
            raise CorruptIndexError("unknown segment format version")
        if metadata.get("codec") != _CODEC:
            raise CorruptIndexError("unknown segment codec")
        if metadata.get("generation") != generation:
            raise CorruptIndexError("segment generation mismatch")
        if metadata.get("schema_fingerprint") != schema_fingerprint:
            raise CorruptIndexError("segment schema fingerprint mismatch")
        if (
            not isinstance(metadata.get("max_doc"), int)
            or metadata["max_doc"] < 0
        ):
            raise CorruptIndexError("invalid segment max_doc")
        files = metadata.get("files")
        if not isinstance(files, dict) or set(files) != set(
            _DATA_FILE_ORDER
        ):
            raise CorruptIndexError("invalid segment file metadata")

    def _read_and_validate_files(
        self, segment_path: Path, metadata: dict[str, object]
    ) -> dict[str, bytes]:
        file_metadata = metadata["files"]
        if not isinstance(file_metadata, dict):
            raise CorruptIndexError("invalid segment file metadata")
        result: dict[str, bytes] = {}
        for filename in _DATA_FILE_ORDER:
            expected = file_metadata[filename]
            if not isinstance(expected, dict):
                raise CorruptIndexError("invalid file metadata entry")
            data = self.fs.read_bytes(segment_path / filename)
            if expected.get("length") != len(data):
                raise CorruptIndexError(f"{filename} length mismatch")
            if expected.get("sha256") != hashlib.sha256(data).hexdigest():
                raise CorruptIndexError(f"{filename} checksum mismatch")
            result[filename] = data
        return result

import json
from pathlib import Path

from minilucene.errors import (
    IndexAlreadyExistsError,
    IndexNotFoundError,
    SchemaMismatchError,
)
from minilucene.reader import IndexReader
from minilucene.schema import Schema
from minilucene.storage.filesystem import FileSystemOps
from minilucene.storage.manifest import Manifest, ManifestStore
from minilucene.storage.segment_store import SegmentStore

_SCHEMA_FORMAT_VERSION = 1


class Index:
    def __init__(self, path: Path, schema: Schema) -> None:
        self.path = Path(path)
        self.schema = schema
        self._manifest_store = ManifestStore(self.path)

    @classmethod
    def create(cls, path: Path, schema: Schema) -> "Index":
        path = Path(path)
        if path.exists() and any(path.iterdir()):
            raise IndexAlreadyExistsError(
                f"index path is not empty: {path}"
            )
        fs = FileSystemOps()
        fs.mkdir(path, parents=True, exist_ok=True)
        cls._write_schema(path, schema, fs)
        ManifestStore(path, fs=fs).create(
            schema_fingerprint=schema.fingerprint
        )
        return cls(path, schema)

    @classmethod
    def open(
        cls, path: Path, schema: Schema | None = None
    ) -> "Index":
        path = Path(path)
        if not (path / "manifest.json").exists():
            raise IndexNotFoundError(f"index manifest not found: {path}")
        persisted_schema = cls._read_schema(path)
        manifest = ManifestStore(path).read()
        if manifest.schema_fingerprint != persisted_schema.fingerprint:
            raise SchemaMismatchError(
                "manifest and persisted schema fingerprints differ"
            )
        if (
            schema is not None
            and schema.fingerprint != persisted_schema.fingerprint
        ):
            raise SchemaMismatchError(
                "supplied schema fingerprint does not match index"
            )
        return cls(path, persisted_schema)

    @staticmethod
    def _write_schema(
        path: Path, schema: Schema, fs: FileSystemOps
    ) -> None:
        payload = {
            "format_version": _SCHEMA_FORMAT_VERSION,
            "fields": schema.to_dict(),
            "fingerprint": schema.fingerprint,
        }
        temporary = path / "schema.tmp"
        destination = path / "schema.json"
        fs.write_bytes(
            temporary,
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8"),
        )
        fs.fsync_file(temporary)
        fs.replace(temporary, destination)
        fs.fsync_directory(path)

    @staticmethod
    def _read_schema(path: Path) -> Schema:
        try:
            payload = json.loads(
                (path / "schema.json")
                .read_text(encoding="utf-8", errors="strict")
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise SchemaMismatchError(
                f"cannot read persisted schema: {error}"
            ) from error
        if not isinstance(payload, dict):
            raise SchemaMismatchError("persisted schema must be an object")
        if payload.get("format_version") != _SCHEMA_FORMAT_VERSION:
            raise SchemaMismatchError("unknown schema format version")
        fields = payload.get("fields")
        if not isinstance(fields, dict):
            raise SchemaMismatchError("persisted schema fields are invalid")
        try:
            schema = Schema.from_dict(fields)
        except ValueError as error:
            raise SchemaMismatchError(str(error)) from error
        if payload.get("fingerprint") != schema.fingerprint:
            raise SchemaMismatchError(
                "persisted schema fingerprint does not match fields"
            )
        return schema

    def manifest(self) -> Manifest:
        return self._manifest_store.read()

    def writer(self, **options):
        from minilucene.writer import IndexWriter

        return IndexWriter(self, **options)

    def open_reader(self) -> IndexReader:
        manifest = self.manifest()
        segment_store = SegmentStore(self.path)
        segments = tuple(
            segment_store.open(
                segment.segment_generation,
                manifest.schema_fingerprint,
            )
            for segment in manifest.segments
        )
        return IndexReader(self.schema, segments)

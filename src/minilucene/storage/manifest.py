"""Validate and atomically publish the durable index commit root.

Segment files may exist without being committed, but recovery follows only
``manifest.json``.  Publishing uses temp-write, file fsync, atomic rename, and
directory fsync so a restart observes either the previous complete manifest or
the new complete manifest, never a partially written root.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from minilucene.storage.filesystem import FileSystemOps

_FORMAT_VERSION = 1


@dataclass(frozen=True, slots=True)
class SegmentCommit:
    segment_generation: int
    live_docs_generation: int | None = None
    live_docs_checksum: str | None = None

    def __post_init__(self) -> None:
        if self.segment_generation <= 0:
            raise ValueError("segment generation must be positive")
        if (self.live_docs_generation is None) != (
            self.live_docs_checksum is None
        ):
            raise ValueError(
                "live-doc generation and checksum must appear together"
            )
        if (
            self.live_docs_generation is not None
            and self.live_docs_generation <= 0
        ):
            raise ValueError("live-doc generation must be positive")
        if self.live_docs_checksum == "":
            raise ValueError("live-doc checksum must be non-empty")


@dataclass(frozen=True, slots=True)
class Manifest:
    """A validated point-in-time list of committed segment generations."""

    format_version: int
    schema_fingerprint: str
    commit_generation: int
    segments: tuple[SegmentCommit, ...]
    next_segment_generation: int
    next_commit_generation: int

    def __post_init__(self) -> None:
        if self.format_version != _FORMAT_VERSION:
            raise ValueError("unknown manifest format version")
        if not self.schema_fingerprint:
            raise ValueError("manifest schema fingerprint must be non-empty")
        if self.commit_generation < 0:
            raise ValueError("commit generation must be non-negative")
        if self.next_commit_generation <= self.commit_generation:
            raise ValueError(
                "next commit generation must exceed current generation"
            )
        generations = self.segment_generations
        if len(set(generations)) != len(generations):
            raise ValueError("manifest segment generations must be unique")
        if self.next_segment_generation <= max(generations, default=0):
            raise ValueError(
                "next segment generation must exceed referenced segments"
            )

    @property
    def segment_generations(self) -> tuple[int, ...]:
        return tuple(
            segment.segment_generation for segment in self.segments
        )

    @classmethod
    def initial(cls, schema_fingerprint: str) -> "Manifest":
        return cls(
            format_version=_FORMAT_VERSION,
            schema_fingerprint=schema_fingerprint,
            commit_generation=0,
            segments=(),
            next_segment_generation=1,
            next_commit_generation=1,
        )

    @classmethod
    def next_from(
        cls,
        current: "Manifest",
        *,
        segments: tuple[SegmentCommit, ...],
        next_segment_generation: int | None = None,
    ) -> "Manifest":
        minimum_next_segment = max(
            (
                segment.segment_generation
                for segment in segments
            ),
            default=0,
        ) + 1
        return cls(
            format_version=_FORMAT_VERSION,
            schema_fingerprint=current.schema_fingerprint,
            commit_generation=current.next_commit_generation,
            segments=tuple(segments),
            next_segment_generation=max(
                current.next_segment_generation,
                minimum_next_segment,
                next_segment_generation or 1,
            ),
            next_commit_generation=current.next_commit_generation + 1,
        )


class ManifestStore:
    """Persist the single restart-visible commit root."""

    def __init__(
        self, root: Path, *, fs: FileSystemOps | None = None
    ) -> None:
        self.root = Path(root)
        self.fs = fs or FileSystemOps()
        self.fs.mkdir(self.root, parents=True, exist_ok=True)
        self.path = self.root / "manifest.json"
        self.temporary_path = self.root / "manifest.tmp"

    def create(self, *, schema_fingerprint: str) -> Manifest:
        if self.fs.exists(self.path):
            raise FileExistsError(f"manifest already exists: {self.path}")
        manifest = Manifest.initial(schema_fingerprint)
        self.write_atomic(manifest)
        return manifest

    def write_atomic(self, manifest: Manifest) -> None:
        """Durably replace the current manifest without exposing partial JSON."""

        data = json.dumps(
            {
                "format_version": manifest.format_version,
                "schema_fingerprint": manifest.schema_fingerprint,
                "commit_generation": manifest.commit_generation,
                "segments": [
                    asdict(segment) for segment in manifest.segments
                ],
                "next_segment_generation": (
                    manifest.next_segment_generation
                ),
                "next_commit_generation": manifest.next_commit_generation,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        # Durability needs both levels: fsync the temporary file before rename,
        # then fsync the directory so the name replacement itself survives a
        # crash.  The manifest is last because it makes earlier segment and
        # live-doc files reachable during recovery.
        self.fs.write_bytes(self.temporary_path, data)
        self.fs.fsync_file(self.temporary_path)
        self.fs.replace(self.temporary_path, self.path)
        self.fs.fsync_directory(self.root)

    def read(self) -> Manifest:
        try:
            value = json.loads(
                self.fs.read_bytes(self.path).decode(
                    "utf-8", errors="strict"
                )
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError(f"invalid manifest: {error}") from error
        if not isinstance(value, dict):
            raise TypeError("manifest must be a JSON object")
        expected_keys = {
            "format_version",
            "schema_fingerprint",
            "commit_generation",
            "segments",
            "next_segment_generation",
            "next_commit_generation",
        }
        if set(value) != expected_keys:
            raise ValueError("manifest fields do not match format")
        raw_segments = value["segments"]
        if not isinstance(raw_segments, list):
            raise TypeError("manifest segments must be a list")
        try:
            segments = tuple(
                SegmentCommit(**segment) for segment in raw_segments
            )
            return Manifest(
                format_version=value["format_version"],
                schema_fingerprint=value["schema_fingerprint"],
                commit_generation=value["commit_generation"],
                segments=segments,
                next_segment_generation=value[
                    "next_segment_generation"
                ],
                next_commit_generation=value[
                    "next_commit_generation"
                ],
            )
        except (TypeError, KeyError, ValueError) as error:
            raise ValueError(f"invalid manifest fields: {error}") from error

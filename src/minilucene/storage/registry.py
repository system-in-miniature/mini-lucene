import re
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path

from minilucene.storage.filesystem import FileSystemOps

_SEGMENT_DIRECTORY = re.compile(r"seg_(\d+)")


@dataclass(frozen=True, slots=True)
class LifecycleDiagnostics:
    reader_owners: tuple[str, ...]
    writer_owner: str | None
    segment_owners: dict[int, tuple[str, ...]]
    temporary_jobs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _Owner:
    kind: str
    generations: frozenset[int]


class SegmentRegistry:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self._owners: dict[str, _Owner] = {}
        self._lock = threading.RLock()

    def acquire(self, kind: str, generations: tuple[int, ...]) -> str:
        if kind not in {"reader", "writer"}:
            raise ValueError(f"unknown segment owner kind: {kind}")
        owner_id = f"{kind}-{uuid.uuid4().hex}"
        with self._lock:
            self._owners[owner_id] = _Owner(
                kind=kind,
                generations=frozenset(generations),
            )
        return owner_id

    def replace(
        self, owner_id: str, generations: tuple[int, ...]
    ) -> None:
        with self._lock:
            owner = self._owners.get(owner_id)
            if owner is None:
                raise KeyError(f"unknown segment owner: {owner_id}")
            self._owners[owner_id] = _Owner(
                kind=owner.kind,
                generations=frozenset(generations),
            )

    def release(self, owner_id: str) -> None:
        with self._lock:
            self._owners.pop(owner_id, None)

    def diagnostics(self) -> LifecycleDiagnostics:
        with self._lock:
            readers = tuple(
                sorted(
                    owner_id
                    for owner_id, owner in self._owners.items()
                    if owner.kind == "reader"
                )
            )
            writers = tuple(
                owner_id
                for owner_id, owner in self._owners.items()
                if owner.kind == "writer"
            )
            segment_owners: dict[int, list[str]] = {}
            for owner_id, owner in self._owners.items():
                for generation in owner.generations:
                    segment_owners.setdefault(generation, []).append(owner_id)
            return LifecycleDiagnostics(
                reader_owners=readers,
                writer_owner=writers[0] if writers else None,
                segment_owners={
                    generation: tuple(sorted(owners))
                    for generation, owners in segment_owners.items()
                },
            )

    def collect_garbage(
        self,
        *,
        manifest_generations: tuple[int, ...],
        fs: FileSystemOps | None = None,
    ) -> tuple[Path, ...]:
        fs = fs or FileSystemOps()
        segments_path = self.root / "segments"
        if not fs.exists(segments_path):
            return ()
        with self._lock:
            retained = set(manifest_generations)
            for owner in self._owners.values():
                retained.update(owner.generations)
            removable: list[Path] = []
            for path in fs.list_directory(segments_path):
                match = _SEGMENT_DIRECTORY.fullmatch(path.name)
                if (
                    match is None
                    or not path.is_dir()
                    or not (path / "segment.json").is_file()
                ):
                    continue
                generation = int(match.group(1))
                if generation not in retained:
                    removable.append(path)
            for path in removable:
                fs.remove_tree(path)
            if removable:
                fs.fsync_directory(segments_path)
            return tuple(removable)


_REGISTRIES: dict[Path, SegmentRegistry] = {}
_REGISTRIES_LOCK = threading.Lock()


def registry_for(root: Path) -> SegmentRegistry:
    canonical = Path(root).resolve()
    with _REGISTRIES_LOCK:
        registry = _REGISTRIES.get(canonical)
        if registry is None:
            registry = SegmentRegistry(canonical)
            _REGISTRIES[canonical] = registry
        return registry

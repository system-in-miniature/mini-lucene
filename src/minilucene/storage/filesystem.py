import os
import shutil
from pathlib import Path


class FileSystemOps:
    def mkdir(
        self, path: Path, *, parents: bool = False, exist_ok: bool = False
    ) -> None:
        Path(path).mkdir(parents=parents, exist_ok=exist_ok)

    def write_bytes(self, path: Path, data: bytes) -> None:
        with Path(path).open("wb") as stream:
            stream.write(data)

    def read_bytes(self, path: Path) -> bytes:
        return Path(path).read_bytes()

    def fsync_file(self, path: Path) -> None:
        descriptor = os.open(Path(path), os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def fsync_directory(self, path: Path) -> None:
        descriptor = os.open(
            Path(path), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        )
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def replace(self, source: Path, destination: Path) -> None:
        os.replace(source, destination)

    def exists(self, path: Path) -> bool:
        return Path(path).exists()

    def remove_tree(self, path: Path) -> None:
        shutil.rmtree(path)

    def remove_file(self, path: Path) -> None:
        Path(path).unlink()

    def list_directory(self, path: Path) -> tuple[Path, ...]:
        return tuple(Path(path).iterdir())

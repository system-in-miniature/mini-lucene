import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Self

from minilucene.errors import WriterAlreadyOpenError

if TYPE_CHECKING:
    from minilucene.index.directory import Index


class IndexWriter:
    def __init__(self, index: "Index") -> None:
        self.index = index
        self._lock_path = Path(index.path) / ".writer.lock"
        self._closed = False
        try:
            descriptor = os.open(
                self._lock_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
        except FileExistsError as error:
            raise WriterAlreadyOpenError(
                f"writer already open for index: {index.path}"
            ) from error
        try:
            payload = json.dumps(
                {"pid": os.getpid()}, separators=(",", ":")
            ).encode("utf-8")
            os.write(descriptor, payload)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._lock_path.unlink()
        except FileNotFoundError:
            pass

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

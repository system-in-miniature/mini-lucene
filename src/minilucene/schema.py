from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterator, Mapping
from dataclasses import asdict, dataclass
from types import MappingProxyType


class SchemaError(ValueError):
    """Raised when a schema or document violates its frozen contract."""


@dataclass(frozen=True, slots=True)
class FieldType:
    indexed: bool
    tokenized: bool
    stored: bool
    store_positions: bool
    boost: float
    analyzer_name: str | None

    def __post_init__(self) -> None:
        if not math.isfinite(self.boost) or self.boost <= 0:
            raise SchemaError("field boost must be finite and positive")
        if self.store_positions and not self.indexed:
            raise SchemaError("positions require an indexed field")


def TextField(*, stored: bool = False, boost: float = 1.0) -> FieldType:
    return FieldType(
        indexed=True,
        tokenized=True,
        stored=stored,
        store_positions=True,
        boost=boost,
        analyzer_name="standard",
    )


def KeywordField(*, stored: bool = False, boost: float = 1.0) -> FieldType:
    return FieldType(
        indexed=True,
        tokenized=False,
        stored=stored,
        store_positions=False,
        boost=boost,
        analyzer_name="keyword",
    )


def StoredField() -> FieldType:
    return FieldType(
        indexed=False,
        tokenized=False,
        stored=True,
        store_positions=False,
        boost=1.0,
        analyzer_name=None,
    )


class Schema(Mapping[str, FieldType]):
    def __init__(self, **fields: FieldType) -> None:
        if not fields:
            raise SchemaError("schema must contain at least one field")
        if any(
            not isinstance(name, str)
            or not name
            or not isinstance(field, FieldType)
            for name, field in fields.items()
        ):
            raise SchemaError(
                "schema fields require non-empty names and FieldType values"
            )
        self._fields = MappingProxyType(dict(sorted(fields.items())))
        payload = json.dumps(
            {name: asdict(field) for name, field in self._fields.items()},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        self.fingerprint = hashlib.sha256(payload).hexdigest()

    def __getitem__(self, key: str) -> FieldType:
        return self._fields[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._fields)

    def __len__(self) -> int:
        return len(self._fields)

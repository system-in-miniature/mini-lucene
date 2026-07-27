from dataclasses import dataclass


@dataclass(frozen=True)
class KeywordField:
    stored: bool = False


@dataclass(frozen=True)
class TextField:
    stored: bool = False


class Schema:
    def __init__(self, **fields: object) -> None:
        self.fields = fields

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Schema) and self.fields == other.fields


class MemoryIndex:
    def __init__(self, schema: Schema) -> None:
        self.schema = schema

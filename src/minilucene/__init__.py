from minilucene.schema import KeywordField, Schema, StoredField, TextField


class MemoryIndex:
    def __init__(self, schema: Schema) -> None:
        self.schema = schema


__all__ = [
    "KeywordField",
    "MemoryIndex",
    "Schema",
    "StoredField",
    "TextField",
]

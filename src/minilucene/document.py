from collections.abc import Mapping
from types import MappingProxyType

from minilucene.schema import Schema, SchemaError

FrozenDocument = Mapping[str, str]


def freeze_document(
    schema: Schema, values: Mapping[str, object]
) -> FrozenDocument:
    unknown = sorted(set(values) - set(schema))
    if unknown:
        raise SchemaError(f"unknown field: {unknown[0]}")
    frozen: dict[str, str] = {}
    for name, value in values.items():
        if not isinstance(value, str):
            raise SchemaError(f"field {name} must be str")
        frozen[name] = value
    return MappingProxyType(dict(sorted(frozen.items())))

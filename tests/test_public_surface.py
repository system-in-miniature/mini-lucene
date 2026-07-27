from minilucene import (
    KeywordField,
    MemoryIndex,
    Schema,
    TextField,
    __version__,
)


def test_public_surface_imports():
    schema = Schema(
        id=KeywordField(stored=True),
        body=TextField(stored=True),
    )
    assert MemoryIndex(schema).schema == schema


def test_package_exports_its_distribution_version():
    assert __version__ == "0.1.0"

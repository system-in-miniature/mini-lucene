from minilucene import KeywordField, MemoryIndex, Schema, TextField


def test_public_surface_imports():
    schema = Schema(
        id=KeywordField(stored=True),
        body=TextField(stored=True),
    )
    assert MemoryIndex(schema).schema == schema

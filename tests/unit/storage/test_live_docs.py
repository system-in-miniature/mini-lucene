import pytest

from minilucene.storage.live_docs import LiveDocsCodec


def test_live_docs_round_trip():
    encoded = LiveDocsCodec.encode(
        max_doc=5,
        live_docs=frozenset({0, 2, 4}),
    )
    assert LiveDocsCodec.decode(5, encoded) == frozenset({0, 2, 4})


def test_live_docs_empty_and_full_round_trip():
    assert LiveDocsCodec.decode(
        0,
        LiveDocsCodec.encode(max_doc=0, live_docs=frozenset()),
    ) == frozenset()
    assert LiveDocsCodec.decode(
        9,
        LiveDocsCodec.encode(
            max_doc=9,
            live_docs=frozenset(range(9)),
        ),
    ) == frozenset(range(9))


def test_live_docs_rejects_id_outside_segment():
    with pytest.raises(ValueError, match="outside"):
        LiveDocsCodec.encode(max_doc=2, live_docs=frozenset({2}))


def test_live_docs_rejects_nonzero_unused_bits():
    encoded = bytearray(
        LiveDocsCodec.encode(max_doc=5, live_docs=frozenset({0}))
    )
    encoded[-1] |= 0b1000_0000
    with pytest.raises(ValueError, match="unused"):
        LiveDocsCodec.decode(5, bytes(encoded))


def test_live_docs_rejects_wrong_expected_max_doc():
    encoded = LiveDocsCodec.encode(
        max_doc=3,
        live_docs=frozenset({0}),
    )
    with pytest.raises(ValueError, match="max_doc"):
        LiveDocsCodec.decode(4, encoded)

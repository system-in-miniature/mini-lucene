import pytest

from minilucene.storage.varint import (
    decode_delta_sequence,
    decode_uvarint,
    encode_delta_sequence,
    encode_uvarint,
)


@pytest.mark.parametrize("value", [0, 1, 127, 128, 16_384, 2**63 - 1])
def test_uvarint_round_trip(value):
    encoded = encode_uvarint(value)
    assert decode_uvarint(encoded, 0) == (value, len(encoded))


def test_uvarint_decode_honors_nonzero_offset():
    encoded = b"prefix" + encode_uvarint(300)
    assert decode_uvarint(encoded, 6) == (300, len(encoded))


@pytest.mark.parametrize("value", [-1, 2**64])
def test_uvarint_rejects_values_outside_uint64(value):
    with pytest.raises(ValueError):
        encode_uvarint(value)


def test_delta_sequence_round_trip():
    encoded = encode_delta_sequence((0, 2, 130, 1_000))
    decoded, offset = decode_delta_sequence(encoded, 0, 4)
    assert decoded == (0, 2, 130, 1_000)
    assert offset == len(encoded)


def test_delta_sequence_requires_strict_increase():
    with pytest.raises(ValueError, match="increasing"):
        encode_delta_sequence((2, 2))


def test_unterminated_varint_is_rejected():
    with pytest.raises(ValueError, match="unterminated"):
        decode_uvarint(b"\x80", 0)


def test_overlong_varint_is_rejected():
    with pytest.raises(ValueError, match="overflow"):
        decode_uvarint(b"\x81" * 10 + b"\x00", 0)

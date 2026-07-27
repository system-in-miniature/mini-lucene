_MAX_UINT64 = 2**64 - 1


def encode_uvarint(value: int) -> bytes:
    if not isinstance(value, int) or not 0 <= value <= _MAX_UINT64:
        raise ValueError("unsigned varint value outside uint64")
    encoded = bytearray()
    while value >= 0x80:
        encoded.append((value & 0x7F) | 0x80)
        value >>= 7
    encoded.append(value)
    return bytes(encoded)


def decode_uvarint(data: bytes, offset: int) -> tuple[int, int]:
    if not isinstance(offset, int) or offset < 0 or offset > len(data):
        raise ValueError("varint offset outside input")
    value = 0
    for byte_index in range(10):
        position = offset + byte_index
        if position >= len(data):
            raise ValueError("unterminated unsigned varint")
        byte = data[position]
        if byte_index == 9 and byte > 1:
            raise ValueError("unsigned varint overflow")
        value |= (byte & 0x7F) << (7 * byte_index)
        if not byte & 0x80:
            return value, position + 1
    raise ValueError("unsigned varint overflow")


def encode_delta_sequence(values: tuple[int, ...]) -> bytes:
    previous = 0
    encoded = bytearray()
    for index, value in enumerate(values):
        if not isinstance(value, int) or value < 0:
            raise ValueError("delta values must be non-negative integers")
        if index and value <= previous:
            raise ValueError("delta values must be strictly increasing")
        delta = value if index == 0 else value - previous
        encoded.extend(encode_uvarint(delta))
        previous = value
    return bytes(encoded)


def decode_delta_sequence(
    data: bytes, offset: int, count: int
) -> tuple[tuple[int, ...], int]:
    if not isinstance(count, int) or count < 0:
        raise ValueError("delta sequence count must be non-negative")
    values: list[int] = []
    previous = 0
    for index in range(count):
        delta, offset = decode_uvarint(data, offset)
        if index and delta == 0:
            raise ValueError("delta values must be strictly increasing")
        value = delta if index == 0 else previous + delta
        if value > _MAX_UINT64:
            raise ValueError("delta sequence overflow")
        values.append(value)
        previous = value
    return tuple(values), offset

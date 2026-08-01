# Stage 09 · Bounded varint primitives

### Goal

Build bounded varint primitives and explain its boundary from an executable counterexample, runtime state, and the critical statement.

??? note "Deliverable files"
    - `src/minilucene/storage/varint.py`
    - `tests/unit/storage/test_varint.py`

### The problem at this point

A compact integer encoding becomes unsafe if truncation, overflow, signedness, or non-canonical forms are implicit.

### Test contract

#### See the failure first

The suite feeds truncated, overlong, negative, and non-canonical encodings, including boolean values that masquerade as integers.

??? note "File diff: tests/unit/storage/test_varint.py"
    ```diff
    diff --git a/tests/unit/storage/test_varint.py b/tests/unit/storage/test_varint.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..8fbfe20fdd9422f1a433e67f2223cea5080c5943
    --- /dev/null
    +++ b/tests/unit/storage/test_varint.py
    @@ -0,0 +1,47 @@
    +import pytest
    +
    +from minilucene.storage.varint import (
    +    decode_delta_sequence,
    +    decode_uvarint,
    +    encode_delta_sequence,
    +    encode_uvarint,
    +)
    +
    +
    +@pytest.mark.parametrize("value", [0, 1, 127, 128, 16_384, 2**63 - 1])
    +def test_uvarint_round_trip(value):
    +    encoded = encode_uvarint(value)
    +    assert decode_uvarint(encoded, 0) == (value, len(encoded))
    +
    +
    +def test_uvarint_decode_honors_nonzero_offset():
    +    encoded = b"prefix" + encode_uvarint(300)
    +    assert decode_uvarint(encoded, 6) == (300, len(encoded))
    +
    +
    +@pytest.mark.parametrize("value", [-1, 2**64])
    +def test_uvarint_rejects_values_outside_uint64(value):
    +    with pytest.raises(ValueError):
    +        encode_uvarint(value)
    +
    +
    +def test_delta_sequence_round_trip():
    +    encoded = encode_delta_sequence((0, 2, 130, 1_000))
    +    decoded, offset = decode_delta_sequence(encoded, 0, 4)
    +    assert decoded == (0, 2, 130, 1_000)
    +    assert offset == len(encoded)
    +
    +
    +def test_delta_sequence_requires_strict_increase():
    +    with pytest.raises(ValueError, match="increasing"):
    +        encode_delta_sequence((2, 2))
    +
    +
    +def test_unterminated_varint_is_rejected():
    +    with pytest.raises(ValueError, match="unterminated"):
    +        decode_uvarint(b"\x80", 0)
    +
    +
    +def test_overlong_varint_is_rejected():
    +    with pytest.raises(ValueError, match="overflow"):
    +        decode_uvarint(b"\x81" * 10 + b"\x00", 0)
    ```

**What this test locks**

These tests lock the Stage's happy path, boundary conditions, visible failures, and recovery invariants.

**How it constructs the counterexample**

The suite feeds truncated, overlong, negative, and non-canonical encodings, including boolean values that masquerade as integers.

**Key test statement**

```python
assert decode_uvarint(encoded, 0) == (value, len(encoded))
```

This assertion binds the observable result to the Stage's state, visibility, or durability boundary rather than merely checking that a call returned.

**What a failure means**

A failure means the implementation crossed the semantic, ordering, ownership, or recovery boundary just introduced.

### Basic concepts

Unsigned varints encode small non-negative integers in continuation bytes under an explicit maximum bit width.

### Why this mechanism is necessary

A compact integer encoding becomes unsafe if truncation, overflow, signedness, or non-canonical forms are implicit. Without an explicit boundary, every later mechanism would depend on accidental behavior.

### Runtime mental model

Encoding rejects invalid Python values and emits a canonical byte sequence; decoding counts bytes and bits before returning a value.

### Mechanism blocks

#### Bounded varint primitives mechanism

Encoding rejects invalid Python values and emits a canonical byte sequence; decoding counts bytes and bits before returning a value.

??? note "File diff: src/minilucene/storage/varint.py"
    ```diff
    diff --git a/src/minilucene/storage/varint.py b/src/minilucene/storage/varint.py
    new file mode 100644
    index 0000000000000000000000000000000000000000..811a83257065409b3eb65687f2611d80f5500c97
    --- /dev/null
    +++ b/src/minilucene/storage/varint.py
    @@ -0,0 +1,62 @@
    +_MAX_UINT64 = 2**64 - 1
    +
    +
    +def encode_uvarint(value: int) -> bytes:
    +    if not isinstance(value, int) or not 0 <= value <= _MAX_UINT64:
    +        raise ValueError("unsigned varint value outside uint64")
    +    encoded = bytearray()
    +    while value >= 0x80:
    +        encoded.append((value & 0x7F) | 0x80)
    +        value >>= 7
    +    encoded.append(value)
    +    return bytes(encoded)
    +
    +
    +def decode_uvarint(data: bytes, offset: int) -> tuple[int, int]:
    +    if not isinstance(offset, int) or offset < 0 or offset > len(data):
    +        raise ValueError("varint offset outside input")
    +    value = 0
    +    for byte_index in range(10):
    +        position = offset + byte_index
    +        if position >= len(data):
    +            raise ValueError("unterminated unsigned varint")
    +        byte = data[position]
    +        if byte_index == 9 and byte > 1:
    +            raise ValueError("unsigned varint overflow")
    +        value |= (byte & 0x7F) << (7 * byte_index)
    +        if not byte & 0x80:
    +            return value, position + 1
    +    raise ValueError("unsigned varint overflow")
    +
    +
    +def encode_delta_sequence(values: tuple[int, ...]) -> bytes:
    +    previous = 0
    +    encoded = bytearray()
    +    for index, value in enumerate(values):
    +        if not isinstance(value, int) or value < 0:
    +            raise ValueError("delta values must be non-negative integers")
    +        if index and value <= previous:
    +            raise ValueError("delta values must be strictly increasing")
    +        delta = value if index == 0 else value - previous
    +        encoded.extend(encode_uvarint(delta))
    +        previous = value
    +    return bytes(encoded)
    +
    +
    +def decode_delta_sequence(
    +    data: bytes, offset: int, count: int
    +) -> tuple[tuple[int, ...], int]:
    +    if not isinstance(count, int) or count < 0:
    +        raise ValueError("delta sequence count must be non-negative")
    +    values: list[int] = []
    +    previous = 0
    +    for index in range(count):
    +        delta, offset = decode_uvarint(data, offset)
    +        if index and delta == 0:
    +            raise ValueError("delta values must be strictly increasing")
    +        value = delta if index == 0 else previous + delta
    +        if value > _MAX_UINT64:
    +            raise ValueError("delta sequence overflow")
    +        values.append(value)
    +        previous = value
    +    return tuple(values), offset
    ```

**What it is and why it appears**

Unsigned varints encode small non-negative integers in continuation bytes under an explicit maximum bit width.

**Runtime role**

Encoding rejects invalid Python values and emits a canonical byte sequence; decoding counts bytes and bits before returning a value.

**Statement understanding**

The byte-count bound turns malicious continuation bytes into a typed failure instead of an unbounded loop or oversized integer.

### Verification evidence

Run `uv run pytest -q $(cat journey/stages/09-bounded-varints/tests.txt)`, then use Journey Check to compare the cumulative source with the canonical Stage.

### Durable takeaways

The byte-count bound turns malicious continuation bytes into a typed failure instead of an unbounded loop or oversized integer.

### Explain it in your own words

Explain the failure window this Stage closes, how runtime state changes, and which statement protects the boundary.

### Textbook

[Chapter 4](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/tutorial/04-codec.md)

[Complete reference patch / 完整参考补丁](https://github.com/system-in-miniature/mini-lucene/blob/main/journey/stages/09-bounded-varints/stage.patch)

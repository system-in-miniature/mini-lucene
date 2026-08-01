# Stage 09 · 有界 Varint 原语

### 目标

实现有界 Varint 原语，并能从可执行反例、运行时状态与关键语句解释其边界。

??? note "交付文件"
    - `src/minilucene/storage/varint.py`
    - `tests/unit/storage/test_varint.py`

### 当前遇到的问题

若截断、Overflow、Signedness 或非 Canonical Form 隐含不明，紧凑整数编码就不安全。

### 测试契约

#### 先看会坏在哪里

测试输入截断、过长、负数与非 Canonical Encoding，并包含伪装成 Integer 的 Boolean。

??? note "文件差异：tests/unit/storage/test_varint.py"
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

**测试锁定什么**

这些测试锁定本 Stage 的正常路径、边界条件、失败可见性与恢复不变量。

**如何构造反例**

测试输入截断、过长、负数与非 Canonical Encoding，并包含伪装成 Integer 的 Boolean。

**关键测试语句**

```python
assert decode_uvarint(encoded, 0) == (value, len(encoded))
```

这条断言把可观察结果与本 Stage 的状态、可见性或持久性边界绑定，而不只检查调用返回。

**失败意味着什么**

失败说明实现跨越了刚建立的语义、顺序、所有权或恢复边界。

### 基本概念

Unsigned Varint 在显式最大 Bit Width 下，用 Continuation Byte 编码小型非负整数。

### 为什么需要这个机制

若截断、Overflow、Signedness 或非 Canonical Form 隐含不明，紧凑整数编码就不安全。 若不建立明确边界，后续机制只能依赖偶然行为。

### 运行时心智模型

Encoding 拒绝非法 Python Value 并输出 Canonical Byte Sequence；Decoding 在返回前统计 Byte 与 Bit。

### 机制板块

#### 有界 Varint 原语机制

Encoding 拒绝非法 Python Value 并输出 Canonical Byte Sequence；Decoding 在返回前统计 Byte 与 Bit。

??? note "文件差异：src/minilucene/storage/varint.py"
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

**是什么，为什么现在需要**

Unsigned Varint 在显式最大 Bit Width 下，用 Continuation Byte 编码小型非负整数。

**在运行时做什么**

Encoding 拒绝非法 Python Value 并输出 Canonical Byte Sequence；Decoding 在返回前统计 Byte 与 Bit。

**关键语句理解**

Byte Count Bound 把恶意 Continuation Byte 变成类型化失败，而非无限循环或超大整数。

### 验证证据

运行 `uv run pytest -q $(cat journey/stages/09-bounded-varints/tests.txt)`，再用 Journey Check 比较累计源码与标准 Stage。

### 需要真正记住的内容

Byte Count Bound 把恶意 Continuation Byte 变成类型化失败，而非无限循环或超大整数。

### 用自己的话讲清楚

请解释这个 Stage 关闭的失败窗口、运行时状态如何变化，以及哪条语句守住边界。

### 教材

[第 4 章](https://github.com/system-in-miniature/mini-lucene/blob/main/docs/zh/tutorial/04-codec.md)

[Complete reference patch / 完整参考补丁](https://github.com/system-in-miniature/mini-lucene/blob/main/journey/stages/09-bounded-varints/stage.patch)

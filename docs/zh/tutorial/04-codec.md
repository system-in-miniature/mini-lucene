# 第 4 章：磁盘编码

持久化不是“把 RAM 对象 pickle 一下”。索引格式需要显式 framing、确定性顺序、
完整性元数据，以及拒绝歧义输入的 reader。MiniLucene 用四个数据文件加元数据保存
一个不可变段。它与 Lucene 文件格式不兼容，但教授同一条系统原则：字节只有一种
经验证的解释，否则就 fail closed。

## 学习目标

完成本章后，你能够编码/解码 unsigned varint，解释递增 doc ID 与 position 的
delta encoding，说明四个文件的职责，追踪 SHA-256 与严格 framing 校验，并区分
完整性检测与崩溃原子发布。

## 机制讲解：小整数与显式帧

`src/minilucene/storage/varint.py` 实现 unsigned LEB128 风格整数。
`encode_uvarint` 每字节放 7 个 payload bit，还有后续时设置高位；小于 128 的数
只需一字节，128 是 `80 01`，300 是 `ac 02`。由于 Python 的 `bool` 是 `int`
子类，当前类型与范围检查会接受布尔值：`False` 编码为 `00`，`True` 编码为
`01`。这是 Python 实现特性，不是独立的 Boolean wire type；其他输入必须是
uint64 范围内的整数。
`decode_uvarint` 最多读十字节，返回 `(value, next_offset)`，拒绝未终止和溢出。

`encode_delta_sequence` 保存严格递增 tuple 的首个绝对值和后续差值：
`(3,10,11)` 变成 `(3,7,1)`。严格递增拒绝零 delta，避免重复 ID/position。
`decode_delta_sequence` 同时校验 count、顺序与 uint64 溢出。

`src/minilucene/storage/codec.py` 的 `SegmentDataCodec.encode` 产生恰好四份字节：

- `terms.bin`：排序后的 `(field, term)` 与其 postings offset/length；
- `postings.bin`：posting list 连续帧，含数量、delta doc ID、tf、position 数与
  delta positions；
- `stored.bin`：文档数及逐文档 length-framed 规范 JSON；
- `norms.bin`：排序字段名及每个文档的 varint 字段长度。

`SegmentDataCodec.decode` 首先要求文件名集合恰好相等，缺文件不当空文件，多文件
也不忽略。`_decode_terms` 要求 key 严格排序，posting slice 从 offset 0 开始、
连续、无 gap；`_decode_postings` 要求范围合法且消费所有字节；
`_decode_posting_list` 要求 doc ID 递增并恰好消费 frame。stored/norms 同样拒绝
坏 UTF-8、错误 JSON 类型、乱序、截断和 trailing bytes。这排除了“合法前缀加
隐藏垃圾”的多重解释。

### 元数据与 SHA-256

`src/minilucene/storage/segment_store.py` 的 `SegmentStore.publish` 在临时段目录
写四个文件、逐个 fsync，并把 length 与 SHA-256 写入 `segment.json`。元数据还含
magic、format version、codec、generation、Schema 指纹与 `max_doc`。随后 fsync
元数据和临时目录，rename 到最终代际名，再 fsync 父目录。

`SegmentStore.open` 反向执行：`_read_metadata` 要求严格 UTF-8 JSON，
`_validate_metadata` 校验身份字段与精确文件集合，
`_read_and_validate_files` 先查 length/digest，再让 codec 解析；预期底层错误
包装为 `CorruptIndexError`。SHA-256 检测数据与元数据不一致，但没有密钥/签名，
不能认证写入者，也不会单独赋予多文件 commit 原子性。

四文件不是四份独立真相。doc ID 必须小于 `max_doc`，norm 数组和 stored count
必须覆盖同一空间。`src/minilucene/storage/image.py` 的
`SegmentImage.__post_init__` 校验跨文件逻辑，`SegmentStore.open` 又把解码后的
`max_doc` 与元数据对照。调用方只会得到完整 coherent image 或异常。

### 损坏、兼容与恢复是三个问题

损坏检查问字节是否满足格式与 digest；兼容检查问 reader 是否理解 magic/version/
codec；恢复协议问崩溃后选择哪个完整 generation。`SegmentDataCodec.decode`、
`SegmentStore.open` 和 manifest 分层回答。checksum 正确的段仍可能不兼容；合法
兼容段仍可能是未 commit orphan；manifest 命名的坏段也不能“跳过后部分打开”。

codec 是 eager 的：open 读取校验全部文件并构造完整 `SegmentImage`，简单但开销
随段大小增长。生产格式常用随机访问、mmap、block index、lazy decode 与 cache。
规范序列化仍带来稳定 fixture、可重复 hash 和唯一表示；布局变化应提升 version，
而不是让旧 decoder 猜。

## 对照真实 Apache Lucene

Lucene 有 versioned codec、segment info、field infos、stored fields、terms、
postings、norms、doc values、points、live docs 与 compound file 等结构，并用
packed integer、block compression、skip data、FST term index 和兼容机制。
MiniLucene 的 `educational-v1` 不具备这些性能与兼容工程，使用 JSON、逐文件
SHA-256、eager read 和简单 varint；双方不能互读。详见
[段格式](../../segment-format.md)、[Lucene 映射](../../lucene-mapping.md)及
[行为矩阵](../../behavior-matrix.md)。

## 动手实验：观察基础编码

```bash
export UV_CACHE_DIR=/tmp/minilucene-uv-cache
uv run --offline python - <<'PY'
from minilucene.storage.varint import decode_uvarint, encode_delta_sequence, encode_uvarint
from minilucene.storage.codec import SegmentDataCodec
for value in (1, 127, 128, 300):
    encoded = encode_uvarint(value)
    print(value, encoded.hex(), decode_uvarint(encoded, 0))
print("bools", encode_uvarint(False).hex(), encode_uvarint(True).hex())
print("deltas", encode_delta_sequence((3, 10, 11)).hex())
try:
    SegmentDataCodec.decode(generation=1, schema_fingerprint="x",
                            files={"terms.bin": b""})
except ValueError as error:
    print(type(error).__name__, str(error))
PY
```

实测输出：

```text
1 01 (1, 1)
127 7f (127, 1)
128 8001 (128, 2)
300 ac02 (300, 2)
bools 00 01
deltas 030701
ValueError segment data requires exactly terms, postings, stored, and norms files
```

```bash
uv run --offline pytest -q tests/unit/storage/test_varint.py \
  tests/unit/storage/test_segment_codec.py tests/storage/test_segment_store.py
```

实测：`27 passed in 0.28s`。

## 练习

1. **理解题：** 为什么合法 frame 后有 trailing bytes 也必须拒绝？

    ??? note "参考答案"
        否则同一字节可被解释成合法值加忽略数据，或新版结构；精确消费保证唯一解释。

2. **理解题：** SHA-256 在此证明和不证明什么？

    ??? note "参考答案"
        它证明字节与元数据 digest 一致，不认证写入者，也不提供 commit 原子性。

3. **动手题：** 给循环加入 16384。验收：hex 为 `808001`，offset 为 3。

    ??? note "参考答案"
        7-bit payload 需要三字节，直接 encode/decode 即可，不改 `src/`。

4. **动手题：** 编码 `(3,3)`。验收：抛出含 strictly increasing 的
   `ValueError`。

    ??? note "参考答案"
        重复绝对值产生零 delta，违反 posting/position 排序契约。

## 小结

codec 把逻辑 image 变成四个规范 frame 文件；varint/delta 压缩有序整数，排序、
无 gap 与精确消费消除歧义，hash 在解析前发现变化。下一章说明为什么“段字节合法”
仍不等于“查询可见”或“重启可恢复”。

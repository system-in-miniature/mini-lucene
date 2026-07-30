> **语言**: [English](../segment-format.md) | 简体中文

# MiniLucene V1 段数据格式

MiniLucene 段（segment）是确定性的教学文件。它们不是 Apache Lucene 文件，
除 MiniLucene 自身段元数据中记录的格式版本外，不作任何兼容性承诺。

所有字符串均为严格 UTF-8。所有整数均为无符号 64 位变长整数
（unsigned 64-bit varint）。字节字符串帧（byte string frame）如下：

```text
byte_length:uvarint
bytes[byte_length]
```

文档 ID 是稠密、从零开始且局部于单个不可变段的。

## `terms.bin`

```text
term_count:uvarint
repeat term_count:
    field:utf8_frame
    term:utf8_frame
    postings_offset:uvarint
    postings_length:uvarint
```

条目严格按 `(field, term)` 排序。偏移量连续且指向 `postings.bin`；
间隙、重叠、越界切片、重复词项和尾随字节均属于数据损坏。

## `postings.bin`

每个词项指向一个完整的倒排列表帧（posting-list frame）：

```text
posting_count:uvarint
repeat posting_count:
    doc_id_delta:uvarint
    term_frequency:uvarint
    position_count:uvarint
    position_deltas[position_count]:uvarint
```

第一个文档值和位置值是绝对值。后续值是正差值，因此解码后的 ID 和位置必须严格递增。
关键词字段的词项频率为正，且存储位置数为零。

## `stored.bin`

```text
document_count:uvarint
repeat document_count:
    canonical_json:utf8_frame
```

每个 JSON 对象将字段名映射到 Unicode 字符串。编码使用排序键、不含无意义空白，
并直接保留 Unicode 字符：

```python
json.dumps(
    value,
    sort_keys=True,
    ensure_ascii=False,
    separators=(",", ":"),
)
```

帧顺序即局部文档 ID 顺序。

## `norms.bin`

```text
field_count:uvarint
repeat field_count:
    field:utf8_frame
    document_length_count:uvarint
    document_lengths[document_length_count]:uvarint
```

字段严格排序。每个已索引字段都为段内每个文档保存且仅保存一个分析后词元长度。

## 完整性边界

这四个文件不会自行发布。数据文件写入后，系统会写入并同步 `segment.json`；
该文件为每个文件记录格式魔数/版本、代次（generation）、模式指纹
（schema fingerprint）、字节长度、SHA-256 校验和以及编解码器标识符。
已提交清单是一个更晚且独立的发布边界。

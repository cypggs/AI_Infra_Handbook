# 7. 工程实践（Mini Demo）

本章提供一个 CPU 可运行的 Python Mini Demo，模拟存储系统的核心机制：块分配、inode 文件系统、对象存储与版本控制、分片上传、最终一致性、三副本冗余、XOR 纠删码、分层缓存，以及 AI checkpoint 保存/加载。

## 7.1 目录与运行方式

代码位于：

```text
docs/01-foundation/storage-systems/mini-demo/
├── pyproject.toml
├── README.md
├── storage_systems_mini/
│   ├── __init__.py
│   ├── block.py
│   ├── inode_fs.py
│   ├── object_store.py
│   ├── erasure_coding.py
│   ├── tiered_cache.py
│   ├── checkpoint.py
│   └── demo.py
└── tests/test_all.py
```

安装依赖并运行测试：

```bash
cd docs/01-foundation/storage-systems/mini-demo
pip install -e ".[dev]"
pytest tests/ -v
```

直接运行演示：

```bash
python -m storage_systems_mini.demo
```

## 7.2 模块设计

### 7.2.1 块设备 `block.py`

`BlockDevice` 用内存模拟固定大小的块、分配位图以及坏块标记。

```python
bd = BlockDevice(num_blocks=8, block_size=16)
b0 = bd.allocate()
bd.write_block(b0, b"hello, block 0!")
print(bd.read_block(b0))
```

它说明了大文件/ checkpoint 如何被切成离散块写入底层设备。

### 7.2.2 inode 文件系统 `inode_fs.py`

`InodeFS` 在块设备之上实现简单的 inode、直接块指针和目录项。

```python
fs = InodeFS(bd)
fs.create("model.bin")
fs.write("model.bin", b"AI model weights are here.")
print(fs.read("model.bin"))
print(fs.stat("model.bin"))
```

### 7.2.3 对象存储 `object_store.py`

`ObjectStore` 模拟 S3 语义：bucket、key、ETag、版本控制、multipart 上传、两种耐久策略（三副本 / XOR 纠删码），并支持模拟最终一致性。

```python
store = ObjectStore(strategy="replica", eventual_delay=0.1)
store.create_bucket("models")
store.put("models", "v1/weights.pt", b"weights v1")
```

- `strategy="replica"`：保存 3 份完整数据；
- `strategy="xor"`：把数据切分为 `k` 个数据块 + 1 个 XOR 校验块，可恢复任意一个块丢失。

### 7.2.4 XOR 纠删码 `erasure_coding.py`

```python
codec = SimpleXORCodec(k=3)
chunks = codec.encode(b"erasure coding demo")
broken = chunks.copy()
broken[0] = None
print(codec.decode(broken))  # 仍可恢复
```

实际生产系统使用 Reed-Solomon（如 HDFS EC、Ceph、MinIO），这里用 XOR 单校验块演示纠删码的基本思想。

### 7.2.5 分层缓存 `tiered_cache.py`

`TieredCache` 模拟热层（本地 NVMe）和暖层（对象存储）：

- 写入先进入 hot tier；
- hot tier 达到容量后按 LRU 淘汰到 warm tier；
- 读取未命中时从 warm tier 拉取并晋升到 hot tier。

```python
cache = TieredCache(hot_capacity=2, object_store=store, bucket="cache")
cache.put("a", b"data-a")
cache.put("b", b"data-b")
cache.put("c", b"data-c")  # a 被淘汰到 warm tier
```

### 7.2.6 AI checkpoint 管理器 `checkpoint.py`

`CheckpointManager` 把模型状态切片成对象，先保存到缓存，再异步上传到对象存储，并用 MD5 校验和验证完整性。

```python
mgr = CheckpointManager(cache, store, bucket="checkpoints")
state = {"embed.weight": b"embeddings", "lm.head.weight": b"head weights"}
meta = mgr.save(state, "gpt-mini")
loaded = mgr.load(meta)
handle = mgr.async_upload(meta)
ok = mgr.wait_for_upload(handle)
```

## 7.3 测试结果

```bash
pytest tests/ -v
```

```text
test_all.py::test_block_allocate_read_write PASSED
test_all.py::test_block_bad_block_raises PASSED
test_all.py::test_inode_fs_create_write_read PASSED
test_all.py::test_object_store_put_get PASSED
test_all.py::test_multipart_reassembly PASSED
test_all.py::test_three_replica_survive_loss PASSED
test_all.py::test_xor_recover_one_chunk PASSED
test_all.py::test_xor_preserves_trailing_zeros PASSED
test_all.py::test_eventual_consistency_visibility PASSED
test_all.py::test_tiered_cache_lru_eviction PASSED
test_all.py::test_checkpoint_save_load_roundtrip PASSED
test_all.py::test_checkpoint_async_upload PASSED
============================== 12 passed in 0.17s ==============================
```

## 7.4 关键运行输出

```text
Storage Systems Mini Demo

============================================================
 1. 块设备：分配、读写与坏块
============================================================
已分配块数量: 2
读取 b0: b'hello, block 0!\x00'
读取 b1: b'hello, block 1!\x00'
标记 b1 为坏块后，空闲块: 7

============================================================
 2. Inode 文件系统：创建、写入、读取、删除
============================================================
写入 model.bin 大小: 26
读取 model.bin: b'AI model weights are here.'
model.bin stat: {'ino': 1, 'size': 26, 'blocks': [0, 1, 2, 3], 'ctime': ...}
删除后目录内容: []

============================================================
 9. 模型 Checkpoint：保存/加载/异步上传
============================================================
checkpoint 元数据: {'name': 'gpt-mini', 'keys': {...}}
加载结果: {'embed.weight': b'embeddings', 'lm.head.weight': b'head weights'}
异步上传完成: True
```

## 7.5 Mini Demo 与真实存储的差异

| 方面 | Mini Demo | 真实存储系统 |
|---|---|---|
| 块设备 | 内存数组 | NVMe/SSD/HDD，真实 Flash 控制器、FTL |
| 文件系统 | 单层 inode + 直接块指针 | ext4/xfs，多级间接块、日志、extent |
| 对象存储 | 内存字典 | S3/MinIO/Ceph，分布式元数据、纠删码集群 |
| 一致性 | 时间戳模拟 | Quorum、Raft、MVCC、版本向量 |
| 纠删码 | 单 XOR 校验 | Reed-Solomon、LRC、Torn 页修复 |
| 缓存 | 内存 OrderedDict | Alluxio/JuiceFS/FUSE，预取、异步回写 |
| checkpoint | 单线程模拟 | PyTorch DCP、DeepSpeed、Orbax，多 rank 分片 |

## 7.6 一句话总结

**这个 Mini Demo 把存储系统的抽象栈压缩到几百行 Python，帮助理解：AI 训练 checkpoint 如何从“应用层状态”落到“块/对象/缓存/副本”的每一层。**

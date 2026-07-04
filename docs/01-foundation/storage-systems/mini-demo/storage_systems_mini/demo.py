"""Entry-point demo for storage_systems_mini."""

from storage_systems_mini import (
    BlockDevice,
    CheckpointManager,
    InodeFS,
    ObjectStore,
    SimpleXORCodec,
    TieredCache,
)


def banner(title: str) -> None:
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


def demo_block_device() -> None:
    banner("1. 块设备：分配、读写与坏块")
    bd = BlockDevice(num_blocks=8, block_size=16)
    b0 = bd.allocate()
    b1 = bd.allocate()
    bd.write_block(b0, b"hello, block 0!")
    bd.write_block(b1, b"hello, block 1!")
    print(f"已分配块数量: {bd.allocated_count()}")
    print(f"读取 b{b0}: {bd.read_block(b0)!r}")
    print(f"读取 b{b1}: {bd.read_block(b1)!r}")
    bd.mark_bad(b1)
    print(f"标记 b{b1} 为坏块后，空闲块: {bd.free_count()}")


def demo_inode_fs() -> None:
    banner("2. Inode 文件系统：创建、写入、读取、删除")
    bd = BlockDevice(num_blocks=16, block_size=8)
    fs = InodeFS(bd)
    fs.create("model.bin")
    data = b"AI model weights are here."
    fs.write("model.bin", data)
    print(f"写入 model.bin 大小: {len(data)}")
    print(f"读取 model.bin: {fs.read('model.bin')!r}")
    print(f"model.bin stat: {fs.stat('model.bin')}")
    fs.delete("model.bin")
    print(f"删除后目录内容: {fs.listdir()}")


def demo_object_store() -> None:
    banner("3. 对象存储：上传、下载、列出、版本控制")
    store = ObjectStore(strategy="replica")
    store.create_bucket("models")
    info = store.put("models", "v1/weights.pt", b"weights v1")
    print(f"put 返回: {info}")
    print(f"get 结果: {store.get('models', 'v1/weights.pt')!r}")
    print(f"对象列表: {store.list_objects('models')}")
    store.put("models", "v1/weights.pt", b"weights v2")
    print(f"再次上传后对象数量: {len(store.list_objects('models'))}")
    store.delete("models", "v1/weights.pt")
    print(f"删除后 get: {store.get('models', 'v1/weights.pt')!r}")


def demo_multipart() -> None:
    banner("4. 分片上传：重新组装")
    store = ObjectStore(strategy="replica")
    upload_id = store.create_multipart_upload("models", "big-model.pt")
    store.upload_part(upload_id, 1, b"part-one-")
    store.upload_part(upload_id, 2, b"part-two-")
    store.upload_part(upload_id, 3, b"part-three")
    result = store.complete_multipart_upload(upload_id)
    print(f"分片上传完成: {result}")
    print(f"合并后内容: {store.get('models', 'big-model.pt')!r}")


def demo_eventual_consistency() -> None:
    banner("5. 最终一致性：写入后短暂不可见")
    store = ObjectStore(strategy="replica", eventual_delay=0.1)
    store.create_bucket("models")
    store.put("models", "new.pt", b"fresh data")
    print(f"立即 get: {store.get('models', 'new.pt')!r}")
    import time
    time.sleep(0.15)
    print(f"延迟后 get: {store.get('models', 'new.pt')!r}")


def demo_replica_survival() -> None:
    banner("6. 三副本：丢失任意两个片段仍可恢复")
    store = ObjectStore(strategy="replica")
    store.create_bucket("models")
    original = b"important checkpoint"
    store.put("models", "ckpt.pt", original)
    store.simulate_fragment_loss("models", "ckpt.pt", 0)
    store.simulate_fragment_loss("models", "ckpt.pt", 1)
    recovered = store.recover_data("models", "ckpt.pt")
    print(f"原始数据: {original!r}")
    print(f"丢失 2 个副本后恢复: {recovered!r}")


def demo_xor_recovery() -> None:
    banner("7. XOR 纠删码：丢失任意一个 chunk 可恢复")
    codec = SimpleXORCodec(k=3)
    data = b"erasure coding demo"
    chunks = codec.encode(data)
    print(f"原始数据: {data!r}")
    print(f"生成 {len(chunks)} 个 chunk (k=3 数据 + 1 校验)")
    for i in [0, 1, 2, 3]:
        broken = chunks.copy()
        broken[i] = None
        recovered = codec.decode(broken)
        print(f"丢失 chunk {i} 后恢复: {recovered!r}")


def demo_tiered_cache() -> None:
    banner("8. 分层缓存：LRU 淘汰与写回")
    store = ObjectStore(strategy="replica")
    cache = TieredCache(hot_capacity=2, object_store=store, bucket="cache")
    cache.put("a", b"data-a")
    cache.put("b", b"data-b")
    cache.put("c", b"data-c")  # should evict a to warm tier
    print(f"hot tier keys: {cache.hot_keys()}")
    print(f"a 在 warm tier? {store.get('cache', 'a') is not None}")
    print(f"读取 b 后 hot keys: {cache.get('b')!r} -> {cache.hot_keys()}")
    cache.flush()


def demo_checkpoint() -> None:
    banner("9. 模型 Checkpoint：保存/加载/异步上传")
    store = ObjectStore(strategy="replica")
    cache = TieredCache(hot_capacity=4, object_store=store, bucket="checkpoints")
    mgr = CheckpointManager(cache, store, bucket="checkpoints")
    state = {
        "embed.weight": b"embeddings",
        "lm.head.weight": b"head weights",
    }
    meta = mgr.save(state, "gpt-mini")
    print(f"checkpoint 元数据: {meta}")
    loaded = mgr.load(meta)
    print(f"加载结果: {loaded}")
    handle = mgr.async_upload(meta)
    ok = mgr.wait_for_upload(handle)
    print(f"异步上传完成: {ok}")


def main() -> None:
    print("\nStorage Systems Mini Demo")
    demo_block_device()
    demo_inode_fs()
    demo_object_store()
    demo_multipart()
    demo_eventual_consistency()
    demo_replica_survival()
    demo_xor_recovery()
    demo_tiered_cache()
    demo_checkpoint()
    banner("Demo 结束")


if __name__ == "__main__":
    main()

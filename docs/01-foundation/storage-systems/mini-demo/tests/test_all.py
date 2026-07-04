"""Tests for storage_systems_mini package."""

import time

import pytest

from storage_systems_mini import (
    BlockDevice,
    CheckpointManager,
    InodeFS,
    ObjectStore,
    SimpleXORCodec,
    TieredCache,
)


def test_block_allocate_read_write():
    bd = BlockDevice(num_blocks=4, block_size=8)
    bid = bd.allocate()
    bd.write_block(bid, b"abc")
    assert bd.read_block(bid).rstrip(b"\x00") == b"abc"
    bd.free(bid)
    assert bd.allocated_count() == 0


def test_block_bad_block_raises():
    bd = BlockDevice(num_blocks=4, block_size=8)
    bid = bd.allocate()
    bd.mark_bad(bid)
    with pytest.raises(OSError):
        bd.read_block(bid)
    with pytest.raises(OSError):
        bd.write_block(bid, b"x")


def test_inode_fs_create_write_read():
    bd = BlockDevice(num_blocks=8, block_size=8)
    fs = InodeFS(bd)
    fs.create("f.txt")
    data = b"hello, inode filesystem!"
    fs.write("f.txt", data)
    assert fs.read("f.txt") == data
    assert fs.stat("f.txt")["size"] == len(data)


def test_object_store_put_get():
    store = ObjectStore(strategy="replica")
    store.create_bucket("b")
    store.put("b", "k", b"v")
    assert store.get("b", "k") == b"v"
    store.delete("b", "k")
    assert store.get("b", "k") is None


def test_multipart_reassembly():
    store = ObjectStore(strategy="replica")
    uid = store.create_multipart_upload("b", "k")
    store.upload_part(uid, 2, b"2-")
    store.upload_part(uid, 1, b"1-")
    store.upload_part(uid, 3, b"3")
    store.complete_multipart_upload(uid)
    assert store.get("b", "k") == b"1-2-3"


def test_three_replica_survive_loss():
    store = ObjectStore(strategy="replica")
    store.create_bucket("b")
    data = b"critical data"
    store.put("b", "k", data)
    store.simulate_fragment_loss("b", "k", 0)
    store.simulate_fragment_loss("b", "k", 1)
    assert store.recover_data("b", "k") == data


def test_xor_recover_one_chunk():
    codec = SimpleXORCodec(k=3)
    data = b"recover me please"
    chunks = codec.encode(data)
    for i in range(len(chunks)):
        broken = chunks.copy()
        broken[i] = None
        assert codec.decode(broken) == data


def test_xor_preserves_trailing_zeros():
    codec = SimpleXORCodec(k=3)
    data = b"hello\x00\x00\x00"
    chunks = codec.encode(data)
    chunks[2] = None
    assert codec.decode(chunks) == data


def test_eventual_consistency_visibility():
    store = ObjectStore(strategy="replica", eventual_delay=0.05)
    store.create_bucket("b")
    store.put("b", "k", b"v")
    assert store.get("b", "k") is None
    time.sleep(0.08)
    assert store.get("b", "k") == b"v"


def test_tiered_cache_lru_eviction():
    store = ObjectStore(strategy="replica")
    cache = TieredCache(hot_capacity=2, object_store=store, bucket="c")
    cache.put("a", b"1")
    cache.put("b", b"2")
    cache.put("c", b"3")  # evict a
    assert cache.hot_keys() == ["b", "c"]
    assert store.get("c", "a") == b"1"


def test_checkpoint_save_load_roundtrip():
    store = ObjectStore(strategy="replica")
    cache = TieredCache(hot_capacity=4, object_store=store, bucket="ckpt")
    mgr = CheckpointManager(cache, store, "ckpt")
    state = {"w1": b"weight-one", "w2": b"weight-two"}
    meta = mgr.save(state, "m")
    loaded = mgr.load(meta)
    assert loaded == state


def test_checkpoint_async_upload():
    store = ObjectStore(strategy="replica")
    cache = TieredCache(hot_capacity=4, object_store=store, bucket="ckpt")
    mgr = CheckpointManager(cache, store, "ckpt")
    state = {"w": b"weight"}
    meta = mgr.save(state, "m")
    handle = mgr.async_upload(meta)
    assert mgr.wait_for_upload(handle)
    assert store.get("ckpt", "m/w") == b"weight"

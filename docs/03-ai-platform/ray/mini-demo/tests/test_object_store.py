"""Tests for the per-node object store."""
import pytest

from ray_mini.model import ObjectRef
from ray_mini.object_store import ObjectStore


def test_put_primary_pins_object():
    store = ObjectStore(node_id=0, capacity=100, spill_threshold=1.0)
    ref = ObjectRef(id=1, size=10, owner_node=0)
    store.put_primary(ref)
    assert store.has(1)
    assert store.used == 10


def test_release_moves_primary_to_evictable():
    store = ObjectStore(node_id=0, capacity=100, spill_threshold=1.0)
    ref = ObjectRef(id=1, size=10, owner_node=0)
    store.put_primary(ref)
    store.release(1)
    assert 1 not in store.primary
    assert 1 in store.evictable
    assert store.has(1)


def test_eager_spilling():
    store = ObjectStore(node_id=0, capacity=10, spill_threshold=0.8)
    # 3 evictable objects of size 3 each = 9 used; threshold 8 -> spill one LRU.
    for rid in [1, 2, 3]:
        store.add_evictable_copy(ObjectRef(id=rid, size=3, owner_node=0))
    assert store.spill_count >= 1
    assert store.used <= 8


def test_restore_from_spill():
    store = ObjectStore(node_id=0, capacity=10, spill_threshold=0.5)
    ref = ObjectRef(id=1, size=6, owner_node=0)
    store.add_evictable_copy(ref)
    assert 1 in store.spilled
    assert store.get(1)
    assert 1 in store.evictable


def test_lru_eviction_order():
    store = ObjectStore(node_id=0, capacity=10, spill_threshold=1.0)
    for rid in [1, 2, 3]:
        store.add_evictable_copy(ObjectRef(id=rid, size=3, owner_node=0))
    store.get(1)  # touch ref 1
    store._free(3)  # need 3 units free
    # Least recently used should be evicted first (ref 2, then 3).
    assert 1 in store.evictable

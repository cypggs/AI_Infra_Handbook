"""Tiered cache simulator: hot (local) and warm (object store) tiers."""

from collections import OrderedDict
from typing import Optional

from .object_store import ObjectStore


class TieredCache:
    """A two-tier cache with LRU eviction in the hot tier and write-back to warm."""

    def __init__(self, hot_capacity: int, object_store: ObjectStore, bucket: str):
        self.hot_capacity = hot_capacity
        self.store = object_store
        self.bucket = bucket
        self.store.create_bucket(bucket)
        self._hot: OrderedDict[str, bytes] = OrderedDict()
        self._dirty: set = set()

    def put(self, key: str, data: bytes) -> None:
        """Write to hot tier, mark dirty, and evict to warm if necessary."""
        if key in self._hot:
            self._hot.move_to_end(key)
        self._hot[key] = data
        self._dirty.add(key)
        self._evict_if_needed()

    def get(self, key: str) -> Optional[bytes]:
        """Read from hot tier or promote from warm tier."""
        if key in self._hot:
            self._hot.move_to_end(key)
            return self._hot[key]
        data = self.store.get(self.bucket, key)
        if data is None:
            return None
        self._hot[key] = data
        self._evict_if_needed()
        return data

    def flush(self) -> None:
        """Write all dirty hot objects back to warm tier."""
        for key in list(self._dirty):
            self.store.put(self.bucket, key, self._hot[key])
        self._dirty.clear()

    def _evict_if_needed(self) -> None:
        while len(self._hot) > self.hot_capacity:
            oldest_key, oldest_data = self._hot.popitem(last=False)
            if oldest_key in self._dirty:
                self.store.put(self.bucket, oldest_key, oldest_data)
                self._dirty.discard(oldest_key)

    def hot_keys(self) -> list:
        return list(self._hot.keys())

    def is_dirty(self, key: str) -> bool:
        return key in self._dirty

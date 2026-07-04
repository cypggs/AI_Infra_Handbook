"""Model checkpoint manager using cache + object store."""

import hashlib
import threading
import time
from typing import Dict, List, Optional

from .object_store import ObjectStore
from .tiered_cache import TieredCache


class CheckpointManager:
    """Slices a model state dict into objects, saves to cache + object store.

    - Each tensor/value becomes one object with an MD5 checksum.
    - Saves go to the hot cache first and then flush to the object store.
    - Simulated async upload runs in a background thread.
    """

    def __init__(
        self,
        cache: TieredCache,
        object_store: ObjectStore,
        bucket: str,
    ):
        self.cache = cache
        self.store = object_store
        self.bucket = bucket
        self.store.create_bucket(bucket)
        self._pending: Dict[str, dict] = {}

    def save(self, state_dict: Dict[str, bytes], name: str) -> dict:
        """Save state dict. Returns metadata including checksums and object keys."""
        metadata = {"name": name, "created_at": time.time(), "keys": {}}
        for tensor_name, data in state_dict.items():
            obj_key = f"{name}/{tensor_name}"
            checksum = hashlib.md5(data).hexdigest()
            self.cache.put(obj_key, data)
            metadata["keys"][tensor_name] = {"key": obj_key, "checksum": checksum, "size": len(data)}
        self.cache.flush()
        return metadata

    def load(self, metadata: dict) -> Dict[str, bytes]:
        """Load state dict and validate checksums."""
        result: Dict[str, bytes] = {}
        for tensor_name, info in metadata["keys"].items():
            data = self.cache.get(info["key"])
            if data is None:
                raise FileNotFoundError(f"missing object {info['key']}")
            actual = hashlib.md5(data).hexdigest()
            if actual != info["checksum"]:
                raise RuntimeError(f"checksum mismatch for {tensor_name}")
            result[tensor_name] = data
        return result

    def async_upload(self, metadata: dict) -> str:
        """Start a simulated async upload. Returns a handle to poll."""
        handle = hashlib.md5(f"{metadata['name']}/{time.time()}".encode()).hexdigest()
        self._pending[handle] = {"status": "running", "metadata": metadata}

        def _upload():
            time.sleep(0.05)  # simulate network latency
            for tensor_name, info in metadata["keys"].items():
                data = self.cache.get(info["key"])
                if data is not None:
                    self.store.put(self.bucket, info["key"], data)
            self._pending[handle]["status"] = "done"

        threading.Thread(target=_upload, daemon=True).start()
        return handle

    def wait_for_upload(self, handle: str, timeout: float = 2.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._pending.get(handle, {}).get("status") == "done":
                return True
            time.sleep(0.01)
        return False

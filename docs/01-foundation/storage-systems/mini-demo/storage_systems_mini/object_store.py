"""Object store simulator with replicas and erasure coding."""

import hashlib
import time
from typing import Dict, List, Optional, Set

from .erasure_coding import SimpleXORCodec


class ObjectStore:
    """A memory-only object store simulating S3-like semantics.

    Supports buckets, object metadata, multipart upload, versioning, and two
    durability strategies: "replica" (3 copies) or "xor" (k data + 1 parity).
    """

    def __init__(
        self,
        strategy: str = "replica",
        xor_k: int = 3,
        eventual_delay: float = 0.0,
    ):
        if strategy not in ("replica", "xor"):
            raise ValueError("strategy must be 'replica' or 'xor'")
        self.strategy = strategy
        self.xor_k = xor_k
        self.eventual_delay = eventual_delay
        self._buckets: Dict[str, Dict[str, List[dict]]] = {}
        self._multipart: Dict[str, dict] = {}
        self._xor = SimpleXORCodec(k=xor_k)

    def create_bucket(self, bucket: str) -> None:
        self._buckets.setdefault(bucket, {})

    def list_buckets(self) -> List[str]:
        return list(self._buckets.keys())

    def put(self, bucket: str, key: str, data: bytes) -> dict:
        self.create_bucket(bucket)
        etag = hashlib.md5(data).hexdigest()
        version_id = str(int(time.time() * 1e6))

        if self.strategy == "replica":
            fragments = [data, data, data]
        else:
            fragments = self._xor.encode(data)

        obj = {
            "key": key,
            "data": data,
            "etag": etag,
            "size": len(data),
            "version_id": version_id,
            "fragments": fragments,
            "deleted": False,
            "visible_at": time.time() + self.eventual_delay,
        }
        self._buckets[bucket].setdefault(key, []).append(obj)
        return {"etag": etag, "version_id": version_id}

    def get(self, bucket: str, key: str, version_id: Optional[str] = None) -> Optional[bytes]:
        obj = self._resolve(bucket, key, version_id)
        if obj is None:
            return None
        if time.time() < obj["visible_at"]:
            return None
        return obj["data"]

    def list_objects(self, bucket: str, prefix: str = "") -> List[dict]:
        if bucket not in self._buckets:
            return []
        results = []
        for key, versions in self._buckets[bucket].items():
            if key.startswith(prefix):
                for v in versions:
                    if not v["deleted"]:
                        results.append({"key": key, "size": v["size"], "version_id": v["version_id"]})
        return results

    def delete(self, bucket: str, key: str, version_id: Optional[str] = None) -> None:
        obj = self._resolve(bucket, key, version_id)
        if obj is not None:
            obj["deleted"] = True

    def create_multipart_upload(self, bucket: str, key: str) -> str:
        upload_id = hashlib.md5(f"{bucket}/{key}/{time.time()}".encode()).hexdigest()
        self._multipart[upload_id] = {"bucket": bucket, "key": key, "parts": []}
        return upload_id

    def upload_part(self, upload_id: str, part_number: int, data: bytes) -> None:
        if upload_id not in self._multipart:
            raise ValueError("invalid upload_id")
        self._multipart[upload_id]["parts"].append((part_number, data))

    def complete_multipart_upload(self, upload_id: str) -> dict:
        if upload_id not in self._multipart:
            raise ValueError("invalid upload_id")
        mp = self._multipart.pop(upload_id)
        parts = sorted(mp["parts"], key=lambda x: x[0])
        data = b"".join(data for _, data in parts)
        return self.put(mp["bucket"], mp["key"], data)

    def simulate_fragment_loss(self, bucket: str, key: str, fragment_index: int) -> None:
        """Mark one fragment as lost for testing durability."""
        obj = self._resolve(bucket, key)
        if obj is None:
            raise ValueError("object not found")
        fragments = obj["fragments"]
        if not (0 <= fragment_index < len(fragments)):
            raise IndexError("fragment index out of range")
        fragments[fragment_index] = None

    def recover_data(self, bucket: str, key: str) -> bytes:
        """Reconstruct data from remaining fragments."""
        obj = self._resolve(bucket, key)
        if obj is None:
            raise ValueError("object not found")
        if self.strategy == "replica":
            remaining = [f for f in obj["fragments"] if f is not None]
            if not remaining:
                raise RuntimeError("all replicas lost")
            return remaining[0]
        return self._xor.decode(obj["fragments"])

    def _resolve(self, bucket: str, key: str, version_id: Optional[str] = None) -> Optional[dict]:
        if bucket not in self._buckets or key not in self._buckets[bucket]:
            return None
        versions = self._buckets[bucket][key]
        if version_id is not None:
            for v in versions:
                if v["version_id"] == version_id:
                    return v
            return None
        for v in reversed(versions):
            if not v["deleted"]:
                return v
        return None

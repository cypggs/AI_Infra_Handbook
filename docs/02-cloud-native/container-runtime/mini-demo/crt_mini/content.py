"""Content Store：按 digest 存 blob（层内容、config），内容寻址 + 去重。

对应 containerd 的 Content Store：镜像层的原始内容（压缩归档）按 SHA256 摘要存储，
digest 相同的内容只存一份（去重），是镜像共享与复用的根基。
"""
from __future__ import annotations


class ContentStore:
    def __init__(self) -> None:
        self._blobs: dict[str, object] = {}

    def put(self, key: str, blob: object) -> bool:
        """存入 blob；若 digest 已存在则跳过（去重）。返回是否为新增。"""
        if key in self._blobs:
            return False
        self._blobs[key] = blob
        return True

    def get(self, key: str) -> object:
        return self._blobs[key]

    def has(self, key: str) -> bool:
        return key in self._blobs

    def size(self) -> int:
        return len(self._blobs)

    def list(self) -> list[str]:
        return list(self._blobs.keys())

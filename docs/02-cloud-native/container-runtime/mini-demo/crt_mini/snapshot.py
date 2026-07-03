"""Snapshotter：把层解包成快照树，提供 overlayfs 联合挂载 + copy-on-write 的 rootfs。

对应 containerd 的 Snapshotter（默认 overlayfs）：
- 每个层解包成一个 committed（只读）快照，层之间形成父-子链；
- 容器运行时在链顶 prepare 一个 active（可写）快照（COW 的 upperdir）；
- merged 视图 = 所有下层（lowerdir）自底向上叠加 + 本快照（upperdir）覆盖；
- 写一个已存在于下层（lower）的文件时，overlayfs 先把它整个 copy-up 到 upper（COW），
  哪怕只改 1 字节，也复制整个文件——这是 overlayfs 的关键代价。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .image import Layer


@dataclass
class Snapshot:
    name: str
    parent: str | None  # 父快照名
    kind: str  # "committed" | "active"
    files: dict[str, str] = field(default_factory=dict)  # 本快照自身拥有的文件


class Snapshotter:
    def __init__(self, content_store: object | None = None) -> None:
        self.content = content_store
        self.snaps: dict[str, Snapshot] = {}

    def commit_layer(self, name: str, layer: Layer, parent: str | None = None) -> None:
        """把一个层解包成一个 committed（只读）快照。"""
        if name in self.snaps:
            return  # 已存在则复用（去重）
        self.snaps[name] = Snapshot(
            name=name, parent=parent, kind="committed", files=dict(layer.files)
        )

    def prepare(self, key: str, parent: str | None = None) -> None:
        """在父链之上 prepare 一个 active（可写）快照——容器的 upperdir。"""
        self.snaps[key] = Snapshot(name=key, parent=parent, kind="active", files={})

    def _chain(self, name: str) -> list[Snapshot]:
        """从 name 向上走到根，返回自底向上（根在前）的快照链。"""
        chain: list[Snapshot] = []
        cur = name
        while cur is not None:
            snap = self.snaps.get(cur)
            if snap is None:
                break
            chain.append(snap)
            cur = snap.parent
        chain.reverse()  # 根（最低层）在前，顶（最高层）在后
        return chain

    def merged(self, key: str) -> dict[str, str]:
        """计算联合挂载视图：下层自底向上叠加，本快照（upper）覆盖在上。"""
        view: dict[str, str] = {}
        for snap in self._chain(key):
            view.update(snap.files)  # 后（上层）覆盖前（下层）
        return view

    def write(self, key: str, path: str, content: str) -> dict:
        """在 active 快照里写文件，模拟 copy-on-write。

        返回 COW 记账：是否触发了从下层的 copy-up、copy-up 了多少字节。
        关键点：修改一个存在于下层的文件时，先把**整个下层文件**复制到 upper，再改。
        """
        snap = self.snaps[key]
        assert snap.kind == "active", "only active snapshots are writable"
        cow = {"copied_from_lower": False, "copied_bytes": 0, "written_bytes": len(content)}
        if path not in snap.files:
            # 该文件尚未在 upper，若下层存在则需 copy-up
            lower_view = self.merged(snap.parent) if snap.parent else {}
            if path in lower_view:
                cow["copied_from_lower"] = True
                cow["copied_bytes"] = len(lower_view[path])  # 整个文件被复制
        snap.files[path] = content
        return cow

    def remove(self, key: str) -> None:
        self.snaps.pop(key, None)

    def stats(self) -> dict[str, dict]:
        return {n: {"kind": s.kind, "files": len(s.files)} for n, s in self.snaps.items()}

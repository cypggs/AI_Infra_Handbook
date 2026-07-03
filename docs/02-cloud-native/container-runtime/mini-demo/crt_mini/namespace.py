"""Namespace 隔离抽象（模拟，不调用真实 unshare/clone 系统调用）。

每个 Namespace 对象代表一组被隔离的资源视图。一个容器持有一个 NamespaceSet：
pid/net/mnt/uts/ipc/user 各自独立（= 真实容器默认全隔离）。
Pod 内多容器可通过 shared_with 共享 net/ipc namespace（对应 K8s pause 容器持沙箱）。
"""
from __future__ import annotations

from dataclasses import dataclass, field

NAMESPACE_TYPES = ("pid", "net", "mnt", "uts", "ipc", "user", "cgroup")


@dataclass
class Namespace:
    """一个被隔离的命名空间。members 用于演示"容器只看到自己的成员"。"""

    type: str
    members: list = field(default_factory=list)

    def add(self, item: object) -> None:
        self.members.append(item)

    def visible(self) -> list:
        return list(self.members)


@dataclass
class NamespaceSet:
    """一个容器的命名空间集合。值为 None 表示与宿主共享（未隔离）。"""

    pid: Namespace | None = None
    net: Namespace | None = None
    mnt: Namespace | None = None
    uts: Namespace | None = None
    ipc: Namespace | None = None
    user: Namespace | None = None

    @classmethod
    def isolated(cls) -> "NamespaceSet":
        """创建完全隔离的命名空间集合（每种类型各一个新 ns）。"""
        ns = cls()
        for t in ("pid", "net", "mnt", "uts", "ipc", "user"):
            setattr(ns, t, Namespace(type=t))
        return ns

    def shared_with(self, other: "NamespaceSet", types: tuple[str, ...] = ("net", "ipc")) -> None:
        """加入另一个容器的 net/ipc 命名空间（Pod 共享网络栈）。"""
        for t in types:
            setattr(self, t, getattr(other, t))

    def isolated_types(self) -> list[str]:
        """列出真正独立（非宿主共享）的 namespace 类型。"""
        return [t for t in NAMESPACE_TYPES if getattr(self, t, None) is not None]

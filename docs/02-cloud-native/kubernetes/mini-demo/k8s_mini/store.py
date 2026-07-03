"""store.py — etcd 的极简模拟：强一致 KV + watch/notify。

真实 etcd 用 Raft 做强一致；这里单进程内存 dict 即"真相源"。
关键保留 etcd 的两个特性：
  1. 唯一真相（apiserver 是唯一客户端）
  2. watch（控制器/scheduler/kubelet 通过它拿增量事件）—— 对应 informer 的 list+watch
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable


class EventType(str, Enum):
    ADDED = "ADDED"
    MODIFIED = "MODIFIED"
    DELETED = "DELETED"


@dataclass
class Event:
    type: EventType
    resource_kind: str  # "pod" / "node" / "deployment" / "replicaset"
    key: str
    obj: Any


class Store:
    """按 (kind, key) 存对象，变更时通知所有 watcher。"""

    def __init__(self) -> None:
        self._data: dict[tuple[str, str], Any] = {}
        self._watchers: list[Callable[[Event], None]] = []
        self._lock = threading.Lock()

    def add_watcher(self, fn: Callable[[Event], None]) -> None:
        self._watchers.append(fn)

    def put(self, kind: str, key: str, obj: Any) -> Any:
        with self._lock:
            existed = (kind, key) in self._data
            self._data[(kind, key)] = obj
        event_type = EventType.MODIFIED if existed else EventType.ADDED
        self._notify(Event(event_type, kind, key, obj))
        return obj

    def get(self, kind: str, key: str) -> Any | None:
        with self._lock:
            return self._data.get((kind, key))

    def delete(self, kind: str, key: str) -> Any | None:
        with self._lock:
            obj = self._data.pop((kind, key), None)
        if obj is not None:
            self._notify(Event(EventType.DELETED, kind, key, obj))
        return obj

    def all_of(self, kind: str) -> list[Any]:
        with self._lock:
            return [obj for (knd, _key), obj in self._data.items() if knd == kind]

    def _notify(self, event: Event) -> None:
        # 复制 watcher 列表，避免回调中增删导致遍历问题
        for fn in list(self._watchers):
            try:
                fn(event)
            except Exception:  # pragma: no cover - watcher 异常不应中断 store
                pass

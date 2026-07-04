"""Rate-limited workqueue for reconcile requests."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Item:
    key: tuple[str, str, str]
    obj: dict
    retries: int = 0
    context: dict[str, Any] = field(default_factory=dict)


class WorkQueue:
    def __init__(self, max_retries: int = 3) -> None:
        self._queue: list[Item] = []
        self._max_retries = max_retries

    def add(self, item: Item) -> None:
        self._queue.append(item)

    def get(self) -> Item | None:
        if not self._queue:
            return None
        return self._queue.pop(0)

    def done(self, item: Item) -> None:
        pass

    def requeue(self, item: Item) -> bool:
        if item.retries >= self._max_retries:
            return False
        item.retries += 1
        self._queue.append(item)
        return True

    def has_pending(self) -> bool:
        return bool(self._queue)

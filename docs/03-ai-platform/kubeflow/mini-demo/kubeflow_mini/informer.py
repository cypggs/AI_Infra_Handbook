"""Informer-style event bus over the in-memory store."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from kubeflow_mini.store import Store


@dataclass
class Event:
    event_type: str  # add, update, delete
    obj: dict


Handler = Callable[[Event], None]


class Informer:
    def __init__(self, store: Store) -> None:
        self.store = store
        self._handlers: list[Handler] = []
        self._pending: list[Event] = []

    def add_event_handler(self, handler: Handler) -> None:
        self._handlers.append(handler)

    def emit(self, event: Event) -> None:
        self._pending.append(event)

    def process_next(self) -> bool:
        if not self._pending:
            return False
        event = self._pending.pop(0)
        for handler in self._handlers:
            handler(event)
        return True

    def has_pending(self) -> bool:
        return bool(self._pending)

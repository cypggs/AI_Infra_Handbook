from __future__ import annotations

import copy
import json
import os
from abc import ABC, abstractmethod
from typing import Any, Dict


class Storage(ABC):
    """Abstract backend for persisting memory snapshots."""

    @abstractmethod
    def save(self, data: Dict[str, Any], path: str | None = None) -> None:
        ...

    @abstractmethod
    def load(self, path: str | None = None) -> Dict[str, Any]:
        ...


class InMemoryStorage(Storage):
    """Keeps the latest snapshot in memory (useful for tests)."""

    def __init__(self) -> None:
        self._data: Dict[str, Any] = {}

    def save(self, data: Dict[str, Any], path: str | None = None) -> None:
        self._data = copy.deepcopy(data)

    def load(self, path: str | None = None) -> Dict[str, Any]:
        return copy.deepcopy(self._data)


class JsonFileStorage(Storage):
    """Persists memory snapshots to a JSON file."""

    def __init__(self, path: str) -> None:
        self.path = path

    def save(self, data: Dict[str, Any], path: str | None = None) -> None:
        target = path or self.path
        with open(target, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self, path: str | None = None) -> Dict[str, Any]:
        target = path or self.path
        if not os.path.exists(target):
            return {}
        with open(target, "r", encoding="utf-8") as f:
            return json.load(f)

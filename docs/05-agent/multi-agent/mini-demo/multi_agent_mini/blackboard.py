"""Shared workspace for agents."""

from __future__ import annotations

from typing import Any


class Blackboard:
    """A scoped key/value workspace shared by agents.

    Scopes:
        * ``shared``  - visible to all agents and included in ``to_dict``.
        * ``readonly`` - visible to all agents but should not be mutated.
        * ``private`` - stored on the board but hidden from ``to_dict``.
    """

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    def read(self, key: str) -> Any | None:
        """Return the value for ``key`` or ``None`` if absent."""
        entry = self._data.get(key)
        if entry is None:
            return None
        return entry["value"]

    def write(self, key: str, value: Any, scope: str = "shared") -> None:
        """Store ``value`` under ``key`` with the given ``scope``."""
        if scope not in {"shared", "readonly", "private"}:
            raise ValueError(f"Invalid scope: {scope}")
        self._data[key] = {"value": value, "scope": scope}

    def delete(self, key: str) -> bool:
        """Remove ``key``. Returns ``True`` if it existed."""
        if key in self._data:
            del self._data[key]
            return True
        return False

    def to_dict(self) -> dict[str, Any]:
        """Return a snapshot of all non-private entries."""
        return {
            key: entry["value"]
            for key, entry in self._data.items()
            if entry["scope"] in {"shared", "readonly"}
        }

    def keys(self) -> list[str]:
        """Return all keys currently stored."""
        return list(self._data.keys())

    def scope(self, key: str) -> str | None:
        """Return the scope of ``key`` or ``None`` if absent."""
        entry = self._data.get(key)
        return entry["scope"] if entry else None

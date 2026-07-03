"""Shared and per-process workspace (blackboard) for the mini Agent OS.

Processes can read/write named values in their own private namespace and in
a shared namespace. The workspace is the persistent blackboard that survives
individual agent steps.
"""

from __future__ import annotations

from typing import Any


class Workspace:
    """Key/value blackboard with per-process and shared namespaces."""

    def __init__(self) -> None:
        # Shared namespace visible to every process.
        self._shared: dict[str, Any] = {}
        # Per-process namespaces keyed by process ID.
        self._private: dict[str, dict[str, Any]] = {}

    def _ensure_private(self, pid: str) -> None:
        if pid not in self._private:
            self._private[pid] = {}

    def write_shared(self, key: str, value: Any) -> None:
        """Write a value to the shared namespace."""
        self._shared[key] = value

    def read_shared(self, key: str, default: Any = None) -> Any:
        """Read a value from the shared namespace."""
        return self._shared.get(key, default)

    def write_private(self, pid: str, key: str, value: Any) -> None:
        """Write a value to a process's private namespace."""
        self._ensure_private(pid)
        self._private[pid][key] = value

    def read_private(self, pid: str, key: str, default: Any = None) -> Any:
        """Read a value from a process's private namespace."""
        self._ensure_private(pid)
        return self._private[pid].get(key, default)

    def shared_snapshot(self) -> dict[str, Any]:
        """Return a copy of the shared namespace."""
        return dict(self._shared)

    def private_snapshot(self, pid: str) -> dict[str, Any]:
        """Return a copy of a process's private namespace."""
        self._ensure_private(pid)
        return dict(self._private[pid])

    def all_namespaces(self) -> dict[str, dict[str, Any]]:
        """Return a copy of shared plus every private namespace."""
        return {"shared": self.shared_snapshot(), **{pid: dict(ns) for pid, ns in self._private.items()}}

    def clear(self) -> None:
        """Reset the workspace."""
        self._shared.clear()
        self._private.clear()

    def __repr__(self) -> str:
        return f"Workspace(shared={self._shared!r}, private={list(self._private)})"

"""Scoped shared workspace for reflection artifacts."""

from typing import Any


class Workspace:
    """In-memory key/value store with scope labels and per-key history.

    Scopes:
        * ``shared``  — normal read/write shared state.
        * ``readonly`` — write-once shared state; overwrites raise ``ValueError``.
        * ``private`` — stored like shared state but tagged for isolation.
    """

    VALID_SCOPES = {"shared", "readonly", "private"}

    def __init__(self) -> None:
        """Create an empty workspace."""
        self._store: dict[str, dict[str, Any]] = {}

    def write(self, key: str, value: Any, scope: str = "shared") -> None:
        """Write ``value`` under ``key`` with the given scope.

        Args:
            key: Identifier for the value.
            value: Any object to store.
            scope: One of ``shared``, ``readonly``, or ``private``.

        Raises:
            ValueError: If ``scope`` is invalid or a ``readonly`` key is
                overwritten.
        """
        if scope not in self.VALID_SCOPES:
            raise ValueError(f"Invalid scope '{scope}'; must be one of {self.VALID_SCOPES}")

        if key in self._store and self._store[key]["scope"] == "readonly":
            raise ValueError(f"Cannot overwrite readonly key '{key}'")

        if key not in self._store:
            self._store[key] = {"scope": scope, "value": value, "history": []}
        else:
            self._store[key]["value"] = value
            self._store[key]["scope"] = scope

        self._store[key]["history"].append(value)

    def read(self, key: str) -> Any:
        """Return the current value stored under ``key``.

        Raises:
            KeyError: If ``key`` does not exist.
        """
        if key not in self._store:
            raise KeyError(key)
        return self._store[key]["value"]

    def delete(self, key: str) -> None:
        """Remove ``key`` and its history from the workspace.

        Raises:
            KeyError: If ``key`` does not exist.
        """
        if key not in self._store:
            raise KeyError(key)
        del self._store[key]

    def keys(self) -> list[str]:
        """Return all keys currently stored."""
        return list(self._store.keys())

    def to_dict(self) -> dict[str, Any]:
        """Return a shallow snapshot of current key/value pairs."""
        return {key: entry["value"] for key, entry in self._store.items()}

    def history(self, key: str) -> list[Any]:
        """Return the chronological list of values written to ``key``.

        Raises:
            KeyError: If ``key`` does not exist.
        """
        if key not in self._store:
            raise KeyError(key)
        return list(self._store[key]["history"])

    def scope(self, key: str) -> str:
        """Return the scope label for ``key``.

        Raises:
            KeyError: If ``key`` does not exist.
        """
        if key not in self._store:
            raise KeyError(key)
        return self._store[key]["scope"]

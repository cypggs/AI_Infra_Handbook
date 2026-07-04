"""In-memory object store keyed by (kind, namespace, name)."""
from __future__ import annotations


class Store:
    def __init__(self) -> None:
        self._objects: dict[tuple[str, str, str], dict] = {}

    @staticmethod
    def key(kind: str, namespace: str, name: str) -> tuple[str, str, str]:
        return (kind, namespace, name)

    def create(self, obj: dict) -> dict:
        meta = obj["metadata"]
        k = self.key(obj["kind"], meta["namespace"], meta["name"])
        if k in self._objects:
            raise ValueError(f"{k} already exists")
        obj.setdefault("status", {})
        self._objects[k] = obj
        return obj

    def update(self, obj: dict) -> dict:
        meta = obj["metadata"]
        k = self.key(obj["kind"], meta["namespace"], meta["name"])
        self._objects[k] = obj
        return obj

    def delete(self, kind: str, namespace: str, name: str) -> dict | None:
        return self._objects.pop(self.key(kind, namespace, name), None)

    def get(self, kind: str, namespace: str, name: str) -> dict | None:
        return self._objects.get(self.key(kind, namespace, name))

    def list(self, kind: str, namespace: str | None = None) -> list[dict]:
        results = []
        for (k, ns, n), obj in self._objects.items():
            if k != kind:
                continue
            if namespace is not None and ns != namespace:
                continue
            results.append(obj)
        return results

    def __contains__(self, item: tuple[str, str, str]) -> bool:
        return item in self._objects

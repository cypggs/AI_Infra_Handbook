"""In-memory XCom store for Airflow Mini Demo."""

from typing import Any, Optional


class XCom:
    """Simple key-value store indexed by (dag_id, run_id, task_id, key)."""

    def __init__(self):
        self._store: dict[tuple[str, str, str, str], Any] = {}

    def push(
        self,
        dag_id: str,
        run_id: str,
        task_id: str,
        key: str,
        value: Any,
    ) -> None:
        self._store[(dag_id, run_id, task_id, key)] = value

    def pull(
        self,
        dag_id: str,
        run_id: str,
        task_id: str,
        key: str = "return_value",
    ) -> Optional[Any]:
        return self._store.get((dag_id, run_id, task_id, key))

    def clear(self) -> None:
        self._store.clear()

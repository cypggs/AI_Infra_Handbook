"""Triggerer simulation for deferrable operators."""

from typing import Any, Callable, Dict, List


class Triggerer:
    """Async listener that wakes deferred tasks when conditions are met."""

    def __init__(self):
        # filepath -> list of callbacks
        self._callbacks: Dict[str, List[Callable]] = {}
        # filepath -> readiness flag
        self._ready: Dict[str, bool] = {}

    def register(self, filepath: str, context: dict) -> None:
        callback = lambda: self._resume_task(context)
        self._callbacks.setdefault(filepath, []).append(callback)
        if filepath not in self._ready:
            self._ready[filepath] = False

    def mark_ready(self, filepath: str) -> None:
        self._ready[filepath] = True

    def is_ready(self, filepath: str) -> bool:
        return self._ready.get(filepath, False)

    def _resume_task(self, context: dict) -> None:
        """Mark deferred task as scheduled so Scheduler can re-queue it."""
        dag = context["dag"]
        run_id = context["run_id"]
        task_id = context["task_id"]
        from airflow_mini.state import SCHEDULED

        context["db"].task_instances[(dag.dag_id, run_id, task_id)]["state"] = SCHEDULED

    def tick(self) -> int:
        """Wake up all ready triggers. Returns number resumed."""
        resumed = 0
        for filepath, ready in list(self._ready.items()):
            if ready:
                for cb in self._callbacks.get(filepath, []):
                    cb()
                    resumed += 1
                self._callbacks[filepath].clear()
        return resumed

    def reset(self) -> None:
        self._callbacks.clear()
        self._ready.clear()

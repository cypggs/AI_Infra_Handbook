"""In-memory executor simulation."""

from typing import List, Tuple

from airflow_mini.dag import DAG, DeferSignal
from airflow_mini.state import DEFERRED, FAILED, QUEUED, RUNNING, SUCCESS
from airflow_mini.xcom import XCom


class LocalExecutor:
    """Execute tasks in-memory within the same process."""

    def __init__(self, db, xcom: XCom):
        self.db = db
        self.xcom = xcom
        self._queue: List[Tuple[DAG, str, str]] = []

    def queue(self, dag: DAG, run_id: str, task_id: str) -> None:
        key = (dag.dag_id, run_id, task_id)
        self.db.task_instances[key]["state"] = QUEUED
        self._queue.append((dag, run_id, task_id))

    def execute_queued(self) -> None:
        # Snapshot to allow re-queuing during execution
        batch = list(self._queue)
        self._queue.clear()

        for dag, run_id, task_id in batch:
            key = (dag.dag_id, run_id, task_id)
            ti = self.db.task_instances[key]
            ti["state"] = RUNNING

            task = dag.tasks[task_id]
            context = {
                "dag": dag,
                "run_id": run_id,
                "task_id": task_id,
                "xcom": self.xcom,
                "db": self.db,
                "triggerer": self.db.triggerer,
            }
            try:
                result = task.operator.execute(context)
            except DeferSignal:
                ti["state"] = DEFERRED
                continue
            except Exception:
                ti["state"] = FAILED
                ti["try_number"] += 1
                continue

            ti["state"] = SUCCESS
            self.xcom.push(dag.dag_id, run_id, task_id, "return_value", result)

    def has_queued(self) -> bool:
        return bool(self._queue)

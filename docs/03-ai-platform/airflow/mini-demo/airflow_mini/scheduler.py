"""Scheduler simulation."""

from airflow_mini.dag import DAG
from airflow_mini.state import (
    FAILED,
    NONE,
    QUEUED,
    SCHEDULED,
    SUCCESS,
    TERMINAL_TI_STATES,
)


class InMemoryDB:
    """Simulated Metadata Database."""

    def __init__(self, triggerer):
        self.dag_runs: dict = {}
        self.task_instances: dict = {}
        self.triggerer = triggerer


class Scheduler:
    """Create DAG Runs and schedule ready TaskInstances."""

    def __init__(self, db: InMemoryDB, executor, triggerer):
        self.db = db
        self.executor = executor
        self.triggerer = triggerer

    def create_dag_run(self, dag: DAG, run_id: str, logical_date: str) -> None:
        self.db.dag_runs[(dag.dag_id, run_id)] = {
            "state": "running",
            "logical_date": logical_date,
        }
        for task_id in dag.tasks:
            self.db.task_instances[(dag.dag_id, run_id, task_id)] = {
                "state": NONE,
                "try_number": 0,
            }

    def schedule(self, dag: DAG, run_id: str) -> int:
        """Move ready TaskInstances from none/scheduled to queued."""
        queued = 0
        for task in dag.topo_order():
            key = (dag.dag_id, run_id, task.task_id)
            ti = self.db.task_instances[key]
            if ti["state"] in TERMINAL_TI_STATES or ti["state"] == QUEUED:
                continue

            upstream_ok = all(
                self.db.task_instances[(dag.dag_id, run_id, t.task_id)]["state"] == SUCCESS
                for t in task.upstream
            )
            if upstream_ok and ti["state"] in (NONE, SCHEDULED):
                ti["state"] = SCHEDULED
                self.executor.queue(dag, run_id, task.task_id)
                queued += 1
        return queued

    def update_dag_run_state(self, dag: DAG, run_id: str) -> str:
        states = [
            self.db.task_instances[(dag.dag_id, run_id, t.task_id)]["state"]
            for t in dag.tasks.values()
        ]
        if any(s == FAILED for s in states):
            self.db.dag_runs[(dag.dag_id, run_id)]["state"] = "failed"
        elif all(s == SUCCESS for s in states):
            self.db.dag_runs[(dag.dag_id, run_id)]["state"] = "success"
        return self.db.dag_runs[(dag.dag_id, run_id)]["state"]

    def run_to_completion(self, dag: DAG, run_id: str, max_rounds: int = 20) -> str:
        """Simple loop that schedules and executes until done or deferred."""
        for _ in range(max_rounds):
            self.triggerer.tick()
            self.schedule(dag, run_id)
            if self.executor.has_queued():
                self.executor.execute_queued()
            self.update_dag_run_state(dag, run_id)
            if self.is_complete(dag, run_id):
                break
        return self.db.dag_runs[(dag.dag_id, run_id)]["state"]

    def is_complete(self, dag: DAG, run_id: str) -> bool:
        return all(
            self.db.task_instances[(dag.dag_id, run_id, t.task_id)]["state"]
            in TERMINAL_TI_STATES
            for t in dag.tasks.values()
        )

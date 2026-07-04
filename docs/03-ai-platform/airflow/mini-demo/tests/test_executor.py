"""Tests for Executor and XCom."""

from airflow_mini.dag import DAG, PythonOperator
from airflow_mini.executor import LocalExecutor
from airflow_mini.scheduler import InMemoryDB, Scheduler
from airflow_mini.state import FAILED, SUCCESS
from airflow_mini.triggerer import Triggerer
from airflow_mini.xcom import XCom


def test_executor_runs_task_and_writes_xcom():
    triggerer = Triggerer()
    xcom = XCom()
    db = InMemoryDB(triggerer)
    executor = LocalExecutor(db, xcom)
    scheduler = Scheduler(db, executor, triggerer)

    dag = DAG("test")
    dag.add_task(PythonOperator("a", lambda c: {"rows": 42}))

    scheduler.create_dag_run(dag, "r1", "2026-07-01")
    executor.queue(dag, "r1", "a")
    executor.execute_queued()

    assert db.task_instances[("test", "r1", "a")]["state"] == SUCCESS
    assert xcom.pull("test", "r1", "a", "return_value") == {"rows": 42}


def test_executor_marks_failure():
    triggerer = Triggerer()
    xcom = XCom()
    db = InMemoryDB(triggerer)
    executor = LocalExecutor(db, xcom)
    scheduler = Scheduler(db, executor, triggerer)

    dag = DAG("test")

    def fail(context):
        raise RuntimeError("boom")

    dag.add_task(PythonOperator("a", fail))

    scheduler.create_dag_run(dag, "r1", "2026-07-01")
    executor.queue(dag, "r1", "a")
    executor.execute_queued()

    assert db.task_instances[("test", "r1", "a")]["state"] == FAILED


def test_xcom_passes_data_between_tasks():
    triggerer = Triggerer()
    xcom = XCom()
    db = InMemoryDB(triggerer)
    executor = LocalExecutor(db, xcom)
    scheduler = Scheduler(db, executor, triggerer)

    dag = DAG("test")

    def produce(context):
        return {"value": 10}

    def consume(context):
        upstream = xcom.pull("test", "r1", "produce", "return_value")
        return {"received": upstream["value"]}

    p = dag.add_task(PythonOperator("produce", produce))
    c = dag.add_task(PythonOperator("consume", consume))
    p >> c

    scheduler.create_dag_run(dag, "r1", "2026-07-01")
    executor.queue(dag, "r1", "produce")
    executor.execute_queued()
    executor.queue(dag, "r1", "consume")
    executor.execute_queued()

    assert xcom.pull("test", "r1", "consume", "return_value") == {"received": 10}

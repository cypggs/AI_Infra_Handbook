"""Tests for Scheduler."""

from airflow_mini.dag import DAG, PythonOperator
from airflow_mini.executor import LocalExecutor
from airflow_mini.scheduler import InMemoryDB, Scheduler
from airflow_mini.state import NONE, QUEUED, SUCCESS
from airflow_mini.triggerer import Triggerer
from airflow_mini.xcom import XCom


def test_create_dag_run_and_task_instances():
    triggerer = Triggerer()
    db = InMemoryDB(triggerer)
    executor = LocalExecutor(db, XCom())
    scheduler = Scheduler(db, executor, triggerer)

    dag = DAG("test")
    dag.add_task(PythonOperator("a", lambda c: 1))

    scheduler.create_dag_run(dag, "r1", "2026-07-01")

    assert ("test", "r1") in db.dag_runs
    assert db.task_instances[("test", "r1", "a")]["state"] == NONE


def test_schedule_only_ready_tasks():
    triggerer = Triggerer()
    db = InMemoryDB(triggerer)
    executor = LocalExecutor(db, XCom())
    scheduler = Scheduler(db, executor, triggerer)

    dag = DAG("test")
    a = dag.add_task(PythonOperator("a", lambda c: 1))
    b = dag.add_task(PythonOperator("b", lambda c: 2))
    a >> b

    scheduler.create_dag_run(dag, "r1", "2026-07-01")
    scheduler.schedule(dag, "r1")

    assert db.task_instances[("test", "r1", "a")]["state"] == QUEUED
    assert db.task_instances[("test", "r1", "b")]["state"] == NONE


def test_run_to_completion():
    triggerer = Triggerer()
    xcom = XCom()
    db = InMemoryDB(triggerer)
    executor = LocalExecutor(db, xcom)
    scheduler = Scheduler(db, executor, triggerer)

    dag = DAG("test")
    a = dag.add_task(PythonOperator("a", lambda c: "a-result"))
    b = dag.add_task(PythonOperator("b", lambda c: "b-result"))
    a >> b

    scheduler.create_dag_run(dag, "r1", "2026-07-01")
    state = scheduler.run_to_completion(dag, "r1")

    assert state == SUCCESS
    assert db.task_instances[("test", "r1", "a")]["state"] == SUCCESS
    assert db.task_instances[("test", "r1", "b")]["state"] == SUCCESS

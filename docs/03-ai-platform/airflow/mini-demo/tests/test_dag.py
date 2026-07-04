"""Tests for DAG abstractions."""

import pytest

from airflow_mini.dag import DAG, PythonOperator


def test_topological_order():
    dag = DAG("test")
    a = dag.add_task(PythonOperator("a", lambda c: 1))
    b = dag.add_task(PythonOperator("b", lambda c: 2))
    c = dag.add_task(PythonOperator("c", lambda c: 3))
    a >> b >> c

    order = dag.topo_order()
    ids = [t.task_id for t in order]
    assert ids == ["a", "b", "c"]


def test_cycle_detection():
    dag = DAG("cycle")
    a = dag.add_task(PythonOperator("a", lambda c: 1))
    b = dag.add_task(PythonOperator("b", lambda c: 2))
    a >> b
    b >> a

    with pytest.raises(ValueError, match="Cycle detected"):
        dag.topo_order()


def test_self_dependency_rejected():
    dag = DAG("self")
    a = dag.add_task(PythonOperator("a", lambda c: 1))
    with pytest.raises(ValueError):
        a >> a

"""End-to-end demo test."""

from airflow_mini.demo import build_ml_pipeline_dag, run_demo
from airflow_mini.state import SUCCESS


def test_run_demo():
    result = run_demo()
    assert result["dag_run_state"] == SUCCESS
    assert all(s == SUCCESS for s in result["task_states"].values())
    assert result["xcom_notify"]["model"] == "logistic-regression"


def test_build_dag():
    dag = build_ml_pipeline_dag()
    order = [t.task_id for t in dag.topo_order()]
    assert order == ["wait_file", "extract", "transform", "train", "notify"]

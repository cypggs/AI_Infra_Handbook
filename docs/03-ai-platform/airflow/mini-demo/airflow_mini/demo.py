"""End-to-end demo of Airflow Mini."""

from airflow_mini.dag import DAG, PythonOperator, WaitFileOperator
from airflow_mini.executor import LocalExecutor
from airflow_mini.parser import DagBag, DagProcessor
from airflow_mini.scheduler import InMemoryDB, Scheduler
from airflow_mini.state import SUCCESS
from airflow_mini.triggerer import Triggerer
from airflow_mini.xcom import XCom


def build_ml_pipeline_dag() -> DAG:
    """Build a demo DAG: wait_file -> extract -> transform -> train -> notify."""
    dag = DAG(dag_id="ml_pipeline", schedule="@daily")

    wait_file = dag.add_task(WaitFileOperator(
        task_id="wait_file",
        filepath="/data/input/done.flag",
    ))

    def extract(context):
        return {"rows": 1000, "path": "s3://bucket/raw/data.parquet"}

    extract_task = dag.add_task(PythonOperator(task_id="extract", python_callable=extract))

    def transform(context):
        xcom = context["xcom"]
        upstream = xcom.pull(context["dag"].dag_id, context["run_id"], "extract")
        return {"rows": upstream["rows"], "transformed": True}

    transform_task = dag.add_task(PythonOperator(task_id="transform", python_callable=transform))

    def train(context):
        xcom = context["xcom"]
        upstream = xcom.pull(context["dag"].dag_id, context["run_id"], "transform")
        return {"model": "logistic-regression", "rows": upstream["rows"]}

    train_task = dag.add_task(PythonOperator(task_id="train", python_callable=train))

    def notify(context):
        xcom = context["xcom"]
        upstream = xcom.pull(context["dag"].dag_id, context["run_id"], "train")
        return {"notified": True, "model": upstream["model"]}

    notify_task = dag.add_task(PythonOperator(task_id="notify", python_callable=notify))

    wait_file >> extract_task >> transform_task >> train_task >> notify_task
    return dag


def run_demo() -> dict:
    """Run the full DAG lifecycle and return summary."""
    triggerer = Triggerer()
    xcom = XCom()
    db = InMemoryDB(triggerer)
    executor = LocalExecutor(db, xcom)
    scheduler = Scheduler(db, executor, triggerer)

    dag = build_ml_pipeline_dag()
    processor = DagProcessor(DagBag())
    processor.process_dag(dag)

    run_id = "manual__2026-07-01"
    scheduler.create_dag_run(dag, run_id, logical_date="2026-07-01")

    # First scheduling round: wait_file defers, others blocked
    scheduler.schedule(dag, run_id)
    executor.execute_queued()

    # Mark file ready and resume
    triggerer.mark_ready("/data/input/done.flag")
    scheduler.run_to_completion(dag, run_id)

    # Collect results
    ti_states = {
        task_id: db.task_instances[(dag.dag_id, run_id, task_id)]["state"]
        for task_id in dag.tasks
    }
    dag_run_state = db.dag_runs[(dag.dag_id, run_id)]["state"]

    return {
        "dag_id": dag.dag_id,
        "run_id": run_id,
        "dag_run_state": dag_run_state,
        "task_states": ti_states,
        "xcom_notify": xcom.pull(dag.dag_id, run_id, "notify", "return_value"),
    }


if __name__ == "__main__":
    result = run_demo()
    print("Airflow Mini Demo result:")
    for k, v in result.items():
        print(f"  {k}: {v}")
    assert result["dag_run_state"] == SUCCESS, "Demo DAG should complete successfully"
    print("Demo passed!")

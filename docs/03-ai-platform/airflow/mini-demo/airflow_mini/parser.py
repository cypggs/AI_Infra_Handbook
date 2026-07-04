"""DAG parsing / processing simulation."""

from typing import Dict, List

from airflow_mini.dag import DAG


class DagBag:
    """In-memory bag of parsed DAGs."""

    def __init__(self):
        self.dags: Dict[str, DAG] = {}

    def add_dag(self, dag: DAG) -> None:
        self.dags[dag.dag_id] = dag

    def get_dag(self, dag_id: str) -> DAG:
        if dag_id not in self.dags:
            raise KeyError(f"DAG {dag_id} not found")
        return self.dags[dag_id]

    def list_dags(self) -> List[DAG]:
        return list(self.dags.values())


class DagProcessor:
    """Simulate parsing DAG files into a DagBag."""

    def __init__(self, dag_bag: DagBag):
        self.dag_bag = dag_bag

    def process_dag(self, dag: DAG) -> None:
        # Validate DAG is a DAG (no cycles)
        dag.topo_order()
        self.dag_bag.add_dag(dag)

    def process_dags(self, dags: List[DAG]) -> None:
        for dag in dags:
            self.process_dag(dag)

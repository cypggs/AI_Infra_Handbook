"""End-to-end demo: Profile → Notebook → Pipeline Run → Katib → PyTorchJob → KServe."""
from __future__ import annotations

from kubeflow_mini.controllers import Controllers, FakeClock, make_obj
from kubeflow_mini.informer import Informer
from kubeflow_mini.store import Store
from kubeflow_mini.workqueue import WorkQueue


def build_demo() -> tuple[Store, Controllers]:
    store = Store()
    informer = Informer(store)
    queue = WorkQueue()
    clock = FakeClock()
    controllers = Controllers(store, informer, queue, clock)
    informer.add_event_handler(controllers.handle_event)
    return store, controllers


def create_resources(store: Store, controllers: Controllers) -> None:
    # 1. Profile
    profile = make_obj("Profile", "", "alice", {
        "owner": {"kind": "User", "name": "alice@example.com"},
        "resourceQuotaSpec": {"hard": {"requests.cpu": "10", "requests.memory": "40Gi"}},
    })
    store.create(profile)
    controllers.emit("add", profile)

    # 2. Notebook
    nb = make_obj("Notebook", "alice", "eda", {"image": "jupyter/scipy-notebook:latest"})
    store.create(nb)
    controllers.emit("add", nb)

    # 3. Pipeline
    pipeline = make_obj("Pipeline", "alice", "train-and-serve", {
        "tasks": {
            "preprocess": {"kind": "Job", "depends_on": []},
            "tune": {"kind": "Experiment", "depends_on": ["preprocess"]},
            "train": {"kind": "PyTorchJob", "depends_on": ["tune"]},
            "deploy": {"kind": "InferenceService", "depends_on": ["train"]},
        }
    })
    store.create(pipeline)
    controllers.emit("add", pipeline)

    # 4. Run
    run = make_obj("Run", "alice", "run-001", {"pipelineRef": "train-and-serve"})
    store.create(run)
    controllers.emit("add", run)


def run_demo() -> dict:
    store, controllers = build_demo()
    create_resources(store, controllers)
    steps = controllers.run_until_idle(max_steps=50)

    run = store.get("Run", "alice", "run-001")
    isvc = store.get("InferenceService", "alice", "run-001-deploy")
    experiment = store.get("Experiment", "alice", "run-001-tune")
    return {
        "steps": steps,
        "run_phase": run["status"].get("phase") if run else None,
        "best_lr": experiment["status"].get("bestParams", {}).get("lr") if experiment else None,
        "best_metric": experiment["status"].get("bestMetric") if experiment else None,
        "service_url": isvc["status"].get("url") if isvc else None,
    }


if __name__ == "__main__":
    result = run_demo()
    print("Demo result:", result)

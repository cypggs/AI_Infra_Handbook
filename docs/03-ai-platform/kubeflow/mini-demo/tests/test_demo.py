"""Tests for kubeflow-mini demo."""
from kubeflow_mini import Store
from kubeflow_mini.controllers import Controllers, FakeClock, make_obj
from kubeflow_mini.informer import Informer
from kubeflow_mini.workqueue import WorkQueue


def _setup():
    store = Store()
    informer = Informer(store)
    queue = WorkQueue()
    clock = FakeClock()
    controllers = Controllers(store, informer, queue, clock)
    informer.add_event_handler(controllers.handle_event)
    return store, controllers


def test_store_create_and_get():
    store, _ = _setup()
    obj = make_obj("Profile", "", "alice", {})
    store.create(obj)
    assert store.get("Profile", "", "alice") is obj


def test_profile_creates_namespace_and_quota():
    store, controllers = _setup()
    profile = make_obj("Profile", "", "alice", {
        "owner": {"kind": "User", "name": "alice@example.com"},
        "resourceQuotaSpec": {"hard": {"cpu": "10"}},
    })
    store.create(profile)
    controllers.reconcile(profile)
    assert store.get("Namespace", "", "alice") is not None
    assert store.get("ResourceQuota", "alice", "alice-quota") is not None
    assert profile["status"]["phase"] == "Active"


def test_notebook_waits_for_profile():
    store, controllers = _setup()
    nb = make_obj("Notebook", "alice", "eda", {})
    store.create(nb)
    controllers.reconcile(nb)
    assert store.get("StatefulSet", "alice", "eda-sts") is None

    profile = make_obj("Profile", "", "alice", {})
    store.create(profile)
    controllers.reconcile(profile)
    controllers.reconcile(nb)
    assert store.get("StatefulSet", "alice", "eda-sts") is not None


def test_notebook_becomes_ready_after_one_tick():
    store, controllers = _setup()
    profile = make_obj("Profile", "", "alice", {})
    store.create(profile)
    controllers.reconcile(profile)
    nb = make_obj("Notebook", "alice", "eda", {})
    store.create(nb)
    controllers.reconcile(nb)
    assert nb["status"]["phase"] == "Pending"
    controllers.clock.step()
    controllers.reconcile(nb)
    assert nb["status"]["phase"] == "Ready"


def test_pipeline_validation_fails_on_missing_dependency():
    store, controllers = _setup()
    pipeline = make_obj("Pipeline", "alice", "p", {
        "tasks": {"a": {"kind": "Job", "depends_on": ["missing"]}}
    })
    store.create(pipeline)
    controllers.reconcile(pipeline)
    assert pipeline["status"]["phase"] == "Failed"


def test_experiment_creates_trials_and_picks_best_lr():
    store, controllers = _setup()
    exp = make_obj("Experiment", "alice", "tune", {"maxTrialCount": 3})
    store.create(exp)
    controllers.reconcile(exp)
    trials = store.list("Trial", "alice")
    assert len(trials) == 3
    # two steps: one to set ready_at, one to complete
    controllers.step()
    controllers.step()
    controllers.reconcile(exp)
    assert exp["status"]["phase"] == "Succeeded"
    # highest lr wins in the toy metric (loss = 0.1 - lr*10)
    lrs = [t["spec"]["lr"] for t in trials]
    assert exp["status"]["bestParams"]["lr"] == max(lrs)


def test_pytorchjob_creates_pods():
    store, controllers = _setup()
    job = make_obj("PyTorchJob", "alice", "train", {
        "replicas": {"Master": 1, "Worker": 2}
    })
    store.create(job)
    controllers.reconcile(job)
    pods = store.list("Pod", "alice")
    assert len(pods) == 3


def test_demo_end_to_end():
    from kubeflow_mini.demo import run_demo
    result = run_demo()
    assert result["run_phase"] == "Succeeded"
    assert result["best_lr"] is not None
    assert result["service_url"].startswith("http://run-001-deploy.alice.svc")

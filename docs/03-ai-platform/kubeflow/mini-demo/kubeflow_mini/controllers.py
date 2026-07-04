"""Reconcilers for Kubeflow-like CRDs using FakeClock."""
from __future__ import annotations

from dataclasses import dataclass

from kubeflow_mini.informer import Event, Informer
from kubeflow_mini.store import Store
from kubeflow_mini.workqueue import Item, WorkQueue


@dataclass
class FakeClock:
    now: int = 0

    def step(self) -> None:
        self.now += 1


def make_obj(kind: str, namespace: str, name: str, spec: dict | None = None) -> dict:
    return {
        "kind": kind,
        "metadata": {"namespace": namespace, "name": name},
        "spec": spec or {},
        "status": {"phase": "Pending"},
    }


TOP_LEVEL_KINDS = {
    "Profile",
    "Notebook",
    "Pipeline",
    "Run",
    "Experiment",
    "Trial",
    "Job",
    "PyTorchJob",
    "Pod",
    "InferenceService",
}

TERMINAL_PHASES = {"Active", "Valid", "Ready", "Succeeded", "Failed"}


class Controllers:
    def __init__(self, store: Store, informer: Informer, queue: WorkQueue, clock: FakeClock) -> None:
        self.store = store
        self.informer = informer
        self.queue = queue
        self.clock = clock

    def enqueue(self, obj: dict) -> None:
        if obj["status"].get("phase") in TERMINAL_PHASES:
            return
        meta = obj["metadata"]
        key = Store.key(obj["kind"], meta["namespace"], meta["name"])
        self.queue.add(Item(key=key, obj=obj))

    def emit(self, event_type: str, obj: dict) -> None:
        self.informer.emit(Event(event_type, obj))

    def reconcile(self, obj: dict) -> None:
        kind = obj["kind"]
        method = getattr(self, f"reconcile_{kind.lower()}", None)
        if method:
            method(obj)

    # ---------- Profile ----------
    def reconcile_profile(self, profile: dict) -> None:
        ns_name = profile["metadata"]["name"]
        if self.store.get("Namespace", "", ns_name) is None:
            ns = make_obj("Namespace", "", ns_name, {"owner": profile["spec"].get("owner", {})})
            self.store.create(ns)
            self.emit("add", ns)

        quota_name = f"{ns_name}-quota"
        if self.store.get("ResourceQuota", ns_name, quota_name) is None:
            quota = make_obj(
                "ResourceQuota",
                ns_name,
                quota_name,
                profile["spec"].get("resourceQuotaSpec", {}),
            )
            self.store.create(quota)
            self.emit("add", quota)

        profile["status"]["phase"] = "Active"
        self.store.update(profile)
        self.emit("update", profile)

    # ---------- Notebook ----------
    def reconcile_notebook(self, nb: dict) -> None:
        ns = nb["metadata"]["namespace"]
        name = nb["metadata"]["name"]
        if self.store.get("Profile", "", ns) is None:
            return  # wait for Profile

        sts_name = f"{name}-sts"
        if self.store.get("StatefulSet", ns, sts_name) is None:
            sts = make_obj("StatefulSet", ns, sts_name, {"replicas": 1, "notebook": name})
            self.store.create(sts)
            self.emit("add", sts)

        svc_name = f"{name}-svc"
        if self.store.get("Service", ns, svc_name) is None:
            svc = make_obj("Service", ns, svc_name, {"notebook": name})
            self.store.create(svc)
            self.emit("add", svc)

        ready_at = nb["status"].get("ready_at")
        if ready_at is None:
            nb["status"]["ready_at"] = self.clock.now + 1
        elif self.clock.now >= ready_at:
            nb["status"]["phase"] = "Ready"
            nb["status"]["url"] = f"/notebook/{ns}/{name}"
        self.store.update(nb)
        self.emit("update", nb)

    # ---------- Pipeline ----------
    def reconcile_pipeline(self, pipeline: dict) -> None:
        tasks = pipeline["spec"].get("tasks", {})
        # Simple validation: all task dependencies exist.
        for task_name, task in tasks.items():
            for dep in task.get("depends_on", []):
                if dep not in tasks:
                    pipeline["status"]["phase"] = "Failed"
                    pipeline["status"]["reason"] = f"missing dependency {dep}"
                    self.store.update(pipeline)
                    return
        pipeline["status"]["phase"] = "Valid"
        self.store.update(pipeline)
        self.emit("update", pipeline)

    # ---------- Run ----------
    def reconcile_run(self, run: dict) -> None:
        ns = run["metadata"]["namespace"]
        name = run["metadata"]["name"]
        pipeline_name = run["spec"].get("pipelineRef")
        pipeline = self.store.get("Pipeline", ns, pipeline_name) if pipeline_name else None
        if pipeline is None:
            return

        state = run["status"].setdefault("state", {})
        tasks = pipeline["spec"].get("tasks", {})

        for task_name, task in tasks.items():
            if state.get(task_name) == "Succeeded":
                continue
            deps = task.get("depends_on", [])
            if not all(state.get(d) == "Succeeded" for d in deps):
                continue

            resource = self.store.get(task["kind"], ns, f"{name}-{task_name}")
            if resource is None:
                if task["kind"] == "Job":
                    job = make_obj("Job", ns, f"{name}-{task_name}", {"task": task_name})
                    self.store.create(job)
                    self.emit("add", job)
                elif task["kind"] == "Experiment":
                    exp = make_obj(
                        "Experiment",
                        ns,
                        f"{name}-{task_name}",
                        {"algorithm": "random", "maxTrialCount": 3},
                    )
                    self.store.create(exp)
                    self.emit("add", exp)
                elif task["kind"] == "PyTorchJob":
                    lr = run["spec"].get("parameters", {}).get("lr", 0.001)
                    job = make_obj(
                        "PyTorchJob",
                        ns,
                        f"{name}-{task_name}",
                        {"replicas": {"Master": 1, "Worker": 2}, "lr": lr},
                    )
                    self.store.create(job)
                    self.emit("add", job)
                elif task["kind"] == "InferenceService":
                    isvc = make_obj(
                        "InferenceService",
                        ns,
                        f"{name}-{task_name}",
                        {"modelUri": f"s3://{ns}/models/{name}"},
                    )
                    self.store.create(isvc)
                    self.emit("add", isvc)
                state[task_name] = "Running"
            else:
                phase = resource["status"].get("phase")
                terminal = {"Succeeded", "Ready"}
                if phase in terminal or (task["kind"] == "InferenceService" and phase == "Ready"):
                    if task["kind"] == "Experiment":
                        run["spec"].setdefault("parameters", {})["lr"] = resource["status"].get(
                            "bestParams", {}
                        ).get("lr", 0.001)
                    state[task_name] = "Succeeded"

        if all(state.get(t) == "Succeeded" for t in tasks):
            run["status"]["phase"] = "Succeeded"
        else:
            run["status"]["phase"] = "Running"
        self.store.update(run)
        self.emit("update", run)

    # ---------- Job ----------
    def reconcile_job(self, job: dict) -> None:
        ready_at = job["status"].get("ready_at")
        if ready_at is None:
            job["status"]["ready_at"] = self.clock.now + 1
        elif self.clock.now >= ready_at:
            job["status"]["phase"] = "Succeeded"
        self.store.update(job)
        self.emit("update", job)

    # ---------- Experiment / Trial ----------
    def reconcile_experiment(self, exp: dict) -> None:
        ns = exp["metadata"]["namespace"]
        name = exp["metadata"]["name"]
        max_trials = exp["spec"].get("maxTrialCount", 3)
        trials = self.store.list("Trial", ns)
        my_trials = [t for t in trials if t["spec"].get("experiment") == name]

        if len(my_trials) < max_trials:
            for i in range(len(my_trials), max_trials):
                trial_name = f"{name}-trial-{i}"
                lr = round(0.001 + (i * 0.005), 4)
                trial = make_obj(
                    "Trial",
                    ns,
                    trial_name,
                    {"lr": lr, "experiment": name},
                )
                trial["status"]["phase"] = "Pending"
                self.store.create(trial)
                self.emit("add", trial)

        if not my_trials:
            return

        if all(t["status"].get("phase") == "Succeeded" for t in my_trials):
            best = min(my_trials, key=lambda t: t["status"].get("metric", float("inf")))
            exp["status"]["phase"] = "Succeeded"
            exp["status"]["bestParams"] = {"lr": best["spec"]["lr"]}
            exp["status"]["bestMetric"] = best["status"]["metric"]
        else:
            exp["status"]["phase"] = "Running"
        self.store.update(exp)
        self.emit("update", exp)

    def reconcile_trial(self, trial: dict) -> None:
        ready_at = trial["status"].get("ready_at")
        if ready_at is None:
            trial["status"]["ready_at"] = self.clock.now + 1
            # Deterministic metric: lower lr -> lower loss in this toy model.
            lr = trial["spec"]["lr"]
            trial["status"]["metric"] = round(0.1 - lr * 10, 6)
        elif self.clock.now >= ready_at:
            trial["status"]["phase"] = "Succeeded"
        self.store.update(trial)
        self.emit("update", trial)

    # ---------- PyTorchJob ----------
    def reconcile_pytorchjob(self, job: dict) -> None:
        ns = job["metadata"]["namespace"]
        name = job["metadata"]["name"]
        replicas = job["spec"].get("replicas", {})
        total = sum(replicas.values())
        pods = self.store.list("Pod", ns)
        my_pods = [p for p in pods if p["spec"].get("job") == name]

        if len(my_pods) < total:
            for role, count in replicas.items():
                existing = [p for p in my_pods if p["spec"].get("role") == role]
                for i in range(len(existing), count):
                    pod = make_obj("Pod", ns, f"{name}-{role.lower()}-{i}", {"job": name, "role": role})
                    self.store.create(pod)
                    self.emit("add", pod)

        if all(p["status"].get("phase") == "Succeeded" for p in my_pods) and my_pods:
            job["status"]["phase"] = "Succeeded"
            job["status"]["modelUri"] = job["spec"].get("modelUri", f"s3://{ns}/models/{name}")
        else:
            job["status"]["phase"] = "Running"
        self.store.update(job)
        self.emit("update", job)

    # ---------- Pod ----------
    def reconcile_pod(self, pod: dict) -> None:
        ready_at = pod["status"].get("ready_at")
        if ready_at is None:
            pod["status"]["ready_at"] = self.clock.now + 1
        elif self.clock.now >= ready_at:
            pod["status"]["phase"] = "Succeeded"
        self.store.update(pod)
        self.emit("update", pod)

    # ---------- InferenceService ----------
    def reconcile_inferenceservice(self, isvc: dict) -> None:
        ready_at = isvc["status"].get("ready_at")
        if ready_at is None:
            isvc["status"]["ready_at"] = self.clock.now + 1
        elif self.clock.now >= ready_at:
            isvc["status"]["phase"] = "Ready"
            isvc["status"]["url"] = f"http://{isvc['metadata']['name']}.{isvc['metadata']['namespace']}.svc"
        self.store.update(isvc)
        self.emit("update", isvc)

    # ---------- Event routing ----------
    def handle_event(self, event: Event) -> None:
        obj = event.obj
        self.enqueue(obj)

    def process_queue_once(self) -> None:
        item = self.queue.get()
        if item is None:
            return
        obj = self.store.get(*item.key)
        if obj is None:
            return
        try:
            self.reconcile(obj)
        except Exception:
            if not self.queue.requeue(item):
                obj["status"]["phase"] = "Failed"
                self.store.update(obj)

    def step(self) -> bool:
        """Process informer events and workqueue, then advance clock.

        Returns True if any object phase changed this step.
        """
        # Re-enqueue top-level resources so parent controllers observe child updates.
        for obj in list(self.store._objects.values()):
            if (
                obj["kind"] in TOP_LEVEL_KINDS
                and obj["status"].get("phase") not in TERMINAL_PHASES
            ):
                self.enqueue(obj)

        while self.informer.process_next():
            pass

        changed = False
        while self.queue.has_pending():
            item = self.queue.get()
            obj = self.store.get(*item.key)
            if obj is None:
                continue
            old_phase = obj["status"].get("phase")
            try:
                self.reconcile(obj)
            except Exception:
                if not self.queue.requeue(item):
                    obj["status"]["phase"] = "Failed"
                    self.store.update(obj)
            new_phase = obj["status"].get("phase")
            if old_phase != new_phase:
                changed = True
        self.clock.step()
        return changed

    def run_until_idle(self, max_steps: int = 100) -> int:
        for i in range(max_steps):
            had_informer = self.informer.has_pending()
            changed = self.step()
            if not had_informer and not changed and not self.queue.has_pending():
                return i + 1
        return max_steps

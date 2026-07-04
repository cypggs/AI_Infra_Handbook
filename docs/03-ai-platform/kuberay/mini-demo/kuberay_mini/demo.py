"""KubeRay control-plane mini demo.

Simulates a minimal Kubernetes control plane (apiserver, informer, workqueue,
clock) and a KubeRay operator that reconciles RayCluster and RayJob CRDs.
No real Kubernetes or Ray runtime is required.
"""
from __future__ import annotations

import copy
import heapq
import itertools
from dataclasses import dataclass, field
from typing import Any, Callable

RAYCLUSTER_KIND = "RayCluster"
RAYJOB_KIND = "RayJob"
POD_KIND = "Pod"
SERVICE_KIND = "Service"
JOB_KIND = "Job"

HEAD_SVC_SUFFIX = "-head-svc"
SERVE_SVC_SUFFIX = "-serve-svc"


class Conflict(Exception):
    pass


class NotFound(Exception):
    pass


# --------------------------------------------------------------------------- #
# FakeClock
# --------------------------------------------------------------------------- #
class FakeClock:
    def __init__(self) -> None:
        self._now = 0.0

    def now(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


# --------------------------------------------------------------------------- #
# Model helpers
# --------------------------------------------------------------------------- #
def make_metadata(name: str, namespace: str = "default") -> dict:
    return {
        "name": name,
        "namespace": namespace,
        "resourceVersion": "",
        "generation": 1,
        "uid": f"{namespace}/{name}",
    }


def key(obj: dict) -> tuple[str, str, str]:
    return obj["kind"], obj["metadata"]["namespace"], obj["metadata"]["name"]


def owner_ref(owner: dict) -> dict:
    return {
        "apiVersion": "ray.io/v1",
        "kind": owner["kind"],
        "name": owner["metadata"]["name"],
        "uid": owner["metadata"]["uid"],
        "controller": True,
    }


def controller_owner_id(obj: dict) -> tuple[str, str, str] | None:
    for ref in obj.get("metadata", {}).get("ownerReferences", []):
        if ref.get("controller"):
            return (ref["kind"], obj["metadata"]["namespace"], ref["name"])
    return None


def make_ray_cluster(
    name: str,
    namespace: str = "default",
    head_cpu: str = "0",
    worker_replicas: int = 2,
    min_replicas: int = 1,
    max_replicas: int = 4,
    autoscaling: bool = False,
) -> dict:
    return {
        "kind": RAYCLUSTER_KIND,
        "metadata": make_metadata(name, namespace),
        "spec": {
            "headGroupSpec": {
                "rayStartParams": {"num-cpus": head_cpu},
            },
            "workerGroupSpecs": [
                {
                    "groupName": "cpu-workers",
                    "replicas": worker_replicas,
                    "minReplicas": min_replicas,
                    "maxReplicas": max_replicas,
                }
            ],
            "enableInTreeAutoscaling": autoscaling,
        },
        "status": {
            "state": "unknown",
            "readyWorkerReplicas": 0,
            "desiredWorkerReplicas": 0,
            "availableWorkerReplicas": 0,
            "observedGeneration": 0,
        },
    }


def make_ray_job(
    name: str,
    namespace: str = "default",
    entrypoint: str = "python train.py",
    shutdown: bool = True,
    cluster_name: str | None = None,
) -> dict:
    spec: dict = {
        "entrypoint": entrypoint,
        "shutdownAfterJobFinishes": shutdown,
        "submissionMode": "K8sJobMode",
    }
    if cluster_name is None:
        spec["rayClusterSpec"] = make_ray_cluster(f"{name}-cluster", namespace)["spec"]
    else:
        spec["clusterSelector"] = {"name": cluster_name}
    return {
        "kind": RAYJOB_KIND,
        "metadata": make_metadata(name, namespace),
        "spec": spec,
        "status": {
            "jobDeploymentStatus": "New",
            "jobStatus": "PENDING",
            "observedGeneration": 0,
        },
    }


def make_service(name: str, namespace: str, cluster: dict, serve: bool = False) -> dict:
    return {
        "kind": SERVICE_KIND,
        "metadata": make_metadata(name, namespace),
        "spec": {"clusterName": cluster["metadata"]["name"], "serve": serve},
        "status": {},
    }


def make_pod(name: str, namespace: str, cluster: dict, group_name: str | None = None) -> dict:
    return {
        "kind": POD_KIND,
        "metadata": make_metadata(name, namespace),
        "spec": {"clusterName": cluster["metadata"]["name"], "groupName": group_name},
        "status": {"phase": "Pending", "ready": False},
    }


def make_submitter_job(name: str, namespace: str, ray_job: dict, cluster: dict) -> dict:
    return {
        "kind": JOB_KIND,
        "metadata": make_metadata(name, namespace),
        "spec": {
            "entrypoint": ray_job["spec"]["entrypoint"],
            "clusterName": cluster["metadata"]["name"],
        },
        "status": {"phase": "Pending", "ready": False},
    }


# --------------------------------------------------------------------------- #
# FakeApiServer
# --------------------------------------------------------------------------- #
class FakeApiServer:
    def __init__(self) -> None:
        self._store: dict[tuple[str, str, str], dict] = {}
        self._events: list[dict] = []
        self._rv = itertools.count(1)
        self._event_idx = itertools.count(1)
        self._inject_conflict = 0

    def _next_rv(self) -> str:
        return str(next(self._rv))

    def _emit(self, etype: str, obj: dict) -> None:
        self._events.append(
            {
                "index": next(self._event_idx),
                "type": etype,
                "key": key(obj),
                "object": copy.deepcopy(obj),
            }
        )

    def event_index(self) -> int:
        return self._events[-1]["index"] if self._events else 0

    def events_since(self, idx: int) -> list[dict]:
        return [e for e in self._events if e["index"] > idx]

    def get(self, kind: str, namespace: str, name: str) -> dict | None:
        obj = self._store.get((kind, namespace, name))
        return copy.deepcopy(obj) if obj else None

    def list(self, kind: str | None = None, namespace: str | None = None) -> dict[tuple, dict]:
        out = {}
        for k, v in self._store.items():
            if kind and k[0] != kind:
                continue
            if namespace and k[1] != namespace:
                continue
            out[k] = copy.deepcopy(v)
        return out

    def create(self, obj: dict) -> dict:
        k = key(obj)
        if k in self._store:
            raise Conflict(f"{k} already exists")
        obj["metadata"]["resourceVersion"] = self._next_rv()
        obj["metadata"]["generation"] = max(1, obj["metadata"].get("generation", 1))
        self._store[k] = copy.deepcopy(obj)
        self._emit("ADDED", obj)
        return copy.deepcopy(obj)

    def update(self, obj: dict) -> dict:
        k = key(obj)
        cur = self._store.get(k)
        if cur is None:
            raise NotFound(f"{k} not found")
        if obj["metadata"].get("resourceVersion") != cur["metadata"]["resourceVersion"]:
            raise Conflict(f"{k} resourceVersion mismatch")
        if self._inject_conflict > 0:
            self._inject_conflict -= 1
            raise Conflict(f"{k} injected conflict")
        spec_changed = obj.get("spec") != cur.get("spec")
        obj["metadata"]["generation"] = cur["metadata"]["generation"] + (1 if spec_changed else 0)
        obj["metadata"]["resourceVersion"] = self._next_rv()
        self._store[k] = copy.deepcopy(obj)
        self._emit("MODIFIED", obj)
        return copy.deepcopy(obj)

    def update_status(self, obj: dict) -> dict:
        k = key(obj)
        cur = self._store.get(k)
        if cur is None:
            raise NotFound(f"{k} not found")
        if obj["metadata"].get("resourceVersion") != cur["metadata"]["resourceVersion"]:
            raise Conflict(f"{k} status resourceVersion mismatch")
        cur["status"] = copy.deepcopy(obj.get("status", {}))
        cur["metadata"]["resourceVersion"] = self._next_rv()
        self._emit("MODIFIED", cur)
        return copy.deepcopy(cur)

    def delete(self, kind: str, namespace: str, name: str) -> dict | None:
        k = (kind, namespace, name)
        cur = self._store.get(k)
        if cur is None:
            return None
        del self._store[k]
        self._emit("DELETED", cur)
        self._gc_children(cur)
        return copy.deepcopy(cur)

    def _gc_children(self, owner: dict) -> None:
        owner_id = (owner["kind"], owner["metadata"]["namespace"], owner["metadata"]["name"])
        children = [k for k, v in self._store.items() if controller_owner_id(v) == owner_id]
        for ck in children:
            child = self._store.pop(ck)
            self._emit("DELETED", child)
            self._gc_children(child)

    def inject_conflict(self, times: int = 1) -> None:
        self._inject_conflict = times


# --------------------------------------------------------------------------- #
# Informer
# --------------------------------------------------------------------------- #
Handler = Callable[[str, str, str], None]


class Informer:
    def __init__(self, apiserver: FakeApiServer, kind: str, handler: Handler | None = None) -> None:
        self.apiserver = apiserver
        self.kind = kind
        self.handler = handler
        self._index = 0

    def set_handler(self, handler: Handler) -> None:
        self.handler = handler

    def pump(self) -> None:
        events = self.apiserver.events_since(self._index)
        for ev in events:
            self._index = ev["index"]
            if ev["key"][0] != self.kind:
                continue
            if self.handler:
                self.handler(ev["key"][1], ev["key"][2])


# --------------------------------------------------------------------------- #
# WorkQueue
# --------------------------------------------------------------------------- #
@dataclass(order=True)
class QueueItem:
    when: float
    index: int = field(compare=True)
    namespaced_name: tuple = field(compare=False)
    kind: str = field(compare=False)


class WorkQueue:
    def __init__(self, clock: FakeClock) -> None:
        self.clock = clock
        self._heap: list[QueueItem] = []
        self._counter = itertools.count()
        self._seen: set[tuple] = set()
        self._processing: set[tuple] = set()

    def add(self, kind: str, namespace: str, name: str, delay: float = 0.0) -> None:
        token = (kind, namespace, name)
        if token in self._seen or token in self._processing:
            return
        self._seen.add(token)
        heapq.heappush(
            self._heap,
            QueueItem(
                when=self.clock.now() + delay,
                index=next(self._counter),
                namespaced_name=(namespace, name),
                kind=kind,
            ),
        )

    def get(self) -> tuple[str, str, str] | None:
        while self._heap:
            item = self._heap[0]
            if item.when > self.clock.now():
                return None
            heapq.heappop(self._heap)
            token = (item.kind, item.namespaced_name[0], item.namespaced_name[1])
            if token in self._seen:
                self._seen.discard(token)
                self._processing.add(token)
                return token
        return None

    def done(self, kind: str, namespace: str, name: str) -> None:
        self._processing.discard((kind, namespace, name))

    def forget(self, kind: str, namespace: str, name: str) -> None:
        self._seen.discard((kind, namespace, name))
        self._processing.discard((kind, namespace, name))

    def depth(self) -> int:
        return len(self._heap) + len(self._processing)

    def next_ready_after(self) -> float | None:
        if not self._heap:
            return None
        return max(0.0, self._heap[0].when - self.clock.now())


# --------------------------------------------------------------------------- #
# Reconcilers
# --------------------------------------------------------------------------- #
class RayClusterReconciler:
    def __init__(
        self,
        apiserver: FakeApiServer,
        informers: dict[str, Informer],
        clock: FakeClock,
        pod_ready_delay: float,
        log: Callable[[str], None] | None = None,
    ) -> None:
        self.apiserver = apiserver
        self.informers = informers
        self.clock = clock
        self.pod_ready_delay = pod_ready_delay
        self.log = log
        self.reconcile_count = 0

    def _l(self, msg: str) -> None:
        if self.log:
            self.log(f"[{self.clock.now():>6.1f}s] {msg}")

    def _get(self, kind: str, namespace: str, name: str) -> dict | None:
        return self.informers[kind].apiserver.get(kind, namespace, name)

    def _list(self, kind: str, namespace: str | None = None) -> dict[tuple, dict]:
        return self.informers[kind].apiserver.list(kind, namespace)

    def reconcile(self, namespace: str, name: str) -> dict:
        self.reconcile_count += 1
        cluster = self._get(RAYCLUSTER_KIND, namespace, name)
        if cluster is None:
            return {}

        cluster_name = cluster["metadata"]["name"]

        # Reconcile head service
        head_svc_name = cluster_name + HEAD_SVC_SUFFIX
        if self._get(SERVICE_KIND, namespace, head_svc_name) is None:
            svc = make_service(head_svc_name, namespace, cluster, serve=False)
            svc["metadata"]["ownerReferences"] = [owner_ref(cluster)]
            self.apiserver.create(svc)
            self._l(f"created head Service {head_svc_name}")

        # Reconcile serve service
        serve_svc_name = cluster_name + SERVE_SVC_SUFFIX
        if self._get(SERVICE_KIND, namespace, serve_svc_name) is None:
            svc = make_service(serve_svc_name, namespace, cluster, serve=True)
            svc["metadata"]["ownerReferences"] = [owner_ref(cluster)]
            self.apiserver.create(svc)
            self._l(f"created serve Service {serve_svc_name}")

        # Reconcile head pod
        head_pod_name = f"{cluster_name}-head"
        if self._get(POD_KIND, namespace, head_pod_name) is None:
            pod = make_pod(head_pod_name, namespace, cluster, group_name=None)
            pod["metadata"]["ownerReferences"] = [owner_ref(cluster)]
            pod["metadata"]["annotations"] = {"createdAt": str(self.clock.now())}
            self.apiserver.create(pod)
            self._l(f"created head Pod {head_pod_name}")

        # Reconcile worker pods per group
        desired_total = 0
        ready_total = 0
        for group in cluster["spec"]["workerGroupSpecs"]:
            group_name = group["groupName"]
            replicas = group["replicas"]
            desired_total += replicas
            existing = [
                pod
                for pod in self._list(POD_KIND, namespace).values()
                if pod["spec"].get("clusterName") == cluster_name
                and pod["spec"].get("groupName") == group_name
            ]
            # Create missing pods
            for i in range(replicas - len(existing)):
                idx = len(existing) + i
                pod_name = f"{cluster_name}-worker-{group_name}-{idx}"
                pod = make_pod(pod_name, namespace, cluster, group_name=group_name)
                pod["metadata"]["ownerReferences"] = [owner_ref(cluster)]
                pod["metadata"]["annotations"] = {"createdAt": str(self.clock.now())}
                self.apiserver.create(pod)
                self._l(f"created worker Pod {pod_name}")
            # Delete excess pods (newest index first)
            if len(existing) > replicas:
                for pod in sorted(
                    existing,
                    key=lambda p: int(p["metadata"]["name"].rsplit("-", 1)[1]),
                    reverse=True,
                )[: len(existing) - replicas]:
                    self.apiserver.delete(
                        POD_KIND, pod["metadata"]["namespace"], pod["metadata"]["name"]
                    )
                    self._l(f"deleted worker Pod {pod['metadata']['name']}")

            # Count ready
            for pod in existing:
                if pod["status"].get("ready"):
                    ready_total += 1

        # Update status
        new_state = "ready" if ready_total == desired_total and desired_total >= 0 else "provisioning"
        new_status = {
            "state": new_state,
            "readyWorkerReplicas": ready_total,
            "desiredWorkerReplicas": desired_total,
            "availableWorkerReplicas": ready_total,
            "observedGeneration": cluster["metadata"]["generation"],
        }
        if cluster["status"] != new_status:
            cluster["status"] = new_status
            try:
                self.apiserver.update_status(cluster)
                self._l(
                    f"updated RayCluster {cluster_name} status "
                    f"ready={ready_total}/{desired_total} state={new_state}"
                )
            except Conflict:
                return {"requeue": True}

        if ready_total < desired_total:
            return {"requeue_after": self.pod_ready_delay}
        return {}


class RayJobReconciler:
    def __init__(
        self,
        apiserver: FakeApiServer,
        informers: dict[str, Informer],
        clock: FakeClock,
        job_run_delay: float,
        log: Callable[[str], None] | None = None,
    ) -> None:
        self.apiserver = apiserver
        self.informers = informers
        self.clock = clock
        self.job_run_delay = job_run_delay
        self.log = log
        self.reconcile_count = 0

    def _l(self, msg: str) -> None:
        if self.log:
            self.log(f"[{self.clock.now():>6.1f}s] {msg}")

    def _get(self, kind: str, namespace: str, name: str) -> dict | None:
        return self.informers[kind].apiserver.get(kind, namespace, name)

    def _list(self, kind: str, namespace: str | None = None) -> dict[tuple, dict]:
        return self.informers[kind].apiserver.list(kind, namespace)

    def reconcile(self, namespace: str, name: str) -> dict:
        self.reconcile_count += 1
        ray_job = self._get(RAYJOB_KIND, namespace, name)
        if ray_job is None:
            return {}

        status = ray_job["status"]["jobDeploymentStatus"]
        if status in ("Complete", "Failed"):
            return {}

        if status == "New":
            ray_job["status"]["jobDeploymentStatus"] = "Initializing"
            self._update_status(ray_job)
            return {"requeue": True}

        if status == "Initializing":
            cluster = self._get_or_create_cluster(ray_job)
            if cluster is None or cluster["status"].get("state") != "ready":
                return {"requeue_after": 1.0}
            submitter_name = f"{name}-submitter"
            if self._get(JOB_KIND, namespace, submitter_name) is None:
                job = make_submitter_job(submitter_name, namespace, ray_job, cluster)
                job["metadata"]["ownerReferences"] = [owner_ref(ray_job)]
                self.apiserver.create(job)
                self._l(f"created submitter Job {submitter_name}")
            ray_job["status"]["jobDeploymentStatus"] = "Running"
            self._update_status(ray_job)
            return {"requeue_after": self.job_run_delay}

        if status == "Running":
            submitter_name = f"{name}-submitter"
            job = self._get(JOB_KIND, namespace, submitter_name)
            if job is None:
                return {"requeue_after": 1.0}
            if job["status"].get("phase") == "Complete":
                ray_job["status"]["jobDeploymentStatus"] = "Complete"
                ray_job["status"]["jobStatus"] = "SUCCEEDED"
                self._l(f"RayJob {name} completed")
                self._update_status(ray_job)
                if ray_job["spec"].get("shutdownAfterJobFinishes"):
                    cluster = self._find_owned_cluster(namespace, name)
                    if cluster:
                        self.apiserver.delete(
                            RAYCLUSTER_KIND,
                            cluster["metadata"]["namespace"],
                            cluster["metadata"]["name"],
                        )
                        self._l("deleted cluster after job completion")
                return {}
            if job["status"].get("phase") == "Failed":
                ray_job["status"]["jobDeploymentStatus"] = "Failed"
                ray_job["status"]["jobStatus"] = "FAILED"
                self._update_status(ray_job)
                return {}
            return {"requeue_after": self.job_run_delay}

        return {}

    def _get_or_create_cluster(self, ray_job: dict) -> dict | None:
        namespace = ray_job["metadata"]["namespace"]
        spec = ray_job["spec"]
        if spec.get("clusterSelector"):
            name = spec["clusterSelector"]["name"]
            return self._get(RAYCLUSTER_KIND, namespace, name)
        cluster_name = f"{ray_job['metadata']['name']}-cluster"
        cluster = self._get(RAYCLUSTER_KIND, namespace, cluster_name)
        if cluster is None:
            cluster = make_ray_cluster(cluster_name, namespace)
            cluster["metadata"]["ownerReferences"] = [owner_ref(ray_job)]
            self.apiserver.create(cluster)
            self._l(f"created RayCluster {cluster_name} for RayJob")
        return cluster

    def _find_owned_cluster(self, namespace: str, job_name: str) -> dict | None:
        for obj in self._list(RAYCLUSTER_KIND, namespace).values():
            for ref in obj.get("metadata", {}).get("ownerReferences", []):
                if ref.get("controller") and ref["name"] == job_name:
                    return obj
        return None

    def _update_status(self, ray_job: dict) -> None:
        ray_job["status"]["observedGeneration"] = ray_job["metadata"]["generation"]
        try:
            self.apiserver.update_status(ray_job)
        except Conflict:
            pass


# --------------------------------------------------------------------------- #
# Controller loop
# --------------------------------------------------------------------------- #
class Controller:
    def __init__(
        self,
        apiserver: FakeApiServer,
        clock: FakeClock,
        queue: WorkQueue,
        informers: dict[str, Informer],
        cluster_reconciler: RayClusterReconciler,
        job_reconciler: RayJobReconciler,
    ) -> None:
        self.apiserver = apiserver
        self.clock = clock
        self.queue = queue
        self.informers = informers
        self.cluster_reconciler = cluster_reconciler
        self.job_reconciler = job_reconciler
        self.reconcile_total = 0
        self.reconcile_errors = 0
        self.logs: list[str] = []

    def _log(self, msg: str) -> None:
        self.logs.append(msg)
        print(msg)

    def enqueue_owner(self, owner_kind: str) -> Callable[[str, str, str], None]:
        def handler(namespace: str, name: str) -> None:
            obj = self.apiserver.get(POD_KIND, namespace, name) or self.apiserver.get(SERVICE_KIND, namespace, name) or self.apiserver.get(JOB_KIND, namespace, name) or self.apiserver.get(RAYCLUSTER_KIND, namespace, name)
            if obj is None:
                return
            owner_id = controller_owner_id(obj)
            if owner_id and owner_id[0] == owner_kind:
                self.queue.add(owner_id[0], owner_id[1], owner_id[2])
        return handler

    def step(self) -> bool:
        self._make_pods_ready()
        self._advance_submitter_jobs()
        for inf in self.informers.values():
            inf.pump()

        item = self.queue.get()
        if item is None:
            return False
        kind, namespace, name = item
        self.reconcile_total += 1
        try:
            if kind == RAYCLUSTER_KIND:
                result = self.cluster_reconciler.reconcile(namespace, name)
            elif kind == RAYJOB_KIND:
                result = self.job_reconciler.reconcile(namespace, name)
            else:
                result = {}
        except Exception as e:
            self.reconcile_errors += 1
            print(f"reconcile error: {e}")
            result = {}

        self.queue.done(kind, namespace, name)
        if result.get("requeue"):
            self.queue.add(kind, namespace, name)
        elif "requeue_after" in result:
            self.queue.add(kind, namespace, name, delay=result["requeue_after"])
        else:
            self.queue.forget(kind, namespace, name)
        return True

    def run_until_quiescent(self, max_steps: int = 2000) -> None:
        # Initial enqueue of existing objects
        for obj in self.apiserver.list().values():
            self.queue.add(obj["kind"], obj["metadata"]["namespace"], obj["metadata"]["name"])
        steps = 0
        guard = 0
        while steps < max_steps and guard < max_steps * 6:
            guard += 1
            if self.step():
                steps += 1
                continue
            if self.queue.depth() == 0:
                break
            nxt = self.queue.next_ready_after()
            if nxt is not None:
                self.clock.advance(nxt)
            else:
                break
        else:
            raise RuntimeError("controller did not converge")

    def _make_pods_ready(self) -> None:
        for obj in self.apiserver.list(POD_KIND).values():
            created = float(obj.get("metadata", {}).get("annotations", {}).get("createdAt", 0))
            if (
                obj["status"]["phase"] == "Pending"
                and self.clock.now() - created >= self.cluster_reconciler.pod_ready_delay
            ):
                obj["status"]["phase"] = "Running"
                obj["status"]["ready"] = True
                self.apiserver.update(obj)

    def _advance_submitter_jobs(self) -> None:
        for obj in self.apiserver.list(JOB_KIND).values():
            created = float(obj.get("metadata", {}).get("annotations", {}).get("createdAt", 0))
            if obj["status"]["phase"] == "Pending" and self.clock.now() - created >= 1.0:
                obj["status"]["phase"] = "Running"
                self.apiserver.update(obj)
            elif (
                obj["status"]["phase"] == "Running"
                and self.clock.now() - created >= self.job_reconciler.job_run_delay + 1.0
            ):
                obj["status"]["phase"] = "Complete"
                self.apiserver.update(obj)


# --------------------------------------------------------------------------- #
# Demo entry point
# --------------------------------------------------------------------------- #
def build(
    pod_ready_delay: float = 2.0,
    job_run_delay: float = 3.0,
) -> tuple[Controller, FakeApiServer, FakeClock]:
    clock = FakeClock()
    apiserver = FakeApiServer()
    queue = WorkQueue(clock)

    informers = {
        RAYCLUSTER_KIND: Informer(apiserver, RAYCLUSTER_KIND),
        RAYJOB_KIND: Informer(apiserver, RAYJOB_KIND),
        POD_KIND: Informer(apiserver, POD_KIND),
        SERVICE_KIND: Informer(apiserver, SERVICE_KIND),
        JOB_KIND: Informer(apiserver, JOB_KIND),
    }

    cluster_reconciler = RayClusterReconciler(
        apiserver, informers, clock, pod_ready_delay, log=print
    )
    job_reconciler = RayJobReconciler(
        apiserver, informers, clock, job_run_delay, log=print
    )
    controller = Controller(
        apiserver, clock, queue, informers, cluster_reconciler, job_reconciler
    )

    # Main CRD informers enqueue themselves on events
    informers[RAYCLUSTER_KIND].set_handler(
        lambda ns, name: queue.add(RAYCLUSTER_KIND, ns, name)
    )
    informers[RAYJOB_KIND].set_handler(
        lambda ns, name: queue.add(RAYJOB_KIND, ns, name)
    )
    # Owned resources enqueue their owner
    informers[POD_KIND].set_handler(controller.enqueue_owner(RAYCLUSTER_KIND))
    informers[SERVICE_KIND].set_handler(controller.enqueue_owner(RAYCLUSTER_KIND))
    informers[JOB_KIND].set_handler(controller.enqueue_owner(RAYJOB_KIND))

    return controller, apiserver, clock


def run_demo() -> dict[str, Any]:
    controller, apiserver, clock = build()

    # 1. Create a RayCluster
    cluster = make_ray_cluster("example-cluster", worker_replicas=2)
    apiserver.create(cluster)
    controller.run_until_quiescent()

    cluster = apiserver.get(RAYCLUSTER_KIND, "default", "example-cluster")
    assert cluster["status"]["state"] == "ready"
    assert cluster["status"]["readyWorkerReplicas"] == 2

    # 2. Simulate autoscaler scaling workers out to 4
    cluster["spec"]["workerGroupSpecs"][0]["replicas"] = 4
    apiserver.update(cluster)
    controller.run_until_quiescent()

    cluster = apiserver.get(RAYCLUSTER_KIND, "default", "example-cluster")
    assert cluster["status"]["readyWorkerReplicas"] == 4

    # 3. Submit a RayJob that creates its own cluster
    job = make_ray_job("example-job", entrypoint="python train.py --epochs 10")
    apiserver.create(job)
    controller.run_until_quiescent()

    job = apiserver.get(RAYJOB_KIND, "default", "example-job")
    assert job["status"]["jobDeploymentStatus"] == "Complete"

    # The RayJob's cluster should have been deleted after completion
    job_cluster = apiserver.get(RAYCLUSTER_KIND, "default", "example-job-cluster")

    return {
        "cluster_name": "example-cluster",
        "final_worker_count": cluster["status"]["readyWorkerReplicas"],
        "job_name": "example-job",
        "job_status": job["status"]["jobDeploymentStatus"],
        "job_cluster_deleted": job_cluster is None,
        "elapsed_time": clock.now(),
    }


if __name__ == "__main__":
    result = run_demo()
    print("Demo result:", result)

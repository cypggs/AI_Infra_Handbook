"""Reconciler —— InferenceService 的调和业务逻辑（Operator 的心脏）。

四条铁律在这里逐条落地：
  * level-triggered：每次基于当前全量（CR + Deployment + Service）算 diff，不依赖事件序列。
  * 幂等：先 Get 再 Create/Patch；同样的状态调和 N 次只产生一次副作用。
  * 不阻塞：Pod 没 ready 时返回 RequeueAfter，不在 reconcile 里 sleep。
  * 乐观：写靠 apiserver 的 resourceVersion 乐观锁，冲突时返回 error 让框架退避重试。

此外演示 finalizer（删除清理外部资源）、status 子资源（observedGeneration/conditions）、
owner reference（级联 GC）。
"""
from . import model
from .apiserver import Conflict


INSTANCE_LABEL = "app.kubernetes.io/instance"


class InferenceServiceReconciler:
    def __init__(self, apiserver, clock, ready_after, log=None):
        self.apiserver = apiserver
        self.clock = clock
        self.ready_after = ready_after
        self.is_informer = None       # Controller 装配时注入
        self.deploy_informer = None
        self.svc_informer = None
        self._log_cb = log
        self.cleanup_calls = 0        # 观测用：外部清理被调用了几次

    # ------------------------------------------------------------------ #
    def reconcile(self, kind, namespace, name):
        """返回 (result_dict, error)。result: {requeue, requeue_after} 可空；error 非 None 表示失败。"""
        if kind != model.INFERENCE_SERVICE_KIND:
            return {}, None

        is_obj = self.is_informer.get(kind, namespace, name)
        if is_obj is None:
            # CR 已不存在（被真删）。它拥有的子资源会由 apiserver 级联 GC，这里无需做事。
            return {}, None

        # ---- 删除路径：finalizer 清理 ---- #
        if model.is_being_deleted(is_obj):
            return self._reconcile_delete(is_obj)

        # ---- 确保 finalizer 存在（幂等：第一次 reconcile 加上，之后跳过） ---- #
        if not model.has_finalizer(is_obj):
            model.add_finalizer(is_obj)
            try:
                self.apiserver.update(is_obj)
            except Conflict:
                return {}, Conflict("finalizer add conflict")
            self._log(f"[{self._t():>6.1f}s] ensure finalizer on {name}")
            return {"requeue": True}, None

        # ---- 读现状（子资源，命中本地缓存） ---- #
        svc = self.svc_informer.get(model.SERVICE_KIND, namespace, name)
        dep = self.deploy_informer.get(model.DEPLOYMENT_KIND, namespace, name)

        # ---- act：让现状趋近期望 ---- #
        svc = self._reconcile_service(is_obj, svc)
        dep = self._reconcile_deployment(is_obj, dep)

        # ---- 写 status（报告实际状态）---- #
        ready_replicas = (dep or {}).get("status", {}).get("readyReplicas", 0)
        desired = is_obj["spec"]["replicas"]
        new_status = {
            "observedGeneration": is_obj["metadata"]["generation"],
            "readyReplicas": ready_replicas,
            "ready": ready_replicas == desired and desired > 0,
            "conditions": _conditions(ready_replicas, desired),
        }
        if is_obj["status"] != new_status:
            is_obj["status"] = new_status
            try:
                self.apiserver.update_status(is_obj)
            except Conflict:
                return {}, Conflict("status write conflict")
            self._log(
                f"[{self._t():>6.1f}s] status gen={is_obj['metadata']['generation']} "
                f"ready={ready_replicas}/{desired} observedGen={new_status['observedGeneration']}"
            )

        # ---- 决定是否重排：未收敛 → RequeueAfter（不阻塞） ---- #
        if ready_replicas < desired:
            return {"requeue_after": self.ready_after}, None
        return {}, None

    # ------------------------------------------------------------------ #
    def _reconcile_service(self, is_obj, svc):
        name = is_obj["metadata"]["name"]
        ns = is_obj["metadata"]["namespace"]
        labels = {INSTANCE_LABEL: name, "app.kubernetes.io/managed-by": "inference-operator"}
        desired = model.make_service(name, ns, port=8000, selector={INSTANCE_LABEL: name}, labels=labels)

        if svc is None:
            model.set_owner_reference(desired, is_obj)
            self.apiserver.create(desired)
            self._log(f"[{self._t():>6.1f}s] created Service {name}")
            return desired
        if _svc_needs_update(svc, desired):
            desired["metadata"]["resourceVersion"] = svc["metadata"]["resourceVersion"]
            desired["metadata"]["generation"] = svc["metadata"]["generation"]
            model.set_owner_reference(desired, is_obj)
            try:
                self.apiserver.update(desired)
            except Conflict:
                return svc
            self._log(f"[{self._t():>6.1f}s] updated Service {name}")
            return desired
        return svc

    def _reconcile_deployment(self, is_obj, dep):
        name = is_obj["metadata"]["name"]
        ns = is_obj["metadata"]["namespace"]
        labels = {INSTANCE_LABEL: name, "app.kubernetes.io/managed-by": "inference-operator"}
        desired = model.make_deployment(
            name, ns,
            image=is_obj["spec"]["image"],
            replicas=is_obj["spec"]["replicas"],
            labels=labels,
        )

        if dep is None:
            model.set_owner_reference(desired, is_obj)
            self.apiserver.create(desired)
            self._log(
                f"[{self._t():>6.1f}s] created Deployment {name} "
                f"(image={is_obj['spec']['image']}, replicas={is_obj['spec']['replicas']})"
            )
            return desired
        if _deploy_needs_update(dep, desired):
            # 带上当前 rv 才能通过乐观锁；保留旧 readyReplicas 直到平台刷新
            desired["metadata"]["resourceVersion"] = dep["metadata"]["resourceVersion"]
            desired["status"] = dep.get("status", {"readyReplicas": 0})
            model.set_owner_reference(desired, is_obj)
            try:
                self.apiserver.update(desired)
            except Conflict:
                return dep
            self._log(
                f"[{self._t():>6.1f}s] patched Deployment {name} "
                f"(image={is_obj['spec']['image']}, replicas={is_obj['spec']['replicas']})"
            )
            return desired
        return dep

    def _reconcile_delete(self, is_obj):
        name = is_obj["metadata"]["name"]
        # 模拟清理"K8s 外部资源"：注销云负载均衡器后端、归档最后一版指标……
        self.cleanup_calls += 1
        self._log(f"[{self._t():>6.1f}s] finalizer cleanup: unregistered external LB for {name}")
        model.remove_finalizer(is_obj)
        try:
            self.apiserver.update(is_obj)
        except Conflict:
            return {}, Conflict("finalizer remove conflict")
        # update() 检测到"删除中 + 无 finalizer" → 真删 + 级联 GC（Service/Deployment 自动消失）
        return {}, None

    # ------------------------------------------------------------------ #
    def _t(self):
        return self.clock.now()

    def _log(self, msg):
        if self._log_cb:
            self._log_cb(msg)


def _conditions(ready_replicas, desired):
    ready = ready_replicas == desired and desired > 0
    return [
        {
            "type": "Ready",
            "status": "True" if ready else "False",
            "reason": "AllReady" if ready else "Progressing",
        },
        {
            "type": "Available",
            "status": "True" if ready_replicas > 0 else "False",
            "reason": "MinReplicasAvailable" if ready_replicas > 0 else "WaitingForReplicas",
        },
    ]


def _deploy_needs_update(cur, desired):
    return (
        cur["spec"]["replicas"] != desired["spec"]["replicas"]
        or cur["spec"]["image"] != desired["spec"]["image"]
    )


def _svc_needs_update(cur, desired):
    return (
        cur["spec"].get("port") != desired["spec"]["port"]
        or cur["spec"].get("selector") != desired["spec"]["selector"]
    )

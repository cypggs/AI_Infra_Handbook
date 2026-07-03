"""test_controller.py — Deployment / ReplicaSet 控制器测试。

覆盖控制器范式（watch → reconcile，水平触发）：
  - ReplicaSetController 维持副本数（创建/删除 Pod 使之匹配）
  - owner-reference 级联 GC：RS 被删后其 Pod 被回收
  - DeploymentController 滚动升级：v1 → v2，最终全部 v2 且副本数稳定
"""

from k8s_mini.apiserver import ApiServer
from k8s_mini.controller import DeploymentController, ReplicaSetController
from k8s_mini.model import Container, Deployment, Pod, PodPhase, ReplicaSet, Resources
from k8s_mini.store import Store


def _basic_template(image="app:v1"):
    return Pod(name="web-template",
               containers=[Container(name="app", image=image, requests=Resources(1000, 1024))],
               labels={"app": "web"})


def _server_with_controllers():
    api = ApiServer(Store())
    rsc = ReplicaSetController(api)
    depc = DeploymentController(api, rsc)
    return api, rsc, depc


# ----------------------------- ReplicaSet -----------------------------

def test_replicaset_creates_pods_to_match_replicas():
    api, rsc, _ = _server_with_controllers()
    rs = ReplicaSet(name="web-abc", replicas=3, template_labels={"app": "web"},
                    pod_template=_basic_template())
    api.create_replicaset(rs)
    rsc.reconcile()
    pods = [p for p in api.list_pods() if p.owner_rs == "web-abc"]
    assert len(pods) == 3
    assert all(p.phase == PodPhase.PENDING for p in pods)


def test_replicaset_scales_down_on_replica_decrease():
    api, rsc, _ = _server_with_controllers()
    rs = ReplicaSet(name="web-abc", replicas=3, template_labels={"app": "web"},
                    pod_template=_basic_template())
    api.create_replicaset(rs)
    rsc.reconcile()
    assert len(api.list_pods()) == 3
    rs.replicas = 1
    api.update_replicaset(rs)
    rsc.reconcile()
    assert len([p for p in api.list_pods() if p.owner_rs == "web-abc"]) == 1


def test_orphan_pods_are_garbage_collected_when_rs_deleted():
    api, rsc, _ = _server_with_controllers()
    rs = ReplicaSet(name="web-abc", replicas=2, template_labels={"app": "web"},
                    pod_template=_basic_template())
    api.create_replicaset(rs)
    rsc.reconcile()
    assert len(api.list_pods()) == 2
    # 删除 RS → 其 Pod 成为孤儿
    api.delete_replicaset("web-abc")
    rsc.reconcile()
    assert all(p.owner_rs != "web-abc" for p in api.list_pods())


# ----------------------------- Deployment 滚动 -----------------------------

def _run(c, ticks):
    for _ in range(ticks):
        c["depc"].reconcile()
        c["rsc"].reconcile()
        c["sched"].run_once()
        for kl in c["kubelets"].values():
            kl.reconcile(c["tick"])
        c["tick"] += 1


def test_rollout_converges_to_new_image():
    """v1 → v2：最终所有运行中 Pod 镜像都是 app:v2，且数量 = replicas。"""
    from k8s_mini.demo import MiniCluster
    from k8s_mini.scheduler import SchedulingStrategy

    c = MiniCluster()
    c.add_node("node-a", cpu=4000, memory=8000)
    c.add_node("node-b", cpu=4000, memory=8000)
    c.set_strategy(SchedulingStrategy.SPREAD)

    dep = Deployment(name="web", replicas=3, template_labels={"app": "web"},
                     pod_template=_basic_template("app:v1"))
    c.api.create_deployment(dep)
    c.run(ticks=4)
    assert len(c.running_pods()) == 3
    assert all(p.containers[0].image == "app:v1" for p in c.running_pods())

    # 升级到 v2，给足 tick 让滚动收敛
    dep.pod_template.containers[0].image = "app:v2"
    c.api.update_deployment(dep)
    c.run(ticks=12)

    running = c.running_pods()
    assert len(running) == 3
    assert all(p.containers[0].image == "app:v2" for p in running), \
        f"残留 v1 Pod: {[p.containers[0].image for p in running]}"
    # v1 的旧 RS 应已被清掉（本模拟删到 0 即删）
    assert not any(rs.name.endswith("v1") for rs in c.api.list_replicasets())


def test_self_heal_after_pod_deletion():
    """删一个 Pod，RS 控制器应补齐到期望副本数。"""
    from k8s_mini.demo import MiniCluster

    c = MiniCluster()
    c.add_node("node-a", cpu=4000, memory=8000)
    c.add_node("node-b", cpu=4000, memory=8000)
    dep = Deployment(name="web", replicas=3, template_labels={"app": "web"},
                     pod_template=_basic_template("app:v1"))
    c.api.create_deployment(dep)
    c.run(ticks=4)
    assert len(c.running_pods()) == 3

    victim = c.running_pods()[0]
    c.api.delete_pod(victim.name)
    c.run(ticks=4)
    # 自愈后回到 3
    assert len(c.running_pods()) == 3

"""demo.py —— 六个端到端场景演示。

运行：python -m cni_csi_mini.demo
"""

from cni_csi_mini import (
    FakeApiServer, FakeClock,
    make_node, make_pod, make_pvc,
    volume_mount, container_mount,
    BridgePlugin, PluginChain, RouteManager, NetworkPolicyManager,
    make_network_policy, pod_selector, allow_all_ingress,
    VolumeStore, NodeVolumeStore, ControllerServer, NodeServer,
    Kubelet,
)


def build_cluster(num_nodes=2):
    """装配一个两节点集群：apiserver + 网络/存储插件 + 两个 kubelet。"""
    clock = FakeClock(0.0)
    api = FakeApiServer()
    routes = RouteManager()
    policies = NetworkPolicyManager()
    ipams = {}
    bridge = BridgePlugin(ipams=ipams, routes=routes)
    cni_plugin = PluginChain([bridge])

    store = VolumeStore()
    ctrl = ControllerServer(store)

    kubelets = {}
    for i in range(1, num_nodes + 1):
        node_name = f"node-{i}"
        cidr = f"10.244.{i}.0/24"
        node = make_node(node_name, cidr=cidr,
                         labels={"topology.kubernetes.io/zone": f"zone-{i}"})
        api.create(node)
        routes.register_node(node_name, node["status"]["addresses"][0]["address"], cidr)
        node_store = NodeVolumeStore(node_name)
        kubelet = Kubelet(node_name, api, cni_plugin, ctrl, node_store, routes, clock)
        kubelets[node_name] = kubelet

    return {
        "api": api,
        "clock": clock,
        "routes": routes,
        "policies": policies,
        "bridge": bridge,
        "cni_plugin": cni_plugin,
        "store": store,
        "ctrl": ctrl,
        "kubelets": kubelets,
    }


def _print(title, lines):
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")
    for ln in lines:
        print(ln)


# --------------------------------------------------------------------------- #
# 场景 1：CNI ADD + IPAM
# --------------------------------------------------------------------------- #
def scenario_cni_add_ipam():
    ctx = build_cluster(num_nodes=1)
    api = ctx["api"]
    pod = make_pod("web", node_name="node-1")
    api.create(pod)

    ctx["kubelets"]["node-1"].sync_pod(pod)
    final = api.get("Pod", "default", "web")

    lines = [
        f"Pod IP: {final['status']['podIP']}",
        f"Gateway: {ctx['bridge'].ipams['node-1'].gateway()}",
        f"Phase: {final['status']['phase']}",
    ]
    _print("场景 1：CNI ADD + IPAM（单节点分配 Pod IP）", lines)
    return final


# --------------------------------------------------------------------------- #
# 场景 2：多节点 Pod 连通性
# --------------------------------------------------------------------------- #
def scenario_multi_node_connectivity():
    ctx = build_cluster(num_nodes=2)
    api = ctx["api"]

    pod_a = make_pod("app-a", node_name="node-1", labels={"app": "a"})
    pod_b = make_pod("app-b", node_name="node-2", labels={"app": "b"})
    api.create(pod_a)
    api.create(pod_b)

    ctx["kubelets"]["node-1"].sync_pod(pod_a)
    ctx["kubelets"]["node-2"].sync_pod(pod_b)

    a = api.get("Pod", "default", "app-a")
    b = api.get("Pod", "default", "app-b")
    reachable = ctx["routes"].reachable("node-1", b["status"]["podIP"])

    lines = [
        f"app-a on node-1: {a['status']['podIP']}",
        f"app-b on node-2: {b['status']['podIP']}",
        f"node-1 -> app-b reachable: {reachable}",
        f"next hop: {ctx['routes'].next_hop('node-1', b['status']['podIP'])}",
    ]
    _print("场景 2：多节点 Pod 连通性（host-gw 路由）", lines)
    return {"a": a, "b": b, "reachable": reachable}


# --------------------------------------------------------------------------- #
# 场景 3：NetworkPolicy
# --------------------------------------------------------------------------- #
def scenario_network_policy():
    ctx = build_cluster(num_nodes=1)
    api = ctx["api"]
    policies = ctx["policies"]

    web = make_pod("web", node_name="node-1", labels={"app": "web"})
    db = make_pod("db", node_name="node-1", labels={"app": "db"})
    api.create(web)
    api.create(db)
    ctx["kubelets"]["node-1"].sync_pod(web)
    ctx["kubelets"]["node-1"].sync_pod(db)

    # 默认拒绝 db 的所有入站，只允许来自 app=web 的流量访问 3306
    policies.add_policy(make_network_policy(
        "db-allow-web",
        pod_selector=pod_selector({"app": "db"}),
        ingress=[{
            "from": [pod_selector({"app": "web"})],
            "ports": [{"protocol": "TCP", "port": 3306}],
        }],
        policy_types=["Ingress"],
    ))

    allowed = policies.traffic_allowed(web, db, dst_port=3306)
    denied_port = policies.traffic_allowed(web, db, dst_port=8080)
    denied_src = policies.traffic_allowed(db, db, dst_port=3306)

    lines = [
        f"web -> db:3306 allowed: {allowed}",
        f"web -> db:8080 denied: {denied_port}",
        f"db -> db:3306 denied: {denied_src}",
    ]
    _print("场景 3：NetworkPolicy（默认拒绝 + 显式 allow ingress）", lines)
    return {"allowed": allowed, "denied_port": denied_port, "denied_src": denied_src}


# --------------------------------------------------------------------------- #
# 场景 4：CSI volume 生命周期
# --------------------------------------------------------------------------- #
def scenario_csi_volume_lifecycle():
    ctx = build_cluster(num_nodes=1)
    api = ctx["api"]
    ctrl = ctx["ctrl"]

    # 用户创建 PVC
    pvc = make_pvc("data", size_gi=5)
    api.create(pvc)

    # 创建使用 PVC 的 Pod
    pod = make_pod("app", node_name="node-1", volumes=[volume_mount("data", "/data")],
                   containers=[{"name": "main", "image": "busybox",
                                "volumeMounts": [container_mount("vol-data", "/data")]}])
    api.create(pod)
    ctx["kubelets"]["node-1"].sync_pod(pod)

    final_pod = api.get("Pod", "default", "app")
    final_pvc = api.get("PersistentVolumeClaim", "default", "data")
    final_pv = api.get("PersistentVolume", "", "pv-data")
    vol = ctx["store"].get_volume_by_name("data")
    attached = ctx["store"].is_attached_to(vol["volume_id"], "node-1")
    node_store = ctx["kubelets"]["node-1"].node_store

    lines = [
        f"PVC phase: {final_pvc['status']['phase']} bound_pv: {final_pvc['status']['bound_pv']}",
        f"PV phase: {final_pv['status']['phase']} handle: {final_pv['spec']['csi']['volumeHandle']}",
        f"Volume attached to node-1: {attached}",
        f"Node staged: {node_store.is_staged(vol['volume_id'])}",
        f"Node published to pod: {node_store.is_published_to_pod(vol['volume_id'], 'sandbox-node-1-app')}",
        f"Pod phase: {final_pod['status']['phase']}",
    ]
    _print("场景 4：CSI volume 生命周期（动态 provision → attach → stage → publish）", lines)

    # 删除 Pod，验证卸载
    ctx["kubelets"]["node-1"].delete_pod(final_pod)
    lines2 = [
        f"After delete: published: {node_store.is_published_to_pod(vol['volume_id'], 'sandbox-node-1-app')}",
        f"After delete: staged: {node_store.is_staged(vol['volume_id'])}",
        f"After delete: attached: {ctx['store'].is_attached_to(vol['volume_id'], 'node-1')}",
    ]
    _print("场景 4 续：删除 Pod 后逆序卸载", lines2)
    return {"provisioned": final_pv is not None, "attached": attached}


# --------------------------------------------------------------------------- #
# 场景 5：CSI snapshot 和 expand
# --------------------------------------------------------------------------- #
def scenario_csi_snapshot_expand():
    ctx = build_cluster(num_nodes=1)
    ctrl = ctx["ctrl"]
    store = ctx["store"]

    # 创建并扩展原 volume
    vol = ctrl.create_volume("db", size_gi=10)
    ctrl.create_snapshot(vol["volume_id"], "snap-db-v1")
    expanded = ctrl.controller_expand_volume(vol["volume_id"], 20)

    # 从 snapshot 恢复新 volume
    restored = ctrl.create_volume("db-restore", size_gi=10, source_snapshot="snap-db-v1")

    lines = [
        f"Original volume size: {vol['spec']['sizeGi']} Gi",
        f"Snapshot created: {store.get_snapshot('snap-db-v1') is not None}",
        f"Expanded volume size: {expanded['spec']['sizeGi']} Gi (controller_expanded={expanded['status']['controller_expanded']})",
        f"Restored volume size: {restored['spec']['sizeGi']} Gi source={restored['sourceSnapshot']}",
    ]
    _print("场景 5：CSI snapshot 与 expand", lines)
    return {"expanded": expanded["spec"]["sizeGi"] == 20, "restored": restored["sourceSnapshot"] == "snap-db-v1"}


# --------------------------------------------------------------------------- #
# 场景 6：端到端 Pod + 网络 + 存储
# --------------------------------------------------------------------------- #
def scenario_end_to_end():
    ctx = build_cluster(num_nodes=2)
    api = ctx["api"]

    pvc = make_pvc("shared", size_gi=2)
    api.create(pvc)

    pod = make_pod("ai-agent", node_name="node-1",
                   labels={"app": "agent"},
                   volumes=[volume_mount("shared", "/data")],
                   containers=[{"name": "main", "image": "agent:v1",
                                "volumeMounts": [container_mount("vol-shared", "/data")]}])
    api.create(pod)
    ctx["kubelets"]["node-1"].sync_pod(pod)

    final = api.get("Pod", "default", "ai-agent")
    final_pvc = api.get("PersistentVolumeClaim", "default", "shared")

    lines = [
        f"Pod IP: {final['status']['podIP']}",
        f"Pod phase: {final['status']['phase']}",
        f"PVC bound: {final_pvc['status']['phase']} -> {final_pvc['status']['bound_pv']}",
    ]
    _print("场景 6：端到端 Pod（网络 + 存储同时就绪）", lines)
    return {"pod_ip": final["status"]["podIP"], "bound": final_pvc["status"]["phase"] == "Bound"}


def run_demo():
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║   cni-csi-mini：纯 Python 从零实现的 Kubernetes CNI/CSI 教学模拟器   ║")
    print("║   容器网络 + 存储插件：IPAM / 路由 / NetworkPolicy / CSI 全生命周期   ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")
    scenario_cni_add_ipam()
    scenario_multi_node_connectivity()
    scenario_network_policy()
    scenario_csi_volume_lifecycle()
    scenario_csi_snapshot_expand()
    scenario_end_to_end()


if __name__ == "__main__":
    run_demo()

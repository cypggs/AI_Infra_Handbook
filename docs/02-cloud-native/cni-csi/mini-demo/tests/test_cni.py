"""CNI 测试：IPAM、bridge 插件、路由、NetworkPolicy、插件链。"""
import pytest

from cni_csi_mini import model
from cni_csi_mini.cni import (
    IPAM, BridgePlugin, PluginChain, RouteManager, NetworkPolicyManager,
    make_network_policy, pod_selector, allow_all_ingress, default_deny_ingress,
)


def test_ipam_allocates_sequential_ips():
    ipam = IPAM("10.244.1.0/24")
    ip1 = ipam.allocate("s1")
    ip2 = ipam.allocate("s2")
    assert ip1 == "10.244.1.2"
    assert ip2 == "10.244.1.3"


def test_ipam_release_recycles_ip():
    ipam = IPAM("10.244.1.0/24")
    ip = ipam.allocate("s1")
    ipam.release("s1")
    ip2 = ipam.allocate("s2")
    assert ip == ip2


def test_ipam_exhaustion():
    ipam = IPAM("10.244.99.0/30")  # 仅 10.244.99.1/.2 可用（.1 被网关占）
    ipam.allocate("s1")
    with pytest.raises(RuntimeError):
        ipam.allocate("s2")


def test_bridge_plugin_add_idempotent():
    plugin = BridgePlugin()
    node = model.make_node("node-1", cidr="10.244.1.0/24")
    pod = model.make_pod("p1")
    r1 = plugin.add(pod, "sb1", node)
    r2 = plugin.add(pod, "sb1", node)
    assert r1["podIP"] == r2["podIP"]


def test_bridge_plugin_del_releases_ip():
    plugin = BridgePlugin()
    node = model.make_node("node-1", cidr="10.244.1.0/24")
    pod = model.make_pod("p1")
    plugin.add(pod, "sb1", node)
    plugin.del_(pod, "sb1", node)
    assert not plugin.ipams["node-1"].is_allocated("10.244.1.2")


def test_same_node_connectivity():
    routes = RouteManager()
    node = model.make_node("node-1", cidr="10.244.1.0/24")
    routes.register_node("node-1", "192.168.1.11", "10.244.1.0/24")
    assert routes.reachable("node-1", "10.244.1.5")


def test_cross_node_routing():
    routes = RouteManager()
    routes.register_node("node-1", "192.168.1.11", "10.244.1.0/24")
    routes.register_node("node-2", "192.168.1.12", "10.244.2.0/24")
    assert routes.reachable("node-1", "10.244.2.5")
    assert routes.next_hop("node-1", "10.244.2.5") == "192.168.1.12"


def test_network_policy_default_allow_without_policies():
    mgr = NetworkPolicyManager()
    src = model.make_pod("a", labels={"app": "a"})
    dst = model.make_pod("b", labels={"app": "b"})
    assert mgr.traffic_allowed(src, dst, 80) is True


def test_network_policy_default_deny_ingress():
    mgr = NetworkPolicyManager()
    mgr.add_policy(make_network_policy(
        "deny-db",
        pod_selector=pod_selector({"app": "db"}),
        ingress=[default_deny_ingress()],
        policy_types=["Ingress"],
    ))
    src = model.make_pod("web", labels={"app": "web"})
    dst = model.make_pod("db", labels={"app": "db"})
    assert mgr.ingress_allowed(dst, src, 3306) is False


def test_network_policy_allow_specific_port():
    mgr = NetworkPolicyManager()
    mgr.add_policy(make_network_policy(
        "allow-web-to-db",
        pod_selector=pod_selector({"app": "db"}),
        ingress=[{
            "from": [pod_selector({"app": "web"})],
            "ports": [{"protocol": "TCP", "port": 3306}],
        }],
        policy_types=["Ingress"],
    ))
    web = model.make_pod("web", labels={"app": "web"})
    db = model.make_pod("db", labels={"app": "db"})
    assert mgr.traffic_allowed(web, db, 3306) is True
    assert mgr.traffic_allowed(web, db, 8080) is False


def test_network_policy_egress_allow():
    mgr = NetworkPolicyManager()
    mgr.add_policy(make_network_policy(
        "allow-web-egress",
        pod_selector=pod_selector({"app": "web"}),
        egress=[{
            "to": [pod_selector({"app": "db"})],
            "ports": [{"protocol": "TCP", "port": 3306}],
        }],
        policy_types=["Egress"],
    ))
    web = model.make_pod("web", labels={"app": "web"})
    db = model.make_pod("db", labels={"app": "db"})
    other = model.make_pod("other", labels={"app": "other"})
    assert mgr.egress_allowed(web, db, 3306) is True
    assert mgr.egress_allowed(web, other, 80) is False


def test_plugin_chain_order():
    class APlugin:
        def add(self, pod, sandbox_id, node):
            return {"plugin": "A"}
        def del_(self, pod, sandbox_id, node):
            pass

    class BPlugin:
        def add(self, pod, sandbox_id, node):
            return {"plugin": "B"}
        def del_(self, pod, sandbox_id, node):
            pass

    chain = PluginChain([APlugin(), BPlugin()])
    result = chain.add(model.make_pod("p"), "sb", model.make_node("node-1"))
    assert result["plugin"] == "B"

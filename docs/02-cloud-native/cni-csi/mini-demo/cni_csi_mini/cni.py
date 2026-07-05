"""CNI —— 容器网络接口的教学模拟。

对应真实组件：
  - CNIPlugin 接口 ≈ CNI 规范里的 ADD/CHECK/DEL
  - BridgePlugin ≈ bridge / host-local / flannel/host-gw 等插件
  - IPAM ≈ host-local / whereabouts 等地址管理
  - RouteManager ≈ Linux 路由表 + 节点间路由协议（Calico BGP / Flannel VXLAN）
  - NetworkPolicyManager ≈ kube-proxy + iptables/nftables / eBPF Cilium
  - PluginChain ≈ CNI conflist（链式调用多个插件）

所有网络状态都保存在内存 dict 里，没有真正的 netlink、veth、iptables。"""

import copy
import ipaddress
from abc import ABC, abstractmethod


# --------------------------------------------------------------------------- #
# 工具
# --------------------------------------------------------------------------- #
def _parse_cidr(cidr):
    return ipaddress.ip_network(cidr)


def _host_index(net, idx):
    """从网络里取第 idx 个可用主机地址（跳过网络地址和广播地址）。"""
    hosts = list(net.hosts())
    return str(hosts[idx]) if 0 <= idx < len(hosts) else None


def _cidr_prefix(cidr):
    return _parse_cidr(cidr).prefixlen


# --------------------------------------------------------------------------- #
# IPAM（host-local 简化版）
# --------------------------------------------------------------------------- #
class IPAM:
    """每个节点一个 IPAM 实例，从 node.spec.podCIDR 顺序分配，DEL 时回收。"""

    def __init__(self, cidr):
        self.net = _parse_cidr(cidr)
        self._hosts = list(self.net.hosts())
        # 保留 .1 给 cni0 / 网关
        self._allocated = {str(self._hosts[0]): "gateway"}
        self._sandbox_to_ip = {}

    def allocate(self, sandbox_id):
        if sandbox_id in self._sandbox_to_ip:
            return self._sandbox_to_ip[sandbox_id]
        for ip in self._hosts[1:]:
            sip = str(ip)
            if sip not in self._allocated:
                self._allocated[sip] = sandbox_id
                self._sandbox_to_ip[sandbox_id] = sip
                return sip
        raise RuntimeError("IPAM exhausted")

    def release(self, sandbox_id):
        ip = self._sandbox_to_ip.pop(sandbox_id, None)
        if ip is not None:
            self._allocated.pop(ip, None)

    def is_allocated(self, ip):
        return ip in self._allocated

    def gateway(self):
        return str(self._hosts[0])


# --------------------------------------------------------------------------- #
# 路由表
# --------------------------------------------------------------------------- #
class RouteManager:
    """维护每个节点的路由表：
      - 同节点 Pod 直接二层可达
      - 跨节点 Pod 通过目标节点 InternalIP 路由（模拟 host-gw / BGP 下一跳）
    """

    def __init__(self):
        # node_name -> { dest_cidr: next_hop }
        self._routes = {}
        # node_name -> InternalIP
        self._node_ips = {}
        # node_name -> own podCIDR
        self._own_cidr = {}

    def register_node(self, node_name, internal_ip, pod_cidr):
        self._node_ips[node_name] = internal_ip
        self._routes.setdefault(node_name, {})
        self._own_cidr[node_name] = pod_cidr
        # 为其他已注册节点添加到达本节点网段的路由
        for peer, peer_ip in self._node_ips.items():
            if peer == node_name:
                continue
            self._routes[peer][pod_cidr] = internal_ip
            self._routes[node_name][self._peer_cidr(peer)] = peer_ip

    def _peer_cidr(self, node_name):
        # 约定：node_name 形如 node-1，cidr 为 10.244.1.0/24
        idx = int(node_name.split("-")[-1])
        return f"10.244.{idx}.0/24"

    def reachable(self, src_node, dst_ip):
        """判断 src_node 上的 Pod 是否能到达 dst_ip。"""
        if not src_node:
            return False
        # 先检查本节点网段（直连）
        own = self._own_cidr.get(src_node)
        if own and ipaddress.ip_address(dst_ip) in ipaddress.ip_network(own):
            return True
        # 再查路由表
        routes = self._routes.get(src_node, {})
        for cidr, _ in routes.items():
            if ipaddress.ip_address(dst_ip) in ipaddress.ip_network(cidr):
                return True
        return False

    def next_hop(self, src_node, dst_ip):
        """返回 src_node 到 dst_ip 的下一跳 IP，None 表示直连/无路由。"""
        routes = self._routes.get(src_node, {})
        for cidr, nh in routes.items():
            if ipaddress.ip_address(dst_ip) in ipaddress.ip_network(cidr):
                return nh
        return None


# --------------------------------------------------------------------------- #
# NetworkPolicy
# --------------------------------------------------------------------------- #
class NetworkPolicyManager:
    """简化版 NetworkPolicy：
      - 默认无任何策略时全部放行（真实 K8s 行为）
      - 一旦某 Pod 被任一策略选中，则只放行被显式 allow 的流量
      - 支持 ingress 规则：from（podSelector/namespaceSelector）+ ports
      - 支持 egress 规则：to（podSelector/namespaceSelector）+ ports
      - 默认拒绝通过空规则列表 [] 实现
    """

    def __init__(self):
        self._policies = []

    def add_policy(self, policy):
        self._policies.append(copy.deepcopy(policy))

    def reset(self):
        self._policies = []

    def _matches_selector(self, labels, selector):
        """selector 是 {matchLabels: {k:v}} 或 {}（匹配所有）。"""
        if not selector:
            return True
        match = selector.get("matchLabels", {})
        return all(labels.get(k) == v for k, v in match.items())

    def _policy_selects_pod(self, policy, pod):
        return self._matches_selector(pod["metadata"].get("labels", {}),
                                      policy["spec"].get("podSelector", {}))

    def _matches_peer(self, peer, src_pod, dst_pod, direction):
        """匹配 NetworkPolicyPeer：podSelector / namespaceSelector。"""
        if "podSelector" in peer:
            if direction == "ingress":
                labels = src_pod["metadata"].get("labels", {})
            else:
                labels = dst_pod["metadata"].get("labels", {})
            if not self._matches_selector(labels, peer["podSelector"]):
                return False
        if "namespaceSelector" in peer:
            ns = src_pod["metadata"].get("namespace") if direction == "ingress" else dst_pod["metadata"].get("namespace")
            if not self._matches_selector({"name": ns}, peer["namespaceSelector"]):
                return False
        return True

    def ingress_allowed(self, dst_pod, src_pod, dst_port=None):
        """判断从 src_pod 到 dst_pod:dst_port 的入流量是否被允许。"""
        selecting = [p for p in self._policies if self._policy_selects_pod(p, dst_pod)]
        if not selecting:
            return True  # 无策略选中目标 → 默认放行
        for p in selecting:
            for rule in p["spec"].get("ingress", []):
                peers = rule.get("from", [{}])  # 空列表表示无 peer，即无允许规则
                if not peers:
                    continue
                for peer in peers:
                    if not self._matches_peer(peer, src_pod, dst_pod, "ingress"):
                        continue
                    ports = rule.get("ports", [])
                    if not ports or dst_port is None:
                        return True
                    if any(dst_port == pdef.get("port") for pdef in ports):
                        return True
        return False

    def egress_allowed(self, src_pod, dst_pod, dst_port=None):
        """判断从 src_pod 到 dst_pod:dst_port 的出流量是否被允许。"""
        selecting = [p for p in self._policies if self._policy_selects_pod(p, src_pod)]
        if not selecting:
            return True
        for p in selecting:
            for rule in p["spec"].get("egress", []):
                peers = rule.get("to", [{}])
                if not peers:
                    continue
                for peer in peers:
                    if not self._matches_peer(peer, src_pod, dst_pod, "egress"):
                        continue
                    ports = rule.get("ports", [])
                    if not ports or dst_port is None:
                        return True
                    if any(dst_port == pdef.get("port") for pdef in ports):
                        return True
        return False

    def traffic_allowed(self, src_pod, dst_pod, dst_port=None):
        return (self.egress_allowed(src_pod, dst_pod, dst_port) and
                self.ingress_allowed(dst_pod, src_pod, dst_port))


# --------------------------------------------------------------------------- #
# CNI 插件接口与实现
# --------------------------------------------------------------------------- #
class CNIPlugin(ABC):
    @abstractmethod
    def add(self, pod, sandbox_id, node, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def del_(self, pod, sandbox_id, node):
        raise NotImplementedError


class BridgePlugin(CNIPlugin):
    """bridge 插件教学版：
      - 每个节点一个 Linux bridge（cni0）
      - 每个 Pod 一对 veth：一端在容器 ns，一端在主机并接入 bridge
      - IPAM 分配 Pod IP，路由表写入默认路由
    """

    def __init__(self, ipams=None, routes=None):
        # node_name -> IPAM
        self.ipams = ipams or {}
        # node_name -> {sandbox_id: result}
        self.attachments = {}
        self.routes = routes

    def add(self, pod, sandbox_id, node):
        node_name = node["metadata"]["name"]
        ipam = self.ipams.setdefault(node_name,
                                     IPAM(node["spec"]["podCIDR"]))
        if sandbox_id in ipam._sandbox_to_ip:
            # 幂等：返回已分配结果
            return copy.deepcopy(self.attachments[node_name][sandbox_id])

        pod_ip = ipam.allocate(sandbox_id)
        gateway = ipam.gateway()
        cidr = node["spec"]["podCIDR"]
        result = {
            "sandbox_id": sandbox_id,
            "podIP": pod_ip,
            "gateway": gateway,
            "routes": [
                {"dst": "0.0.0.0/0", "gw": gateway},
                {"dst": cidr},
            ],
            "dns": {},
            "interfaces": [
                {"name": "eth0", "sandbox": sandbox_id},
                {"name": "veth0", "host": True},
            ],
        }
        self.attachments.setdefault(node_name, {})[sandbox_id] = result
        return result

    def del_(self, pod, sandbox_id, node):
        node_name = node["metadata"]["name"]
        ipam = self.ipams.get(node_name)
        if ipam is not None:
            ipam.release(sandbox_id)
        self.attachments.get(node_name, {}).pop(sandbox_id, None)


class PluginChain(CNIPlugin):
    """按顺序调用多个 CNI 插件，只有最后一个插件返回的 IP 写入结果。"""

    def __init__(self, plugins):
        self.plugins = plugins

    def add(self, pod, sandbox_id, node):
        result = None
        for p in self.plugins:
            r = p.add(pod, sandbox_id, node)
            if r is not None:
                result = r
        return result or {}

    def del_(self, pod, sandbox_id, node):
        for p in reversed(self.plugins):
            p.del_(pod, sandbox_id, node)


# --------------------------------------------------------------------------- #
# 便捷构造
# --------------------------------------------------------------------------- #
def make_network_policy(name, namespace="default", *, pod_selector=None,
                        ingress=None, egress=None, policy_types=None):
    """构造 NetworkPolicy 资源（简化版）。"""
    return {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "metadata": {"name": name, "namespace": namespace},
        "spec": {
            "podSelector": pod_selector or {},
            "policyTypes": policy_types or [],
            "ingress": ingress or [],
            "egress": egress or [],
        },
    }


def allow_all_ingress():
    return {"from": [{}]}


def allow_all_egress():
    return {"to": [{}]}


def default_deny_ingress():
    return {"from": []}


def default_deny_egress():
    return {"to": []}


def pod_selector(labels):
    return {"matchLabels": labels}

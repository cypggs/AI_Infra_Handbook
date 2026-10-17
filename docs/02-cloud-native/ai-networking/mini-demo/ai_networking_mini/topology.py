"""拓扑生成与路由：fat-tree、leaf-spine、rail-optimized 的跳数与二分带宽计算。

对应真实世界：
- ``build_leaf_spine``  → 通用两层 Clos（任意收敛比），RoCE/以太网集群最常见的 fabric
- ``build_fat_tree``    → 经典 k-ary fat-tree（三层 Clos），无收敛（full bisection）
- ``build_rail_optimized`` → Meta "rail-only"/阿里 HPN 的 rail 思想：每块网卡一条 rail，
  跨 rail 流量必须绕行 scale-up 域（节点内部 NVLink/PCIe），换取去掉 spine 层

所有图用邻接表表示，跳数用 BFS 计算（与闭式公式互相印证），全部是确定性逻辑。
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# 图模型
# ---------------------------------------------------------------------------

@dataclass
class Topology:
    """无向加权图：节点 + 邻接表 + 链路带宽（bps）。"""

    name: str
    nodes: set = field(default_factory=set)
    adj: dict = field(default_factory=dict)          # node -> set(neighbor)
    bw: dict = field(default_factory=dict)           # frozenset({a,b}) -> bps
    kind: dict = field(default_factory=dict)         # node -> "host"/"leaf"/"spine"/"core"/"rail"

    def add_node(self, node: str, kind: str = "switch") -> None:
        self.nodes.add(node)
        self.adj.setdefault(node, set())
        self.kind[node] = kind

    def add_link(self, a: str, b: str, bw: float) -> None:
        if a not in self.nodes or b not in self.nodes:
            raise KeyError(f"unknown node: {a!r} or {b!r}")
        self.adj[a].add(b)
        self.adj[b].add(a)
        self.bw[frozenset((a, b))] = bw

    def link_bw(self, a: str, b: str) -> float:
        return self.bw[frozenset((a, b))]

    def hosts(self) -> list:
        return sorted(n for n in self.nodes if self.kind.get(n) == "host")

    def switches(self) -> list:
        return sorted(n for n in self.nodes if self.kind.get(n) != "host")

    def hop_count(self, a: str, b: str) -> Optional[int]:
        """BFS 最短跳数；不可达返回 None。"""
        if a == b:
            return 0
        seen = {a}
        q = deque([(a, 0)])
        while q:
            node, d = q.popleft()
            for nb in self.adj[node]:
                if nb == b:
                    return d + 1
                if nb not in seen:
                    seen.add(nb)
                    q.append((nb, d + 1))
        return None

    def hop_histogram(self, hosts: Optional[list] = None) -> dict:
        """统计主机两两之间（含网卡端口语义）的跳数分布 {hops: count}。"""
        hs = hosts if hosts is not None else self.hosts()
        hist: dict = {}
        for i in range(len(hs)):
            for j in range(i + 1, len(hs)):
                h = self.hop_count(hs[i], hs[j])
                hist[h] = hist.get(h, 0) + 1
        return dict(sorted(hist.items(), key=lambda kv: (kv[0] is None, kv[0])))


@dataclass
class FabricInfo:
    """一个 fabric 的汇总指标（用于对比表）。"""

    n_hosts: int
    n_switches: int
    n_links: int
    bisection_bw: float          # bps，对半切分后单侧可承载的最小带宽
    oversubscription: float      # >1 表示有收敛
    host_ports: int              # 主机侧总端口数 = 主机数 × 每主机网卡数
    notes: str = ""


# ---------------------------------------------------------------------------
# Leaf-Spine（两层 Clos，任意收敛比）
# ---------------------------------------------------------------------------

def build_leaf_spine(
    n_hosts: int,
    nics_per_host: int = 8,
    downlinks_per_leaf: int = 16,
    uplinks_per_leaf: int = 16,
    bw: float = 400e9,
    name: str = "leaf-spine",
) -> tuple:
    """构建两层 leaf-spine。

    主机 NIC 均匀打到 leaf 上；每个 leaf 用 uplinks_per_leaf 条上行连到
    uplinks_per_leaf 个 spine（一 spine 一上行，经典设计）。
    收敛比 = downlinks / uplinks。
    """
    if n_hosts < 2:
        raise ValueError("n_hosts must be >= 2")
    if downlinks_per_leaf < 1 or uplinks_per_leaf < 1:
        raise ValueError("ports must be positive")

    total_ports = n_hosts * nics_per_host
    n_leaf = math.ceil(total_ports / downlinks_per_leaf)
    n_spine = uplinks_per_leaf  # 一 spine 一上行

    topo = Topology(name)
    for h in range(n_hosts):
        topo.add_node(f"host-{h}", "host")
    for l in range(n_leaf):
        topo.add_node(f"leaf-{l}", "leaf")
    for s in range(n_spine):
        topo.add_node(f"spine-{s}", "spine")

    # 主机 NIC -> leaf（均匀打散）
    for p in range(total_ports):
        h, nic = divmod(p, nics_per_host)
        leaf = p // downlinks_per_leaf
        topo.add_link(f"host-{h}", f"leaf-{leaf}", bw)
    # leaf -> spine
    for l in range(n_leaf):
        for s in range(n_spine):
            topo.add_link(f"leaf-{l}", f"spine-{s}", bw)

    host_side = total_ports * bw
    uplink_side = n_leaf * uplinks_per_leaf * bw
    bisection = min(host_side, uplink_side)
    info = FabricInfo(
        n_hosts=n_hosts,
        n_switches=n_leaf + n_spine,
        n_links=len(topo.bw),
        bisection_bw=bisection,
        oversubscription=downlinks_per_leaf / uplinks_per_leaf,
        host_ports=total_ports,
        notes=f"{n_leaf} leaf × {downlinks_per_leaf} 下行 / {uplinks_per_leaf} 上行",
    )
    return topo, info


# ---------------------------------------------------------------------------
# k-ary fat-tree（三层 Clos，无收敛）
# ---------------------------------------------------------------------------

def fat_tree_sizes(k: int) -> dict:
    """经典 k-ary fat-tree（k 为偶数）的规模闭式公式。

    每个 pod：k/2 个 ToR + k/2 个汇聚；ToR 下半接 k/2 台主机、上半接 k/2 个汇聚；
    汇聚上半接核心；核心 (k/2)^2 台。
    """
    if k < 2 or k % 2 != 0:
        raise ValueError("k must be an even integer >= 2")
    half = k // 2
    return {
        "k": k,
        "hosts_per_pod": half * half,
        "n_hosts": k * half * half,          # k^3 / 4
        "tors_per_pod": half,
        "aggs_per_pod": half,
        "n_core": half * half,
        "n_switches": k * k + (half * half),  # 2k^2/2 ... = k^2 + k^2/4
    }


def build_fat_tree(k: int, bw: float = 400e9) -> tuple:
    """构建经典 k-ary fat-tree（三层 Clos，full bisection）。"""
    s = fat_tree_sizes(k)
    half = k // 2
    topo = Topology(name=f"fat-tree-k{k}")

    for h in range(s["n_hosts"]):
        topo.add_node(f"host-{h}", "host")

    def pod_of(host: int) -> int:
        return host // s["hosts_per_pod"]

    def tor_of(host: int) -> int:
        # 全局 ToR 编号：pod 内第几个 ToR（每台 ToR 下挂 half 台主机）
        within = host % s["hosts_per_pod"]
        return pod_of(host) * half + within // half

    # 交换机用全局编号命名，避免 "tor-p-t" 与编号函数不一致
    for sw in range(k * half):
        topo.add_node(f"tor-{sw}", "leaf")
        topo.add_node(f"agg-{sw}", "spine")
    for c in range(s["n_core"]):
        topo.add_node(f"core-{c}", "core")

    # host -> tor
    for h in range(s["n_hosts"]):
        topo.add_link(f"host-{h}", f"tor-{tor_of(h)}", bw)
    # tor -> agg（pod 内 full-mesh 的上下半）
    for p in range(k):
        for t in range(half):
            for a in range(half):
                topo.add_link(f"tor-{p * half + t}", f"agg-{p * half + a}", bw)
    # agg -> core：agg (p,a) 的第 j 条上行 -> core a*half + j，与经典接法一致
    for p in range(k):
        for a in range(half):
            for j in range(half):
                topo.add_link(f"agg-{p * half + a}", f"core-{a * half + j}", bw)

    info = FabricInfo(
        n_hosts=s["n_hosts"],
        n_switches=s["n_switches"],
        n_links=len(topo.bw),
        bisection_bw=s["n_hosts"] * bw / 2,   # full bisection：对半切带宽足够
        oversubscription=1.0,
        host_ports=s["n_hosts"],
        notes=f"k={k} 三层 Clos，跳数 2/4/6",
    )
    return topo, info


def fat_tree_hop_expectation(k: int) -> dict:
    """k-ary fat-tree 主机两两跳数的闭式分布（与 BFS 结果互相印证）。

    返回 {2: 同 ToR, 4: 同 pod 异 ToR, 6: 跨 pod} 的计数。
    """
    s = fat_tree_sizes(k)
    half = k // 2
    hosts = s["n_hosts"]
    hpp = s["hosts_per_pod"]
    same_tor = hosts // 2 * (half - 1)               # 每台 ToR 下 half 台主机
    same_pod_diff_tor = k * (hpp * (hpp - half) // 2)  # pod 内跨 ToR
    cross_pod = hosts * (hosts - 1) // 2 - same_tor - same_pod_diff_tor
    return {2: same_tor, 4: same_pod_diff_tor, 6: cross_pod}


# ---------------------------------------------------------------------------
# Rail-optimized / rail-only
# ---------------------------------------------------------------------------

def build_rail_optimized(n_hosts: int, nics_per_host: int = 8, bw: float = 400e9) -> tuple:
    """构建 rail-optimized 拓扑：第 r 块网卡接入第 r 条 rail（一个 rail 交换机）。

    同 rail 任意两主机 2 跳；跨 rail 在 fabric 内不可达，必须绕行 scale-up 域
    （节点内部 NVLink/PCIe）——这正是 rail 设计的核心取舍。
    """
    if n_hosts < 2 or nics_per_host < 1:
        raise ValueError("invalid scale")
    topo = Topology(name=f"rail-{nics_per_host}")
    for h in range(n_hosts):
        topo.add_node(f"host-{h}", "host")
    for r in range(nics_per_host):
        topo.add_node(f"rail-{r}", "rail")
    for h in range(n_hosts):
        for r in range(nics_per_host):
            topo.add_link(f"host-{h}", f"rail-{r}", bw)

    info = FabricInfo(
        n_hosts=n_hosts,
        n_switches=nics_per_host,
        n_links=len(topo.bw),
        bisection_bw=n_hosts * nics_per_host * bw / 2,
        oversubscription=1.0,
        host_ports=n_hosts * nics_per_host,
        notes="每 rail 单交换机；跨 rail 必须经 scale-up 域绕行",
    )
    return topo, info


def cross_rail_hops() -> int:
    """跨 rail 通信的绕行跳数：NIC_i -> rail_i -> 节点内部 -> NIC_j -> rail_j。

    fabric 内 4 跳（出、入各 2），另有 scale-up 域内部转发开销不计入 fabric 跳数。
    """
    return 4


def compare_switch_count(n_hosts: int, nics_per_host: int = 8,
                         downlinks_per_leaf: int = 16,
                         uplinks_per_leaf: int = 16) -> dict:
    """对比同等规模下 fat-tree 式 leaf-spine 与 rail-only 的交换机数量。

    rail-only：每条 rail 一台 leaf（只接 n_hosts 个端口），没有 spine 层。
    """
    total_ports = n_hosts * nics_per_host
    n_leaf = math.ceil(total_ports / downlinks_per_leaf)
    n_spine = uplinks_per_leaf
    rail_leaf = nics_per_host  # 每条 rail 一台
    return {
        "leaf_spine_switches": n_leaf + n_spine,
        "leaf_spine_leaf": n_leaf,
        "leaf_spine_spine": n_spine,
        "rail_only_switches": rail_leaf,
        "saved": (n_leaf + n_spine) - rail_leaf,
        "saved_ratio": ((n_leaf + n_spine) - rail_leaf) / (n_leaf + n_spine),
        "assumption": "rail-only 每条 rail 单台 leaf，无 spine；leaf-spine 有 spine 层",
    }

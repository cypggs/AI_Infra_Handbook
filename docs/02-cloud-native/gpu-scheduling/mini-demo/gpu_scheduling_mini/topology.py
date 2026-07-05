"""Topology —— GPU 拓扑感知调度。

对应真实组件：
  - 节点上的 NUMA、PCIe Switch、NVSwitch 拓扑信息
  - kube-scheduler 的 Topology Aware Scheduling / GPU 插件中的打分逻辑

本模块实现一个最小可复现的拓扑打分器：对请求 N 张 GPU 的 Pod，
在节点可用 GPU 中选出拓扑亲和性最好的子集。
"""
import itertools

from . import model


class Topology:
    """描述一个节点上的 GPU 拓扑。"""

    def __init__(self, numa_nodes=None, pcie_switches=None, nvswitch_groups=None):
        """
        每组都是 GPU 索引的 list/set。
        示例（单节点 8-GPU，2 NUMA，4 PCIe switch，8 NVSwitch domain）：
            Topology(
                numa_nodes=[[0,1,2,3], [4,5,6,7]],
                pcie_switches=[[0,1], [2,3], [4,5], [6,7]],
                nvswitch_groups=[[0,1,2,3,4,5,6,7]],
            )
        """
        self.numa_nodes = [set(g) for g in (numa_nodes or [])]
        self.pcie_switches = [set(g) for g in (pcie_switches or [])]
        self.nvswitch_groups = [set(g) for g in (nvswitch_groups or [])]

    @staticmethod
    def _same_group(indices, groups):
        return any(indices <= g for g in groups)


class TopologyScorer:
    """对节点上可用的整卡 GPU 子集进行拓扑亲和性打分。"""

    SCORE_SAME_NUMA = 100
    SCORE_SAME_PCIE = 80
    SCORE_SAME_NVSWITCH = 60
    SCORE_OTHERWISE = 30

    def __init__(self, topology):
        self.topology = topology

    def score_indices(self, indices):
        """对一组 GPU 索引打分（0-100，越高越好）。"""
        s = set(indices)
        if len(s) <= 1:
            return self.SCORE_SAME_NUMA
        if Topology._same_group(s, self.topology.numa_nodes):
            return self.SCORE_SAME_NUMA
        if Topology._same_group(s, self.topology.pcie_switches):
            return self.SCORE_SAME_PCIE
        if Topology._same_group(s, self.topology.nvswitch_groups):
            return self.SCORE_SAME_NVSWITCH
        return self.SCORE_OTHERWISE

    def best_indices(self, node, count):
        """返回节点上分配 count 张整卡 GPU 的最高拓扑得分与推荐索引。

        返回 (score, indices)；资源不足返回 (0, [])。
        """
        available = [
            d.index for d in node["status"]["devices"]
            if d.mig_profile is None and not d.allocated and d.health == "Healthy"
        ]
        if len(available) < count:
            return 0, []

        best_score = -1
        best_indices = []
        # 组合数通常很小（8 选 4 为 70），直接枚举
        for combo in itertools.combinations(sorted(available), count):
            score = self.score_indices(combo)
            if score > best_score:
                best_score = score
                best_indices = list(combo)
        return best_score, best_indices

    def score(self, node, count):
        """Scheduler Framework Score 接口：返回 0-100 的分数。"""
        score, _ = self.best_indices(node, count)
        return score

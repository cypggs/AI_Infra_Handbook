"""topology.py 测试。"""
import pytest

from gpu_scheduling_mini.topology import Topology, TopologyScorer
from gpu_scheduling_mini import model


def _8gpu_topology():
    return Topology(
        numa_nodes=[[0, 1, 2, 3], [4, 5, 6, 7]],
        pcie_switches=[[0, 1], [2, 3], [4, 5], [6, 7]],
        nvswitch_groups=[list(range(8))],
    )


def test_score_same_numa():
    topo = _8gpu_topology()
    scorer = TopologyScorer(topo)
    assert scorer.score_indices([0, 1, 2, 3]) == TopologyScorer.SCORE_SAME_NUMA


def test_score_same_pcie():
    topo = Topology(
        numa_nodes=[[0, 2], [1, 3]],
        pcie_switches=[[0, 1], [2, 3]],
    )
    scorer = TopologyScorer(topo)
    # 0 与 1 在同一 PCIe switch 但不在同一 NUMA
    assert scorer.score_indices([0, 1]) == TopologyScorer.SCORE_SAME_PCIE
    # 0 与 2 在同一 NUMA
    assert scorer.score_indices([0, 2]) == TopologyScorer.SCORE_SAME_NUMA


def test_score_same_nvswitch():
    topo = _8gpu_topology()
    scorer = TopologyScorer(topo)
    assert scorer.score_indices([0, 4]) == TopologyScorer.SCORE_SAME_NVSWITCH


def test_score_otherwise():
    topo = _8gpu_topology()
    scorer = TopologyScorer(topo)
    # 所有 GPU 都在同一个 NVSwitch group，因此不会触发 OTHERWISE
    topo2 = Topology(numa_nodes=[[0, 1], [2, 3]])
    scorer2 = TopologyScorer(topo2)
    assert scorer2.score_indices([0, 3]) == TopologyScorer.SCORE_OTHERWISE


def test_best_indices_prefers_same_numa():
    topo = _8gpu_topology()
    node = model.make_node("n", gpu_count=8, topology=topo)
    scorer = TopologyScorer(topo)
    score, indices = scorer.best_indices(node, 4)
    assert score == TopologyScorer.SCORE_SAME_NUMA
    assert set(indices) in ({0, 1, 2, 3}, {4, 5, 6, 7})


def test_best_indices_not_enough_gpus():
    topo = _8gpu_topology()
    node = model.make_node("n", gpu_count=1, topology=topo)
    scorer = TopologyScorer(topo)
    score, indices = scorer.best_indices(node, 4)
    assert score == 0
    assert indices == []

"""topology 模块测试：图构建、BFS 跳数、二分带宽、rail 对比。"""

import pytest

from ai_networking_mini import topology


class TestTopologyGraph:
    def test_hop_count_self_and_unreachable(self):
        topo = topology.Topology("t")
        topo.add_node("a", "host")
        topo.add_node("b", "host")
        assert topo.hop_count("a", "a") == 0
        assert topo.hop_count("a", "b") is None
        with pytest.raises(KeyError):
            topo.add_link("a", "ghost", 1e9)


class TestLeafSpine:
    def test_minimal_nonblocking(self):
        _, info = topology.build_leaf_spine(
            n_hosts=16, nics_per_host=8,
            downlinks_per_leaf=16, uplinks_per_leaf=16)
        assert info.oversubscription == 1.0
        # 128 个端口 / 16 下行 = 8 leaf；16 spine
        assert info.n_switches == 24

    def test_nonblocking_bisection_equals_host_side(self):
        bw = 400e9
        _, info = topology.build_leaf_spine(
            n_hosts=16, nics_per_host=8, bw=bw,
            downlinks_per_leaf=16, uplinks_per_leaf=16)
        assert info.bisection_bw == 16 * 8 * bw

    def test_congested_bisection_limited_by_uplinks(self):
        bw = 400e9
        _, info = topology.build_leaf_spine(
            n_hosts=32, nics_per_host=8, bw=bw,
            downlinks_per_leaf=16, uplinks_per_leaf=8)
        n_leaf = (32 * 8) // 16
        assert info.bisection_bw == n_leaf * 8 * bw


class TestFatTree:
    def test_sizes_closed_form(self):
        s = topology.fat_tree_sizes(k=4)
        assert s["n_hosts"] == 16          # 4^3/4
        assert s["hosts_per_pod"] == 4
        assert s["n_core"] == 4
        s8 = topology.fat_tree_sizes(k=8)
        assert s8["n_hosts"] == 128
        assert s8["n_core"] == 16
        with pytest.raises(ValueError):
            topology.fat_tree_sizes(k=5)

    def test_full_bisection(self):
        _, info = topology.build_fat_tree(k=8, bw=400e9)
        assert info.oversubscription == 1.0
        assert info.bisection_bw == 128 * 400e9 / 2

    def test_hop_distribution_matches_bfs(self):
        topo, _ = topology.build_fat_tree(k=4)
        hist_bfs = topo.hop_histogram()
        hist_closed = topology.fat_tree_hop_expectation(4)
        assert hist_bfs == hist_closed
        # k=4: 同 ToR 2 跳 8 对；同 pod 跨 ToR 4 跳 16 对；跨 pod 6 跳 96 对
        assert hist_bfs[2] == 8
        assert hist_bfs[4] == 16
        assert hist_bfs[6] == 96

    def test_hop_closed_form_k8(self):
        topo, _ = topology.build_fat_tree(k=8)
        assert topo.hop_histogram() == topology.fat_tree_hop_expectation(8)


class TestRailOptimized:
    def test_same_rail_two_hops(self):
        topo, info = topology.build_rail_optimized(n_hosts=8, nics_per_host=8)
        assert topo.hop_count("host-0", "host-7") == 2
        assert info.n_switches == 8
        assert info.n_links == 64

    def test_cross_rail_detour(self):
        # 跨 rail 必须绕行 scale-up 域：fabric 内 4 跳（出、入各 2）
        assert topology.cross_rail_hops() == 4

    def test_switch_savings(self):
        cmp_ = topology.compare_switch_count(64, 8)
        # leaf-spine: 512/16=32 leaf + 16 spine = 48；rail: 8
        assert cmp_["leaf_spine_switches"] == 48
        assert cmp_["rail_only_switches"] == 8
        assert cmp_["saved"] == 40
        assert 0 < cmp_["saved_ratio"] < 1

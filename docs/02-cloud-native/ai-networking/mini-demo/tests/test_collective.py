"""collective 模块测试：ring/tree/all-to-all 闭式模型与对比。"""

import pytest

from ai_networking_mini import collective


class TestRingAllreduce:
    def test_steps_and_bytes(self):
        r = collective.ring_allreduce(8, 1.0, 1e9, 0)
        assert r["steps"] == 14
        assert r["bytes_per_rank"] == pytest.approx(2 * 7 / 8 * 1.0)
        r2 = collective.ring_allreduce(2, 1.0, 1e9, 0)
        assert r2["steps"] == 2
        with pytest.raises(ValueError):
            collective.ring_allreduce(1, 1.0, 1e9, 0)

    def test_time_split(self):
        r = collective.ring_allreduce(4, 100.0, 1e9, 1e-6)
        assert r["time_s"] == pytest.approx(
            r["latency_part_s"] + r["bandwidth_part_s"])


class TestTreeAllreduce:
    def test_steps_log(self):
        assert collective.tree_allreduce(8, 1.0, 1e9, 0)["steps"] == 6
        assert collective.tree_allreduce(16, 1.0, 1e9, 0)["steps"] == 8
        # 非 2 幂：向上取整
        assert collective.tree_allreduce(5, 1.0, 1e9, 0)["steps"] == 6

    def test_tree_sends_more_bytes_for_large_n(self):
        """n 较大时 tree 每 rank 字节数 log2(n)/2*M > ring 2(n-1)/n*M。"""
        msg = 1e6
        n = 16
        r = collective.ring_allreduce(n, msg, 1e9, 0)
        t = collective.tree_allreduce(n, msg, 1e9, 0)
        assert t["bytes_per_rank"] == pytest.approx(2 * msg)  # log2(16)/2 * M
        assert r["bytes_per_rank"] == pytest.approx(2 * 15 / 16 * msg)
        assert t["bytes_per_rank"] > r["bytes_per_rank"]


class TestAllToAll:
    def test_bytes_and_time(self):
        r = collective.alltoall(8, 100.0, 1e9, 2e-6)
        assert r["bytes_per_rank"] == pytest.approx(7 / 8 * 100.0)
        assert r["steps"] == 1
        assert r["time_s"] == pytest.approx(2e-6 + 7 / 8 * 100.0 * 8 / 1e9)


class TestCompare:
    def test_small_message_tree_wins(self):
        r = collective.compare_allreduce(128, 4 * 1024,
                                         "InfiniBand NDR 400G")
        assert r["winner"] == "tree"

    def test_large_message_ring_wins(self):
        r = collective.compare_allreduce(128, 4 * 1024 ** 3,
                                         "InfiniBand NDR 400G")
        assert r["winner"] == "ring"

    def test_compare_fabrics_sorted(self):
        rows = collective.compare_fabrics(64, 1e9, "ring")
        times = [r["time_s"] for r in rows]
        assert times == sorted(times)
        # NVLink5 必须最快
        assert rows[0]["fabric"].startswith("NVLink5")
        assert rows[-1]["fabric"].startswith("以太网 100G")


class TestAmdahl:
    def test_speedup_formula(self):
        r = collective.step_speedup_from_faster_network(1.0, 0.4, 0.1)
        assert r["old_step_s"] == pytest.approx(1.4)
        assert r["new_step_s"] == pytest.approx(1.1)
        assert r["speedup"] == pytest.approx(1.4 / 1.1)
        assert r["comm_fraction_before"] == pytest.approx(0.4 / 1.4)


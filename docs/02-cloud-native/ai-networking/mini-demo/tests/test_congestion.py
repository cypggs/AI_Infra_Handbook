"""congestion 模块测试：incast、ECN、DCQCN、PFC 死锁。"""

import pytest

from ai_networking_mini import congestion


class TestDelays:
    def test_serialization(self):
        # 4MiB over 400Gbps = 4*8*1024^2/400e9 ≈ 83.9µs
        d = congestion.serialization_delay(4 * 1024 ** 2, 400e9)
        assert d == pytest.approx(4 * 8 * 1024 ** 2 / 400e9)

    def test_incast_scales_linearly(self):
        # 单 sender 无排队
        assert congestion.incast_queue_peak(1, 1000) == 0.0
        t1 = congestion.incast_completion_time(8, 4096, 400e9, 0)
        t2 = congestion.incast_completion_time(16, 4096, 400e9, 0)
        assert t2 == pytest.approx(2 * t1)
        assert congestion.incast_queue_peak(16, 4096) == 15 * 4096


class TestECN:
    def test_piecewise_linear_mark(self):
        assert congestion.ecn_mark_probability(100, 1000, 2000) == 0.0
        assert congestion.ecn_mark_probability(5000, 1000, 2000) == 1.0
        assert congestion.ecn_mark_probability(1500, 1000, 2000) == \
            pytest.approx(0.5)
        # pmax 缩放
        assert congestion.ecn_mark_probability(1500, 1000, 2000, pmax=0.5) == \
            pytest.approx(0.25)
        with pytest.raises(ValueError):
            congestion.ecn_mark_probability(100, 2000, 1000)


class TestDCQCN:
    LINE = 400e9

    def test_persistent_cnp_decreases_rate(self):
        sim = congestion.dcqcn_simulate(16, [True] * 16, self.LINE, self.LINE)
        rates = sim["rates"]
        assert all(rates[i + 1] < rates[i] for i in range(16))
        # 16 步后应有明显下降
        assert rates[16] < 0.9 * self.LINE

    def test_persistent_cnp_alpha_converges(self):
        sim = congestion.dcqcn_simulate(64, [True] * 64, self.LINE, self.LINE)
        # alpha 平滑收敛（g=1/256 的几何收敛）
        assert sim["alphas"][-1] == pytest.approx(1.0 - (1 - 1 / 256) ** 64,
                                                  rel=1e-3)

    def test_idle_recovers_rate(self):
        sim = congestion.dcqcn_simulate(48, [True] * 16 + [False] * 32,
                                        self.LINE, self.LINE)
        rates = sim["rates"]
        assert rates[48] > rates[16]
        assert max(rates) <= self.LINE


class TestPFCDeadlock:
    def test_classic_deadlock_detected(self):
        deps = congestion.classic_pfc_deadlock()
        found, cycle = congestion.detect_deadlock(deps)
        assert found
        assert len(cycle) >= 4
        assert cycle[0] == cycle[-1]  # 首尾成环

    def test_dag_no_deadlock(self):
        deps = congestion.deadlock_free_updown()
        found, cycle = congestion.detect_deadlock(deps)
        assert not found
        assert cycle == []

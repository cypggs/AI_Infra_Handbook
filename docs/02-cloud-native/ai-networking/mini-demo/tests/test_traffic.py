"""traffic 模块测试：流量矩阵、闭式公式、热点因子。"""

import numpy as np
import pytest

from ai_networking_mini import traffic


class TestMatrices:
    def test_ring_edges_cycle(self):
        assert traffic.ring_edges(4) == [(0, 1), (1, 2), (2, 3), (3, 0)]
        with pytest.raises(ValueError):
            traffic.ring_edges(1)

    def test_uniform_alltoall_zero_diagonal(self):
        m = traffic.uniform_alltoall_matrix(8, 10.0)
        assert np.all(np.diag(m) == 0)
        assert m.sum() == 8 * 7 * 10.0

    def test_skewed_alltoall_hot_rank(self):
        m = traffic.skewed_alltoall_matrix(4, 100.0, hot_rank=2, skew=3.0)
        assert m[0, 2] == 400.0
        assert m[0, 1] == 100.0
        assert m[2, 0] == 100.0

    def test_pp_pipeline_symmetric_bidir(self):
        m = traffic.pp_pipeline_matrix(4, 100.0, 2)
        # 边界 0<->1,1<->2,2<->3：前向反向各 2 个 microbatch
        assert m[0, 1] == m[1, 0] == 200.0
        assert m[0, 2] == 0.0
        # 端点 stage 只与一个邻居通信，中间 stage 与两个
        assert m.sum(axis=1)[0] == 200.0
        assert m.sum(axis=1)[1] == 400.0


class TestClosedForm:
    def test_allreduce_bytes(self):
        assert traffic.allreduce_send_bytes(100.0, 2) == 100.0
        # n→∞ 时趋近 2M
        assert traffic.allreduce_send_bytes(1000.0, 1001) == pytest.approx(
            2.0 * 1000.0 * 1000 / 1001)
        # 单 rank 无通信
        assert traffic.allreduce_send_bytes(100.0, 1) == 0.0

    def test_alltoall_bytes(self):
        assert traffic.alltoall_send_bytes(100.0, 4) == 75.0


class TestStats:
    def test_gather_matrix_incast(self):
        # 7 个节点同时向节点 0 汇聚：col0=70B, 均值 8.75B -> incast_factor = 8
        edges = [(i, 0) for i in range(1, 8)]
        m = traffic.matrix_from_edges(8, edges, 10.0)
        s = traffic.matrix_stats(m)
        assert s["incast_factor"] == pytest.approx(8.0)
        assert s["hotspot_factor"] > 1.0


class TestStepSummary:
    CONFIG = {
        "params_bytes": 7e9,
        "n_ranks": 256,
        "tp_message_bytes": 128 * 1024 ** 2,
        "n_tp": 8,
        "ep_token_bytes": 64 * 1024 ** 2,
        "topk": 8,
        "n_ep": 64,
        "local_layers": 10,
        "n_microbatches": 16,
        "activation_bytes": 32 * 1024 ** 2,
    }

    def test_all_strategies_present(self):
        rows = traffic.step_traffic_summary(self.CONFIG)
        assert set(rows) == {"DP 梯度同步", "TP 张量并行", "EP 专家并行",
                             "PP 流水并行"}

    def test_ep_dominates_for_moe(self):
        rows = traffic.step_traffic_summary(self.CONFIG)
        assert traffic.dominant_traffic(rows) == "EP 专家并行"

    def test_tp_per_call_uses_ring_formula(self):
        per_call = traffic.allreduce_send_bytes(
            self.CONFIG["tp_message_bytes"], self.CONFIG["n_tp"])
        rows = traffic.step_traffic_summary(self.CONFIG)
        assert rows["TP 张量并行"]["per_call_bytes"] == pytest.approx(per_call)

"""ep.py 的测试：通信量公式、节点受限路由、负载不均。"""
import pytest

from deepseek_case_mini.ep import (
    EpConfig,
    all_to_all_time,
    combine_bytes_per_gpu,
    dispatch_bytes_per_gpu,
    ep_step_comm_time,
    expert_loads,
    imbalance_factor,
    inter_node_fraction,
    routing_imbalance,
    split_traffic,
    token_payload_bytes,
)


class TestBytes:
    def test_payload_bytes(self):
        cfg = EpConfig(hidden=7168, topk=8, dtype_bytes=2)
        assert token_payload_bytes(cfg) == 7168 * 2

    def test_dispatch_formula(self):
        """dispatch 字节 = tokens × topk × hidden × dtype_bytes。"""
        cfg = EpConfig(hidden=1024, topk=8)
        assert dispatch_bytes_per_gpu(1000, cfg) == 1000 * 8 * 1024 * 2

    def test_combine_equals_dispatch(self):
        cfg = EpConfig()
        assert combine_bytes_per_gpu(4096, cfg) == dispatch_bytes_per_gpu(4096, cfg)

    def test_fp8_dispatch_halves_bytes(self):
        bf16 = EpConfig(hidden=7168, fp8_dispatch=False)
        fp8 = EpConfig(hidden=7168, fp8_dispatch=True)
        # DeepEP 支持 FP8 dispatch：负载字节减半（缩放因子另计，此处为示意）
        assert dispatch_bytes_per_gpu(1000, fp8) < dispatch_bytes_per_gpu(1000, bf16)


class TestNodeLimitedRouting:
    def test_single_node_no_inter(self):
        cfg = EpConfig(ep_size=8, node_size=8, nodes_limited=1)
        assert inter_node_fraction(cfg) == 0.0

    def test_unlimited_fraction(self):
        """不限节点：跨节点占比 = 7/8（8 卡节点）。"""
        cfg = EpConfig(ep_size=64, node_size=8, nodes_limited=None)
        assert inter_node_fraction(cfg) == pytest.approx(7 / 8)

    def test_v3_config_fraction(self):
        """V3 配置：M=4 / 8 节点 ⇒ (3/7)×(7/8) = 3/8。"""
        cfg = EpConfig()  # 默认 nodes_limited=4
        assert cfg.num_nodes == 8
        assert inter_node_fraction(cfg) == pytest.approx((3 / 7) * (7 / 8))

    def test_split_sums_to_total(self):
        cfg = EpConfig()
        nv, ib = split_traffic(1000.0, cfg)
        assert nv + ib == pytest.approx(1000.0)
        assert ib < nv  # 大部分压在 NVLink 上

    def test_node_limited_reduces_time(self):
        cfg_l = EpConfig(nodes_limited=4)
        cfg_u = EpConfig(nodes_limited=None)
        t_l = all_to_all_time(1e9, cfg_l)
        t_u = all_to_all_time(1e9, cfg_u)
        assert t_l < t_u


class TestImbalance:
    def test_perfect_balance(self):
        assert imbalance_factor([10.0] * 8) == 1.0

    def test_imbalance_range(self):
        cfg = EpConfig()
        imb = routing_imbalance(8192, cfg, seed=0)
        assert imb >= 1.0
        assert imb < 3.0

    def test_deterministic(self):
        assert routing_imbalance(8192, EpConfig(), seed=3) == routing_imbalance(
            8192, EpConfig(), seed=3
        )

    def test_different_seeds_differ(self):
        values = {routing_imbalance(4096, EpConfig(), seed=s) for s in range(5)}
        assert len(values) > 1

    def test_expert_loads_average(self):
        cfg = EpConfig()
        loads = expert_loads(8192, cfg, seed=0)
        assert len(loads) == cfg.ep_size
        # 期望均值 = tokens × topk / ep_size
        assert sum(loads) / len(loads) == pytest.approx(
            8192 * cfg.topk / cfg.ep_size, rel=0.1
        )

    def test_imbalance_slows_communication(self):
        cfg = EpConfig()
        t_bal = all_to_all_time(1e9, cfg, imbalance=1.0)
        t_imb = all_to_all_time(1e9, cfg, imbalance=1.5)
        assert t_imb == pytest.approx(t_bal * 1.5)


class TestStepTime:
    def test_ep_step_comm_time_shape(self):
        cfg = EpConfig()
        r = ep_step_comm_time(8192, cfg, seed=0)
        assert set(r) == {
            "dispatch_bytes",
            "imbalance",
            "forward_seconds",
            "backward_seconds",
            "total_seconds",
        }
        assert r["total_seconds"] == pytest.approx(
            r["forward_seconds"] + r["backward_seconds"]
        )
        assert r["backward_seconds"] == pytest.approx(r["forward_seconds"])

    def test_step_time_reasonable_magnitude(self):
        """量级检查：~900 MB dispatch，IB 段占 3/8，应约为几十 ms。"""
        cfg = EpConfig()
        r = ep_step_comm_time(8192, cfg, seed=0)
        assert 1e-3 < r["forward_seconds"] < 1.0

    def test_ep_size_one_node_uses_nvlink_only(self):
        cfg = EpConfig(ep_size=8, node_size=8)
        r = ep_step_comm_time(8192, cfg, seed=0)
        # 单节点：纯 NVLink ⇒ 远快于跨节点情形
        cfg64 = EpConfig()
        r64 = ep_step_comm_time(8192, cfg64, seed=0)
        assert r["total_seconds"] < r64["total_seconds"]

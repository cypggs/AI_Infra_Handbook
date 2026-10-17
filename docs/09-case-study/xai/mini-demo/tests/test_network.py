"""网络通信模型测试。"""

import pytest

from xai_case_mini import network


def test_ring_allreduce_n2():
    # 2 卡 2 步，每步 message/2
    t = network.ring_allreduce_time(2, 1e9, 100e9, efficiency=1.0, rtt_s=0.0)
    assert t == pytest.approx(2 * 0.5e9 / 100e9)


def test_ring_allreduce_scales_linearly_in_message():
    t1 = network.ring_allreduce_time(1024, 1e9, 100e9, 0.9, 0.0)
    t2 = network.ring_allreduce_time(1024, 2e9, 100e9, 0.9, 0.0)
    assert t2 == pytest.approx(2 * t1)


def test_ring_allreduce_efficiency_lowers_effective_bw():
    slow = network.ring_allreduce_time(1024, 1e9, 100e9, 0.60, 0.0)
    fast = network.ring_allreduce_time(1024, 1e9, 100e9, 0.95, 0.0)
    assert fast < slow
    assert slow / fast == pytest.approx(0.95 / 0.60)


def test_ring_allreduce_rtt_adds_up():
    # 步数 = 2*(N-1)，每步加一个 RTT
    n = 100
    base = network.ring_allreduce_time(n, 1e9, 100e9, 1.0, 0.0)
    with_rtt = network.ring_allreduce_time(n, 1e9, 100e9, 1.0, 10e-6)
    assert with_rtt - base == pytest.approx(2 * (n - 1) * 10e-6)


def test_ring_allreduce_edge_cases():
    assert network.ring_allreduce_time(1, 1e9, 100e9) == 0.0
    with pytest.raises(ValueError):
        network.ring_allreduce_time(8, 0.0, 100e9)
    with pytest.raises(ValueError):
        network.ring_allreduce_time(8, 1e9, 0.0)


def test_dual_campus_penalty_positive():
    msg = 1024 ** 3
    single = network.ring_allreduce_time(100_000, msg, network.DEFAULT_PER_GPU_BPS)
    dual = network.dual_campus_allreduce_time(100_000, msg, network.DEFAULT_PER_GPU_BPS)
    assert dual > single


def test_dual_campus_bigger_dci_less_penalty():
    msg = 1024 ** 3
    slow = network.dual_campus_allreduce_time(100_000, msg,
                                              network.DEFAULT_PER_GPU_BPS,
                                              dci_bps=0.8e12)
    fast = network.dual_campus_allreduce_time(100_000, msg,
                                              network.DEFAULT_PER_GPU_BPS,
                                              dci_bps=6.4e12)
    assert fast < slow


def test_cross_site_penalty_model():
    msg = 1024 ** 3
    pen = network.cross_site_penalty(msg, dci_bps=1.6e12, wan_rtt_s=5e-3,
                                     efficiency=1.0)
    # msg/(1.6e12) + 2*5ms
    assert pen == pytest.approx(msg / 1.6e12 + 0.01)


def test_cross_site_penalty_validation():
    with pytest.raises(ValueError):
        network.cross_site_penalty(0.0, 1e12)
    with pytest.raises(ValueError):
        network.cross_site_penalty(1e9, 0.0)


def test_dual_campus_input_validation():
    msg = 1024 ** 3
    with pytest.raises(ValueError):
        network.dual_campus_allreduce_time(1, msg, 100e9)


def test_step_time_mfu():
    r = network.step_time(comm_s=10.0, compute_s=20.0)
    assert r.step_s == pytest.approx(30.0)
    assert r.mfu == pytest.approx(20.0 / 30.0)
    with pytest.raises(ValueError):
        network.step_time(comm_s=1.0, compute_s=0.0)


def test_fabric_comparison_keys_and_ordering():
    comp = network.fabric_comparison(1024 ** 3)
    assert set(comp) == {"infiniband", "spectrum-x", "ethernet-legacy"}
    assert comp["ethernet-legacy"] > comp["spectrum-x"]
    assert comp["spectrum-x"] == pytest.approx(comp["infiniband"])


def test_campus_comparison_penalty_grows_with_model_size():
    rows = network.campus_comparison(n_gpus=100_000)
    assert [r["message_gb"] for r in rows] == [256.0, 1024.0, 4096.0, 16384.0]
    singles = [r["single_s"] for r in rows]
    penalties = [r["penalty_s"] for r in rows]
    losses = [r["throughput_loss"] for r in rows]
    # 单集群耗时随消息线性增长
    assert singles == sorted(singles)
    # 跨园区惩罚随消息大小增长（线性），吞吐损失占比随之扩大
    assert penalties == sorted(penalties)
    assert losses == sorted(losses)
    for r in rows:
        assert r["dual_s"] > r["single_s"] > 0
        assert r["throughput_loss"] > 0
    # 256 GB -> 16 TB，消息 64 倍；去掉 RTT 常数项后惩罚严格 64 倍
    p_small = network.cross_site_penalty(256 * 1024 ** 3, wan_rtt_s=0.0)
    p_large = network.cross_site_penalty(16384 * 1024 ** 3, wan_rtt_s=0.0)
    assert p_large / p_small == pytest.approx(64.0)
    # 常数项（WAN RTT）在小消息时占主导，大消息时带宽项主导
    assert penalties[0] > p_small
    assert penalties[-1] == pytest.approx(p_large + 0.01)

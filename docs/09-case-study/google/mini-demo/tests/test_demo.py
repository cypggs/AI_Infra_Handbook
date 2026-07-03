from google_mini.demo import (
    reconfigure_vs_reroute_insight,
    run_demo,
    torus_vs_ring_insight,
)
from google_mini.metrics import effective_mfu


def test_run_demo_returns_four_configs():
    res = run_demo(seed=7)
    assert set(res.keys()) == {"baseline", "naive", "reconfigure", "reroute"}


def test_baseline_has_no_failures():
    assert run_demo(seed=7)["baseline"].failures == 0


def test_mfu_ranking():
    res = run_demo(seed=7)
    rer = effective_mfu(res["reroute"])
    rec = effective_mfu(res["reconfigure"])
    naive = effective_mfu(res["naive"])
    base = effective_mfu(res["baseline"])
    assert base > rer > rec > naive


def test_fleet_idle_only_reconfigure():
    res = run_demo(seed=7)
    assert res["reconfigure"].fleet_idle_chip_seconds > 0.0
    assert res["reroute"].fleet_idle_chip_seconds == 0.0
    assert res["naive"].fleet_idle_chip_seconds == 0.0


def test_step_penalty_only_reroute():
    res = run_demo(seed=7)
    assert res["reroute"].final_step_penalty > 0.0
    assert res["reconfigure"].final_step_penalty == 0.0


def test_torus_vs_ring_insight_values():
    info = torus_vs_ring_insight()
    assert info["n_chips"] == 4096
    assert info["latency_term_torus"] == 90
    assert info["latency_term_ring"] == 8190
    # 两种消息规模下 torus 都不慢于单环
    assert info["big_torus_s"] < info["big_ring_s"]
    assert info["small_torus_s"] < info["small_ring_s"]


def test_reconfigure_vs_reroute_insight_structure():
    info = reconfigure_vs_reroute_insight()
    assert 0.0 < info["reconfigure_mfu"] < 1.0
    assert len(info["sweep"]) >= 2
    # reroute MFU 随步时惩罚增大单调下降
    mfus = [row["reroute_mfu"] for row in info["sweep"]]
    assert all(mfus[i] >= mfus[i + 1] for i in range(len(mfus) - 1))
    # 小惩罚时 reroute 优于 reconfigure；存在一个 crossover 惩罚
    assert info["sweep"][0]["reroute_mfu"] > info["reconfigure_mfu"]
    assert info["crossover_penalty"] is not None

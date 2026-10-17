"""Tests for failure taxonomy, injection and recovery simulation."""
import pytest

from training_reliability_mini import availability as av
from training_reliability_mini import recovery as rc


def test_timeline_constants_sum():
    assert rc.TIMELINE_COLD_RESTART_MIN == pytest.approx(6.47)
    assert (rc.TIMELINE_STOP_MIN + rc.TIMELINE_RESCHEDULE_MIN
            + rc.TIMELINE_CKPT_LOAD_MIN + rc.TIMELINE_NCCL_MIN
            + rc.TIMELINE_WARMUP_MIN) == pytest.approx(6.47)


def test_taxonomy_weights_sum_to_one():
    total = (rc.TAXONOMY_GPU + rc.TAXONOMY_NETWORK + rc.TAXONOMY_HOST
             + rc.TAXONOMY_SOFTWARE + rc.TAXONOMY_OTHER)
    assert total == pytest.approx(1.0)
    assert rc.TAXONOMY_GPU == pytest.approx(0.587)


def test_sample_failures_categories_valid():
    events = rc.sample_failures(500.0, 512, 8089.6, seed=1)
    assert all(e.category in rc.CATEGORY_PROFILE for e in events)
    assert all(0 <= e.node < 512 for e in events)
    assert all(e.time_h <= 500.0 for e in events)


def test_recover_cold_timeline():
    ev = rc.FailureEvent(1.0, "gpu", 3)
    res = rc.recover(ev, "cold", 120, 30.0)
    assert res.restart_s == pytest.approx(6.47 * 60)
    assert res.rollback_steps == 60
    assert res.lost_s == pytest.approx(60 * 30 + res.downtime_s)


def test_recover_hot_faster_for_hardware():
    for cat in ("gpu", "network", "host"):
        hot = rc.recover(rc.FailureEvent(1.0, cat, 0), "hot", 120, 30.0)
        cold = rc.recover(rc.FailureEvent(1.0, cat, 0), "cold", 120, 30.0)
        assert hot.restart_s < cold.restart_s


def test_recover_hot_falls_back_for_software():
    hot = rc.recover(rc.FailureEvent(1.0, "software", 0), "hot", 120, 30.0)
    cold = rc.recover(rc.FailureEvent(1.0, "software", 0), "cold", 120, 30.0)
    assert hot.restart_s == pytest.approx(cold.restart_s)


def test_recover_detection_latency_by_category():
    assert rc.recover(rc.FailureEvent(0, "gpu", 0), "hot", 10, 30).detect_s == 10.0
    assert rc.recover(rc.FailureEvent(0, "network", 0), "hot", 10, 30).detect_s == 30.0
    assert rc.recover(rc.FailureEvent(0, "host", 0), "hot", 10, 30).detect_s == 2.0


def test_recover_invalid():
    with pytest.raises(ValueError):
        rc.recover(rc.FailureEvent(0, "gpu", 0), "unknown", 10, 30)
    with pytest.raises(ValueError):
        rc.recover(rc.FailureEvent(0, "gpu", 0), "cold", 0, 30)


def test_simulate_run_ettr_bounds():
    res = rc.simulate_run(168.0, 1024, 8089.6, 30.0, 120, "hot", seed=7)
    assert 0.0 < res["ettr"] <= 1.0
    assert res["interruptions"] > 0
    assert res["lost_h"] > 0


def test_simulate_run_hot_beats_cold():
    cold = rc.simulate_run(168.0, 1024, 8089.6, 30.0, 120, "cold", seed=7)
    hot = rc.simulate_run(168.0, 1024, 8089.6, 30.0, 120, "hot", seed=7)
    assert hot["ettr"] > cold["ettr"]
    assert hot["lost_h"] < cold["lost_h"]


def test_simulate_run_long_run_rate():
    # 7-day run at 1024 nodes should see roughly 168/7.9 ~ 21 interruptions.
    res = rc.simulate_run(168.0, 1024, av.NODE_MTBF_RESEARCH_CLUSTER_H,
                          30.0, 120, "hot", seed=7)
    assert 10 <= res["interruptions"] <= 40



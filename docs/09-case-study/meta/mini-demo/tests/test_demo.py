"""Tests for the demo comparison."""

from meta_mini.demo import run_demo
from meta_mini.metrics import effective_utilization


def test_run_demo_returns_three_completed_runs():
    results = run_demo(seed=7)
    assert set(results.keys()) == {"ideal", "naive", "optimized"}
    for name, r in results.items():
        assert r.completed is True, f"{name} did not complete"


def test_ideal_has_no_failures():
    r = run_demo(seed=7)["ideal"]
    assert r.interruptions == 0
    assert r.sdc_detected == 0
    assert r.sdc_baked == 0
    assert r.recompute_steps == 0


def test_naive_never_detects_sdc():
    # validation disabled -> no SDC is ever caught by a detector
    r = run_demo(seed=7)["naive"]
    assert r.sdc_detected == 0
    # with the configured sdc_rate, several SDCs occur and all bake in
    assert r.sdc_baked >= 1
    assert r.interruptions >= 1


def test_optimized_catches_sdc_and_bakes_none():
    r = run_demo(seed=7)["optimized"]
    # validation_interval (100) <= ckpt_interval (200) and target (10000) is a
    # multiple of validation_interval -> every SDC is caught before baking.
    assert r.sdc_baked == 0
    assert r.sdc_detected >= 1


def test_optimized_bakes_no_more_than_naive():
    results = run_demo(seed=7)
    assert results["optimized"].sdc_baked <= results["naive"].sdc_baked
    assert results["naive"].sdc_detected <= results["optimized"].sdc_detected


def test_all_utilizations_in_range():
    for r in run_demo(seed=7).values():
        util = effective_utilization(r)
        assert 0.0 < util <= 1.0


def test_determinism():
    a = run_demo(seed=7)
    b = run_demo(seed=7)
    assert a == b

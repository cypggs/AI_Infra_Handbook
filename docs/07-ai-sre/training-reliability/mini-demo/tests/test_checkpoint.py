"""Tests for the checkpoint interval optimizer."""
import pytest

from training_reliability_mini import checkpoint as ck
from training_reliability_mini import recovery


def test_daly_formula_units():
    # sqrt(2 * 240s * 7.9h) in seconds.
    assert ck.daly_optimal_interval_s(240.0, 7.9) == pytest.approx(
        (2 * 240 * 7.9 * 3600) ** 0.5)


def test_daly_scales_with_sqrt():
    t1 = ck.daly_optimal_interval_s(240.0, 7.9)
    t2 = ck.daly_optimal_interval_s(240.0, 7.9 * 4)
    assert t2 == pytest.approx(2 * t1)


def test_daly_invalid():
    with pytest.raises(ValueError):
        ck.daly_optimal_interval_s(0.0, 7.9)
    with pytest.raises(ValueError):
        ck.daly_optimal_interval_s(240.0, 0.0)


def test_expected_lost_work_half_interval_plus_restart():
    assert ck.expected_lost_work_s(100, 30.0, 60.0) == pytest.approx(1560.0)
    assert ck.expected_lost_work_s(1, 30.0, 0.0) == pytest.approx(15.0)


def test_long_run_efficiency_no_checkpoint_is_low():
    restart_s = recovery.TIMELINE_COLD_RESTART_MIN * 60.0
    eff = ck.long_run_efficiency(5000, 30.0, 240.0, 7.9, restart_s)
    assert eff < 0.90


def test_long_run_efficiency_optimum_beats_extremes():
    restart_s = recovery.TIMELINE_COLD_RESTART_MIN * 60.0
    opt = ck.optimal_interval_grid(30.0, 240.0, 7.9, restart_s)
    best = opt["efficiency"]
    sparse = ck.long_run_efficiency(4000, 30.0, 240.0, 7.9, restart_s)
    tiny = ck.long_run_efficiency(1, 30.0, 240.0, 7.9, restart_s)
    assert best > sparse
    assert best > tiny
    # Honest optimum: blocking 240 s checkpoints + 6.47 min restarts cap
    # long-run efficiency near 87% at 7.9 h MTBF (async checkpointing in
    # production exists precisely to push past this bound).
    assert 0.85 < best < 1.0


def test_grid_optimum_near_daly():
    restart_s = recovery.TIMELINE_COLD_RESTART_MIN * 60.0
    opt = ck.optimal_interval_grid(30.0, 240.0, 7.9, restart_s)
    daly_steps = ck.daly_optimal_interval_s(240.0, 7.9) / 30.0
    assert abs(opt["interval_steps"] - daly_steps) / daly_steps < 0.5


def test_incremental_checkpoint_improves_efficiency():
    restart_s = recovery.TIMELINE_COLD_RESTART_MIN * 60.0
    full = ck.optimal_interval_grid(30.0, 240.0, 7.9, restart_s)
    inc = ck.optimal_interval_grid(30.0, 72.0, 7.9, restart_s)
    assert inc["efficiency"] > full["efficiency"]
    assert inc["interval_steps"] < full["interval_steps"]


def test_efficiency_curve_monotone_after_optimum():
    restart_s = recovery.TIMELINE_COLD_RESTART_MIN * 60.0
    curve = ck.efficiency_curve(30.0, 240.0, 7.9, restart_s, every=25)
    opt = ck.optimal_interval_grid(30.0, 240.0, 7.9, restart_s)
    tail = [r["efficiency"] for r in curve if r["interval_steps"] >= opt["interval_steps"]]
    # Sampled tail is broadly non-increasing (allow small numeric noise).
    assert tail[0] >= tail[-1] - 1e-9
    assert all(b <= a + 1e-9 for a, b in zip(tail, tail[1:]))


def test_efficiency_invalid_inputs():
    with pytest.raises(ValueError):
        ck.long_run_efficiency(0, 30.0, 240.0, 7.9, 60.0)
    with pytest.raises(ValueError):
        ck.long_run_efficiency(10, -1.0, 240.0, 7.9, 60.0)
    with pytest.raises(ValueError):
        ck.optimal_interval_grid(30.0, 240.0, 7.9, 60.0, max_steps=0)


def test_longer_mtbf_allows_sparser_checkpoints():
    restart_s = recovery.TIMELINE_COLD_RESTART_MIN * 60.0
    tight = ck.optimal_interval_grid(30.0, 240.0, 1.0, restart_s)
    loose = ck.optimal_interval_grid(30.0, 240.0, 30.0, restart_s)
    assert loose["interval_steps"] > tight["interval_steps"]


def test_efficiency_curve_structure():
    curve = ck.efficiency_curve(30.0, 240.0, 7.9, 60.0, max_steps=100, every=25)
    assert [r["interval_steps"] for r in curve] == [25, 50, 75, 100]
    assert all(0.0 < r["efficiency"] <= 1.0 for r in curve)

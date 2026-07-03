"""Tests for the core training simulator."""

import pytest

from meta_mini.metrics import (
    checkpoint_overhead_pct,
    effective_utilization,
    recompute_overhead_pct,
    restart_overhead_pct,
    validation_overhead_pct,
)
from meta_mini.model import JobConfig
from meta_mini.simulator import TrainingSimulator


def _partition_sums_to_one(r):
    total = (
        effective_utilization(r)
        + recompute_overhead_pct(r)
        + checkpoint_overhead_pct(r)
        + restart_overhead_pct(r)
        + validation_overhead_pct(r)
    )
    return total


def test_no_failures_only_checkpoint_validation_overhead():
    cfg = JobConfig(
        n_gpus=8,
        target_steps=1000,
        step_seconds=5.0,
        hard_fail_rate=0.0,
        sdc_rate=0.0,
        ckpt_interval=100,
        ckpt_seconds=30.0,
        restart_seconds=120.0,
        validation_interval=100,
        validation_seconds=15.0,
        seed=0,
    )
    r = TrainingSimulator().run(cfg)

    assert r.completed is True
    assert r.interruptions == 0
    assert r.sdc_detected == 0
    assert r.sdc_baked == 0
    assert r.recompute_steps == 0

    util = effective_utilization(r)
    assert 0.0 < util < 1.0          # pure overhead from ckpt + validation
    assert _partition_sums_to_one(r) == pytest.approx(1.0)
    # 10 checkpoints, 10 validations
    assert checkpoint_overhead_pct(r) > 0.0
    assert validation_overhead_pct(r) > 0.0


def test_hard_failures_cause_rollback_and_recompute():
    # Moderate hard-failure rate, no SDC: a few halts, but checkpoint windows
    # are clean often enough that the job still completes.
    cfg = JobConfig(
        n_gpus=16384,
        target_steps=300,
        step_seconds=5.0,
        hard_fail_rate=1.0e-3,        # ~0.023 per-step hazard
        sdc_rate=0.0,
        ckpt_interval=50,
        ckpt_seconds=30.0,
        restart_seconds=120.0,
        validation_interval=0,
        validation_seconds=0.0,
        seed=3,
    )
    r = TrainingSimulator().run(cfg)

    assert r.completed is True
    assert r.interruptions >= 1
    assert r.recompute_steps >= 1
    assert r.sdc_detected == 0
    assert r.sdc_baked == 0


def test_sdc_caught_by_validation_before_baking():
    # Validation more frequent than checkpoint -> every SDC window contains a
    # validation that runs before the checkpoint -> baked == 0.
    cfg = JobConfig(
        n_gpus=16384,
        target_steps=1000,
        step_seconds=5.0,
        hard_fail_rate=0.0,
        sdc_rate=3.0e-4,              # ~0.007 per-step hazard, several SDCs
        ckpt_interval=100,
        ckpt_seconds=30.0,
        restart_seconds=120.0,
        validation_interval=50,       # < ckpt_interval
        validation_seconds=15.0,
        seed=11,
    )
    r = TrainingSimulator().run(cfg)

    assert r.completed is True
    assert r.sdc_detected >= 1
    assert r.sdc_baked == 0


def test_sdc_baked_when_no_validation():
    # No detector -> every SDC bakes into a checkpoint or the final weights.
    # Rate is low enough that checkpoint windows are clean often enough to
    # complete, but high enough that >=1 SDC occurs.
    cfg = JobConfig(
        n_gpus=16384,
        target_steps=1000,
        step_seconds=5.0,
        hard_fail_rate=0.0,
        sdc_rate=3.0e-4,
        ckpt_interval=100,
        ckpt_seconds=30.0,
        restart_seconds=120.0,
        validation_interval=0,        # no detector
        validation_seconds=0.0,
        seed=11,
    )
    r = TrainingSimulator().run(cfg)

    assert r.completed is True
    assert r.sdc_detected == 0
    assert r.sdc_baked >= 1


def test_determinism_same_seed_same_result():
    cfg = JobConfig(
        n_gpus=16384,
        target_steps=500,
        hard_fail_rate=8.0e-5,
        sdc_rate=6.0e-5,
        ckpt_interval=100,
        validation_interval=50,
        seed=42,
    )
    a = TrainingSimulator().run(cfg)
    b = TrainingSimulator().run(cfg)
    assert a == b


def test_abort_when_budget_exhausted():
    # Tiny budget + nonzero target -> the job cannot finish -> completed False.
    cfg = JobConfig(
        n_gpus=8,
        target_steps=1000,
        hard_fail_rate=4.0e-3,
        sdc_rate=4.0e-3,
        ckpt_interval=100,
        validation_interval=50,
        max_step_budget=1,
        seed=0,
    )
    r = TrainingSimulator().run(cfg)
    assert r.completed is False


def test_invalid_config_rejected():
    with pytest.raises(ValueError):
        JobConfig(n_gpus=0)
    with pytest.raises(ValueError):
        JobConfig(target_steps=0)
    with pytest.raises(ValueError):
        JobConfig(ckpt_interval=0)
    with pytest.raises(ValueError):
        JobConfig(validation_interval=-1)

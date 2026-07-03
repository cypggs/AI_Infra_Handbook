"""Tests for the per-step cluster hazard model."""

import pytest

from meta_mini.failures import per_step_cluster_hazard


def test_zero_rate_is_zero_hazard():
    assert per_step_cluster_hazard(0.0, 16384, 5.0) == 0.0


def test_hazard_is_a_probability():
    h = per_step_cluster_hazard(1.0, 16384, 5.0)  # absurdly high rate
    assert 0.0 <= h <= 1.0


def test_larger_cluster_is_more_fragile():
    """N sits in the exponent: doubling GPUs (roughly) doubles the hazard
    when per-GPU probability is small."""
    small = per_step_cluster_hazard(1e-4, 8000, 5.0)
    large = per_step_cluster_hazard(1e-4, 16000, 5.0)
    assert large > small
    # For small p_gpu, hazard ~ n_gpus * p_gpu, so ~2x.
    assert large / small == pytest.approx(2.0, rel=0.01)


def test_matches_small_probability_approximation():
    n_gpus, step = 16384, 5.0
    rate = 8.0e-5
    p_gpu = rate * step / 3600.0
    approx = n_gpus * p_gpu
    exact = per_step_cluster_hazard(rate, n_gpus, step)
    assert exact == pytest.approx(approx, rel=0.01)


def test_invalid_args():
    with pytest.raises(ValueError):
        per_step_cluster_hazard(1e-4, 0, 5.0)
    with pytest.raises(ValueError):
        per_step_cluster_hazard(1e-4, 16, 0.0)
    with pytest.raises(ValueError):
        per_step_cluster_hazard(-1.0, 16, 5.0)

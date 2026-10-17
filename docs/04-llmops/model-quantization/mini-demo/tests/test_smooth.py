"""smooth.py 的单元测试：难度迁移的等价性、α 扫描与收益。"""

import numpy as np
import pytest

from model_quantization_mini import smooth


@pytest.fixture()
def problem():
    rng = np.random.default_rng(3)
    W = rng.standard_normal((64, 128)) * 0.02
    X = smooth.make_outlier_activations(256, 128, n_outliers=4, outlier_scale=30.0, seed=1)
    return W, X


def test_smoothing_is_exact_equivalence(problem):
    """X'W'ᵀ ≡ XWᵀ：缩放本身是数学恒等变换，不引入任何误差。"""
    W, X = problem
    s = smooth.compute_smooth_scales(W, X, alpha=0.5)
    W_s, X_s = smooth.apply_smoothing(W, X, s)
    np.testing.assert_allclose(X_s @ W_s.T, X @ W.T, rtol=1e-10, atol=1e-12)


def test_scales_positive_and_shape(problem):
    W, X = problem
    s = smooth.compute_smooth_scales(W, X, alpha=0.5)
    assert s.shape == (W.shape[1],)
    assert np.all(s > 0)


def test_alpha_extremes(problem):
    """α=0 时 s 只由权重决定，α=1 时只由激活决定。"""
    W, X = problem
    w_max = np.max(np.abs(W), axis=0)
    x_max = np.max(np.abs(X), axis=0)
    s0 = smooth.compute_smooth_scales(W, X, alpha=0.0)
    s1 = smooth.compute_smooth_scales(W, X, alpha=1.0)
    np.testing.assert_allclose(s0, 1.0 / (w_max + 1e-8), rtol=1e-6)
    np.testing.assert_allclose(s1, x_max + 1e-8, rtol=1e-6)


def test_smoothing_reduces_quant_error(problem):
    W, X = problem
    r = smooth.smoothed_quant_error(W, X, alpha=0.5)
    assert r["smoothed_err"] < r["baseline_err"]
    assert r["reduction_factor"] > 1.5


def test_best_alpha_not_at_extremes(problem):
    """最优 α 通常在中间：单边迁移会把难度全推给一方。"""
    W, X = problem
    sweep = smooth.alpha_sweep(W, X)
    best = min(sweep, key=lambda r: r["smoothed_err"])
    assert best["alpha"] in (0.25, 0.5, 0.75)


def test_alpha0_can_hurt(problem):
    """α=0（难度全推给权重）可能比不迁移还差——迁移方向有讲究。"""
    W, X = problem
    r = smooth.smoothed_quant_error(W, X, alpha=0.0)
    assert r["smoothed_err"] > r["baseline_err"]


def test_sweep_deterministic(problem):
    W, X = problem
    a = smooth.alpha_sweep(W, X)
    b = smooth.alpha_sweep(W, X)
    for ra, rb in zip(a, b):
        assert ra["smoothed_err"] == rb["smoothed_err"]

"""gptq_like.py 的单元测试：Hessian、Cholesky 路径与 GPTQ vs RTN。"""

import numpy as np
import pytest

from model_quantization_mini import gptq_like


@pytest.fixture()
def problem():
    """确定性的小规模量化问题：相关特征 + 小权重矩阵。"""
    rng = np.random.default_rng(5)
    W = rng.standard_normal((32, 64)) * 0.05
    X = gptq_like.make_correlated_activations(128, 64, rank=8, seed=0)
    return W, X


def test_hessian_shape_and_pd(problem):
    _, X = problem
    H, _ = gptq_like.build_hessian(X)
    assert H.shape == (64, 64)
    eig = np.linalg.eigvalsh(H)
    assert np.all(eig > 0)  # 阻尼后正定


def test_hessian_detects_dead_columns():
    X = np.random.default_rng(0).standard_normal((32, 8))
    X[:, 3] = 0.0  # 死特征
    _, dead = gptq_like.build_hessian(X)
    assert dead[3] and not dead[0]


def test_chol_upper_of_inverse(problem):
    _, X = problem
    H, _ = gptq_like.build_hessian(X)
    U = gptq_like.chol_upper_of_inverse(H)
    np.testing.assert_allclose(U.T @ U, np.linalg.inv(H), atol=1e-8)
    # U 上三角
    assert np.allclose(U[np.tril_indices_from(U, -1)], 0.0)


def test_gptq_shape_and_determinism(problem):
    W, X = problem
    W1 = gptq_like.gptq_quantize(W, X, bits=4, group_size=32)
    W2 = gptq_like.gptq_quantize(W, X, bits=4, group_size=32)
    assert W1.shape == W.shape
    np.testing.assert_array_equal(W1, W2)


def test_gptq_output_error_beats_rtn(problem):
    """GPTQ 的核心卖点：校准集输出误差显著低于 RTN。"""
    W, X = problem
    for bits in (4, 8):
        g = 64 if bits == 4 else 32
        e_rtn = gptq_like.output_rel_error(X, gptq_like.rtn_quantize(W, bits, g), W)
        e_gptq = gptq_like.output_rel_error(
            X, gptq_like.gptq_quantize(W, X, bits, g), W
        )
        assert e_gptq < e_rtn


def test_gptq_int4_improvement_factor(problem):
    W, X = problem
    e_rtn = gptq_like.output_rel_error(X, gptq_like.rtn_quantize(W, 4, 32), W)
    e_gptq = gptq_like.output_rel_error(X, gptq_like.gptq_quantize(W, X, 4, 32), W)
    assert e_rtn / e_gptq > 1.5


def test_advantage_shrinks_without_correlation():
    """特征无相关时 Hessian 近似对角，补偿空间小——教学对照组。"""
    rng = np.random.default_rng(2)
    W = rng.standard_normal((32, 64)) * 0.05
    X_corr = gptq_like.make_correlated_activations(128, 64, rank=4, seed=0)
    X_white = np.random.default_rng(0).standard_normal((128, 64))
    imp_corr = _improvement(W, X_corr)
    imp_white = _improvement(W, X_white)
    assert imp_corr > imp_white


def _improvement(W, X) -> float:
    e_rtn = gptq_like.output_rel_error(X, gptq_like.rtn_quantize(W, 4, 32), W)
    e_gptq = gptq_like.output_rel_error(X, gptq_like.gptq_quantize(W, X, 4, 32), W)
    return e_rtn / e_gptq

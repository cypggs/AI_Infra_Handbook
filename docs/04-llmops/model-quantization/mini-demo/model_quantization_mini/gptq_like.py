"""简化 OBS/GPTQ 风格的逐列误差补偿量化（纯 numpy、确定性）。

GPTQ 的核心思想（Frantar et al., 2022）：

1. 用校准集激活 X 计算该线性层输入的 Hessian  H = XᵀX（二阶信息）；
2. 按列量化权重：量化第 j 列产生的误差，按 H⁻¹ 的最优补偿系数
   反向传播到尚未量化的列（OBS 的逐列版本）；
3. 剩余列在被量化之前先吸收前序列的误差，因此整体误差显著低于
   逐列独立的 RTN（round-to-nearest）。

实现对齐 GPTQ 参考代码的数值路径：H 阻尼 → Cholesky 求逆 →
upper Cholesky 因子 → 逐列 quantize / compensate。为了教学清晰，
做了两处简化：权重按行（输出通道）取对称 group-wise scale；
不实现 act-order 与稀疏化。
"""

from __future__ import annotations

import numpy as np


def build_hessian(X: np.ndarray, damp: float = 0.01) -> np.ndarray:
    """由校准激活 X (n_samples, in_dim) 构造阻尼后的 Hessian (in_dim, in_dim)。

    零方差（死）特征会被置 1 并返回死列索引，调用方应同步把权重对应列清零。
    """
    X = np.asarray(X, dtype=np.float64)
    H = X.T @ X / max(X.shape[0], 1)
    dead = np.diag(H) == 0.0
    H = H.copy()
    H[dead, dead] = 1.0
    H = H + damp * np.mean(np.diag(H)) * np.eye(H.shape[0])
    return H, dead


def chol_upper_of_inverse(H: np.ndarray) -> np.ndarray:
    """返回 H⁻¹ 的 upper Cholesky 因子 U（H⁻¹ = U Uᵀ，U 上三角）。

    与 GPTQ 参考实现 `cholesky(cholesky_inverse(H), upper=True)` 同路径。
    """
    L = np.linalg.cholesky(H)
    L_inv = np.linalg.inv(L)
    H_inv = L_inv.T @ L_inv
    U = np.linalg.cholesky(H_inv).T  # upper 因子
    return U


def _symmetric_row_scales(W_block: np.ndarray, bits: int) -> np.ndarray:
    """W_block (out, cols) 每行一个对称 scale。"""
    qmax = (1 << (bits - 1)) - 1
    amax = np.max(np.abs(W_block), axis=1, keepdims=True)
    return np.maximum(amax / qmax, 1e-12)


def _rtn_group(W: np.ndarray, bits: int, group_size: int) -> np.ndarray:
    """无补偿的 group-wise RTN（round-to-nearest）基线。"""
    W = W.astype(np.float64)
    qmin, qmax = -(1 << (bits - 1)), (1 << (bits - 1)) - 1
    out = np.empty_like(W)
    for j0 in range(0, W.shape[1], group_size):
        j1 = min(j0 + group_size, W.shape[1])
        s = _symmetric_row_scales(W[:, j0:j1], bits)
        q = np.clip(np.round(W[:, j0:j1] / s), qmin, qmax)
        out[:, j0:j1] = q * s
    return out


def rtn_quantize(W: np.ndarray, bits: int = 4, group_size: int = 64) -> np.ndarray:
    """RTN 基线：对称、按行 scale、group-wise。"""
    return _rtn_group(np.asarray(W), bits, group_size)


def obs_quantize(
    W: np.ndarray,
    H: np.ndarray,
    bits: int = 4,
    group_size: int = 64,
) -> np.ndarray:
    """OBS/GPTQ 风格逐列误差补偿量化。

    W (out, in)，H (in, in) 为 build_hessian 的输出。
    返回量化反量化后的权重（float64）。
    """
    W = np.asarray(W, dtype=np.float64).copy()
    U = chol_upper_of_inverse(H)
    qmin, qmax = -(1 << (bits - 1)), (1 << (bits - 1)) - 1
    d = W.shape[1]

    for j0 in range(0, d, group_size):
        j1 = min(j0 + group_size, d)
        s = _symmetric_row_scales(W[:, j0:j1], bits)
        s = s[:, 0]
        for j in range(j0, j1):
            w = W[:, j]
            q = np.clip(np.round(w / s), qmin, qmax) * s
            err = (w - q) / U[j, j]
            W[:, j] = q
            if j + 1 < d:
                W[:, j + 1 :] -= np.outer(err, U[j, j + 1 :])
    return W


def gptq_quantize(
    W: np.ndarray,
    X: np.ndarray,
    bits: int = 4,
    group_size: int = 64,
) -> np.ndarray:
    """从校准激活出发的完整 GPTQ 流程（含死列处理）。"""
    H, dead = build_hessian(X)
    W = np.asarray(W, dtype=np.float64).copy()
    W[:, dead] = 0.0
    return obs_quantize(W, H, bits, group_size)


def weight_rel_error(W_hat: np.ndarray, W: np.ndarray) -> float:
    """权重相对 Frobenius 误差。"""
    W = np.asarray(W, dtype=np.float64)
    W_hat = np.asarray(W_hat, dtype=np.float64)
    return float(np.linalg.norm(W_hat - W) / np.linalg.norm(W))


def output_rel_error(
    X: np.ndarray, W_hat: np.ndarray, W: np.ndarray
) -> float:
    """校准集上的输出误差 ||X(Ŵ-W)ᵀ|| / ||XWᵀ||（量化对真实前向的影响）。"""
    X = np.asarray(X, dtype=np.float64)
    W = np.asarray(W, dtype=np.float64)
    W_hat = np.asarray(W_hat, dtype=np.float64)
    denom = np.linalg.norm(X @ W.T)
    if denom == 0.0:
        return float(np.linalg.norm(X @ (W_hat - W).T))
    return float(np.linalg.norm(X @ (W_hat - W).T) / denom)


def make_correlated_activations(
    n_samples: int,
    in_dim: int,
    rank: int = 16,
    seed: int = 0,
) -> np.ndarray:
    """构造列间强相关的校准激活（低秩混合），模拟真实特征相关性。

    X = Z @ M，Z 标准正态，M 为衰减谱混合矩阵——这种相关性正是
    GPTQ 误差补偿能发挥作用的场景。
    """
    rng = np.random.default_rng(seed)
    Z = rng.standard_normal((n_samples, in_dim))
    spectrum = np.exp(-np.arange(in_dim) / rank)
    Q, _ = np.linalg.qr(rng.standard_normal((in_dim, in_dim)))
    M = Q @ np.diag(spectrum) @ Q.T
    return Z @ M

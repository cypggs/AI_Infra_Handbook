"""整数与浮点低精度格式的量化/反量化基础件（纯 numpy、确定性）。

覆盖量化工具链里最底层的四个决策：

1. 对称 vs 非对称（zero-point 是否有必要）；
2. per-tensor vs per-channel vs group-wise（缩放粒度）；
3. 定点整数量化（INT8/INT4）与浮点格式模拟（FP8 E4M3/E5M2、FP4 E2M1）；
4. block-float（Microscaling / NVFP4 风格：小块共享一个 scale）。

误差度量统一提供 MSE、相对 L2、余弦相似度、最大绝对误差。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# ---------------------------------------------------------------------------
# 误差度量
# ---------------------------------------------------------------------------


def mse_error(x: np.ndarray, y: np.ndarray) -> float:
    """均方误差。"""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    return float(np.mean((x - y) ** 2))


def rel_l2_error(x: np.ndarray, y: np.ndarray) -> float:
    """相对 L2 误差 ||x - y|| / ||x||（x 为基准）。x 全零时返回绝对误差。"""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    denom = float(np.linalg.norm(x))
    if denom == 0.0:
        return float(np.linalg.norm(x - y))
    return float(np.linalg.norm(x - y) / denom)


def cosine_similarity(x: np.ndarray, y: np.ndarray) -> float:
    """展平后计算余弦相似度。任一向量为零向量时返回 0.0。"""
    x = np.asarray(x, dtype=np.float64).ravel()
    y = np.asarray(y, dtype=np.float64).ravel()
    denom = float(np.linalg.norm(x) * np.linalg.norm(y))
    if denom == 0.0:
        return 0.0
    return float(np.dot(x, y) / denom)


def max_abs_error(x: np.ndarray, y: np.ndarray) -> float:
    """最大绝对误差。"""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    return float(np.max(np.abs(x - y)))


# ---------------------------------------------------------------------------
# 整数量化
# ---------------------------------------------------------------------------

_GRANULARITIES = ("per_tensor", "per_channel", "group_wise")


@dataclass(frozen=True)
class QuantConfig:
    """整数量化配置。

    granularity:
      - per_tensor：整个张量一个 scale/zero_point；
      - per_channel：沿 axis 的每一「条带」一个 scale（如每输出通道）；
      - group_wise：沿 axis 每 group_size 个元素一个 scale（如 g=128）。
    symmetric: True 用对称整数量化（zero_point=0），False 用非对称（带 zero_point）。
    """

    bits: int = 8
    symmetric: bool = True
    granularity: str = "per_tensor"
    group_size: int = 128
    axis: int = 0

    def __post_init__(self) -> None:
        if self.bits < 2 or self.bits > 16:
            raise ValueError(f"bits 必须在 [2, 16]，得到 {self.bits}")
        if self.granularity not in _GRANULARITIES:
            raise ValueError(f"未知粒度: {self.granularity}")
        if self.granularity == "group_wise" and self.group_size < 2:
            raise ValueError("group_wise 需要 group_size >= 2")


@dataclass
class QuantizedTensor:
    """量化后的张量 + 反量化所需全部元数据。

    q / original_shape 使用原始布局；scale / zero_point 使用「量化轴搬到
    最后一维」后的布局（group_wise 时尾维形状为 (n_groups, 1)），
    dequant() 内部负责搬回。
    """

    q: np.ndarray
    scale: np.ndarray
    zero_point: np.ndarray
    config: QuantConfig
    original_shape: tuple

    def _expand_groupwise(self, arr: np.ndarray) -> np.ndarray:
        """把 (..., n_groups, 1) 的 group-wise 参数展开回逐元素 (..., n)。"""
        n = self.original_shape[self.config.axis % len(self.original_shape)]
        g = self.config.group_size
        n_groups = arr.shape[-2]
        full = np.repeat(arr, g, axis=-1).reshape(arr.shape[:-2] + (n_groups * g,))
        return full[..., :n]

    def dequant(self) -> np.ndarray:
        axis = self.config.axis % len(self.original_shape)
        if self.config.granularity == "group_wise":
            scale = self._expand_groupwise(self.scale)  # 搬轴后布局 (..., n)
            zp = self._expand_groupwise(self.zero_point)
        else:
            scale, zp = self.scale, self.zero_point
        if np.ndim(scale) > 0:  # per_tensor 时为标量，无需搬轴
            scale = np.moveaxis(scale, -1, axis)
            zp = np.moveaxis(zp, -1, axis)
        return ((self.q.astype(np.float64) - zp) * scale).reshape(self.original_shape)


def _qrange(bits: int, symmetric: bool) -> tuple[int, int]:
    if symmetric:
        return -(1 << (bits - 1)), (1 << (bits - 1)) - 1
    return 0, (1 << bits) - 1


def quantize_tensor(x: np.ndarray, cfg: QuantConfig) -> QuantizedTensor:
    """按配置量化张量（计算在「量化轴搬到末维」的空间进行，保证广播正确）。"""
    x = np.asarray(x, dtype=np.float64)
    axis = cfg.axis % x.ndim
    xp = np.moveaxis(x, axis, -1)
    n = xp.shape[-1]

    if cfg.granularity == "per_tensor":
        lo: np.ndarray = np.array(np.min(xp))
        hi: np.ndarray = np.array(np.max(xp))
    elif cfg.granularity == "per_channel":
        red = tuple(range(xp.ndim - 1))
        lo = np.min(xp, axis=red, keepdims=True)
        hi = np.max(xp, axis=red, keepdims=True)
    else:  # group_wise
        g = cfg.group_size
        n_groups = (n + g - 1) // g
        pad = n_groups * g - n
        if pad:
            xp_pad = np.concatenate([xp, np.repeat(xp[..., -1:], pad, axis=-1)], axis=-1)
        else:
            xp_pad = xp
        blocks = xp_pad.reshape(xp.shape[:-1] + (n_groups, g))
        lo = np.min(blocks, axis=-1, keepdims=True)
        hi = np.max(blocks, axis=-1, keepdims=True)

    qmin, qmax = _qrange(cfg.bits, cfg.symmetric)
    if cfg.symmetric:
        amax = np.maximum(np.abs(lo), np.abs(hi))
        scale = np.maximum(amax / qmax, 1e-12)
        zero_point = np.zeros_like(scale)
    else:
        scale = np.maximum((hi - lo) / (qmax - qmin), 1e-12)
        zero_point = np.clip(np.round(-lo / scale), qmin, qmax)

    # group_wise 的 (..., n_groups, 1) 参数展开回逐元素（..., n）再参与编码
    if cfg.granularity == "group_wise":
        g = cfg.group_size
        scale_e = np.repeat(scale, g, axis=-1).reshape(xp.shape[:-1] + (n_groups * g,))[..., :n]
        zp_e = np.repeat(zero_point, g, axis=-1).reshape(xp.shape[:-1] + (n_groups * g,))[..., :n]
    else:
        scale_e, zp_e = scale, zero_point

    q = np.round(xp / scale_e)
    if not cfg.symmetric:
        q = q + zp_e
    q = np.clip(q, qmin, qmax).astype(np.int64)
    q = np.moveaxis(q, -1, axis)
    return QuantizedTensor(
        q=q,
        scale=np.asarray(scale, dtype=np.float64),
        zero_point=np.asarray(zero_point, dtype=np.float64),
        config=cfg,
        original_shape=x.shape,
    )


def dequantize_tensor(qt: QuantizedTensor) -> np.ndarray:
    """反量化（等价于 qt.dequant()）。"""
    return qt.dequant()


def effective_bits_per_weight(cfg: QuantConfig, scale_bytes: int = 2) -> float:
    """group-wise 量化的等效位宽 = 数据位宽 + scale 开销 + zero_point 开销。

    对称量化无 zero_point；scale 按 scale_bytes 字节（FP16=2、FP32=4）计。
    """
    if cfg.granularity != "group_wise":
        return float(cfg.bits)
    zp = 0.0 if cfg.symmetric else cfg.bits / cfg.group_size
    return float(cfg.bits) + (scale_bytes * 8.0 + zp) / cfg.group_size


# ---------------------------------------------------------------------------
# 浮点格式模拟（FP8 / FP4，含 Microscaling block-float）
# ---------------------------------------------------------------------------


# 常见低精度格式的最大有限值（OCP 规范）：
# E4M3 保留 S.1111.111 为 NaN（最大为 0x7E=448）；E5M2 指数全 1 保留给 Inf/NaN；
# E2M1 无 Inf/NaN。其他格式按 IEEE「指数全 1 保留」的通用公式回退。
_MAX_FINITE = {
    (4, 3): 448.0,  # FP8 E4M3
    (5, 2): 57344.0,  # FP8 E5M2
    (2, 1): 6.0,  # FP4 E2M1
}


def _max_finite(exp_bits: int, mant_bits: int) -> float:
    if (exp_bits, mant_bits) in _MAX_FINITE:
        return _MAX_FINITE[(exp_bits, mant_bits)]
    # IEEE 风格回退：最大指数域 = 全 1 减 1
    bias = (1 << (exp_bits - 1)) - 1
    return (2.0 - 2.0 ** (-mant_bits)) * (2.0 ** (2**exp_bits - 2 - bias))


def float_quantize(x: np.ndarray, exp_bits: int, mant_bits: int) -> np.ndarray:
    """把 float32 张量模拟量化到任意「exp_bits 指数位 + mant_bits 尾数位」格式。

    采用 round-to-nearest-even（与 IEEE 一致），溢出饱和到该格式最大有限值，
    非正规区间（subnormal）按固定最小 quantum 处理，输入 NaN/Inf 视为最大有限值。
    用 float64 中间运算保证确定性。

    例（E2M1）: 0.4->0.5, 0.1->0, 5.0->4.0（tie-to-even）, 6.0->6.0。
    """
    x = np.asarray(x, dtype=np.float64)
    if exp_bits < 2 or mant_bits < 1:
        raise ValueError("exp_bits>=2 且 mant_bits>=1")
    bias = (1 << (exp_bits - 1)) - 1
    max_fin = _max_finite(exp_bits, mant_bits)

    ax = np.abs(x)
    ax = np.where(np.isfinite(ax), ax, max_fin)

    # 正规区间：quantum = 2^(floor(log2(ax)) - mant_bits)
    with np.errstate(divide="ignore"):
        e = np.floor(np.log2(ax))
    e = np.where((ax == 0) | ~np.isfinite(e), 0.0, e)
    quantum = 2.0 ** (e - mant_bits)
    val = np.round(ax / quantum) * quantum

    # 非正规区间：ax < 2^(1-bias)，固定 quantum
    sub_q = 2.0 ** (1 - bias - mant_bits)
    is_sub = (ax > 0) & (ax < 2.0 ** (1 - bias))
    val = np.where(is_sub, np.round(ax / sub_q) * sub_q, val)

    val = np.minimum(val, max_fin)
    out = np.sign(x) * val
    return out.astype(np.float32)


def float_format_range(exp_bits: int, mant_bits: int) -> tuple[float, float]:
    """返回某浮点格式的 (最小正规数, 最大有限值)。"""
    bias = (1 << (exp_bits - 1)) - 1
    return 2.0 ** (1 - bias), _max_finite(exp_bits, mant_bits)


def block_float_quantize(
    x: np.ndarray,
    block_size: int,
    elem_exp_bits: int = 2,
    elem_mant_bits: int = 1,
    scale_kind: str = "e4m3",
) -> tuple[np.ndarray, dict]:
    """Microscaling 风格的 block-float 量化（沿最后一维分块）。

    scale_kind:
      - "e4m3"：NVFP4 风格，scale 用 FP8 E4M3 表示（动态范围对齐 FP8）；
      - "e8m0"：MXFP4 风格（OCP MX），scale 量化为 2 的整数幂（E8M0）。

    返回 (反量化结果, 元信息 dict)。块内 amax 归一化到元素格式的最大有限值，
    不足一块的尾部用 0 补齐（不影响 amax）。
    """
    if scale_kind not in ("e4m3", "e8m0"):
        raise ValueError("scale_kind 必须是 'e4m3' 或 'e8m0'")
    x = np.asarray(x, dtype=np.float64)
    n = x.shape[-1]
    n_blocks = (n + block_size - 1) // block_size
    pad = n_blocks * block_size - n
    xp = np.pad(x, [(0, 0)] * (x.ndim - 1) + [(0, pad)]) if pad else x
    blocks = xp.reshape(x.shape[:-1] + (n_blocks, block_size))

    _, max_fin = float_format_range(elem_exp_bits, elem_mant_bits)
    amax = np.max(np.abs(blocks), axis=-1, keepdims=True)
    raw_scale = np.where(amax > 0, amax / max_fin, 1.0)

    if scale_kind == "e4m3":
        scale = float_quantize(raw_scale, 4, 3).astype(np.float64)
        scale_bits = 8
    else:
        with np.errstate(divide="ignore"):
            pow2 = np.round(np.log2(raw_scale))
        pow2 = np.where(np.isfinite(pow2), pow2, 0.0)
        scale = 2.0**pow2
        scale_bits = 8

    q = float_quantize(blocks / scale, elem_exp_bits, elem_mant_bits).astype(np.float64)
    x_hat = (q * scale).reshape(x.shape[:-1] + (n_blocks * block_size,))
    if pad:
        x_hat = x_hat[..., :n]

    info = {
        "block_size": block_size,
        "scale_kind": scale_kind,
        "scale_bits": scale_bits,
        "bits_per_elem": elem_exp_bits + elem_mant_bits + 1 + scale_bits / block_size,
    }
    return x_hat, info

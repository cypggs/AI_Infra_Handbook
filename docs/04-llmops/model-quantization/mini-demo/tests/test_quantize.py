"""quantize.py 的单元测试：整数量化、浮点格式模拟、误差度量。"""

import numpy as np
import pytest

from model_quantization_mini.quantize import (
    QuantConfig,
    block_float_quantize,
    cosine_similarity,
    effective_bits_per_weight,
    float_format_range,
    float_quantize,
    max_abs_error,
    mse_error,
    quantize_tensor,
    rel_l2_error,
)


@pytest.fixture()
def weight():
    rng = np.random.default_rng(42)
    return rng.standard_normal((64, 128)) * 0.02


# ---------------------------------------------------------------------------
# 误差度量
# ---------------------------------------------------------------------------


def test_error_metrics_basics():
    x = np.array([1.0, 2.0, 3.0])
    assert mse_error(x, x) == 0.0
    assert rel_l2_error(x, x) == 0.0
    assert cosine_similarity(x, x) == pytest.approx(1.0)
    assert max_abs_error(x, x) == 0.0
    assert rel_l2_error(x, 2 * x) == pytest.approx(1.0)
    assert cosine_similarity(x, -x) == pytest.approx(-1.0)


# ---------------------------------------------------------------------------
# 整数量化
# ---------------------------------------------------------------------------


def test_symmetric_per_tensor_int8(weight):
    qt = quantize_tensor(weight, QuantConfig(bits=8))
    assert qt.zero_point == 0  # 对称量化 zero_point 恒为 0
    assert qt.q.min() >= -128 and qt.q.max() <= 127
    x_hat = qt.dequant()
    # per-tensor scale 是单个标量
    assert np.ndim(qt.scale) == 0
    assert x_hat.shape == weight.shape
    assert rel_l2_error(weight, x_hat) < 0.05


def test_asymmetric_uses_zero_point():
    x = np.abs(np.random.default_rng(0).standard_normal((32, 32)))
    qt = quantize_tensor(x, QuantConfig(bits=8, symmetric=False))
    assert np.all(qt.zero_point >= 0)  # 非负张量 zero_point >= 0
    x_hat = qt.dequant()
    assert rel_l2_error(x, x_hat) < 0.01


def test_per_channel_scale_shape(weight):
    # axis=0：沿输入维分条带 → 每个输出行一个 scale（标准 per-channel 权重量化）
    qt = quantize_tensor(
        weight, QuantConfig(bits=8, granularity="per_channel", axis=0)
    )
    assert qt.scale.shape == (1, 64)
    assert qt.q.shape == weight.shape


def test_per_channel_beats_per_tensor(weight):
    e_pt = rel_l2_error(
        weight, quantize_tensor(weight, QuantConfig(bits=8)).dequant()
    )
    e_pc = rel_l2_error(
        weight,
        quantize_tensor(
            weight, QuantConfig(bits=8, granularity="per_channel", axis=0)
        ).dequant(),
    )
    assert e_pc < e_pt


def test_groupwise_beats_per_channel(weight):
    e_pc = rel_l2_error(
        weight,
        quantize_tensor(
            weight, QuantConfig(bits=4, granularity="per_channel", axis=1)
        ).dequant(),
    )
    e_g32 = rel_l2_error(
        weight,
        quantize_tensor(
            weight,
            QuantConfig(bits=4, granularity="group_wise", group_size=32, axis=1),
        ).dequant(),
    )
    assert e_g32 < e_pc
    assert qt_group_shape_ok(weight)


def qt_group_shape_ok(weight) -> bool:
    qt = quantize_tensor(
        weight,
        QuantConfig(bits=4, granularity="group_wise", group_size=32, axis=1),
    )
    # 128 列 / 32 = 4 组，scale 布局 (64, 4, 1)
    return qt.scale.shape == (64, 4, 1) and qt.q.shape == weight.shape


def test_groupwise_remainder_padded():
    x = np.random.default_rng(1).standard_normal((8, 130))  # 130 = 2×64 + 2
    qt = quantize_tensor(
        x, QuantConfig(bits=8, granularity="group_wise", group_size=64, axis=1)
    )
    assert qt.scale.shape == (8, 3, 1)
    assert qt.dequant().shape == x.shape


def test_groupwise_axis0(weight):
    qt = quantize_tensor(
        weight.T,  # (128, 64)
        QuantConfig(bits=8, granularity="group_wise", group_size=16, axis=0),
    )
    assert qt.dequant().shape == (128, 64)
    assert rel_l2_error(weight.T, qt.dequant()) < 0.05


def test_quantize_deterministic(weight):
    cfg = QuantConfig(bits=4, granularity="group_wise", group_size=64, axis=1)
    q1 = quantize_tensor(weight, cfg).dequant()
    q2 = quantize_tensor(weight, cfg).dequant()
    np.testing.assert_array_equal(q1, q2)


def test_effective_bits_formula():
    cfg = QuantConfig(bits=4, granularity="group_wise", group_size=128)
    assert effective_bits_per_weight(cfg) == pytest.approx(4.125)
    cfg64 = QuantConfig(bits=4, granularity="group_wise", group_size=64)
    assert effective_bits_per_weight(cfg64) == pytest.approx(4.25)
    per_t = QuantConfig(bits=8)
    assert effective_bits_per_weight(per_t) == 8.0


# ---------------------------------------------------------------------------
# 浮点格式模拟
# ---------------------------------------------------------------------------


def test_float_quantize_e2m1_known_values():
    x = np.array([0.0, 0.1, 0.4, 0.5, 1.0, 1.5, 5.0, 6.0, -3.0], dtype=np.float32)
    y = float_quantize(x, 2, 1)
    expected = [0.0, 0.0, 0.5, 0.5, 1.0, 1.5, 4.0, 6.0, -3.0]
    np.testing.assert_allclose(y, expected, atol=0.0)


def test_float_quantize_e4m3_saturates():
    y = float_quantize(np.array([1000.0, -1000.0], dtype=np.float32), 4, 3)
    np.testing.assert_allclose(y, [448.0, -448.0], atol=0.0)


def test_float_format_range():
    lo, hi = float_format_range(4, 3)
    assert lo == pytest.approx(2.0**-6)  # E4M3 最小正规数
    assert hi == pytest.approx(448.0)
    lo2, hi2 = float_format_range(5, 2)
    assert hi2 == pytest.approx(57344.0)  # E5M2 最大有限值
    lo4, hi4 = float_format_range(2, 1)
    assert hi4 == pytest.approx(6.0)  # E2M1 最大有限值


# ---------------------------------------------------------------------------
# block-float（Microscaling）
# ---------------------------------------------------------------------------


def test_block_float_basics(weight):
    x_hat, info = block_float_quantize(weight, block_size=32, scale_kind="e8m0")
    assert x_hat.shape == weight.shape
    assert info["bits_per_elem"] == pytest.approx(4.25)  # 4 + 8/32
    assert rel_l2_error(weight, x_hat) < 0.3


def test_nvfp4_beats_mxfp4(weight):
    nvfp4, info_n = block_float_quantize(weight, block_size=16, scale_kind="e4m3")
    mxfp4, info_m = block_float_quantize(weight, block_size=32, scale_kind="e8m0")
    assert info_n["bits_per_elem"] == pytest.approx(4.5)
    assert info_m["bits_per_elem"] == pytest.approx(4.25)
    # NVFP4 scale 更细（E4M3 vs 2 的幂），精度更高
    assert rel_l2_error(weight, nvfp4) < rel_l2_error(weight, mxfp4)


def test_block_float_beats_bare_fp4(weight):
    bf, _ = block_float_quantize(weight, block_size=16, scale_kind="e4m3")
    bare = float_quantize(weight, 2, 1).astype(np.float64)
    assert rel_l2_error(weight, bf) < 0.2
    assert rel_l2_error(weight, bare) > 0.9  # 裸 E2M1 对 0.02 量级权重完全失效

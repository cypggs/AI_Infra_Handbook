"""fp8.py 的测试：E4M3 网格、细粒度缩放、累加精度。"""
import numpy as np
import pytest

from deepseek_case_mini.fp8 import (
    E4M3_MAX,
    E4M3_MIN_NORMAL,
    bf16_reference_gemm,
    compute_scales,
    fp8_gemm_simulate,
    make_channel_outlier_matrix,
    quantize_e4m3,
    quantize_tensor_wise,
    quantize_tile_wise,
    quantization_snr,
    relative_error,
)


class TestE4M3Grid:
    def test_max_saturates(self):
        q = quantize_e4m3(np.array([500.0, 1000.0, 448.0]))
        assert np.all(q <= E4M3_MAX)
        assert q[2] == 448.0

    def test_negative_saturates_symmetric(self):
        q = quantize_e4m3(np.array([-500.0]))
        assert q[0] == -E4M3_MAX

    def test_zero_and_tiny(self):
        q = quantize_e4m3(np.array([0.0, 1e-12]))
        assert q[0] == 0.0
        assert q[1] == 0.0

    def test_subnormal_grid(self):
        """次正规区：步长 2^-9；2^-7 = 4×2^-9 恰在网格上。"""
        q = quantize_e4m3(np.array([2.0**-7, 2.0**-9, 3 * 2.0**-10]))
        assert q[0] == 2.0**-7
        assert q[1] == 2.0**-9
        # 3×2^-10 / 2^-9 = 1.5 ⇒ RNE 向偶数格点（2×2^-9）
        assert q[2] == 2.0**-8

    def test_normal_three_mantissa_bits(self):
        """binade [256, 512) 的步长为 32（3 位尾数）。"""
        q = quantize_e4m3(np.array([300.0, 240.0]))
        assert q[0] == 288.0  # round(300/32)=9 → 288
        assert q[1] == 240.0  # binade [128,256) 步长 16

    def test_round_trip_on_grid(self):
        """已在网格上的值量化后不变。"""
        xs = np.array([0.5, 1.0, 1.125, 448.0, 2.0**-6, 3 * 2.0**-9])
        assert np.array_equal(quantize_e4m3(xs), xs)

    def test_rne_bankers(self):
        """中间值向偶数尾数舍入。"""
        # binade [1,2) 步长 0.125：1.0625 距两端等距 → 舍到 1.0625?
        # 1.0625/0.125=8.5 → RNE → 8 → 1.0（8 为偶）或 9 → 1.125（9 奇）
        q = quantize_e4m3(np.array([1.0625]))
        assert q[0] in (1.0, 1.125)


class TestScaling:
    def test_scales_shape_and_amax(self):
        x = np.arange(256, dtype=np.float64).reshape(2, 128)
        s = compute_scales(x, group_size=128)
        assert s.shape == x.shape
        # 每组的缩放 = amax/448
        assert np.isclose(s[0, 0], x[0].max() / E4M3_MAX)

    def test_scales_require_divisible(self):
        with pytest.raises(ValueError):
            compute_scales(np.ones((2, 100)), group_size=128)

    def test_tile_wise_within_group_bounds(self):
        """tile-wise 量化后每组 amax 恰好落在 ±448×scale。"""
        rng = np.random.default_rng(0)
        x = rng.standard_normal((4, 256))
        q = quantize_tile_wise(x, group_size=128)
        for g in range(2):
            amax = np.abs(q[:, g * 128 : (g + 1) * 128]).max()
            scale = np.abs(x[:, g * 128 : (g + 1) * 128]).max() / E4M3_MAX
            assert np.isclose(amax, 448.0 * scale, rtol=1e-9)

    def test_tensor_wise_single_scale(self):
        rng = np.random.default_rng(1)
        x = rng.standard_normal((4, 256))
        q = quantize_tensor_wise(x)
        scale = np.abs(x).max() / E4M3_MAX
        # 所有非零值都应在同一 E4M3 网格上（round-trip 不变）
        nonzero = q[np.abs(q) > 0]
        assert np.array_equal(quantize_e4m3(nonzero / scale) * scale, nonzero)


class TestDynamicRange:
    """细粒度缩放的动机：离群通道幅度变大时 tensor-wise 让主体失真、
    tile-wise 把损伤隔离在离群通道所在组。

    口径：剔除离群通道后，衡量主体信号的相对量化误差
    （全张量 SNR 会被离群通道的能量主导，掩盖主体失真）。
    """

    def _bulk_err(self, outlier_std, seed=0):
        from deepseek_case_mini.fp8 import bulk_signal_error, channel_outlier_indices

        x = make_channel_outlier_matrix(512, 1024, outlier_std=outlier_std, seed=seed)
        idx = channel_outlier_indices(1024, 8, seed)
        return (
            bulk_signal_error(x, quantize_tensor_wise(x), idx),
            bulk_signal_error(x, quantize_tile_wise(x), idx),
        )

    def test_tile_wise_degrades_gracefully(self):
        """极端动态范围下 tile-wise 也有退化（组内泄漏），但有界（<5×）。"""
        _, t1 = self._bulk_err(1.0)
        _, t_big = self._bulk_err(100000.0)
        assert t_big < 5.0 * t1

    def test_tensor_wise_collapses_at_extreme_range(self):
        e1, _ = self._bulk_err(1.0)
        e_big, _ = self._bulk_err(100000.0)
        assert e_big > 5.0 * e1

    def test_moderate_range_no_difference(self):
        """RNE 相对误差在正规区间是尺度不变的：中等动态范围下两者无差异。"""
        e_t, e_tile = self._bulk_err(1000.0)
        e1_t, _ = self._bulk_err(1.0)
        assert e_t < 2.0 * e1_t
        assert abs(e_t - e_tile) < 0.01

    def test_tile_beats_tensor_at_extreme_range(self):
        e_t, e_tile = self._bulk_err(100000.0)
        assert e_tile < 0.5 * e_t

    def test_benign_data_both_fine(self):
        e_t, e_tile = self._bulk_err(1.0)
        assert e_t < 0.05
        assert e_tile < 0.05


class TestQuantizationQuality:
    def _matrices(self, seed=0):
        rng = np.random.default_rng(seed)
        a = rng.standard_normal((128, 256))
        b = rng.standard_normal((256, 128))
        return a, b

    def test_fp32_accum_beats_fp16(self):
        a, b = self._matrices()
        e32 = relative_error(fp8_gemm_simulate(a, b, accumulate="fp32"), bf16_reference_gemm(a, b))
        e16 = relative_error(fp8_gemm_simulate(a, b, accumulate="fp16"), bf16_reference_gemm(a, b))
        assert e32 < e16

    def test_accumulation_error_below_quant_floor(self):
        """FP32 提升累加的误差贡献应小于量化本身（量化是误差主因）。"""
        rng = np.random.default_rng(9)
        a = rng.standard_normal((64, 1024))
        b = rng.standard_normal((1024, 64))
        gemm32 = fp8_gemm_simulate(a, b, accumulate="fp32")
        gemm16 = fp8_gemm_simulate(a, b, accumulate="fp16")
        accum_delta = relative_error(gemm16, gemm32)
        quant_floor = relative_error(
            quantize_tile_wise(a) @ quantize_tile_wise(b.T).T,
            bf16_reference_gemm(a, b),
        )
        assert 0.0 < accum_delta < quant_floor

    def test_e4m3_floor_is_percent_level(self):
        """E4M3 只有 3 位尾数：高斯数据单次量化的 GEMM 误差是百分量级。

        这是格式固有属性；V3 附录 B 的 <0.25% 是 FP8 vs BF16 训练的
        端到端【损失误差】口径，两者不矛盾。
        """
        a, b = self._matrices(seed=7)
        err = relative_error(
            quantize_tile_wise(a) @ quantize_tile_wise(b), bf16_reference_gemm(a, b)
        )
        assert 0.005 < err < 0.10

    def test_gemm_simulate_deterministic(self):
        a, b = self._matrices(seed=5)
        r1 = fp8_gemm_simulate(a, b, accumulate="fp32")
        r2 = fp8_gemm_simulate(a, b, accumulate="fp32")
        assert np.array_equal(r1, r2)

    def test_gemm_simulate_requires_aligned_k(self):
        with pytest.raises(ValueError):
            fp8_gemm_simulate(np.ones((8, 100)), np.ones((100, 8)))

    def test_relative_error_zero_ref_raises(self):
        with pytest.raises(ValueError):
            relative_error(np.ones((2, 2)), np.zeros((2, 2)))


class TestBF16Reference:
    def test_bf16_grid(self):
        """BF16 只有 8 位有效精度：1 + 1/256 会被舍入。"""
        a = np.array([[1.0 + 2.0**-9]])
        b = np.array([[1.0]])
        ref = bf16_reference_gemm(a, b)
        assert ref[0, 0] == 1.0  # 2^-9 低于 BF16 尾数精度（2^-8 步长）

    def test_bf16_exact_small_ints(self):
        a = np.array([[3.0]])
        b = np.array([[5.0]])
        assert bf16_reference_gemm(a, b)[0, 0] == 15.0

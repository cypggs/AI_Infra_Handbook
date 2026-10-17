"""S5 测试：权重水印嵌入/抽取/鲁棒性。"""

import numpy as np

from supply_security_mini.watermark import (
    _pattern_from_key,
    detect_watermark,
    embed_watermark,
    quantize,
    simulate_extraction,
    watermark_score,
)

KEY = b"owner-key"
STRENGTH = 0.05


def _weights() -> np.ndarray:
    return np.random.default_rng(7).normal(0.0, 0.02, size=4096)


class TestPattern:
    def test_deterministic(self):
        np.testing.assert_array_equal(
            _pattern_from_key(KEY, (64,)), _pattern_from_key(KEY, (64,))
        )

    def test_sign_pattern(self):
        pattern = _pattern_from_key(KEY, (128,))
        assert set(np.unique(pattern)) == {-1.0, 1.0}


class TestDetect:
    def test_marked_score_approx_strength(self):
        marked = embed_watermark(_weights(), KEY, STRENGTH)
        assert abs(watermark_score(marked, KEY) - STRENGTH) < 0.01

    def test_unmarked_score_near_zero(self):
        assert abs(watermark_score(_weights(), KEY)) < 0.01

    def test_detect_marked(self):
        marked = embed_watermark(_weights(), KEY, STRENGTH)
        assert detect_watermark(marked, KEY, STRENGTH).detected

    def test_wrong_key_not_detected(self):
        marked = embed_watermark(_weights(), KEY, STRENGTH)
        assert not detect_watermark(marked, b"attacker-key", STRENGTH).detected


class TestRobustness:
    def test_survives_quantization(self):
        marked = embed_watermark(_weights(), KEY, STRENGTH)
        assert detect_watermark(quantize(marked), KEY, STRENGTH).detected

    def test_survives_additive_noise(self):
        """独立加噪不改变相关期望，只增加方差。"""
        marked = embed_watermark(_weights(), KEY, STRENGTH)
        noisy = simulate_extraction(marked, noise_std=0.5)
        assert abs(watermark_score(noisy, KEY) - STRENGTH) < 0.02

    def test_survives_thief_rewatermark(self):
        """攻击者叠加水印不能抹去所有者水印。"""
        marked = embed_watermark(_weights(), KEY, STRENGTH)
        stolen = embed_watermark(marked, b"attacker-key", STRENGTH)
        assert detect_watermark(stolen, KEY, STRENGTH).detected

    def test_destroyed_by_coarse_rounding(self):
        """量化步长远大于 strength 时水印被抹除——强度必须超过发布量化步长。"""
        marked = embed_watermark(_weights(), KEY, STRENGTH)
        assert not detect_watermark(quantize(marked, decimals=0), KEY, STRENGTH).detected

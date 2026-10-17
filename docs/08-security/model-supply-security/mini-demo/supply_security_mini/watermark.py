"""S5：模型权重水印嵌入/抽取（确定性伪随机水印）。

玩具化实现学术 watermarking 的标准构造（Kirchenbauer et al. 2023 的权重版思路）：
- 水印 = 由 secret key 种子化生成的 ±1 伪随机模式，按强度叠加到权重上；
- 检测 = 计算 suspect 权重与同一模式的逐坐标均值相关（correlation）：
  未标记权重的期望相关为 0（模式与权重独立、零均值），标记权重的期望相关 = strength；
- 阈值 detection：correlation > strength / 2 判为"带水印"。

确定性：同一 key + 同一权重 → 同一模式、同一 score。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np

#: 检测阈值 = strength / DETECT_FRACTION
DETECT_FRACTION = 2.0


def _pattern_from_key(key: bytes, shape: tuple[int, ...]) -> np.ndarray:
    """从 key 确定性派生 ±1 伪随机模式（形状与权重相同）。"""
    seed = int.from_bytes(hashlib.sha256(key).digest()[:8], "little")
    rng = np.random.default_rng(seed)
    return rng.choice(np.array([-1.0, 1.0]), size=shape)


def embed_watermark(weights: np.ndarray, key: bytes, strength: float) -> np.ndarray:
    """叠加伪随机水印：w' = w + strength * pattern。"""
    pattern = _pattern_from_key(key, weights.shape)
    return weights + strength * pattern


def watermark_score(suspect: np.ndarray, key: bytes) -> float:
    """逐坐标相关：mean(suspect * pattern)。标记模型 ≈ strength，未标记 ≈ 0。"""
    pattern = _pattern_from_key(key, suspect.shape)
    return float(np.mean(suspect * pattern))


@dataclass
class DetectionResult:
    score: float
    threshold: float
    detected: bool


def detect_watermark(
    suspect: np.ndarray, key: bytes, strength: float
) -> DetectionResult:
    threshold = strength / DETECT_FRACTION
    score = watermark_score(suspect, key)
    return DetectionResult(score=score, threshold=threshold, detected=score > threshold)


def simulate_extraction(
    weights: np.ndarray, noise_std: float, seed: int = 42
) -> np.ndarray:
    """模拟攻击者微调/加噪抹除水印：权重 + 高斯噪声。"""
    rng = np.random.default_rng(seed)
    return weights + rng.normal(0.0, noise_std, size=weights.shape)


def quantize(weights: np.ndarray, decimals: int = 2) -> np.ndarray:
    """模拟权重量化发布（如 int8/fp16 导出的扰动近似）。"""
    return np.round(weights, decimals=decimals)

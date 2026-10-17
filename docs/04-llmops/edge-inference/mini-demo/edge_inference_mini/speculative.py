"""投机解码 / MTP（multi-token prediction）的接受率-加速比解析模型。

对应 llama.cpp 的 `--model-draft` 投机解码、GLM/DeepSeek 类 MTP 头、
Medusa/EAGLE 一族方法在端侧的落地评估。

模型（Leviathan et al., 2023 的标准几何分布假设）：

- draft 模型每步提议 γ 个候选 token，每个候选以独立概率 α 被 target 接受；
- 每步实际产出 token 数的期望 E = (1 - α^(γ+1)) / (1 - α)；
- 每步时间 ≈ 1 次 target 验证（内存受限，γ+1 个 token 并行验证的带宽
  与单 token 相当）+ γ 次 draft 推进（成本比 d）；
- 加速比 S = E / (1 + γ·d)。
"""

from __future__ import annotations


def expected_tokens_per_step(alpha: float, gamma: int) -> float:
    """一次验证循环平均产出的 token 数（含必然接受的那 1 个）。"""
    if not 0 < alpha <= 1:
        raise ValueError("alpha must be in (0, 1]")
    if gamma < 1:
        raise ValueError("gamma must be >= 1")
    if alpha == 1.0:
        return float(gamma + 1)
    return (1 - alpha ** (gamma + 1)) / (1 - alpha)


def speedup(alpha: float, gamma: int, draft_cost_ratio: float = 0.0) -> float:
    """端到端加速比。draft_cost_ratio = draft 单步时间 / target 单步时间。"""
    if draft_cost_ratio < 0:
        raise ValueError("draft_cost_ratio must be >= 0")
    e = expected_tokens_per_step(alpha, gamma)
    return e / (1 + gamma * draft_cost_ratio)


def best_gamma(alpha: float, draft_cost_ratio: float, max_gamma: int = 8) -> int:
    """在 1..max_gamma 中扫描使加速比最大的 γ。"""
    if max_gamma < 1:
        raise ValueError("max_gamma must be >= 1")
    return max(range(1, max_gamma + 1), key=lambda g: speedup(alpha, g, draft_cost_ratio))

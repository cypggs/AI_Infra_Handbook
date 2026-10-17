"""模型路由策略模拟：按查询复杂度选择大/小模型，量化成本-质量权衡。

对应主题章节：docs/09-case-study/perplexity/02-core-ideas（推理经济学）。
所有模型为确定性参数，无网络、无随机源。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class ModelTier:
    """一档推理模型。价格为每查询美元（简化报价，仅用于相对比较）。"""

    name: str
    quality: float             # 在"最优复杂度"处的期望答案质量（0-1）
    optimal_complexity: float  # 该模型最擅长的查询复杂度（0-1）
    cost_per_query: float      # 美元 / 查询
    ttft_s: float              # 首 token 延迟（秒）
    tokens_per_s: float        # 解码吞吐（token/s）

    def expected_quality(self, complexity: float) -> float:
        """质量随查询复杂度偏离最优点的衰减曲线（线性，截断在 0）。"""
        distance = abs(complexity - self.optimal_complexity)
        return max(0.0, self.quality * (1.0 - 0.6 * distance))

    def latency_s(self, output_tokens: int) -> float:
        return self.ttft_s + output_tokens / self.tokens_per_s


# 三档模型：参照 Sonar / Sonar Pro / Sonar Reasoning Pro 的公开定位
SMALL = ModelTier(
    name="small(Sonar 档)",
    quality=0.72,
    optimal_complexity=0.25,
    cost_per_query=0.0010,
    ttft_s=0.15,
    tokens_per_s=1200.0,   # Cerebras 官方口径：Sonar ~1200 tok/s
)
MEDIUM = ModelTier(
    name="medium(Sonar Pro 档)",
    quality=0.85,
    optimal_complexity=0.55,
    cost_per_query=0.0060,
    ttft_s=0.30,
    tokens_per_s=450.0,
)
LARGE = ModelTier(
    name="large(Reasoning 档)",
    quality=0.93,
    optimal_complexity=0.90,
    cost_per_query=0.0300,
    ttft_s=0.90,
    tokens_per_s=150.0,
)

TIERS: tuple[ModelTier, ...] = (SMALL, MEDIUM, LARGE)


def estimate_complexity(query: str) -> float:
    """从查询文本启发式估计复杂度（确定性、无模型）。

    规则：长度分（0-0.5）+ 任务词分（0-0.5）+ 疑问句分（0.1），截断到 [0, 1]。
    """
    q = query.strip().lower()
    length_score = min(len(q) / 120.0, 1.0) * 0.5
    hard_markers = (
        "为什么", "比较", "分析", "推导", "证明", "综述", "对比", "因果", "机制",
        "why", "compare", "analysis", "analyze", "derive", "prove", "versus",
        " vs ", "trade-off",
    )
    hits = sum(1 for m in hard_markers if m in q)
    marker_score = min(hits * 0.25, 0.5)
    question_score = 0.1 if q.endswith("？") or q.endswith("?") else 0.0
    return min(1.0, length_score + marker_score + question_score)


def route(query: str, tiers: tuple[ModelTier, ...] = TIERS,
          quality_floor: float = 0.0) -> ModelTier:
    """阈值路由：有质量下限选"满足下限的最便宜档"，否则选质量/成本性价比最高者。"""
    complexity = estimate_complexity(query)
    if quality_floor > 0.0:
        affordable = [t for t in tiers
                      if t.expected_quality(complexity) >= quality_floor]
        if affordable:
            return min(affordable, key=lambda t: t.cost_per_query)
    return max(tiers, key=lambda t: t.expected_quality(complexity) / t.cost_per_query)


def pareto_frontier(complexity: float,
                    tiers: tuple[ModelTier, ...] = TIERS
                    ) -> list[tuple[ModelTier, float, float]]:
    """返回 (模型, 期望质量, 每查询成本)，按成本升序——成本-质量权衡曲线。"""
    points = [(t, t.expected_quality(complexity), t.cost_per_query) for t in tiers]
    points.sort(key=lambda p: p[2])
    return points


def simulate_stream(n_queries: int,
                    complexity_fn: Callable[[int], float],
                    route_fn: Callable[[float], ModelTier],
                    tiers: tuple[ModelTier, ...] = TIERS) -> dict:
    """在确定性查询流上评估一种路由策略。"""
    total_cost = 0.0
    total_quality = 0.0
    per_tier: dict[str, int] = {}
    for i in range(n_queries):
        c = complexity_fn(i)
        tier = route_fn(c)
        total_cost += tier.cost_per_query
        total_quality += tier.expected_quality(c)
        per_tier[tier.name] = per_tier.get(tier.name, 0) + 1
    return {
        "n_queries": n_queries,
        "total_cost_usd": total_cost,
        "mean_quality": total_quality / n_queries,
        "per_tier": per_tier,
    }

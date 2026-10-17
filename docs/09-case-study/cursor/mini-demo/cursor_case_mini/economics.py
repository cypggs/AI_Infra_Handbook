"""订阅制推理经济学：token 成本 vs 月费盈亏平衡。

公开口径（cursor.com/blog/june-2025-pricing 及官方定价页）：
- Pro $20/月，含 $20 按 API 价计的用量额度（frontier 模型）
- $20 额度约等于 225 次 Sonnet 4 请求、550 次 Gemini 请求或 650 次 GPT-4.1
  请求（中位用量口径）
- Auto 模式（Router 调度）成本更低：官方 Router 博客口径 Auto Intelligence
  cost per commit $6.76 vs Fable 5 $12.69（约省 47%），博客另称相对同级
  frontier 模型约省 60%；Balance $4.63、Opus 4.8 $7.34

本模块：给定每请求 token 量与模型单价，复现官方盈亏平衡口径，并对比
固定订阅 vs 按量计费的毛利率敏感性。所有单价为教学取整值。
"""

from __future__ import annotations

from dataclasses import dataclass

# 教学单价（$/M token）：取公开 API 价数量级
MODEL_PRICES: dict[str, tuple[float, float]] = {
    #            输入 $/M   输出 $/M
    "sonnet_4": (3.0, 15.0),
    "gemini": (1.25, 10.0),
    "gpt_4.1": (2.0, 8.0),
}

# 中位请求 token 量（教学取整，对齐官方 225/550/650 次口径）
MEDIAN_TOKENS: dict[str, tuple[float, float]] = {
    "sonnet_4": (15_000.0, 3_000.0),
    "gemini": (4_000.0, 3_200.0),
    "gpt_4.1": (6_000.0, 2_400.0),
}

PRO_FEE = 20.0  # $/月
INCLUDED_USAGE = 20.0  # $ 额度


def request_cost(model: str) -> float:
    """单次请求成本（$），= in_tok * 输入价 + out_tok * 输出价。"""
    pin, pout = MODEL_PRICES[model]
    tin, tout = MEDIAN_TOKENS[model]
    return (tin * pin + tout * pout) / 1e6


def break_even_requests(model: str, budget: float = INCLUDED_USAGE) -> float:
    return budget / request_cost(model)


@dataclass
class MarginResult:
    requests: int
    revenue: float
    serving_cost: float
    margin_pct: float
    verdict: str


def monthly_margin(model: str, requests: int, fee: float = PRO_FEE) -> MarginResult:
    """订阅毛利率：收入固定为 fee，成本随请求数线性增长。"""
    cost = request_cost(model) * requests
    revenue = fee + max(0.0, cost - INCLUDED_USAGE) * 1.0  # 超额部分按成本价转售
    margin = (revenue - cost) / revenue * 100 if revenue > 0 else 0.0
    if requests <= break_even_requests(model):
        verdict = "盈利（额度内）"
    else:
        verdict = "亏损（补贴超额用户，靠长尾盈利用户对冲）"
    return MarginResult(
        requests=requests,
        revenue=round(revenue, 2),
        serving_cost=round(cost, 2),
        margin_pct=round(margin, 1),
        verdict=verdict,
    )


# Router 口径的 cost per commit（官方博客数字）
COST_PER_COMMIT: dict[str, float] = {
    "auto_intelligence": 6.76,
    "auto_balance": 4.63,
    "fable_5": 12.69,
    "opus_4.8": 7.34,
}


def routing_savings(mode: str = "auto_intelligence", baseline: str = "fable_5") -> float:
    """相对全量走 frontier 基线的成本节省比例。"""
    return (COST_PER_COMMIT[baseline] - COST_PER_COMMIT[mode]) / COST_PER_COMMIT[baseline] * 100.0


def tab_serving_cost_day(requests_per_day: float = 400e6, cost_per_m: float = 0.10) -> float:
    """Tab 档小模型推理日成本教学模型（单价 $/M token 请求折算）。

    官方口径：Tab 每天 4 亿+ 请求。真实成本结构未公开，此处只演示
    "免费不限量的 Tab 如何靠小模型 + 规模摊薄"的数量级关系。
    """
    return requests_per_day / 1e6 * cost_per_m

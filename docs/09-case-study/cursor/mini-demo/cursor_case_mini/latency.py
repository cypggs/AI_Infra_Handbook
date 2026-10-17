"""Tab 补全端到端延迟预算分解。

参照官方公开口径：Cursor 2025 年 1 月 Tab 模型更新把服务端延迟
从约 475 ms 降到约 260 ms（官方博客口径）。本模块把 260 ms 的教学预算
拆成客户端/网络/服务端各阶段，并用固定种子的对数正态抖动生成
确定性的 P50/P95 样本，演示"端到端延迟 = 各环节相加，优化大头环节"的方法论。

所有数值为教学预算，不代表 Cursor 内部真实分解。
"""

from __future__ import annotations

import numpy as np

# 教学预算（毫秒），合计 260 ms，对应官方 2025-01 更新后的服务端口径量级。
TAB_BUDGET: dict[str, float] = {
    "按键防抖与本地触发": 10.0,
    "上下文组装(光标邻域+最近编辑+打开文件)": 25.0,
    "本地缓存查询(KV/草稿缓存)": 2.0,
    "网络往返(TLS+RTT)": 40.0,
    "服务端排队与路由": 5.0,
    "Prefill(长上下文填充,预填 hungry)": 130.0,
    "首 token 解码": 30.0,
    "客户端渲染与预测显示": 10.0,
    "杂项(打点/序列化)": 8.0,
}

# 更新前口径：同结构下整体放大 475/260 倍，用于对照演示。
LEGACY_SCALE = 475.0 / 260.0


def total_ms(budget: dict[str, float] | None = None) -> float:
    return float(sum((budget or TAB_BUDGET).values()))


def legacy_budget() -> dict[str, float]:
    return {k: v * LEGACY_SCALE for k, v in TAB_BUDGET.items()}


def sample_end_to_end(n: int = 10_000, seed: int = 42) -> dict[str, float]:
    """用固定种子生成端到端延迟样本，返回 P50/P95/P99（毫秒）。

    每个阶段独立做对数正态抖动（sigma=0.15），保证确定性。
    """
    rng = np.random.default_rng(seed)
    samples = np.zeros(n, dtype=np.float64)
    for stage, base in TAB_BUDGET.items():
        jitter = rng.lognormal(mean=0.0, sigma=0.15, size=n)
        samples += base * jitter
    return {
        "mean": float(np.mean(samples)),
        "p50": float(np.percentile(samples, 50)),
        "p95": float(np.percentile(samples, 95)),
        "p99": float(np.percentile(samples, 99)),
    }


def top_stages(budget: dict[str, float] | None = None, k: int = 3) -> list[tuple[str, float]]:
    """按贡献排序的前 k 个阶段——优化建议永远从大头开始。"""
    b = budget or TAB_BUDGET
    return sorted(b.items(), key=lambda kv: kv[1], reverse=True)[:k]


def sensitivity(stage: str, saved_ms: float, budget: dict[str, float] | None = None) -> float:
    """若某阶段省下 saved_ms，端到端延迟下降百分比（假设其它阶段不变）。"""
    b = budget or TAB_BUDGET
    base = total_ms(b)
    after = base - min(saved_ms, b.get(stage, 0.0))
    return (base - after) / base * 100.0

"""Perplexity 案例研究 Mini Demo：答案引擎推理经济学。

5 个端到端场景：
  1. 成本-质量帕累托：三档模型在确定性查询流上的路由模拟
  2. 缓存收益：exact + 语义缓存的命中率与成本节省
  3. 流式感知延迟：TTFT 主导的用户感知时间
  4. 重排层权衡：NDCG@5 与检索延迟的折中曲线
  5. 一次查询的生命线：端到端延迟分解 + 推理经济学总账
"""

from __future__ import annotations

from . import caching, rerank, routing, streaming


def scenario_routing() -> dict:
    """场景 1：1000 条确定性查询流，三种路由策略对比。"""
    # 确定性复杂度流：50% 简单（0.1-0.3）、30% 中等（0.4-0.6）、20% 复杂（0.7-0.9）
    def complexity_fn(i: int) -> float:
        bucket = i % 10
        if bucket < 5:
            return 0.1 + 0.05 * (i % 4)
        if bucket < 8:
            return 0.4 + 0.05 * (i % 4)
        return 0.7 + 0.05 * (i % 4)

    strategies = {
        "全走小模型": lambda c: routing.SMALL,
        "全走大模型": lambda c: routing.LARGE,
    }

    def threshold_route(c: float):
        """按复杂度选档：满足质量下限 0.62 的最便宜档。"""
        affordable = [t for t in routing.TIERS if t.expected_quality(c) >= 0.62]
        return min(affordable, key=lambda t: t.cost_per_query) if affordable else routing.LARGE

    strategies["阈值路由(质量下限 0.62)"] = threshold_route

    results = {}
    for name, fn in strategies.items():
        r = routing.simulate_stream(1000, complexity_fn, fn)
        r["mean_quality"] = round(r["mean_quality"], 4)
        r["total_cost_usd"] = round(r["total_cost_usd"], 2)
        results[name] = r
    return results


def scenario_caching() -> dict:
    """场景 2：600 条查询流（40% 重复、20% 同义改写），缓存收益。"""
    templates = [
        ("kubernetes pod 状态 pending 原因", 0),
        ("vllm pagedattention 分页 注意力 原理", 60),
        ("mla 多头 潜在 注意力 机制", 120),
        ("rag 检索 质量 评估 指标", 180),
        ("推理 首 token 延迟 ttft 优化", 240),
        ("gpu 显存 带宽 算力 区别", 300),
    ]
    paraphrases = {
        "kubernetes pod 状态 pending 原因": "kubernetes pod 状态 pending 原因 排查",
        "vllm pagedattention 分页 注意力 原理": "vllm pagedattention 分页 注意力 原理 解释",
        "mla 多头 潜在 注意力 机制": "mla 多头 潜在 注意力 机制 详解",
        "rag 检索 质量 评估 指标": "rag 检索 质量 评估 指标 方法",
        "推理 首 token 延迟 ttft 优化": "推理 首 token 延迟 ttft 优化 手段",
        "gpu 显存 带宽 算力 区别": "gpu 显存 带宽 算力 区别 对比",
    }
    stream = []
    for i in range(600):
        tpl, base_t = templates[i % len(templates)]
        now = base_t + (i // len(templates)) * 8.0
        if i % 5 == 4:  # 20% 改写
            stream.append((paraphrases[tpl], now))
        else:
            stream.append((tpl, now))
    res = caching.simulate_traffic(stream, answer_cost=0.004,
                                   ttl_s=3600.0, semantic_threshold=0.85)
    for key in ("exact_hit_rate", "semantic_hit_rate", "total_hit_rate", "savings_pct"):
        res[key] = round(res[key], 4)
    return res


def scenario_streaming() -> dict:
    """场景 3：Sonar 档 vs Reasoning 档的流式感知延迟。"""
    sonar = streaming.StreamConfig(ttft_s=0.15, tokens_per_s=1200.0, chunk_size=8)
    reasoning = streaming.StreamConfig(ttft_s=0.90, tokens_per_s=150.0, chunk_size=8)
    out = {}
    for name, cfg in (("Sonar 档(1200 tok/s)", sonar),
                      ("Reasoning 档(150 tok/s)", reasoning)):
        full = streaming.perceived_latency_nonstreaming(cfg, 400)
        first100 = streaming.perceived_latency_streaming(cfg, 400, read_tokens=100)
        out[name] = {
            "ttft_s": cfg.ttft_s,
            "nonstream_full_s": round(full, 2),
            "stream_first100_s": round(first100, 2),
            "speedup_first100x": round(full / first100, 2),
            "ttft_share_of_full": round(cfg.ttft_s / full, 4),
        }
    sens = streaming.sensitivity(sonar, n_tokens=400, read_tokens=100)
    out["敏感性(Sonar 档, 读 100 token)"] = {
        k: round(v, 4) for k, v in sens.items()
    }
    return out


def scenario_rerank() -> dict:
    """场景 4：重排候选池扫描与质量-延迟权衡。"""
    true_rel, ids = rerank.build_corpus(seed=42)
    base = rerank.pipeline_ndcg(true_rel, top_k=5, use_rerank=False, seed=42)
    reranked = rerank.pipeline_ndcg(true_rel, top_k=24, use_rerank=True, seed=42)
    curve = rerank.sweep_pool_size(true_rel, pool_sizes=[5, 8, 12, 16, 24], seed=42)
    return {
        "n_docs": len(ids),
        "ndcg5_no_rerank_top5": round(base, 4),
        "ndcg5_rerank_pool24": round(reranked, 4),
        "latency_ms_no_rerank": rerank.latency_model(5, use_rerank=False),
        "latency_ms_rerank_pool24": rerank.latency_model(24),
        "curve": curve,
    }


def scenario_lifecycle() -> dict:
    """场景 5：一次查询的生命线——端到端延迟分解与成本总账。"""
    # 延迟预算（毫秒，参照公开口径的合成值）
    stages = [
        ("查询理解与路由", 5.0),
        ("缓存查询(exact+语义)", 2.0),
        ("检索召回(Photon 量级 p99)", 65.0),
        ("重排(top-24)", 48.0),
        ("首次生成 TTFT(Sonar)", 150.0),
        ("流式解码 300 token @1200 tok/s", 250.0),
        ("引用渲染与后处理", 30.0),
    ]
    total_ms = sum(ms for _, ms in stages)
    econ = {
        "answer_engine_usd_per_1k": 4.30,       # 路由+重排+生成混合策略
        "naive_all_large_usd_per_1k": 30.00,    # 全部走大模型
    }
    econ["savings_pct"] = round(
        (1 - econ["answer_engine_usd_per_1k"] / econ["naive_all_large_usd_per_1k"]) * 100, 1)
    return {
        "stages": stages,
        "total_ms": total_ms,
        "cost_accounting": econ,
    }


def main() -> None:
    print("=" * 64)
    print("场景 1：成本-质量帕累托（1000 条确定性查询流）")
    print("=" * 64)
    for name, r in scenario_routing().items():
        print(f"{name}: 成本 ${r['total_cost_usd']:.2f}, "
              f"平均质量 {r['mean_quality']:.4f}, 分发 {r['per_tier']}")

    print()
    print("=" * 64)
    print("场景 2：缓存收益（600 条查询流，40% 重复 + 20% 同义改写）")
    print("=" * 64)
    r = scenario_caching()
    print(f"查询总数 {r['n_queries']}: exact 命中 {r['n_exact']}，"
          f"语义命中 {r['n_semantic']}，未命中 {r['n_miss']}")
    print(f"exact 命中率 {r['exact_hit_rate']:.2%}，语义命中率 {r['semantic_hit_rate']:.2%}，"
          f"总命中率 {r['total_hit_rate']:.2%}")
    print(f"成本 ${r['cost_usd']:.2f}（无缓存基线 ${r['baseline_cost_usd']:.2f}），"
          f"节省 {r['savings_pct']:.2f}%")

    print()
    print("=" * 64)
    print("场景 3：流式感知延迟（400 token 答案）")
    print("=" * 64)
    for name, d in scenario_streaming().items():
        if "敏感性" in name:
            print(f"{name}: 基线 {d['base_s']:.4f}s，TTFT+10% -> {d['ttft_plus10pct_s']:.4f}s，"
                  f"吞吐-10% -> {d['tput_minus10pct_s']:.4f}s，TTFT 占比 {d['ttft_share']:.2%}")
        else:
            print(f"{name}: 非流式整段 {d['nonstream_full_s']:.2f}s，"
                  f"流式读到 100 token {d['stream_first100_s']:.2f}s，"
                  f"感知加速 {d['speedup_first100x']:.2f}x，"
                  f"TTFT 占整段 {d['ttft_share_of_full']:.2%}")

    print()
    print("=" * 64)
    print("场景 4：重排层效果与延迟权衡（24 文档合成语料）")
    print("=" * 64)
    r = scenario_rerank()
    print(f"不重排(top-5 直接截断): NDCG@5={r['ndcg5_no_rerank_top5']:.4f}，"
          f"延迟 {r['latency_ms_no_rerank']:.0f}ms")
    print(f"重排(召回 24 -> 截 5): NDCG@5={r['ndcg5_rerank_pool24']:.4f}，"
          f"延迟 {r['latency_ms_rerank_pool24']:.0f}ms")
    for row in r["curve"]:
        print(f"  候选池 {row['pool']:>2}: NDCG@5={row['ndcg5']:.4f}，"
              f"延迟 {row['latency_ms']:.0f}ms")

    print()
    print("=" * 64)
    print("场景 5：一次查询的生命线（端到端延迟分解 + 成本总账）")
    print("=" * 64)
    r = scenario_lifecycle()
    for stage, ms in r["stages"]:
        print(f"  {stage:<34} {ms:6.0f} ms")
    print(f"  {'合计':<34} {r['total_ms']:6.0f} ms")
    c = r["cost_accounting"]
    print(f"推理经济学：混合策略 ${c['answer_engine_usd_per_1k']:.2f}/千次，"
          f"全大模型基线 ${c['naive_all_large_usd_per_1k']:.2f}/千次，"
          f"节省 {c['savings_pct']:.1f}%")


if __name__ == "__main__":
    main()

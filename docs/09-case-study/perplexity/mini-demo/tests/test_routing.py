"""routing 模块测试。"""

from perplexity_case_mini import routing


def test_estimate_complexity_bounds():
    for q in ["", "hi", "a" * 500, "为什么 为什么 为什么 为什么 为什么 为什么?"]:
        c = routing.estimate_complexity(q)
        assert 0.0 <= c <= 1.0


def test_simple_query_low_complexity():
    assert routing.estimate_complexity("巴黎 天气") < 0.2


def test_compare_query_high_complexity():
    q = ("请比较 vllm 与 sglang 在吞吐、显存占用与调度策略上的差异，"
         "并分析为什么 compare 分析")
    assert routing.estimate_complexity(q) > 0.5


def test_question_suffix_adds_score():
    base = routing.estimate_complexity("kubernetes pod pending")
    with_q = routing.estimate_complexity("kubernetes pod pending?")
    assert with_q > base


def test_quality_at_optimum():
    assert routing.SMALL.expected_quality(0.25) == 0.72
    assert routing.MEDIUM.expected_quality(0.55) == 0.85
    assert routing.LARGE.expected_quality(0.90) == 0.93


def test_quality_decays_with_distance():
    assert (routing.SMALL.expected_quality(0.55)
            < routing.SMALL.expected_quality(0.35))
    assert (routing.SMALL.expected_quality(0.35)
            < routing.SMALL.expected_quality(0.25))


def test_quality_at_extreme_complexity():
    # 最优点 0.25，复杂度 0 处质量 = 0.72 * (1 - 0.6*0.25)
    assert abs(routing.SMALL.expected_quality(0.0) - 0.612) < 1e-9


def test_latency_formula():
    cfg = routing.SMALL
    assert abs(cfg.latency_s(600) - (0.15 + 600 / 1200.0)) < 1e-9


def test_route_with_floor_picks_cheapest_affordable():
    # 长度 ≥120、无任务词：复杂度 0.5。
    # small 质量 0.612 < 0.62 不满足，medium（0.8245）满足且比 large 便宜。
    q = "x " * 61  # 归一化后 122 字符，长度分满档 0.5，复杂度恰为 0.5
    c = routing.estimate_complexity(q)
    assert c == 0.5
    tier = routing.route(q, quality_floor=0.62)
    assert tier is routing.MEDIUM


def test_route_floor_direct():
    # 复杂度被截断到 1.0：small/medium 均接近失效，large 兜底。
    q = "为什么 compare 分析 推导 versus 证明 综述 对比 因果 机制"
    c = routing.estimate_complexity(q)
    assert c >= 0.5
    tier = routing.route(q, quality_floor=0.62)
    assert tier.expected_quality(c) >= 0.62 or tier is routing.LARGE


def test_route_default_best_ratio():
    tier = routing.route("任意查询")
    best = max(routing.TIERS,
               key=lambda t: t.expected_quality(
                   routing.estimate_complexity("任意查询")) / t.cost_per_query)
    assert tier is best


def test_pareto_frontier_sorted_by_cost():
    points = routing.pareto_frontier(0.5)
    costs = [p[2] for p in points]
    assert costs == sorted(costs)
    assert len(points) == 3


def test_simulate_stream_all_small():
    r = routing.simulate_stream(1000, lambda i: 0.2, lambda c: routing.SMALL)
    assert abs(r["total_cost_usd"] - 1.0) < 1e-6
    assert r["per_tier"]["small(Sonar 档)"] == 1000
    assert abs(r["mean_quality"] - routing.SMALL.expected_quality(0.2)) < 1e-9

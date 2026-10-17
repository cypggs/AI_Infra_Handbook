from cursor_case_mini.economics import (
    COST_PER_COMMIT,
    INCLUDED_USAGE,
    MEDIAN_TOKENS,
    MODEL_PRICES,
    break_even_requests,
    monthly_margin,
    request_cost,
    routing_savings,
    tab_serving_cost_day,
)


class TestCost:
    def test_cost_positive(self):
        for m in MODEL_PRICES:
            assert request_cost(m) > 0

    def test_cost_formula(self):
        pin, pout = MODEL_PRICES["sonnet_4"]
        tin, tout = MEDIAN_TOKENS["sonnet_4"]
        expected = (tin * pin + tout * pout) / 1e6
        assert abs(request_cost("sonnet_4") - expected) < 1e-12

    def test_official_magnitude_alignment(self):
        # 官方口径：$20 约 225 次 Sonnet 4 / 550 次 Gemini / 650 次 GPT-4.1
        assert abs(break_even_requests("sonnet_4") - 225) <= 12
        assert abs(break_even_requests("gemini") - 550) <= 27
        assert abs(break_even_requests("gpt_4.1") - 650) <= 32

    def test_sonnet_most_expensive(self):
        assert request_cost("sonnet_4") > request_cost("gemini")
        assert request_cost("sonnet_4") > request_cost("gpt_4.1")


class TestMargin:
    def test_light_user_profitable(self):
        r = monthly_margin("sonnet_4", 100)
        assert r.margin_pct > 0
        assert "盈利" in r.verdict

    def test_heavy_user_below_water(self):
        r = monthly_margin("sonnet_4", 600)
        assert r.serving_cost > INCLUDED_USAGE
        assert "亏损" in r.verdict

    def test_revenue_never_below_fee(self):
        r = monthly_margin("sonnet_4", 10_000)
        assert r.revenue >= 20.0

    def test_margin_monotonic_in_usage(self):
        margins = [monthly_margin("sonnet_4", n).margin_pct for n in (50, 200, 400, 800)]
        assert all(margins[i] >= margins[i + 1] for i in range(3))
        assert margins[0] > margins[-1]  # 重度用户毛利率单调恶化

    def test_break_even_is_zero_margin_point(self):
        be = int(break_even_requests("gpt_4.1"))
        below = monthly_margin("gpt_4.1", be - 1)
        assert "盈利" in below.verdict


class TestRouting:
    def test_intelligence_savings_official_magnitude(self):
        # 官方 Router 博客 cost-per-commit 表：vs Fable 5 约省 47%
        assert abs(routing_savings() - 46.7) < 0.5

    def test_balance_positive(self):
        assert routing_savings("auto_balance", "fable_5") > 0

    def test_commit_costs_present(self):
        assert set(COST_PER_COMMIT) == {"auto_intelligence", "auto_balance", "fable_5", "opus_4.8"}


class TestTab:
    def test_daily_cost_scales(self):
        assert tab_serving_cost_day(400e6, 0.10) == 40.0
        assert tab_serving_cost_day(800e6, 0.10) == 80.0

    def test_daily_cost_positive(self):
        assert tab_serving_cost_day() > 0

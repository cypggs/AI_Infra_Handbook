"""投机解码/MTP：接受率-加速比解析模型。"""

import pytest

from edge_inference_mini.speculative import (
    best_gamma,
    expected_tokens_per_step,
    speedup,
)


class TestExpectedTokens:
    def test_alpha_one_all_accepted(self):
        # α=1 时 γ 个 draft 全部接受 + 必然产出的 1 个 = γ+1
        assert expected_tokens_per_step(1.0, 4) == pytest.approx(5.0)

    def test_geometric_series(self):
        # α=0.75, γ=4: (1-0.75^5)/0.25
        assert expected_tokens_per_step(0.75, 4) == pytest.approx((1 - 0.75**5) / 0.25)
        assert expected_tokens_per_step(0.75, 4) == pytest.approx(3.0508, abs=1e-4)

    def test_more_drafts_monotonic_up(self):
        a = expected_tokens_per_step(0.7, 2)
        b = expected_tokens_per_step(0.7, 6)
        assert b > a

    def test_alpha_bounds(self):
        with pytest.raises(ValueError):
            expected_tokens_per_step(0.0, 4)
        with pytest.raises(ValueError):
            expected_tokens_per_step(0.75, 0)


class TestSpeedup:
    def test_no_draft_cost(self):
        # draft 免费时加速比 = E / 1
        assert speedup(0.75, 4, 0.0) == pytest.approx(expected_tokens_per_step(0.75, 4))

    def test_demo_numbers(self):
        s = speedup(0.75, 4, draft_cost_ratio=0.15)
        assert s == pytest.approx(3.0508 / 1.6, abs=1e-3)
        assert s == pytest.approx(1.91, abs=0.01)

    def test_low_acceptance_below_one(self):
        # α=0.3 且 draft 不便宜时加速比 < 1（投机反而变慢）
        assert speedup(0.3, 4, draft_cost_ratio=0.3) < 1.0

    def test_negative_cost_rejected(self):
        with pytest.raises(ValueError):
            speedup(0.75, 4, draft_cost_ratio=-0.1)


class TestBestGamma:
    def test_picks_max_in_range(self):
        g = best_gamma(0.8, 0.1, max_gamma=8)
        assert 1 <= g <= 8
        assert speedup(0.8, g, 0.1) == max(speedup(0.8, gg, 0.1) for gg in range(1, 9))

    def test_cheap_draft_likes_long_gamma(self):
        assert best_gamma(0.9, 0.05) >= best_gamma(0.9, 0.4)

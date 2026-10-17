from cursor_case_mini.latency import (
    TAB_BUDGET,
    legacy_budget,
    sample_end_to_end,
    sensitivity,
    top_stages,
    total_ms,
)


class TestBudget:
    def test_total_is_260ms(self):
        assert total_ms() == 260.0

    def test_all_stages_positive(self):
        assert all(v > 0 for v in TAB_BUDGET.values())

    def test_legacy_total_matches_475(self):
        assert abs(total_ms(legacy_budget()) - 475.0) < 1e-6

    def test_legacy_is_scaled_version(self):
        for k in TAB_BUDGET:
            assert abs(legacy_budget()[k] / TAB_BUDGET[k] - 475.0 / 260.0) < 1e-9

    def test_top_stage_is_prefill(self):
        assert top_stages(k=1)[0][0].startswith("Prefill")

    def test_top3_cover_majority(self):
        covered = sum(v for _, v in top_stages(k=3))
        assert covered / total_ms() > 0.6


class TestSensitivity:
    def test_saving_biggest_stage_matters_most(self):
        prefill_saving = sensitivity("Prefill(长上下文填充,预填 hungry)", 50)
        render_saving = sensitivity("客户端渲染与预测显示", 50)
        assert prefill_saving > render_saving

    def test_saving_capped_at_stage_value(self):
        s = sensitivity("本地缓存查询(KV/草稿缓存)", 100)
        assert abs(s - 2.0 / 260.0 * 100) < 1e-9  # 只能省掉该阶段全部 2ms

    def test_zero_saving_no_change(self):
        assert sensitivity("网络往返(TLS+RTT)", 0) == 0.0


class TestSamples:
    def test_deterministic(self):
        a = sample_end_to_end()
        b = sample_end_to_end()
        assert a == b

    def test_percentile_ordering(self):
        s = sample_end_to_end()
        assert s["p50"] <= s["p95"] <= s["p99"]

    def test_p50_near_deterministic_sum(self):
        s = sample_end_to_end(n=20_000, seed=1)
        assert abs(s["p50"] - 260.0) / 260.0 < 0.05

    def test_p95_above_p50(self):
        s = sample_end_to_end()
        assert s["p95"] > s["p50"]

    def test_seed_changes_distribution(self):
        a = sample_end_to_end(seed=1)
        b = sample_end_to_end(seed=2)
        assert a != b

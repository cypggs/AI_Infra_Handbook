from cursor_case_mini.speculative import ApplyEngine, VERIFY_BATCH, scan_edit_rate, simulate_edit


class TestSimulate:
    def test_deterministic(self):
        a = simulate_edit(2048, 0.05)
        b = simulate_edit(2048, 0.05)
        assert a == b

    def test_hit_rate_bounds(self):
        s = simulate_edit(4096, 0.1)
        assert 0.0 < s["hit_rate"] < 1.0

    def test_lower_edit_rate_higher_hit(self):
        low = simulate_edit(4096, 0.02)
        high = simulate_edit(4096, 0.30)
        assert low["hit_rate"] > high["hit_rate"]

    def test_speedup_above_1(self):
        s = simulate_edit(8192, 0.05)
        assert s["speedup"] > 1.0

    def test_lower_edit_rate_higher_speedup(self):
        low = simulate_edit(8192, 0.02)
        high = simulate_edit(8192, 0.40)
        assert low["speedup"] > high["speedup"]

    def test_token_accounting(self):
        s = simulate_edit(2048, 0.1)
        assert s["n_changed"] + s["n_verified"] == s["n_tokens"]

    def test_zero_edit_rate_pure_verification(self):
        s = simulate_edit(2048, 0.0)
        assert s["hit_rate"] == 1.0
        assert s["gen_steps"] == 0
        assert s["speedup"] == VERIFY_BATCH

    def test_full_rewrite_no_verification(self):
        s = simulate_edit(2048, 1.0)
        assert s["hit_rate"] == 0.0
        assert s["speedup"] == 1.0

    def test_seed_changes_outcome(self):
        a = simulate_edit(4096, 0.1, seed=1)
        b = simulate_edit(4096, 0.1, seed=2)
        assert a["n_changed"] != b["n_changed"]


class TestEngine:
    def test_official_magnitude_alignment(self):
        # 5% 改动率加速比代入 75 tok/s 应落在官方 ~1000 tok/s 附近
        s = simulate_edit(8192, 0.05, seed=7)
        eng = ApplyEngine()
        assert 900 < eng.fast_apply_tps(s["speedup"]) < 1100

    def test_wall_time_decreases_with_speedup(self):
        eng = ApplyEngine()
        assert eng.edit_wall_time_ms(8192, 10.0) < eng.edit_wall_time_ms(8192, 2.0)

    def test_wall_time_scales_linearly(self):
        eng = ApplyEngine()
        assert abs(eng.edit_wall_time_ms(16384, 5.0) - 2 * eng.edit_wall_time_ms(8192, 5.0)) < 1e-9


class TestScan:
    def test_five_rates(self):
        rows = scan_edit_rate()
        assert len(rows) == 5

    def test_monotonic_decreasing(self):
        rows = scan_edit_rate()
        hits = [h for _, h, _ in rows]
        assert all(hits[i] > hits[i + 1] for i in range(len(hits) - 1))

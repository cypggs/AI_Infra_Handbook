from kv_cache_mini.demo import (
    kv_bytes_per_token,
    run_demo,
    scenario_block_allocator,
    scenario_kv_economics,
    scenario_pd_migration,
    scenario_radix_prefix,
    scenario_tiered_cache,
)


class TestKVEconomics:
    def test_bytes_per_token_fp16_llama70b_like(self):
        # 80 层 × 8 kv heads × 128 dim × 2(K,V) × 2 字节 = 320 KiB
        assert kv_bytes_per_token(80, 8, 128, 2) == 2 * 80 * 8 * 128 * 2

    def test_fp8_halves_fp16(self):
        fp16 = kv_bytes_per_token(80, 8, 128, 2)
        fp8 = kv_bytes_per_token(80, 8, 128, 1)
        assert fp8 * 2 == fp16

    def test_economics_scenario_values(self):
        result = scenario_kv_economics()
        assert result["bytes_per_token_fp16"] == 327680
        assert result["bytes_per_token_fp8"] == 163840
        assert result["bytes_per_token_int4"] == 81920
        assert result["gib_per_seq_128k_fp16"] == 40.0


class TestScenarios:
    def test_block_allocator_scenario(self):
        r = scenario_block_allocator()
        assert r["copies"] == 1            # fork 后写一次触发一次 COW
        assert r["evictions"] == 1
        assert r["num_free_after"] == 0

    def test_radix_prefix_scenario(self):
        r = scenario_radix_prefix()
        assert r["hit_a"] == 0             # 首条无命中
        assert r["hit_b"] == 64            # 第二条命中整个系统提示
        assert r["hit_new"] == 64          # 任意新请求都命中系统提示
        assert r["tokens_cached"] == 64 + 3 + 2  # 公共段 64 + 两条分叉叶子

    def test_tiered_cache_scenario_saves_time(self):
        r = scenario_tiered_cache()
        assert r["hit_rate"] > 0.5
        assert r["savings_s"] > 0

    def test_pd_migration_scenario_overlap(self):
        r = scenario_pd_migration()
        assert r["pipelined_ttft_ms"] < r["sequential_ttft_ms"]
        assert r["overlap_gain_ms"] > 0


class TestRunDemo:
    def test_run_demo_returns_all_scenarios(self, capsys):
        result = run_demo()
        assert set(result) == {
            "1_block_allocator",
            "2_radix_prefix",
            "3_tiered_cache",
            "4_pd_migration",
            "5_kv_economics",
        }
        out = capsys.readouterr().out
        assert "5_kv_economics" in out

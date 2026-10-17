"""内存模型：权重字节数、KV 每 token 字节数、decode 吞吐、上下文规划。"""

import pytest

from edge_inference_mini.memory import (
    GIB,
    decode_bytes_per_token,
    decode_tokens_per_s,
    kv_budget_bytes,
    kv_bytes_per_token,
    max_context_len,
    quant_plan,
    weight_bytes,
)


class TestWeightBytes:
    def test_fp16_no_overhead(self):
        # 8e9 参数 × 16 bit / 8 = 16 GB
        assert weight_bytes(8e9, 16.0, overhead=0.0) == 16_000_000_000

    def test_q4_overhead(self):
        # 8 GB 名义 + 8% 元数据 = 8.64 GB
        assert weight_bytes(8e9, 8.0, overhead=0.08) == 8_640_000_000

    def test_invalid_bits(self):
        with pytest.raises(ValueError):
            weight_bytes(8e9, 0.0)


class TestKVBytes:
    def test_llama3_8b_fp16(self):
        # 2 × 32 层 × 8 KV 头 × 128 dim × 2 B = 131072 B
        assert kv_bytes_per_token(32, 8, 128, 2) == 131_072

    def test_mqa_kv_heads_one(self):
        assert kv_bytes_per_token(32, 1, 128, 2) == 16_384

    def test_invalid_dims(self):
        with pytest.raises(ValueError):
            kv_bytes_per_token(0, 8, 128)


class TestDecode:
    def test_bytes_per_token_adds_kv(self):
        assert decode_bytes_per_token(1000, 100, 5) == 1500

    def test_tokens_per_s_formula(self):
        # 68 GB/s × 0.85 / 5.18 GB ≈ 11.16
        t = decode_tokens_per_s(68.0, 5.18e9, 0.85)
        assert t == pytest.approx(11.1583, rel=1e-3)

    def test_double_bandwidth_double_tps(self):
        a = decode_tokens_per_s(68.0, 5e9)
        b = decode_tokens_per_s(136.0, 5e9)
        assert b == pytest.approx(2 * a)

    def test_utilization_bounds(self):
        with pytest.raises(ValueError):
            decode_tokens_per_s(68.0, 5e9, utilization=1.5)


class TestCapacity:
    def test_budget_positive(self):
        assert kv_budget_bytes(8.0, 0.8, 4.9) == int((8.0 - 0.8 - 4.9) * GIB)

    def test_budget_zero_when_full(self):
        assert kv_budget_bytes(8.0, 0.8, 8.0) == 0

    def test_max_context_floor(self):
        assert max_context_len(131_073, 131_072) == 1

    def test_quant_plan_halving(self):
        plan = quant_plan(32, 8, 128, 8.0, 0.8, 4.9)
        assert plan["fp16"]["bytes_per_token"] == 131_072
        assert plan["int8"]["bytes_per_token"] == 65_536
        assert plan["int4"]["bytes_per_token"] == 32_768
        assert plan["int8"]["max_context"] == 2 * plan["fp16"]["max_context"] or \
            plan["int8"]["max_context"] == 2 * plan["fp16"]["max_context"] + 1
        assert plan["int4"]["max_context"] >= 4 * plan["fp16"]["max_context"] - 4

    def test_quant_plan_matches_demo(self):
        # 与 demo 场景 2 输出逐字一致
        w_gib = weight_bytes(8e9, 4.8, overhead=0.08) / GIB
        plan = quant_plan(32, 8, 128, 8.0, 0.8, w_gib)
        assert plan["fp16"]["max_context"] == 19_431
        assert plan["int8"]["max_context"] == 38_863
        assert plan["int4"]["max_context"] == 77_726

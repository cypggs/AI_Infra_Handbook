import math

from multimodal_inference_mini.codec import (
    ENCODEC_1_5K,
    ENCODEC_6K,
    MIMI,
    CodecSpec,
    compare_codecs,
    kv_growth_per_minute,
    streaming_chunk_plan,
)


class TestCodecSpec:
    def test_mimi_derived_numbers(self):
        assert MIMI.tokens_per_second == 100.0
        assert MIMI.bits_per_token == 11
        assert MIMI.bit_rate == 1100.0
        assert MIMI.frame_latency_ms == 80.0

    def test_encodec_6k_bitrate(self):
        assert ENCODEC_6K.tokens_per_second == 600.0
        assert ENCODEC_6K.bits_per_token == 10
        assert ENCODEC_6K.bit_rate == 6000.0

    def test_encodec_1_5k_is_quieter(self):
        assert ENCODEC_1_5K.bit_rate < ENCODEC_6K.bit_rate
        assert ENCODEC_1_5K.tokens_per_second == 150.0

    def test_tokens_for_duration_rounds_up(self):
        assert MIMI.tokens_for_duration(1.0) == 100
        assert MIMI.tokens_for_duration(0.5) == 50
        assert MIMI.tokens_for_duration(0.001) == 1

    def test_semantic_subset(self):
        assert MIMI.semantic_tokens_for_duration(10.0) == 250
        assert ENCODEC_6K.semantic_tokens_for_duration(10.0) == 0

    def test_seconds_for_tokens_inverse(self):
        assert math.isclose(MIMI.seconds_for_tokens(100), 1.0)
        assert MIMI.seconds_for_tokens(0) == 0.0

    def test_negative_duration_rejected(self):
        import pytest

        with pytest.raises(ValueError):
            MIMI.tokens_for_duration(-1)

    def test_bits_grow_with_codebook_size(self):
        small = CodecSpec("s", 24000, 12.5, 8, 256)
        big = CodecSpec("b", 24000, 12.5, 8, 4096)
        assert small.bits_per_token == 8
        assert big.bits_per_token == 12


class TestCompare:
    def test_compare_codecs_rows(self):
        rows = compare_codecs([MIMI, ENCODEC_6K], seconds=60.0)
        assert [r["name"] for r in rows] == ["mimi", "encodec_6k"]
        assert rows[0]["tokens"] == 6000
        assert rows[1]["tokens"] == 36000

    def test_kv_growth_ratio(self):
        growth = kv_growth_per_minute([MIMI], text_tokens_per_minute=200.0)
        assert growth["mimi"] == 30.0  # 6000 audio tokens vs 200 text tokens

    def test_kv_growth_scaling(self):
        growth = kv_growth_per_minute([MIMI], text_tokens_per_minute=100.0)
        assert growth["mimi"] == 60.0


class TestStreaming:
    def test_chunk_plan_full_minute(self):
        chunks = streaming_chunk_plan(MIMI, seconds=1.0, chunk_ms=80.0)
        assert len(chunks) == 13  # 12 full 80ms chunks + 1 partial (40ms)
        assert chunks[-1][2] == 4  # 0.04s * 100 tok/s -> 4 tokens
        assert sum(c[2] for c in chunks) == MIMI.tokens_for_duration(1.0)

    def test_chunk_plan_covers_duration(self):
        chunks = streaming_chunk_plan(ENCODEC_6K, seconds=0.25, chunk_ms=100.0)
        assert chunks[-1][1] == 0.25
        assert sum(c[2] for c in chunks) == ENCODEC_6K.tokens_for_duration(0.25)

    def test_chunk_plan_rejects_bad_chunk(self):
        import pytest

        with pytest.raises(ValueError):
            streaming_chunk_plan(MIMI, seconds=1.0, chunk_ms=0)

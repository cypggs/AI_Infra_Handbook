from multimodal_inference_mini.voice import (
    DEFAULT_CONFIG,
    VoiceConfig,
    budget_headroom,
    first_audio_breakdown,
    interrupt_response_latency,
    optimization_table,
    tune,
)


class TestBreakdown:
    def test_total_is_sum_of_stages(self):
        b = first_audio_breakdown(DEFAULT_CONFIG)
        assert b["total_ms"] == round(sum(b["stages"].values()), 2)
        assert set(b["stages"]) == {
            "endpointing", "stt_finalize", "llm_ttft",
            "tts_first_frame", "transport",
        }

    def test_default_total_is_850(self):
        assert first_audio_breakdown(DEFAULT_CONFIG)["total_ms"] == 850.0


class TestBudget:
    def test_headroom_positive_when_under_budget(self):
        h = budget_headroom(DEFAULT_CONFIG, budget_ms=900.0)
        assert h["headroom_ms"] == 50.0
        assert h["meets_budget"] is True

    def test_headroom_negative_when_over_budget(self):
        h = budget_headroom(DEFAULT_CONFIG, budget_ms=600.0)
        assert h["headroom_ms"] == -250.0
        assert h["meets_budget"] is False

    def test_max_allowable_per_stage(self):
        h = budget_headroom(DEFAULT_CONFIG, budget_ms=600.0)
        # 600 - (850 - 300) = 50: LLM TTFT 最多还有 50ms 余量
        assert h["max_allowable_ms"]["llm_ttft"] == 50.0

    def test_zero_sum_tuning_reaches_budget(self):
        cfg = tune(
            DEFAULT_CONFIG,
            endpointing_ms=200, stt_finalize_ms=100, llm_ttft_ms=150,
            tts_first_frame_ms=90, transport_ms=60,
        )
        b = first_audio_breakdown(cfg)
        assert b["total_ms"] == 600.0
        assert budget_headroom(cfg, 600.0)["meets_budget"] is True


class TestInterrupt:
    def test_interrupt_latency_equals_cancel_plus_restart(self):
        i = interrupt_response_latency(DEFAULT_CONFIG)
        assert i["total_ms"] == round(i["vad_trigger_ms"] + i["cancel_ms"]
                                      + i["pipeline_restart_ms"], 2)

    def test_interrupt_cost_over_normal(self):
        normal = first_audio_breakdown(DEFAULT_CONFIG)["total_ms"]
        intr = interrupt_response_latency(DEFAULT_CONFIG)
        assert intr["total_ms"] - normal == 110.0

    def test_faster_cancel_reduces_interrupt_latency(self):
        fast = tune(DEFAULT_CONFIG, cancel_ms=10)
        assert (interrupt_response_latency(fast)["total_ms"]
                < interrupt_response_latency(DEFAULT_CONFIG)["total_ms"])


class TestOptimization:
    def test_each_stage_halving_gain(self):
        rows = optimization_table(DEFAULT_CONFIG, 600.0)
        assert len(rows) == 5
        for row in rows:
            assert row["gain_ms"] == row["original_ms"] / 2.0
            assert row["new_total_ms"] == 850.0 - row["gain_ms"]

    def test_biggest_stage_gives_biggest_gain(self):
        rows = optimization_table(DEFAULT_CONFIG)
        gains = sorted(r["gain_ms"] for r in rows)
        assert gains[-1] == 150.0  # llm_ttft (300ms) dominates

    def test_tune_validates_fields(self):
        try:
            tune(DEFAULT_CONFIG, no_such_stage_ms=1)
        except TypeError:
            pass
        else:
            raise AssertionError("tune should reject unknown fields")

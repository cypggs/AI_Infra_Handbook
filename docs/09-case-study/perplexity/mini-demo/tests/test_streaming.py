"""streaming 模块测试。"""

from perplexity_case_mini import streaming
from perplexity_case_mini.demo import scenario_streaming


def _cfg():
    return streaming.StreamConfig(ttft_s=0.15, tokens_per_s=1200.0, chunk_size=8)


def test_total_time_formula():
    cfg = _cfg()
    assert abs(streaming.total_time(cfg, 600) - (0.15 + 0.5)) < 1e-9


def test_nonstreaming_equals_total():
    cfg = _cfg()
    assert (streaming.perceived_latency_nonstreaming(cfg, 400)
            == streaming.total_time(cfg, 400))


def test_streaming_read_all_equals_total():
    cfg = _cfg()
    assert abs(streaming.perceived_latency_streaming(cfg, 400)
               - streaming.total_time(cfg, 400)) < 1e-9


def test_first_render_time():
    cfg = _cfg()
    assert abs(streaming.first_render_time(cfg) - (0.15 + 1 / 1200.0)) < 1e-9


def test_speedup_greater_than_one():
    cfg = _cfg()
    assert streaming.perceived_speedup(cfg, 400, 100) > 1.0


def test_perceived_latency_monotonic_in_ttft():
    slow = streaming.StreamConfig(0.30, 1200.0, 8)
    assert (streaming.perceived_latency_streaming(slow, 400, 100)
            > streaming.perceived_latency_streaming(_cfg(), 400, 100))


def test_sensitivity_ttft_share():
    cfg = _cfg()
    sens = streaming.sensitivity(cfg, 400, 100)
    base = streaming.perceived_latency_streaming(cfg, 400, 100)
    assert abs(sens["base_s"] - base) < 1e-9
    assert abs(sens["ttft_share"] - 0.15 / base) < 1e-9
    assert sens["ttft_plus10pct_s"] > base
    assert sens["tput_minus10pct_s"] > base


def test_scenario_streaming_numbers():
    out = scenario_streaming()
    sonar = out["Sonar 档(1200 tok/s)"]
    assert sonar["nonstream_full_s"] == 0.48
    assert sonar["stream_first100_s"] == 0.23
    assert sonar["speedup_first100x"] == 2.07
    reasoning = out["Reasoning 档(150 tok/s)"]
    assert reasoning["nonstream_full_s"] == 3.57
    assert reasoning["stream_first100_s"] == 1.57

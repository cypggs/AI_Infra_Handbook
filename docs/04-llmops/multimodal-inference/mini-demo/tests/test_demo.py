from multimodal_inference_mini.demo import (
    run_demo,
    scenario_1_resolution_sweep,
    scenario_2_mixed_batching,
    scenario_3_latency_budget,
    scenario_4_codec,
    scenario_5_duplex_trace,
    scenario_6_interrupt_latency,
)


class TestDemoRuns:
    def test_scenario_1(self, capsys):
        scenario_1_resolution_sweep()
        out = capsys.readouterr().out
        assert "视觉 token" in out
        assert "3024x4032" in out

    def test_scenario_2(self, capsys):
        scenario_2_mixed_batching()
        out = capsys.readouterr().out
        assert "prefill slowdown" in out
        assert "overlap" in out.lower()

    def test_scenario_3(self, capsys):
        scenario_3_latency_budget()
        out = capsys.readouterr().out
        assert "850" in out
        assert "headroom" in out

    def test_scenario_4(self, capsys):
        scenario_4_codec()
        out = capsys.readouterr().out
        assert "mimi" in out
        assert "encodec_6k" in out

    def test_scenario_5(self, capsys):
        scenario_5_duplex_trace()
        out = capsys.readouterr().out
        assert "SPEECH_CONFIRMED" in out
        assert "SPEECH_FALSE_ALARM" in out
        assert "turns_completed=1" in out

    def test_scenario_6(self, capsys):
        scenario_6_interrupt_latency()
        out = capsys.readouterr().out
        assert "打断" in out
        assert "110.0" in out  # 打断代价 = 80 + 30

    def test_run_demo_completes(self, capsys):
        run_demo()
        out = capsys.readouterr().out
        assert out.count("场景") == 6

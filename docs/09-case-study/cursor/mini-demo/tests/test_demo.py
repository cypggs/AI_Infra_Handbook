from cursor_case_mini.demo import (
    run_all,
    scenario_economics,
    scenario_indexing,
    scenario_latency,
    scenario_sandbox,
    scenario_speculative,
)


class TestScenarios:
    def test_run_all_deterministic(self):
        assert run_all() == run_all()

    def test_all_scenarios_present(self):
        out = run_all()
        for i in range(1, 6):
            assert f"场景{i}" in out

    def test_scenarios_individually_deterministic(self):
        assert scenario_indexing() == scenario_indexing()
        assert scenario_latency() == scenario_latency()
        assert scenario_speculative() == scenario_speculative()
        assert scenario_sandbox() == scenario_sandbox()
        assert scenario_economics() == scenario_economics()

    def test_latency_scenario_mentions_260(self):
        assert "260" in scenario_latency()

    def test_speculative_scenario_mentions_1000(self):
        assert "1000" in scenario_speculative()

    def test_economics_scenario_mentions_sonnet_break_even(self):
        out = scenario_economics()
        assert "sonnet_4" in out
        assert "222" in out  # 20 / 0.09，官方口径约 225 次

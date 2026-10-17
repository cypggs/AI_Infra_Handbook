"""demo 端到端场景测试。"""

from perplexity_case_mini import demo


def test_scenario_routing_numbers():
    r = demo.scenario_routing()
    small = r["全走小模型"]
    assert small["total_cost_usd"] == 1.00
    assert small["mean_quality"] == 0.6271
    large = r["全走大模型"]
    assert large["total_cost_usd"] == 30.00
    routed = r["阈值路由(质量下限 0.62)"]
    assert routed["total_cost_usd"] == 2.75
    assert routed["mean_quality"] == 0.7121
    assert routed["mean_quality"] > large["mean_quality"]
    assert routed["total_cost_usd"] < large["total_cost_usd"]


def test_scenario_caching_keys():
    r = demo.scenario_caching()
    for key in ("n_queries", "exact_hit_rate", "semantic_hit_rate",
                "cost_usd", "baseline_cost_usd", "savings_pct"):
        assert key in r


def test_scenario_streaming_keys():
    r = demo.scenario_streaming()
    assert "Sonar 档(1200 tok/s)" in r
    assert "Reasoning 档(150 tok/s)" in r
    assert r["Sonar 档(1200 tok/s)"]["ttft_share_of_full"] == 0.3103


def test_scenario_rerank_keys():
    r = demo.scenario_rerank()
    assert r["n_docs"] == 24
    assert len(r["curve"]) == 5


def test_scenario_lifecycle_total():
    r = demo.scenario_lifecycle()
    assert len(r["stages"]) == 7
    assert r["total_ms"] == sum(ms for _, ms in r["stages"])
    assert r["cost_accounting"]["savings_pct"] == 85.7


def test_main_runs(capsys):
    demo.main()
    out = capsys.readouterr().out
    assert "场景 1" in out
    assert "场景 5" in out
    assert "550 ms" in out

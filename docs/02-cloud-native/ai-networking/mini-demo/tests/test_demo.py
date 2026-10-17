"""demo 场景冒烟测试：6 个场景都能跑通且关键结论成立。"""

from ai_networking_mini import demo


def test_scenario_1_fat_tree():
    from ai_networking_mini import topology
    r = demo.scenario_1_fat_tree()
    assert r["n_hosts"] == 128
    assert r["oversubscription"] == 1.0
    assert r["hop_histogram"] == topology.fat_tree_hop_expectation(8)


def test_scenario_2_rail():
    r = demo.scenario_2_rail()
    assert r["rail_switches"] == 8
    assert r["saved_ratio"] > 0.8
    assert r["same_rail_hops"] == 2


def test_scenario_3_traffic():
    r = demo.scenario_3_traffic_matrix()
    assert r["dominant"] == "EP 专家并行"
    assert r["uniform_hotspot"] == 1.0
    assert r["skewed_hotspot"] > 1.0


def test_scenario_4_dcqcn():
    r = demo.scenario_4_dcqcn()
    assert r["rate_after_congestion_gbps"] < 400 * 0.9
    assert r["rate_after_recovery_gbps"] > r["rate_after_congestion_gbps"]


def test_scenario_5_pfc_deadlock():
    r = demo.scenario_5_pfc_deadlock()
    assert r["deadlock"] and not r["deadlock_free"]


def test_scenario_6_collectives():
    r = demo.scenario_6_collectives()
    assert r["small_winner"] == "tree"
    assert r["large_winner"] == "ring"
    assert r["fabric_order"][0] == "NVLink5 (GB200)"


def test_main_runs_all(capsys):
    demo.main()
    out = capsys.readouterr().out
    assert "全部 6 个 AI 集群网络场景通过" in out

"""端到端 demo 场景测试。"""

import io
import contextlib

from xai_case_mini import demo


def _run_scenario(fn):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = fn()
    return result, buf.getvalue()


def test_scenario_build_schedule_output():
    report, out = _run_scenario(demo.scenario_build_schedule)
    assert report["conventional_days"] > report["cluster_ready_days"]
    assert "122" in out
    assert "关键路径" in out
    assert "temp_turbines" in report["aggressive_critical_path"]


def test_scenario_power_gap_output():
    result, out = _run_scenario(demo.scenario_power_gap)
    assert result["demand_100k_mw"] < result["demand_200k_mw"]
    # 燃气轮机计划比纯等电网更快满足需求
    assert result["plan_b"]["first_ok_day"] < result["plan_a"]["first_ok_day"]
    assert "燃气轮机" in out


def test_scenario_single_vs_multi_campus_output():
    result, out = _run_scenario(demo.scenario_single_vs_multi_campus)
    assert len(result["rows"]) == 4
    penalties = [r["penalty_s"] for r in result["rows"]]
    assert penalties == sorted(penalties)  # 惩罚随消息增大
    assert "单集群" in out


def test_scenario_roce_vs_ib_output():
    result, out = _run_scenario(demo.scenario_roce_vs_ib)
    times = result["fabric_times_s"]
    assert times["ethernet-legacy"] > times["spectrum-x"]
    assert "MFU" in out


def test_scenario_cooling_density_output():
    result, out = _run_scenario(demo.scenario_cooling_density)
    for gpu, rows in result.items():
        assert rows[1].racks < rows[0].racks  # dlc 机柜更少
    assert "液冷" in out


def test_main_runs_all_scenarios():
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        demo.main()
    out = buf.getvalue()
    for marker in ("场景 1", "场景 2", "场景 3", "场景 4", "场景 5",
                   "演示完成"):
        assert marker in out

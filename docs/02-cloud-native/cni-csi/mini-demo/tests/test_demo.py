"""demo.py 端到端：六个场景都应成功完成并返回预期结果。"""
from cni_csi_mini.demo import (
    scenario_cni_add_ipam,
    scenario_multi_node_connectivity,
    scenario_network_policy,
    scenario_csi_volume_lifecycle,
    scenario_csi_snapshot_expand,
    scenario_end_to_end,
    run_demo,
)


def test_scenario_cni_add_ipam():
    final = scenario_cni_add_ipam()
    assert final["status"]["podIP"].startswith("10.244.1")
    assert final["status"]["phase"] == "Running"


def test_scenario_multi_node_connectivity():
    res = scenario_multi_node_connectivity()
    assert res["reachable"] is True
    assert res["a"]["status"]["podIP"] != res["b"]["status"]["podIP"]


def test_scenario_network_policy():
    res = scenario_network_policy()
    assert res["allowed"] is True
    assert res["denied_port"] is False
    assert res["denied_src"] is False


def test_scenario_csi_volume_lifecycle():
    res = scenario_csi_volume_lifecycle()
    assert res["provisioned"] is True
    assert res["attached"] is True


def test_scenario_csi_snapshot_expand():
    res = scenario_csi_snapshot_expand()
    assert res["expanded"] is True
    assert res["restored"] is True


def test_scenario_end_to_end():
    res = scenario_end_to_end()
    assert res["pod_ip"].startswith("10.244")
    assert res["bound"] is True


def test_run_demo_runs_without_error(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "场景 1" in out
    assert "场景 6" in out

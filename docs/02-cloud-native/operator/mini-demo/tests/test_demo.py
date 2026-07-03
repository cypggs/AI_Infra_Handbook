"""demo.py 端到端：四个场景都应成功完成并返回预期结果。"""
from operator_mini import model
from operator_mini.demo import (
    build, scenario_create, scenario_scale_upgrade,
    scenario_delete, scenario_drift, run_demo,
)


def test_scenario_create_ready():
    final = scenario_create()
    assert final["status"]["ready"] is True
    assert final["status"]["readyReplicas"] == 2


def test_scenario_scale_upgrade_converges():
    final = scenario_scale_upgrade()
    assert final["status"]["ready"] is True
    assert final["status"]["readyReplicas"] == 4
    assert final["status"]["observedGeneration"] == 2


def test_scenario_delete_cascade():
    res = scenario_delete()
    assert res == {"cr_gone": True, "deploy_gone": True, "svc_gone": True}


def test_scenario_drift_restored():
    res = scenario_drift()
    assert res == {"restored": True}


def test_build_wires_all_informers():
    controller, apiserver, _ = build()
    assert controller.reconciler.is_informer is not None
    assert controller.reconciler.deploy_informer is not None
    assert controller.reconciler.svc_informer is not None


def test_run_demo_runs_without_error(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "场景 1" in out
    assert "场景 4" in out

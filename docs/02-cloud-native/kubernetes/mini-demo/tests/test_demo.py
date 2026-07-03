"""test_demo.py — 端到端场景测试（四个场景的关键不变量）。

这些测试把 demo 的四个场景当作契约：每个场景都对关键结果做断言，
保证演示输出始终符合预期（确定性、可回归）。
"""

import pytest

from k8s_mini.demo import (
    run_demo,
    scenario_gang,
    scenario_gpu,
    scenario_rollout,
    scenario_scheduling,
)


def test_run_demo_does_not_raise(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "演示完成" in out


def test_scenario_scheduling_binpack_concentrates_spread_distributes():
    r = scenario_scheduling()
    # binpack：3 个 Pod 全在一个节点
    binpack = r["binpack"]
    assert max(binpack.values()) == 3
    assert sum(1 for v in binpack.values() if v > 0) == 1
    # spread：三个节点各 1 个
    spread = r["spread"]
    assert sorted(spread.values()) == [1, 1, 1]


def test_scenario_gpu_assigns_distinct_devices():
    r = scenario_gpu()
    placed = r["placed"]
    # 3 个 Pod 全部 Running，各拿到 1 张独立 GPU
    assert len(placed) == 3
    assert all(phase == "Running" for _, _, phase, _ in placed)
    devices = sorted(d for _, _, _, d in placed)
    assert all(len(d) == 1 for d in devices)
    # 全集群 4 张卡，用掉 3 张，剩 1 张
    assert sum(r["free"].values()) == 1


def test_scenario_rollout_converges_to_v2_and_self_heals():
    r = scenario_rollout()
    # v1 阶段 3 个 Pod
    assert len(r["v1_pods"]) == 3
    # 滚动后全部 v2
    assert r["images_after_rollout"]
    assert all(img == "app:v2" for img in r["images_after_rollout"].values())
    assert len(r["v2_pods"]) == 3
    # 自愈：删除前后都维持 3
    assert r["self_heal_before"] == 3
    assert r["self_heal_after"] == 3


def test_scenario_gang_ok_succeeds_fail_rejected():
    r = scenario_gang()
    assert r["gang_ok_scheduled"] == 2
    assert r["gang_fail_scheduled"] == 0
    assert r["gang_status"]["gang-ok"] == "2/2 scheduled"
    assert r["gang_status"]["gang-fail"] == "0/3 scheduled"

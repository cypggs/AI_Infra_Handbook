"""端到端场景测试。"""
from __future__ import annotations

from rl_post_training_mini.demo import (
    scenario_1_simple_grpo,
    scenario_2_multi_step_convergence,
    scenario_3_weight_version_sync,
    scenario_4_kl_penalty,
    scenario_5_long_tail,
    scenario_6_reward_hacking,
)


def test_scenario_1_simple_grpo(capsys):
    scenario_1_simple_grpo()
    out = capsys.readouterr().out
    assert "场景 1" in out
    assert "Mean reward" in out


def test_scenario_2_multi_step():
    scenario_2_multi_step_convergence()


def test_scenario_3_weight_sync():
    scenario_3_weight_version_sync()


def test_scenario_4_kl_penalty():
    scenario_4_kl_penalty()


def test_scenario_5_long_tail():
    scenario_5_long_tail()


def test_scenario_6_reward_hacking():
    scenario_6_reward_hacking()

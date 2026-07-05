"""demo.py 测试 —— 每个场景作为一个独立测试。"""
import pytest

from gpu_scheduling_mini import demo


def test_scenario_1_device_plugin_registration():
    demo.scenario_1_device_plugin_registration()


def test_scenario_2_scheduler_filter_score_bind():
    demo.scenario_2_scheduler_filter_score_bind()


def test_scenario_3_mig_scheduling():
    demo.scenario_3_mig_scheduling()


def test_scenario_4_gang_scheduling():
    demo.scenario_4_gang_scheduling()


def test_scenario_5_topology_aware():
    demo.scenario_5_topology_aware()


def test_scenario_6_gpu_sharing():
    demo.scenario_6_gpu_sharing()


def test_run_all():
    demo.run_all()

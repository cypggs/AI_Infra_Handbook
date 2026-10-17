"""demo.py 的测试：5 个端到端场景的输出结构、量级与确定性。"""
import numpy as np

from deepseek_case_mini.demo import (
    scenario_ep,
    scenario_fp8,
    scenario_mla,
    scenario_pipeline,
    scenario_step_budget,
)
from deepseek_case_mini.pipeline import bubble_1f1b, bubble_dualpipe


class TestScenarioPipeline:
    def test_structure(self):
        s = scenario_pipeline()
        assert s["pp"] == 16
        assert s["bubble_1f1b"] > s["bubble_dualpipe"] > 0.0
        assert 0.5 < s["reduction_ratio"] < 0.8
        assert "legend" in s["sim_timeline"]

    def test_sim_bubble_positive(self):
        s = scenario_pipeline()
        assert s["sim_bubble"] > 0.0
        assert s["sim_makespan"] > 0.0

    def test_deterministic(self):
        a = scenario_pipeline()
        b = scenario_pipeline()
        assert a["sim_makespan"] == b["sim_makespan"]


class TestScenarioFp8:
    def test_sweep_structure(self):
        s = scenario_fp8()
        assert set(s["bulk_sweep"]) == {1.0, 1000.0, 30000.0, 100000.0}

    def test_tile_degrades_boundedly_tensor_collapses(self):
        s = scenario_fp8()
        sweep = s["bulk_sweep"]
        # tile-wise 有界退化（组内泄漏），tensor-wise 崩溃
        assert sweep[100000.0]["tile_wise"] < 5.0 * sweep[1.0]["tile_wise"]
        assert sweep[100000.0]["tensor_wise"] > 5.0 * sweep[1.0]["tensor_wise"]
        # 极端动态范围下 tile-wise 主体保真度显著更好
        assert sweep[100000.0]["tile_wise"] < 0.5 * sweep[100000.0]["tensor_wise"]

    def test_quant_floor_is_percent_level(self):
        s = scenario_fp8()
        assert 0.005 < s["quant_floor_tile"] < 0.10
        assert 0.005 < s["quant_floor_tensor"] < 0.10

    def test_accum_delta_positive_and_small(self):
        s = scenario_fp8()
        assert 0.0 < s["accum_delta_fp16"] < s["quant_floor_tile"]

    def test_deterministic(self):
        assert scenario_fp8(seed=0)["quant_floor_tile"] == scenario_fp8(seed=0)[
            "quant_floor_tile"
        ]


class TestScenarioEp:
    def test_magnitudes(self):
        s = scenario_ep()
        # 8192 tokens × 8 experts × 7168 × 2B ≈ 939.5 MB
        assert 8e8 < s["dispatch_bytes"] < 1e9
        assert s["nvlink_bytes"] + s["ib_bytes"] == s["dispatch_bytes"]
        assert s["ib_bytes"] < s["nvlink_bytes"]

    def test_node_limited_wins(self):
        s = scenario_ep()
        assert s["seconds_limited"] < s["seconds_unlimited"]
        assert s["speedup_node_limited"] > 1.0

    def test_deterministic(self):
        assert scenario_ep(seed=1)["seconds_limited"] == scenario_ep(seed=1)[
            "seconds_limited"
        ]


class TestScenarioMla:
    def test_v3_numbers(self):
        s = scenario_mla()
        assert s["v3_mha_bytes_per_token"] == 65536
        assert s["v3_mla_bytes_per_token"] == 1152
        assert 56.0 < s["compression_ratio"] < 57.0

    def test_reconstruction(self):
        s = scenario_mla()
        assert s["recon_error_clean"] < 1e-9
        assert 0.0 < s["recon_error_noisy"] < 0.2

    def test_dsa_ratio(self):
        assert scenario_mla()["dsa_flops_ratio"] == 2048 / (128 * 1024)


class TestScenarioStepBudget:
    def test_compute_time_from_official_numbers(self):
        """单卡 8192 tokens × 0.648 ms = 5.3 s 左右。"""
        s = scenario_step_budget()
        assert 4000 < s["compute_ms_per_microbatch"] < 7000

    def test_compute_dominates_comm(self):
        s = scenario_step_budget()
        assert s["compute_to_comm_ratio"] > 10.0

    def test_dualpipe_saves_time(self):
        s = scenario_step_budget()
        # W=0.2 时 3W=0.6 < F+B=3 ⇒ DualPipe 无暴露通信，气泡更小
        assert s["bubble_dualpipe_ms"] < s["bubble_1f1b_ms"]
        assert s["step_time_saved_ms"] > 0.0
        assert s["bubble_ratio_dualpipe"] < s["bubble_ratio_1f1b"]

    def test_step_budget_deterministic(self):
        a = scenario_step_budget(seed=0)
        b = scenario_step_budget(seed=0)
        assert a["compute_ms_per_microbatch"] == b["compute_ms_per_microbatch"]


class TestCrossScenario:
    def test_bubble_formulas_used_in_demo(self):
        """demo 场景 1 与 pipeline 模块闭式公式一致。"""
        s = scenario_pipeline()
        assert s["bubble_1f1b"] == bubble_1f1b(16, 1.0, 2.0)
        assert s["bubble_dualpipe"] == bubble_dualpipe(16, 1.0, 2.0, 0.2)

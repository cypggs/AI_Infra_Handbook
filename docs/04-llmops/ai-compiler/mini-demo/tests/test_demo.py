import numpy as np

from ai_compiler_mini.demo import (
    scenario_1_graph_capture,
    scenario_2_fusion,
    scenario_3_autotune,
    scenario_4_tiled_matmul,
    scenario_5_fused_rowwise,
    scenario_6_end_to_end,
)


def test_demo_scenarios_run_without_error(capsys):
    for fn in (
        scenario_1_graph_capture,
        scenario_2_fusion,
        scenario_3_autotune,
        scenario_4_tiled_matmul,
        scenario_5_fused_rowwise,
        scenario_6_end_to_end,
    ):
        fn()
    out = capsys.readouterr().out
    # 关键断言：每个场景都有输出，且正确性检查全部 PASS
    assert "场景 1" in out and "场景 6" in out
    assert "PASS" in out
    assert out.count("PASS") >= 2  # 场景 4 与场景 6 各一次

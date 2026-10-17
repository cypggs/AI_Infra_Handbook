"""demo.py 的端到端测试：6 个场景的输出满足预期的不等式关系。"""

from model_quantization_mini import demo


def test_scenario_linear_quant_ordering():
    r = demo.scenario_linear_quant()
    # 位宽越大误差越小
    assert r["int8_per_tensor"] < r["int4_per_tensor"]
    # 粒度越细误差越小（同位宽）
    assert r["int8_group32"] < r["int8_per_channel"] < r["int8_per_tensor"]
    assert r["int4_group32"] < r["int4_per_channel"] < r["int4_per_tensor"]


def test_scenario_group_tradeoff():
    r = demo.scenario_group_tradeoff()
    # group 越小误差越低、等效位宽越高
    assert r["32"]["err"] < r["64"]["err"] < r["128"]["err"]
    assert r["32"]["bits"] > r["64"]["bits"] > r["128"]["bits"] > r["512"]["bits"]
    # group32 误差仍低于 per-channel
    assert r["32"]["err"] < r["512"]["err"]


def test_scenario_smooth_quant():
    r = demo.scenario_smooth_quant()
    assert r["baseline"] > r["alpha_0.5"]
    assert r["best_alpha"] in (0.25, 0.5, 0.75)
    assert r["best_reduction"] > 2.0


def test_scenario_gptq_vs_rtn():
    r = demo.scenario_gptq_vs_rtn()
    assert r["int4_gptq_output"] < r["int4_rtn_output"]
    assert r["int8_gptq_output"] < r["int8_rtn_output"]
    assert r["int4_improve"] > 1.5


def test_scenario_kv_long_context():
    r = demo.scenario_kv_long_context()
    for T in (128, 256, 384, 512):
        assert r[f"int8_channel_{T}"] > 0.999
        assert r[f"int4_channel_{T}"] > r[f"int4_token_{T}"]
    assert r["int4_channel_512"] > 0.95


def test_scenario_fp4_fp8_formats():
    r = demo.scenario_fp4_fp8_formats()
    keys = ("NVFP4(blk16,E4M3scale)", "MXFP4(blk32,E8M0scale)", "bare_E2M1")
    assert r[keys[0]] < r[keys[1]] < r[keys[2]]
    # FP8：大离群时 E5M2（范围大）显著占优，无离群时 E4M3（精度高）占优
    assert r["act_e5m2"] < 0.2 < r["act_e4m3"]
    assert r["act_e4m3_noout"] < r["act_e5m2_noout"]


def test_run_demo_completes():
    results = demo.run_demo()
    assert set(results) == {
        "linear_quant",
        "group_tradeoff",
        "smooth_quant",
        "gptq_vs_rtn",
        "kv_long_context",
        "fp4_fp8_formats",
    }

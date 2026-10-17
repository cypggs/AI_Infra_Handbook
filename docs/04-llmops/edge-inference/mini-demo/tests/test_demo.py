"""demo.py 场景输出与文档数字逐字一致的回归测试。"""

import pytest

from edge_inference_mini import demo


def test_scenario_bandwidth_decode():
    r = demo.scenario_bandwidth_decode()
    assert r["tok_q4"] == pytest.approx(11.15, abs=0.01)
    assert r["tok_fp16"] == pytest.approx(3.61, abs=0.01)
    assert r["ratio"] == pytest.approx(3.09, abs=0.01)
    assert r["mtp_speedup"] == pytest.approx(1.91, abs=0.01)
    assert r["tok_mtp"] == pytest.approx(21.26, abs=0.01)


def test_scenario_kv_capacity():
    plan = demo.scenario_kv_capacity()
    assert plan["fp16"]["max_context"] == 19_431
    assert plan["int8"]["max_context"] == 38_863
    assert plan["int4"]["max_context"] == 77_726


def test_scenario_hetero_fallback():
    r = demo.scenario_hetero_fallback()
    assert r["total_us"] == pytest.approx(5811.5, abs=0.1)
    assert r["fallback_transfer_us"] == pytest.approx(978.7, abs=0.1)


def test_scenario_mmap_streaming():
    r = demo.scenario_mmap_streaming()
    assert r["pages"] == 316_407
    assert r["preload_s"] == pytest.approx(0.076, abs=1e-3)
    assert r["demand_s"] == pytest.approx(7.986, abs=1e-3)
    assert r["prefetch_s"] == pytest.approx(0.323, abs=1e-3)
    assert r["sparse_s"] == pytest.approx(2.396, abs=1e-3)
    assert r["sparse_prefetch_s"] == pytest.approx(0.097, abs=1e-3)


def test_scenario_lora_switch():
    r = demo.scenario_lora_switch()
    assert r["adapter_mib"] == pytest.approx(56.0, abs=0.05)
    assert r["merged_gib"] == pytest.approx(12.06, abs=0.01)
    assert r["switch_us"] == pytest.approx(1977.1, abs=0.1)
    assert r["ratio_pct"] == pytest.approx(0.45, abs=0.01)


def test_scenario_edge_cloud_route():
    results = demo.scenario_edge_cloud_route()
    assert results["病历摘要"]["decision"] == "device"
    assert results["闲聊问答"]["decision"] == "public_cloud"
    assert results["会议纪要"]["decision"] == "private_cloud"
    assert results["长文续写"]["decision"] == "public_cloud"
    assert results["长文续写"]["device_s"] == pytest.approx(112.88, abs=0.01)


def test_run_demo_smoke(capsys):
    demo.run_demo()
    out = capsys.readouterr().out
    assert "场景 1" in out and "场景 6" in out
    assert len(out.splitlines()) > 30

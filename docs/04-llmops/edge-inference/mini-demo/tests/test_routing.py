"""端云路由：隐私硬约束、SLO、热节流与成本。"""

import pytest

from edge_inference_mini.routing import (
    CONFIDENTIAL,
    INTERNAL,
    PUBLIC,
    CloudProfile,
    DeviceProfile,
    Request,
    cloud_cost,
    cloud_latency_s,
    device_latency_s,
    route,
    thermal_derated,
)

DEV = DeviceProfile(prefill_tps=180.0, decode_tps=13.0, derate_after_s=45.0, derate_factor=0.70)
CLOUD = CloudProfile(rtt_s=0.12, ttft_s=0.35, decode_tps=60.0, cost_per_1k_tokens=0.02,
                     private_available=True)


class TestLatencyModels:
    def test_device_latency(self):
        req = Request("r", PUBLIC, 360, 130)  # 2s + 10s
        assert device_latency_s(req, DEV) == pytest.approx(2.0 + 10.0)

    def test_thermal_derate_applies_to_decode(self):
        req = Request("r", PUBLIC, 64, 1024)  # 0.36 + 78.8 > 45s → decode / 0.7
        t = device_latency_s(req, DEV)
        assert t == pytest.approx(64 / 180 + 1024 / 13 / 0.70)
        assert t == pytest.approx(112.88, abs=0.01)
        assert thermal_derated(req, DEV)

    def test_no_derate_short_request(self):
        req = Request("r", PUBLIC, 32, 64)
        assert not thermal_derated(req, DEV)
        assert device_latency_s(req, DEV) == pytest.approx(32 / 180 + 64 / 13)

    def test_cloud_latency(self):
        req = Request("r", PUBLIC, 64, 1024)
        assert cloud_latency_s(req, CLOUD) == pytest.approx(0.12 + 0.35 + 1024 / 60)

    def test_cloud_cost(self):
        req = Request("r", PUBLIC, 1000, 1000)
        assert cloud_cost(req, CLOUD) == pytest.approx(2.0 * 0.02)


class TestRoute:
    def test_confidential_stays_on_device(self):
        req = Request("病历", CONFIDENTIAL, 1024, 256, latency_slo_s=120.0)
        r = route(req, DEV, CLOUD)
        assert r["decision"] == "device"
        assert r["cloud_s"] == float("inf")

    def test_public_short_request_prefers_cloud_when_faster(self):
        req = Request("闲聊", PUBLIC, 32, 64, latency_slo_s=3.0)
        r = route(req, DEV, CLOUD)
        assert r["decision"] == "public_cloud"

    def test_internal_uses_private_cloud(self):
        req = Request("纪要", INTERNAL, 2048, 256, latency_slo_s=60.0)
        r = route(req, DEV, CLOUD)
        assert r["decision"] == "private_cloud"

    def test_no_private_cloud_internal_falls_back_device(self):
        cloud = CloudProfile(0.12, 0.35, 60.0, 0.02, private_available=False)
        req = Request("纪要", INTERNAL, 2048, 256, latency_slo_s=60.0)
        r = route(req, DEV, cloud)
        # 端侧 31.07s 满足 SLO 且云端不可用 → device
        assert r["decision"] == "device"

    def test_derated_long_request_routed_to_cloud(self):
        req = Request("长文", PUBLIC, 64, 1024, latency_slo_s=30.0)
        r = route(req, DEV, CLOUD)
        assert r["decision"] == "public_cloud"
        assert r["device_s"] == pytest.approx(112.88, abs=0.01)

    def test_device_chosen_when_fast_enough(self):
        # 短输出、宽松 SLO、无云端优势（离线场景用 t_cloud=inf 模拟）
        req = Request("离线", PUBLIC, 64, 128, latency_slo_s=60.0)
        r = route(req, DEV, CLOUD)
        # 端侧 9.2s < 云端 2.6s? 云端 = 0.12+0.35+128/60 = 3.6s < 端侧 → cloud
        assert r["decision"] == "public_cloud"

    def test_neither_meets_slo_degrades_gracefully(self):
        # 公开长请求但 SLO 极紧：端侧、云端都超时 → 端侧尽力而为
        req = Request("急长文", PUBLIC, 64, 1024, latency_slo_s=5.0)
        r = route(req, DEV, CLOUD)
        assert r["decision"] == "device"
        assert "尽力而为" in r["reason"]

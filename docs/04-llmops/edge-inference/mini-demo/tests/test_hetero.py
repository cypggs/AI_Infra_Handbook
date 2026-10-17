"""异构放置与回退：能力表、roofline 时延、回退链与传输税。"""

import pytest

from edge_inference_mini.hetero import (
    Device,
    Op,
    fallback_tax,
    op_time_us,
    place_op,
    schedule_layer,
)


@pytest.fixture()
def devices():
    npu = Device("NPU", 22.0, 45.0, 136.0,
                 frozenset({"matmul_int8", "matmul_fp16", "elementwise"}))
    gpu = Device("GPU", 6.0, 8.0, 68.0,
                 frozenset({"matmul_int8", "matmul_fp16", "elementwise", "softmax", "norm"}))
    cpu = Device("CPU", 1.5, 3.0, 34.0,
                 frozenset({"matmul_int8", "matmul_fp16", "elementwise", "softmax", "norm"}),
                 is_fallback=True)
    return [npu, gpu, cpu]


class TestDeviceRates:
    def test_int8_rate(self, devices):
        npu = devices[0]
        assert npu.rate_flops("matmul_int8") == 45e12

    def test_unsupported_returns_none(self, devices):
        assert devices[0].rate_flops("softmax") is None

    def test_elementwise_discounted(self, devices):
        # 元素级算子按 FP16 速率的 50% 折算
        assert devices[0].rate_flops("elementwise") == 11e12


class TestOpTime:
    def test_roofline_max(self, devices):
        # 纯计算受限的算子：时间 = flops / rate
        op = Op("m", "matmul_int8", 45e9, 0.0, 0.0)
        assert op_time_us(op, devices[0]) == pytest.approx(1000.0)

    def test_memory_bound(self, devices):
        # 0 FLOP、搬 136 MB @ 136 GB/s → 1000 us
        op = Op("m", "elementwise", 0.0, 136e6, 0.0)
        assert op_time_us(op, devices[0]) == pytest.approx(1000.0)

    def test_unsupported_raises(self, devices):
        op = Op("s", "softmax", 1e6, 1e6, 1e6)
        with pytest.raises(ValueError):
            op_time_us(op, devices[0])


class TestPlaceOp:
    def test_fastest_device_chosen(self, devices):
        op = Op("m", "matmul_int8", 45e9, 0.0, 0.0)
        p = place_op(op, devices)
        assert p.device == "NPU"
        assert p.transfer_us == 0.0

    def test_fallback_adds_transfer(self, devices):
        op = Op("s", "softmax", 1e6, 8e6, 8e6)
        p = place_op(op, devices, fabric_gbs=60.0, preferred=devices[0])
        # NPU 不支持 softmax → 回退 GPU（比 CPU 快），传输 16 MB @ 60 GB/s
        assert p.device == "GPU"
        assert p.via == "NPU"
        assert p.transfer_us == pytest.approx(16e6 / 60e9 * 1e6)

    def test_no_support_raises(self, devices):
        weird = Op("w", "custom_op", 1.0, 1.0, 1.0)
        with pytest.raises(ValueError):
            place_op(weird, devices)


class TestScheduleLayer:
    def test_sequential_sum(self, devices):
        ops = [Op("a", "matmul_int8", 45e9, 0.0, 0.0),
               Op("b", "matmul_int8", 45e9, 0.0, 0.0)]
        placements, total = schedule_layer(ops, devices)
        # 每个 1000 us，串行 → 2000 us
        assert total == pytest.approx(2000.0)
        assert len(placements) == 2

    def test_matches_demo_scenario(self, devices):
        from edge_inference_mini.demo import _layer_ops
        placements, total = schedule_layer(_layer_ops(512), devices, fabric_gbs=60.0,
                                           preferred=devices[0])
        assert total == pytest.approx(5811.5, abs=0.1)
        assigned = {p.op: p.device for p in placements}
        assert assigned["qkv_gemm"] == "NPU"
        assert assigned["softmax"] == "GPU"
        assert assigned["norm1"] == "GPU"
        assert assigned["gate_up"] == "NPU"
        transfer = sum(p.transfer_us for p in placements)
        assert transfer == pytest.approx(978.7, abs=0.1)
        assert transfer / total == pytest.approx(0.1684, abs=1e-3)

    def test_fallback_tax_zero_without_fallback(self, devices):
        placements, _ = schedule_layer([Op("a", "matmul_int8", 1e9, 0.0, 0.0)], devices)
        assert fallback_tax(placements) == 0.0

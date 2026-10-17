"""LoRA 热切换 vs 合并：内存与切换时延的解析关系。"""

import pytest

from edge_inference_mini.lora import (
    SWITCH_FIXED_OVERHEAD_US,
    hot_switch_us,
    lora_adapter_bytes,
    memory_ratio,
    merged_adapter_bytes,
)


class TestAdapterBytes:
    def test_demo_adapter(self):
        # 32 层 × 7 目标 × 2 矩阵 × 4096 × 16 × 2 B
        b = lora_adapter_bytes(32, 7, 4096, rank=16)
        assert b == 32 * 7 * 2 * 4096 * 16 * 2
        assert b / 2**20 == pytest.approx(56.0)

    def test_invalid(self):
        with pytest.raises(ValueError):
            lora_adapter_bytes(0, 7, 4096, 16)


class TestMergedBytes:
    def test_demo_merged(self):
        b = merged_adapter_bytes(32, 7, 4096, 11008)
        per_layer = (4 * 4096 * 4096 + 3 * 4096 * 11008) * 2
        assert b == 32 * per_layer
        assert b / 2**30 == pytest.approx(12.06, abs=0.01)


class TestSwitchCost:
    def test_formula(self):
        b = lora_adapter_bytes(32, 7, 4096, rank=16)
        t = hot_switch_us(b, 68.0)
        move = 2 * b / 68e9 * 1e6
        assert t == pytest.approx(move + SWITCH_FIXED_OVERHEAD_US)
        assert t == pytest.approx(1977.1, abs=0.1)

    def test_higher_bw_faster(self):
        b = lora_adapter_bytes(32, 7, 4096, rank=16)
        assert hot_switch_us(b, 136.0) < hot_switch_us(b, 68.0)

    def test_bad_bandwidth(self):
        with pytest.raises(ValueError):
            hot_switch_us(1000, 0.0)


class TestMemoryRatio:
    def test_demo_ratio(self):
        a = lora_adapter_bytes(32, 7, 4096, rank=16)
        m = merged_adapter_bytes(32, 7, 4096, 11008)
        assert memory_ratio(a, m) == pytest.approx(0.0045, abs=1e-4)

    def test_merged_zero_raises(self):
        with pytest.raises(ValueError):
            memory_ratio(1, 0)

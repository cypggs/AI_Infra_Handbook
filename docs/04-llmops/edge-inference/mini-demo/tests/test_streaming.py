"""流式加载：页数、缺页/预取/热子集模型。"""

import pytest

from edge_inference_mini.streaming import (
    mmap_latency_us,
    page_count,
    preload_latency_us,
    working_set_gib,
)

TOTAL = 5_184_000_000  # demo 中 Q4_K_M 权重文件大小
PAGE = 16 * 1024
BW = 68.0
FAULT = 25.0


class TestPageCount:
    def test_exact(self):
        assert page_count(5_184_000_000, 16 * 1024) == 316_407

    def test_partial_page_rounds_up(self):
        assert page_count(PAGE + 1, PAGE) == 2

    def test_zero(self):
        assert page_count(0, PAGE) == 0

    def test_bad_page(self):
        with pytest.raises(ValueError):
            page_count(100, 0)


class TestLatency:
    def test_preload_pure_bandwidth(self):
        assert preload_latency_us(TOTAL, BW) == pytest.approx(TOTAL / 68e9 * 1e6)

    def test_demand_all_pages_fault(self):
        t = mmap_latency_us(TOTAL, PAGE, BW, FAULT)
        read = 316_407 * PAGE / 68e9 * 1e6
        assert t == pytest.approx(read + 316_407 * FAULT)
        assert t / 1e6 == pytest.approx(7.986, abs=1e-3)

    def test_prefetch_batches_faults(self):
        t = mmap_latency_us(TOTAL, PAGE, BW, FAULT, prefetch_pages=32)
        read = 316_407 * PAGE / 68e9 * 1e6
        import math
        assert t == pytest.approx(read + math.ceil(316_407 / 32) * FAULT)
        assert t / 1e6 == pytest.approx(0.323, abs=1e-3)

    def test_prefetch_faster_than_demand(self):
        d = mmap_latency_us(TOTAL, PAGE, BW, FAULT)
        p = mmap_latency_us(TOTAL, PAGE, BW, FAULT, prefetch_pages=32)
        assert p < d / 10

    def test_hot_subset_reads_less(self):
        full = mmap_latency_us(TOTAL, PAGE, BW, FAULT, prefetch_pages=32)
        sparse = mmap_latency_us(TOTAL, PAGE, BW, FAULT, access_fraction=0.30,
                                 prefetch_pages=32)
        assert sparse < full * 0.4
        assert sparse / 1e6 == pytest.approx(0.097, abs=1e-3)

    def test_access_fraction_bounds(self):
        with pytest.raises(ValueError):
            mmap_latency_us(TOTAL, PAGE, BW, FAULT, access_fraction=0.0)
        with pytest.raises(ValueError):
            mmap_latency_us(TOTAL, PAGE, BW, FAULT, access_fraction=1.5)

    def test_bad_bandwidth(self):
        with pytest.raises(ValueError):
            mmap_latency_us(TOTAL, PAGE, 0.0, FAULT)


class TestWorkingSet:
    def test_gib_scaling(self):
        assert working_set_gib(4.0, 0.5) == 2.0

    def test_bounds(self):
        with pytest.raises(ValueError):
            working_set_gib(4.0, 0.0)

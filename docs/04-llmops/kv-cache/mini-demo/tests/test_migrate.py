import pytest

from kv_cache_mini.migrate import PDScheduler, TransferEngine


def make_scheduler(num_blocks=8, num_streams=1, decode_time=0.0):
    engine = TransferEngine(bandwidth_bytes_per_s=1e9, num_streams=num_streams)
    return PDScheduler(
        engine=engine,
        num_blocks=num_blocks,
        block_bytes=1e6,           # 1 MB → 单块传输 1ms
        decode_time_per_block=decode_time,
    )


class TestTransferEngine:
    def test_block_transfer_time(self):
        engine = TransferEngine(bandwidth_bytes_per_s=2e9)
        assert engine.block_transfer_time(4e6) == pytest.approx(0.002)

    def test_overhead_added(self):
        engine = TransferEngine(bandwidth_bytes_per_s=1e9, overhead_s=0.001)
        assert engine.block_transfer_time(1e6) == pytest.approx(0.002)

    def test_single_stream_arrivals_sequential(self):
        engine = TransferEngine(bandwidth_bytes_per_s=1e9)
        arrivals = engine.arrival_times(4, 1e6)
        assert arrivals == [0.001, 0.002, 0.003, 0.004]

    def test_multi_stream_interleaves(self):
        engine = TransferEngine(bandwidth_bytes_per_s=1e9, num_streams=2)
        arrivals = engine.arrival_times(4, 1e6)
        # 流0: block 0,2 → 0.001, 0.002；流1: block 1,3 → 0.001, 0.002
        assert arrivals == [0.001, 0.001, 0.002, 0.002]

    def test_invalid_params(self):
        with pytest.raises(ValueError):
            TransferEngine(bandwidth_bytes_per_s=0)
        with pytest.raises(ValueError):
            TransferEngine(bandwidth_bytes_per_s=1e9, num_streams=0)


class TestPDScheduler:
    def test_sequential_ttft_scales_with_blocks(self):
        sched = make_scheduler(num_blocks=8)
        assert sched.sequential_ttft_s() == pytest.approx(0.008)

    def test_pipelined_ttft_waits_only_first_block(self):
        sched = make_scheduler(num_blocks=8, decode_time=0.0005)
        result = sched.simulate_pipelined()
        assert result["ttft_s"] == pytest.approx(0.001 + 0.0005)

    def test_overlap_gain_formula(self):
        # 收益 = (n-1) × 单块传输时间（decode 比传输快的情形）
        sched = make_scheduler(num_blocks=8, decode_time=0.0)
        assert sched.overlap_gain_s() == pytest.approx(7 * 0.001)

    def test_pipelined_makespan_with_slow_decode(self):
        # decode 比传输慢时，makespan 由 decode 决定
        sched = make_scheduler(num_blocks=4, decode_time=0.01)
        result = sched.simulate_pipelined()
        assert result["makespan_s"] == pytest.approx(0.001 + 4 * 0.01)

    def test_zero_blocks(self):
        sched = make_scheduler(num_blocks=0)
        result = sched.simulate_pipelined()
        assert result == {"ttft_s": 0.0, "makespan_s": 0.0, "arrivals": []}
        assert sched.sequential_ttft_s() == 0.0

    def test_multi_stream_reduces_arrivals(self):
        single = make_scheduler(num_blocks=8, num_streams=1)
        multi = make_scheduler(num_blocks=8, num_streams=4)
        r1 = single.simulate_pipelined()
        r2 = multi.simulate_pipelined()
        assert max(r2["arrivals"]) < max(r1["arrivals"])
        assert r2["ttft_s"] == pytest.approx(r1["ttft_s"])  # 首块不受流数影响

    def test_gain_ratio_between_zero_and_one(self):
        sched = make_scheduler(num_blocks=16, decode_time=0.0)
        ratio = sched.overlap_gain_ratio()
        assert 0.0 < ratio < 1.0
        assert ratio == pytest.approx(15 / 16)

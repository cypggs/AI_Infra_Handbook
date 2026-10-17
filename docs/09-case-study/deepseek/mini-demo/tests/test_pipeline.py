"""pipeline.py 的测试：Table 2 闭式公式 + 列表调度器复现。"""
from deepseek_case_mini.pipeline import (
    ascii_timeline,
    bubble_1f1b,
    bubble_dualpipe,
    bubble_reduction_ratio,
    dualpipe_exposed_comm,
    memory_units,
    pipeline_bubble_ratio,
    simulate_pipeline,
)

F = 1.0
B = 2.0
W = 0.2


class TestClosedForm:
    def test_1f1b_matches_table2(self):
        """Table 2：1F1B 气泡 = (PP-1)(F+B)。"""
        assert bubble_1f1b(16, F, B) == 15 * 3.0
        assert bubble_1f1b(4, F, B) == 3 * 3.0

    def test_1f1b_pp1_no_bubble(self):
        assert bubble_1f1b(1, F, B) == 0.0

    def test_dualpipe_matches_table2(self):
        """Table 2：DualPipe 气泡 = (PP/2-1)(F+B-3W)。"""
        assert bubble_dualpipe(16, F, B, W) == 7 * (3.0 - 3 * W)
        assert bubble_dualpipe(8, F, B, 0.0) == 3 * 3.0

    def test_dualpipe_requires_even_pp(self):
        try:
            bubble_dualpipe(15, F, B, W)
        except ValueError:
            return
        raise AssertionError("奇数 PP 应抛 ValueError")

    def test_dualpipe_comm_cannot_be_negative(self):
        """W 很大时内层取 0（通信盖不住的部分走暴露路径）。"""
        assert bubble_dualpipe(8, F, B, 10.0) == 0.0

    def test_dualpipe_strictly_smaller_than_1f1b(self):
        for pp in (4, 8, 16, 32):
            assert bubble_dualpipe(pp, F, B, W) < bubble_1f1b(pp, F, B)

    def test_reduction_ratio_pp16(self):
        """PP=16, F=1, B=2, W=0.2 ⇒ 缩减 1 - 7×2.4/45。"""
        expected = 1.0 - 7 * (3.0 - 3 * W) / (15 * 3.0)
        assert abs(bubble_reduction_ratio(16, F, B, W) - expected) < 1e-12
        assert 0.5 < expected < 0.8

    def test_exposed_comm_when_w_too_large(self):
        """3W > F+B 时暴露 3W-(F+B)，每 chunk。"""
        assert dualpipe_exposed_comm(16, 2.0, F, B) == 6.0 - 3.0
        assert dualpipe_exposed_comm(16, W, F, B) == 0.0

    def test_memory_units(self):
        """Table 2：DualPipe 参数 2×、激活 PP+1；1F1B 参数 1×、激活 PP。"""
        assert memory_units("1f1b", 16) == {"params": 16.0, "activations": 16.0}
        assert memory_units("dualpipe", 16) == {"params": 32.0, "activations": 17.0}

    def test_bubble_ratio_helpers(self):
        assert pipeline_bubble_ratio(3.0, 30.0) == 0.1
        try:
            pipeline_bubble_ratio(1.0, 0.0)
        except ValueError:
            return
        raise AssertionError("makespan=0 应抛 ValueError")


class TestSimulator:
    def test_schedule_respects_stage_serialization(self):
        r = simulate_pipeline(pp=4, num_microbatches=6, f=F, b=B)
        for s in range(4):
            tasks = sorted(
                [t for t in r.tasks if t.stage == s], key=lambda t: t.start
            )
            for a, b_ in zip(tasks, tasks[1:]):
                assert a.end <= b_.start + 1e-12

    def test_schedule_respects_dependencies(self):
        r = simulate_pipeline(pp=4, num_microbatches=5, f=F, b=B)
        by_key = {(t.mb, t.stage, t.kind): t for t in r.tasks}
        for t in r.tasks:
            if t.kind == "F" and t.stage > 0:
                dep = by_key[(t.mb, t.stage - 1, "F")]
                assert t.start >= dep.end - 1e-12
            if t.kind == "B" and t.stage < 3:
                dep = by_key[(t.mb, t.stage + 1, "B")]
                assert t.start >= dep.end - 1e-12

    def test_simulator_1f1b_matches_closed_form(self):
        """M >> PP 时，调度器数值气泡精确等于 Table 2 闭式 (PP-1)(F+B)。

        1F1B makespan = M(F+B) + (PP-1)(F+B)：填充与排空段之和，
        与 GPipe 气泡同源（1F1B 省的是显存，不是气泡）。
        """
        pp, m = 8, 400
        r = simulate_pipeline(pp=pp, num_microbatches=m, f=F, b=B)
        predicted = m * (F + B) + (pp - 1) * (F + B)
        assert abs(r.makespan - predicted) < 1e-9

    def test_simulator_gpipe_window_none_more_overlap(self):
        """GPipe（无窗口约束）与 1F1B 的填充段相同（气泡同源，仅显存差异）。"""
        r_pipe = simulate_pipeline(pp=8, num_microbatches=400, f=F, b=B, window=None)
        r_1f1b = simulate_pipeline(pp=8, num_microbatches=400, f=F, b=B)
        assert abs(r_pipe.makespan - r_1f1b.makespan) < 1e-9

    def test_simulator_bubble_ratio_positive_and_small(self):
        r = simulate_pipeline(pp=16, num_microbatches=1000, f=F, b=B)
        assert 0.0 < r.bubble_ratio < 0.1

    def test_simulator_deterministic(self):
        a = simulate_pipeline(pp=4, num_microbatches=10, f=F, b=B)
        b_ = simulate_pipeline(pp=4, num_microbatches=10, f=F, b=B)
        assert a.makespan == b_.makespan
        assert [(t.start, t.end) for t in a.tasks] == [
            (t.start, t.end) for t in b_.tasks
        ]

    def test_makespan_monotone_in_pp(self):
        prev = 0.0
        for pp in (2, 4, 8, 16):
            r = simulate_pipeline(pp=pp, num_microbatches=64, f=F, b=B)
            assert r.makespan > prev
            prev = r.makespan

    def test_ascii_timeline_shape(self):
        r = simulate_pipeline(pp=4, num_microbatches=6, f=F, b=B)
        art = ascii_timeline(r, pp=4, width=40)
        lines = art.splitlines()
        assert len(lines) == 4 + 2  # 4 stage 行 + header + legend
        assert "legend" in lines[-1]
        assert "#" in art and "o" in art


class TestConsistency:
    def test_sim_bubble_matches_closed_form(self):
        """数值气泡 == Table 2 闭式气泡（M >> PP 时精确一致）。"""
        r = simulate_pipeline(pp=8, num_microbatches=400, f=F, b=B)
        assert abs(r.bubble - bubble_1f1b(8, F, B)) < 1e-9

import pytest

from cursor_case_mini.sandbox import Host, QuotaError, Sandbox, run_workload


def make_host():
    return Host(total_cpu=32, total_mem_gb=128)


class TestQuota:
    def test_launch_within_capacity(self):
        h = make_host()
        assert h.launch(Sandbox("a", 4, 16, 3), tick=0) is True
        assert h.used_cpu() == 4
        assert h.used_mem() == 16

    def test_reject_over_cpu(self):
        h = make_host()
        assert h.launch(Sandbox("a", 30, 16, 3), 0)
        assert h.launch(Sandbox("b", 4, 16, 3), 0) is False  # 34 > 32

    def test_reject_over_mem(self):
        h = make_host()
        assert h.launch(Sandbox("a", 4, 120, 3), 0)
        assert h.launch(Sandbox("b", 4, 16, 3), 0) is False  # 136 > 128

    def test_nonpositive_quota_rejected(self):
        h = make_host()
        with pytest.raises(QuotaError):
            h.launch(Sandbox("a", 0, 16, 3), 0)
        with pytest.raises(QuotaError):
            h.launch(Sandbox("a", 4, -1, 3), 0)

    def test_enforce_within_quota(self):
        h = make_host()
        sb = Sandbox("a", 4, 16, 3)
        h.enforce_quota(sb, 3.5, 15.0)  # 不抛异常

    def test_enforce_violation(self):
        sb = Sandbox("a", 4, 16, 3)
        with pytest.raises(QuotaError):
            Host().enforce_quota(sb, 5.0, 16.0)
        with pytest.raises(QuotaError):
            Host().enforce_quota(sb, 4.0, 17.0)


class TestLifecycle:
    def test_ttl_reclaim(self):
        h = make_host()
        h.launch(Sandbox("a", 4, 16, ttl_ticks=2), tick=0)
        assert len(h.sandboxes) == 1
        h.tick(2)
        assert len(h.sandboxes) == 0

    def test_reclaim_event_logged(self):
        h = make_host()
        h.launch(Sandbox("a", 4, 16, 1), 0)
        h.tick(1)
        assert any("回收 agent=a" in e for e in h.events)

    def test_utilization_reported(self):
        h = make_host()
        h.launch(Sandbox("a", 8, 16, 5), 0)
        st = h.tick(0)
        assert st["cpu_util"] == 0.25


class TestWorkload:
    def test_all_small_agents_fit(self):
        reqs = [Sandbox(f"a{i}", 4, 8, 3) for i in range(4)]
        stats = run_workload(make_host(), reqs, n_ticks=6)
        assert stats["launched"] == 4

    def test_oversubscription_queues(self):
        reqs = [Sandbox(f"a{i}", 16, 32, 2) for i in range(4)]
        stats = run_workload(make_host(), reqs, n_ticks=3)
        # 32 核同时只放得下 2 个 16 核沙箱，后两个排队等回收后再启动
        assert stats["queued_events"] >= 2
        assert stats["launched"] == 4

    def test_deterministic(self):
        reqs = [Sandbox(f"a{i}", 4, 8, 2) for i in range(6)]
        a = run_workload(make_host(), reqs, n_ticks=6)
        b = run_workload(make_host(), reqs, n_ticks=6)
        assert a == b

    def test_reclaimed_equals_finished(self):
        reqs = [Sandbox(f"a{i}", 4, 8, 2) for i in range(3)]
        stats = run_workload(make_host(), reqs, n_ticks=8)
        assert stats["reclaimed"] == 3

    def test_util_bounded(self):
        reqs = [Sandbox(f"a{i}", 8, 16, 4) for i in range(3)]
        stats = run_workload(make_host(), reqs, n_ticks=8)
        assert 0.0 <= stats["avg_cpu_util"] <= 1.0

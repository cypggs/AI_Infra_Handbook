"""Tests for linux_systems_mini."""
from linux_systems_mini import CFSScheduler, CgroupV2, DiskRequest, IOScheduler, OOMKiller, PageCache, Process, ProcessMemory


def test_nice_affects_weight():
    assert Process(pid=1, name="a", nice=-20).weight > Process(pid=2, name="b", nice=0).weight
    assert Process(pid=1, name="a", nice=0).weight > Process(pid=2, name="b", nice=19).weight


def test_cfs_picks_smallest_vruntime():
    sched = CFSScheduler(tasks=[
        Process(pid=1, name="a", nice=0, vruntime=100),
        Process(pid=2, name="b", nice=0, vruntime=10),
    ])
    chosen = sched.step()
    assert chosen is not None
    assert chosen.pid == 2


def test_nice_zero_runtime_grows_faster_than_negative():
    lo = Process(pid=1, name="lo", nice=10)
    hi = Process(pid=2, name="hi", nice=-10)
    sched = CFSScheduler(tasks=[lo, hi])
    for _ in range(5):
        sched.step()
    # Lower nice (higher weight) accumulates vruntime slower
    assert lo.vruntime > hi.vruntime


def test_page_cache_lru_eviction():
    cache = PageCache(capacity=2)
    cache.access(1, 1)
    cache.access(2, 1)
    cache.access(1, 1)  # touch page 1
    cache.access(3, 2)  # evicts page 2
    assert 1 in cache.pages
    assert 3 in cache.pages
    assert 2 not in cache.pages


def test_page_cache_hit_miss():
    cache = PageCache(capacity=2)
    assert cache.access(1, 1) is False
    assert cache.access(1, 1) is True
    assert cache.hits == 1
    assert cache.misses == 1


def test_oom_victim_is_fattest():
    killer = OOMKiller([
        ProcessMemory(pid=1, name="thin", rss=10),
        ProcessMemory(pid=2, name="fat", rss=1000),
    ])
    victim = killer.pick_victim()
    assert victim is not None
    assert victim.name == "fat"


def test_io_deadline_orders_by_deadline():
    reqs = [
        DiskRequest(req_id=1, owner=1, lba=100, deadline=5.0),
        DiskRequest(req_id=2, owner=1, lba=10, deadline=1.0),
    ]
    sched = IOScheduler(policy="deadline", requests=reqs)
    assert [r.req_id for r in sched.schedule(0.0)] == [2, 1]


def test_io_cfq_round_robins_owners():
    reqs = [
        DiskRequest(req_id=1, owner=1, lba=100, deadline=5.0),
        DiskRequest(req_id=2, owner=1, lba=101, deadline=6.0),
        DiskRequest(req_id=3, owner=2, lba=10, deadline=2.0),
    ]
    sched = IOScheduler(policy="cfq", requests=reqs)
    order = [r.req_id for r in sched.schedule(0.0)]
    assert order == [1, 3, 2]


def test_cgroup_cpu_weight_fraction():
    g1 = CgroupV2(name="a", cpu_weight=100)
    g2 = CgroupV2(name="b", cpu_weight=100)
    assert g1.cpu_share_fraction(200) == 0.5
    assert g2.cpu_share_fraction(200) == 0.5


def test_cgroup_cpu_cap_trumps_weight():
    g = CgroupV2(name="a", cpu_weight=10000, cpu_max_nanos=50_000_000, cpu_period_nanos=100_000_000)
    assert g.cpu_limit_fraction() == 0.5
    # Even with huge weight, effective share cannot exceed cap
    assert g.effective_cpu_fraction(total_weight=11000) == 0.5


def test_cgroup_memory_limit():
    g = CgroupV2(name="a", memory_max=100)
    ok, usage = g.request_memory(60, current_usage=30)
    assert ok and usage == 90
    ok, usage = g.request_memory(20, current_usage=90)
    assert ok is False and usage == 90

"""test_cgroup — CPU throttle、内存 OOM、pids 上限。"""
from crt_mini.cgroup import Cgroup


def test_cpu_throttle_when_quota_exceeded():
    cg = Cgroup(name="/job", cpu_quota_us=50_000, cpu_period_us=100_000)
    assert cg.cpu_max == "50000 100000"
    # 每周期要 80000us，但配额 50000us → 节流
    r1 = cg.tick(80_000)
    r2 = cg.tick(80_000)
    assert r1 == "throttled" and r2 == "throttled"
    assert cg.nr_throttled == 2
    assert cg.throttled_usec == 60_000  # 两个周期各超 30000us
    assert cg.cpu_used_us == 100_000    # 只有配额部分真正执行


def test_cpu_ok_within_quota():
    cg = Cgroup(name="/ok", cpu_quota_us=100_000)
    assert cg.tick(40_000) == "ok"
    assert cg.nr_throttled == 0


def test_cpu_unlimited_never_throttles():
    cg = Cgroup(name="/unc")
    assert cg.tick(10**9) == "ok"
    assert cg.cpu_max == "max"


def test_memory_oom_when_exceeding_max():
    cg = Cgroup(name="/mem", memory_max=4096)
    assert cg.consume_memory(2048) == "ok"
    assert cg.memory_current == 2048
    assert cg.consume_memory(4096) == "oom"   # 累计超 4096
    assert cg.oom_kills == 1
    assert cg.memory_current == 2048          # OOM 分配被拒，回滚


def test_memory_release_and_unlimited():
    cg = Cgroup(name="/u")
    cg.consume_memory(1000)
    cg.release_memory(400)
    assert cg.memory_current == 600
    unlimited = Cgroup(name="/uu", memory_max=-1)
    assert unlimited.memory_max == -1
    assert unlimited.consume_memory(10**12) == "ok"  # 不限


def test_pids_limit_blocks_fork():
    cg = Cgroup(name="/p", pids_max=2)
    assert cg.acquire_pid() == "ok"
    assert cg.acquire_pid() == "ok"
    assert cg.acquire_pid() == "pids-exceeded"  # fork bomb 被挡
    assert cg.nr_pids == 2


def test_stat_shape():
    cg = Cgroup(name="/s", cpu_quota_us=10_000, memory_max=100)
    cg.tick(20_000)
    cg.consume_memory(50)
    st = cg.stat()
    assert st["cpu.max"] == "10000 100000"
    assert st["nr_throttled"] == 1
    assert st["memory.current"] == 50
    assert st["memory.max"] == 100

"""Demo entry point for the Linux systems mini simulator."""
from __future__ import annotations

from linux_systems_mini.scheduler import CFSScheduler, Process
from linux_systems_mini.memory import OOMKiller, PageCache, ProcessMemory
from linux_systems_mini.io import DiskRequest, IOScheduler
from linux_systems_mini.cgroup import CgroupV2


def demo_cfs() -> None:
    print("=== CFS Scheduler Demo ===")
    sched = CFSScheduler(tasks=[
        Process(pid=1, name="train-main", nice=0),
        Process(pid=2, name="dataloader", nice=5),
        Process(pid=3, name="logger", nice=10),
    ])
    log = sched.run(12)
    for pid, v in log:
        name = next(t.name for t in sched.tasks if t.pid == pid)
        print(f"  run {name:12s} -> vruntime={v:.2f}")
    print(f"  final vruntime spread: {sched.normalized_vruntime_spread():.2f}")


def demo_page_cache() -> None:
    print("\n=== Page Cache LRU Demo ===")
    cache = PageCache(capacity=4)
    accesses = [(101, 1), (102, 1), (103, 2), (104, 2), (101, 1), (105, 3)]
    for page_id, owner in accesses:
        hit = cache.access(page_id, owner)
        print(f"  access page {page_id} owner={owner}: {'HIT' if hit else 'MISS'}")
    print(f"  hits={cache.hits} misses={cache.misses}")
    print(f"  final pages: {list(cache.pages.keys())}")


def demo_oom() -> None:
    print("\n=== OOM Killer Demo ===")
    killer = OOMKiller([
        ProcessMemory(pid=1, name="train", rss=800, nice=0, runtime=100),
        ProcessMemory(pid=2, name="dataloader", rss=300, nice=5, runtime=100),
        ProcessMemory(pid=3, name="monitor", rss=50, nice=10, runtime=7200),
    ])
    for p in killer.processes:
        print(f"  {p.name:12s} rss={p.rss} nice={p.nice} score={killer.score(p):.1f}")
    victim = killer.pick_victim()
    print(f"  victim: {victim.name if victim else 'none'}")


def demo_io() -> None:
    print("\n=== I/O Scheduler Demo ===")
    reqs = [
        DiskRequest(req_id=1, owner=1, lba=100, deadline=5.0),
        DiskRequest(req_id=2, owner=2, lba=10, deadline=2.0),
        DiskRequest(req_id=3, owner=1, lba=105, deadline=8.0),
        DiskRequest(req_id=4, owner=2, lba=15, deadline=1.5),
    ]
    for policy in ("noop", "deadline", "cfq"):
        sched = IOScheduler(policy=policy, requests=list(reqs))
        ordered = sched.schedule(current_time=0.0)
        misses = sched.deadline_misses(current_time=0.0)
        ids = [r.req_id for r in ordered]
        print(f"  policy={policy:8s} order={ids} deadline_misses={misses}")


def demo_cgroup() -> None:
    print("\n=== cgroup v2 Resource Limit Demo ===")
    groups = [
        CgroupV2(name="guaranteed", cpu_weight=800, cpu_max_nanos=200_000_000, memory_max=4_000_000_000),
        CgroupV2(name="burstable", cpu_weight=400, memory_max=2_000_000_000),
        CgroupV2(name="best-effort", cpu_weight=100),
    ]
    shares = CgroupV2("root").total_requested_cpu(groups)
    for name, frac in shares.items():
        print(f"  {name:12s} effective CPU fraction={frac:.2%}")

    g = groups[0]
    ok, usage = g.request_memory(1_000_000_000, current_usage=3_000_000_000)
    print(f"  guaranteed request 1GB @ used 3GB: allowed={ok}, usage={usage}")
    ok, usage = g.request_memory(2_000_000_000, current_usage=3_000_000_000)
    print(f"  guaranteed request 2GB @ used 3GB: allowed={ok}, usage={usage}")


def main() -> None:
    demo_cfs()
    demo_page_cache()
    demo_oom()
    demo_io()
    demo_cgroup()


if __name__ == "__main__":
    main()

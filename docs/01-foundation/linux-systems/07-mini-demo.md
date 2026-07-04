# 7. 工程实践：Linux 机制模拟器

本章的 Mini Demo 是一个 CPU 可运行的 Linux 机制模拟器。它用纯 Python 模拟了 CFS 调度器、页缓存 LRU、OOM killer、I/O 调度器和 cgroup v2 资源限制，帮助你在不读内核源码的情况下建立直觉。

> **注意**：这是教学模拟器，不是真实 Linux 内核。真实调优需要在真实系统上使用 `perf`、`bpftrace`、`numactl` 等工具。

## 7.1 目录结构

```
docs/01-foundation/linux-systems/mini-demo/
├── README.md
├── pyproject.toml
├── linux_systems_mini/
│   ├── __init__.py
│   ├── scheduler.py    # CFS 调度器
│   ├── memory.py       # Page Cache LRU + OOM Killer
│   ├── io.py           # I/O 调度器
│   ├── cgroup.py       # cgroup v2 CPU/memory
│   └── demo.py         # 入口脚本
└── tests/
    └── test_all.py
```

## 7.2 运行方式

```bash
cd docs/01-foundation/linux-systems/mini-demo
pip install -e ".[dev]"
pytest tests/ -v
python -m linux_systems_mini.demo
```

## 7.3 CFS 调度器

核心代码在 `scheduler.py`：

```python
class Process:
    pid: int
    name: str
    nice: int
    vruntime: float
    weight: float   # nice 越低，weight 越大

class CFSScheduler:
    tasks: List[Process]
    # 用优先队列按 vruntime 排序

    def step(self) -> Process:
        task = pop smallest vruntime
        task.vruntime += time_slice * (1024 / task.weight)
        push back
        return task
```

运行 `demo.py` 可以看到：nice 越低（权重越大）的进程，vruntime 增长越慢，因此更频繁被调度。

```
=== CFS Scheduler Demo ===
  run train-main   -> vruntime=10.00
  run dataloader   -> vruntime=30.52
  run logger       -> vruntime=93.13
  run train-main   -> vruntime=20.00
  ...
  final vruntime spread: 13.13
```

## 7.4 页缓存与 OOM

`memory.py` 实现了 LRU 页缓存和 OOM score。

```python
class PageCache:
    capacity: int
    pages: OrderedDict[int, Page]  # LRU 顺序

    def access(self, page_id, owner):
        if hit: move_to_end; return True
        else: evict LRU if needed; load; return False
```

Demo 输出展示了 miss/hit 和 LRU 淘汰：

```
=== Page Cache LRU Demo ===
  access page 101 owner=1: MISS
  access page 102 owner=1: MISS
  access page 103 owner=2: MISS
  access page 104 owner=2: MISS
  access page 101 owner=1: HIT
  access page 105 owner=3: MISS
  hits=1 misses=5
  final pages: [103, 104, 101, 105]
```

OOM score 主要由 RSS 决定，运行时间长、nice 低的进程会被保护：

```
=== OOM Killer Demo ===
  train        rss=800 nice=0 score=727.3
  dataloader   rss=300 nice=5 score=247.7
  monitor      rss=50 nice=10 score=1.0
  victim: train
```

## 7.5 I/O 调度器

`io.py` 实现了三种策略：

- **noop**：先来先服务；
- **deadline**：按截止时间排序；
- **cfq**：按进程轮转。

```
=== I/O Scheduler Demo ===
  policy=noop     order=[1, 2, 3, 4] deadline_misses=1
  policy=deadline order=[4, 2, 1, 3] deadline_misses=0
  policy=cfq      order=[1, 2, 3, 4] deadline_misses=0
```

## 7.6 cgroup 资源限制

`cgroup.py` 模拟了 CPU weight、CPU hard cap 和 memory limit。

```
=== cgroup v2 Resource Limit Demo ===
  guaranteed   effective CPU fraction=61.54%
  burstable    effective CPU fraction=30.77%
  best-effort  effective CPU fraction=7.69%
  guaranteed request 1GB @ used 3GB: allowed=True, usage=4000000000
  guaranteed request 2GB @ used 3GB: allowed=False, usage=3000000000
```

## 7.7 与真实 Linux 的差异

| 模拟器 | 真实 Linux |
|---|---|
| Python 对象模拟进程 | `task_struct` + `sched_entity` |
| 优先队列模拟运行队列 | `cfs_rq` + 红黑树 + 负载均衡 |
| 简化的 LRU 列表 | 复杂页回收算法 + 多级页表 |
| 离散事件 I/O 调度 | `bio` + I/O scheduler + 设备驱动 |
| 简化 CPU/memory 限制公式 | cgroup v2 `cpu.weight/max` + `memory.max/high/low` |

## 7.8 本节小结

- Mini Demo 用 Python 模拟了 Linux 的 CFS、page cache、OOM、I/O 调度、cgroup；
- 通过运行 demo，可以直观看到 nice 值、LRU 淘汰、调度策略、资源限制的效果；
- 这只是一个教学工具，真实系统调优需要真实工具和真实环境。

下一节进入生产环境：AI 场景下的 Linux 调优与排障。

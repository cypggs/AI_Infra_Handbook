# Linux 系统与性能调优 Mini Demo

本目录包含一个 CPU 可运行的 Linux 机制模拟器，用于帮助理解 Linux 内核中与 AI Infra 最相关的几个子系统。

> **注意**：这是一个教学模拟器，不是真实 Linux 内核。它用于建立直觉，真实调优需要在真实 Linux 系统上使用 `perf`、`bpftrace`、`numactl` 等工具。

## 模拟内容

| 模块 | 文件 | 模拟的机制 |
|---|---|---|
| CFS 调度器 | `linux_systems_mini/scheduler.py` | vruntime、nice 值、红黑树运行队列 |
| 页缓存与 OOM | `linux_systems_mini/memory.py` | LRU 淘汰、OOM score |
| I/O 调度器 | `linux_systems_mini/io.py` | noop、deadline、cfq 排序策略 |
| cgroup 资源限制 | `linux_systems_mini/cgroup.py` | cpu.shares / cpu.max、memory.limit |
| 入口脚本 | `linux_systems_mini/demo.py` | 展示所有模块的运行效果 |

## 安装与运行

```bash
cd docs/01-foundation/linux-systems/mini-demo
pip install -e ".[dev]"
pytest tests/ -v
python -m linux_systems_mini.demo
```

## 与真实 Linux 的差异

| 模拟器 | 真实 Linux |
|---|---|
| Python 对象模拟进程 | task_struct + sched_entity |
| 简单列表/红黑树模拟运行队列 | 真实的 `cfs_rq` + 红黑树 + 负载均衡 |
| 固定 page size 和简化的 LRU | 复杂页回收算法 + PGD/PUD/PMD/PTE |
| 离散事件 I/O 调度 | 真实块层 `bio` + I/O scheduler + 设备驱动 |
| 简化的 CPU/memory 限制公式 | cgroup v2 `cpu.weight/max` + `memory.max/high/low` |

## 推荐阅读顺序

1. 先阅读本章文档，理解 CFS、page cache、I/O 调度、cgroup 的概念；
2. 运行 `demo.py`，观察模拟输出；
3. 打开源码，看每个机制是怎么被简化模拟的；
4. 回到生产环境，用真实工具验证。

# 8. 企业生产实践：AI 场景的 Linux 调优与排障

生产环境的 Linux 调优不是“改一个参数就起飞”，而是先定位瓶颈，再有针对性地调整。本章聚焦 AI 训练/推理中最常见的场景。

## 8.1 训练场景：GPU 利用率低，CPU 在拖后腿

### 现象

- `nvidia-smi` 显示 GPU 利用率波动大，经常掉到 30% 以下；
- CPU 使用率不高，但 DataLoader 线程抢不到 CPU；
- 数据加载延迟高。

### 可能原因

1. DataLoader `num_workers` 太少；
2. 数据预处理（decode、augment）在 Python GIL 下串行；
3. CPU 被其他高优先级进程抢占；
4. I/O 带宽不足，page cache 命中率低；
5. NUMA 绑定错误，CPU 访问远程内存或远程 GPU。

### 调优手段

| 手段 | 命令/配置 | 效果 |
|---|---|---|
| 增加 DataLoader workers | `num_workers=8/16` | 并行加载数据 |
| 使用 `pin_memory=True` | PyTorch DataLoader | 加速 CPU→GPU 拷贝 |
| CPU 亲和性 | `taskset -c 0-31` | 减少缓存抖动 |
| NUMA 绑定 | `numactl --cpunodebind=0 --membind=0` | 本地内存访问 |
| 提升进程优先级 | `nice -n -5` 或 `chrt` | 减少被抢占 |
| 使用 SSD / 并行文件系统 | — | 提升 I/O 吞吐 |
| 预取数据集到内存/本地 SSD | `cp` / `torch.utils.data` | 减少网络文件系统依赖 |

## 8.2 推理场景：Latency 抖动

### 现象

- P99 延迟比 P50 高很多；
- 延迟偶尔 spikes；
- 同一条请求有时快有时慢。

### 可能原因

1. CPU 抢占：其他进程或服务抢占了推理进程的 CPU；
2. cgroup CPU throttle：容器 CPU limit 设置过低；
3. 内核态开销：系统调用、上下文切换、中断处理；
4. GC / 内存分配抖动；
5. 网络中断绑定不当。

### 调优手段

| 手段 | 命令/配置 | 效果 |
|---|---|---|
| CPU 隔离 | `isolcpus=8-15` + taskset | 避免其他任务干扰 |
| 禁用 CPU limit 或提高 limit | K8s `resources.limits.cpu` | 减少 throttle |
| 实时调度 | `SCHED_FIFO` 慎用 | 降低被抢占概率 |
| 中断绑定 | `/proc/irq/<n>/smp_affinity` | 把网卡中断绑定到非业务 CPU |
| 使用 HugePages | `hugetlbfs` / THP | 减少 TLB miss |
| 减少系统调用 | `vLLM` 的 zero-copy、batching | 降低内核态开销 |

## 8.3 OOM 与内存问题

### 现象

- 容器被 OOM Kill；
- 系统 swap 爆满；
- 进程 RSS 持续增长。

### 排查

```bash
# 查看 OOM killer 日志
dmesg | grep -i "killed process"

# 查看 cgroup memory 状态
cat /sys/fs/cgroup/memory.stat
cat /sys/fs/cgroup/memory.current
cat /sys/fs/cgroup/memory.max

# 查看进程内存
cat /proc/<pid>/status | grep -E "VmRSS|VmSize"
```

### 调优手段

| 问题 | 手段 |
|---|---|
| cgroup OOM | 增大 `memory.limit`，或优化程序内存使用 |
| 系统 OOM | 增加物理内存、swap、或调整 `oom_score_adj` |
| 内存泄漏 | 用 `valgrind`、`memray`、或 eBPF 追踪分配 |
| page cache 占用过多 | 调整 `vm.dirty_ratio`、`vm.dirty_background_ratio` |
| 大模型内存碎片化 | 使用 HugePages、减少动态分配 |

## 8.4 I/O 与 checkpoint 抖动

### 现象

- 训练每隔一段时间卡顿，对应 checkpoint 保存；
- `iowait` 高；
- 分布式文件系统（如 Lustre、GPFS）响应慢。

### 调优手段

| 手段 | 命令/配置 |
|---|---|
| 异步 checkpoint | 保存到本地 NVMe，后台上传到共享存储 |
| Direct I/O | `torch.save(..., _use_new_zipfile_serialization=True)` + `O_DIRECT` |
| 调整脏页回写 | `vm.dirty_ratio=40`, `vm.dirty_background_ratio=10` |
| 选择合适的文件系统 | 大数据集用 xfs，海量小文件考虑其他方案 |
| I/O 调度器 | NVMe 用 `none` 或 `mq-deadline` |

## 8.5 网络与分布式训练

### 现象

- NCCL all-reduce 时间长；
- 网络吞吐不达标；
- 某些节点通信慢。

### 调优手段

| 手段 | 命令/配置 |
|---|---|
| RDMA / InfiniBand | 确认 `NCCL_IB_HCA`、`NCCL_SOCKET_IFNAME` |
| IRQ affinity | 把网卡中断绑定到特定 CPU |
| RPS/RFS/XPS | 均匀分布软中断，固定同 flow |
| busy polling | `net.core.busy_poll`、`net.core.busy_budget` |
| 禁用 irqbalance | 手动控制中断分布 |

## 8.6 cgroup v2 迁移实践

Kubernetes 1.25+ 默认 cgroup v2。迁移时需要注意：

- `cpu.shares` 变成 `cpu.weight`；
- `cpu.cfs_quota_us` 变成 `cpu.max`；
- `memory.limit_in_bytes` 变成 `memory.max`；
- 不再有 `memory.kmem.limit_in_bytes`；
- 某些老旧的监控脚本需要更新路径。

## 8.7 常用排查流程

遇到性能问题时，建议按这个顺序排查：

```
1. top / htop      → CPU、内存、进程状态
2. vmstat 1        → 上下文切换、I/O、CPU 空闲类型
3. iostat -x 1     → 磁盘 I/O 瓶颈
4. mpstat -P ALL 1 → 单个 CPU 核心是否热点
5. sar -n DEV 1    → 网络吞吐
6. perf top        → 热点函数
7. bpftrace        → 动态追踪具体事件
```

## 8.8 本节小结

- AI 训练要关注 CPU-GPU 协同、I/O、NUMA；
- AI 推理要关注延迟抖动、CPU 抢占、中断绑定；
- OOM 排查要结合 cgroup、系统日志、进程状态；
- checkpoint 和网络问题往往和 Linux I/O、网络子系统有关；
- 调优前先观测，用工具链定位瓶颈。

下一节总结系统化的性能分析方法论。

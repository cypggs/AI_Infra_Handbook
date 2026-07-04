# 9. 最佳实践：Linux 性能分析方法论

调优 Linux 不是玄学。好的方法论能让你少走弯路，避免“看到一个参数就改”的乱枪打鸟。

## 9.1 先观测，再调优

任何调优都应该从数据开始，而不是从猜测开始。

```mermaid
flowchart LR
    A[定义问题] --> B[选择指标]
    B --> C[采集数据]
    C --> D[定位瓶颈]
    D --> E[制定假设]
    E --> F[小范围验证]
    F --> G[全量 rollout]
    G --> H[持续监控]
```

## 9.2 USE 方法

Brendan Gregg 提出的 USE 方法适用于资源型瓶颈分析：

| 资源 | 使用率 | 饱和度 | 错误 |
|---|---|---|---|
| CPU | `mpstat`、`top` | run queue、load average | machine check、thermal |
| 内存 | `free`、`vmstat` | swap、OOM | ECC error |
| 磁盘 | `iostat` | I/O wait、queue depth | SMART error |
| 网络 | `sar -n DEV` | retransmit、buffer full | CRC、drop |

**使用率**高 + **饱和度**高 → 资源不足，需要扩容或优化。

## 9.3 Red Method

Red Method 更适合应用层：

- **Rate**：请求速率；
- **Errors**：错误率；
- **Duration**：请求延迟。

AI 推理服务可以用 Red Method 监控 QPS、错误率、P50/P99 延迟，再用 Linux 工具定位延迟根因。

## 9.4 自上而下 vs 自下而上

| 方法 | 起点 | 适用 |
|---|---|---|
| 自上而下 | 应用指标（QPS、latency） | 已知应用慢，找系统原因 |
| 自下而上 | 系统指标（CPU、I/O） | 系统告警，找受影响应用 |

AI 平台通常先用 Grafana/Prometheus 发现异常，再用 `perf`、`bpftrace` 钻到内核层。

## 9.5 常见误区

### 误区 1：盲目修改内核参数

网上的“性能优化 50 条”不一定适合你的场景。比如：

- `vm.swappiness=0` 在某些场景下会导致 OOM；
- `tcp_tw_recycle` 已经被废弃；
- 实时调度用不好会让系统卡死。

### 误区 2：只看平均值

AI 推理 latency 的 P99 往往比 P50 重要得多。只看平均会掩盖长尾问题。

### 误区 3：忽视 NUMA

多路服务器上，错误的 NUMA 绑定会让内存带宽下降 20% 以上。

### 误区 4：CPU limit 设得太低

Kubernetes 的 CPU limit 通过 cgroup quota 实现，过低的 limit 会导致 throttle 和延迟抖动。

## 9.6 建立基线

调优前一定要建立基线：

- 训练任务每步时间；
- 推理 QPS / P50 / P99；
- 系统 CPU、内存、I/O、网络指标；
- 变更后对比。

没有基线，就无法判断调优是否有效。

## 9.7 eBPF 现代追踪

eBPF 让你可以安全地在内核里运行小程序，动态追踪事件。

常用工具：

- `bpftrace`：脚本式追踪；
- `bcc`：Python/C 工具集；
- `perf`：采样和 tracepoint；
- `ftrace`：内核函数追踪。

AI 场景可以用 eBPF 追踪：

- 系统调用耗时；
- 上下文切换；
- TCP 重传；
- 文件系统 I/O；
- cgroup throttle 事件。

## 9.8 配置管理

生产环境的内核参数和 systemd unit 应该用 IaC 管理：

- Ansible / Puppet / Chef；
- Kubernetes DaemonSet + init container；
- 节点镜像标准化。

避免每台机器手工 `sysctl -w`。

## 9.9 本节小结

- 调优前先观测，定义指标，建立基线；
- USE 方法分析资源瓶颈，Red Method 分析应用；
- 不要迷信通用优化参数；
- 关注 P99、NUMA、cgroup throttle；
- eBPF 是现代化内核追踪的利器；
- 用配置管理工具固化调优结果。

下一节是面试题。

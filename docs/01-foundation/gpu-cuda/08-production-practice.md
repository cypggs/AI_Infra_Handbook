# 8. 企业生产实践：选型、虚拟化、监控与故障排查

GPU 是 AI 基础设施中最昂贵的组件之一。生产环境中的每一个决策——买哪张卡、怎么切分、怎么监控、怎么排错——都直接影响成本和稳定性。

## 8.1 GPU 选型：训练 vs 推理

### 训练场景

训练关注**算力峰值**和**多卡互联**。

| 指标 | 为什么重要 |
|---|---|
| FP8/FP16 Tensor Core 算力 | 决定训练速度 |
| 显存容量 | 决定能放多大的模型和 batch |
| NVLink / NVSwitch | 决定多卡通信效率 |
| 能效比 | 决定长期电费 |

**推荐**：H100 SXM（主流）、H200（长上下文/大 batch）、B200/GB200（下一代大规模训练）。

### 推理场景

推理更关注**延迟、吞吐、显存**。

| 指标 | 为什么重要 |
|---|---|
| 显存带宽 | Decode 阶段是内存瓶颈 |
| FP8/FP4 支持 | 量化后吞吐提升 |
| 显存容量 | KV Cache 占用巨大 |
| 单卡成本 | 推理通常需要大量卡 |

**推荐**：H100/H200（高并发）、B200（FP4 低延迟）、L40S/RTX 4090（低成本离线推理）。

## 8.2 GPU 虚拟化技术对比

在 Kubernetes 等多租户环境中，需要把物理 GPU 切成更小的单位。

| 技术 | 粒度 | 隔离性 | 适用场景 |
|---|---|---|---|
| **MIG（Multi-Instance GPU）** | 硬件级，最多 7 实例 | 强（内存、计算隔离） | 多租户训练/推理 |
| **MPS（Multi-Process Service）** | 进程级共享 | 中（共享显存，错开执行） | 小模型多进程推理 |
| **Time-slicing** | 时间片轮转 | 弱 | 开发测试、低负载 |
| **vGPU** | 软件虚拟化 | 较强 | VDI、虚拟化平台 |

### MIG

A100/H100 支持把一张 80GB GPU 切成多个独立实例，例如：

- 1g.10gb：1/7 计算 + 10GB 显存
- 2g.20gb：2/7 计算 + 20GB 显存
- 3g.40gb：3/7 计算 + 40GB 显存

MIG 实例之间是硬件隔离的，适合生产多租户。

### MPS

MPS 允许多个 CUDA 进程共享同一张 GPU，通过错开执行提高利用率。它的隔离性不如 MIG，但开销更小，适合同一信任域内的多服务共享。

详细调度逻辑参见 [Kubernetes GPU 调度](/02-cloud-native/kubernetes/)。

## 8.3 NVIDIA GPU Operator 与 Device Plugin

在 Kubernetes 上使用 GPU 通常需要：

- **NVIDIA Device Plugin**：把 GPU 作为 `nvidia.com/gpu` 资源暴露给 kubelet；
- **GPU Feature Discovery**：给节点打标签（GPU 型号、MIG 能力等）；
- **MIG Manager**：动态切分 MIG；
- **DCGM Exporter**：暴露 GPU 指标到 Prometheus。

GPU Operator 把这些组件打包成一个 Helm Chart，自动在节点上安装驱动、container toolkit 和相关 DaemonSet。

## 8.4 监控：DCGM 关键指标

生产环境应监控以下 DCGM 指标：

| 指标 | 含义 | 告警建议 |
|---|---|---|
| `DCGM_FI_DEV_GPU_UTIL` | GPU 利用率 | 低于 50% 可能说明 batch 不足或 CPU 瓶颈 |
| `DCGM_FI_DEV_MEM_COPY_UTIL` | 显存带宽利用率 | 接近 100% 说明内存瓶颈 |
| `DCGM_FI_DEV_FB_FREE / FB_USED` | 显存使用 | 超过 90% 预警 OOM |
| `DCGM_FI_DEV_GPU_TEMP` | GPU 温度 | 超过 85°C 告警 |
| `DCGM_FI_DEV_POWER_USAGE` | 功耗 | 异常波动可能预示硬件问题 |
| `DCGM_FI_DEV_PCIE_REPLAY_COUNTER` | PCIe 重传 | 持续增长说明链路不稳定 |
| `DCGM_FI_DEV_XID_ERRORS` | Xid 错误码 | 非零即需关注 |

## 8.5 Xid 错误码：GPU 的“蓝屏代码”

Xid 是 NVIDIA GPU 的硬件错误码。常见码：

| Xid | 含义 | 处理 |
|---|---|---|
| 48 | 双位 ECC 错误 | 通常需要重置 GPU 或换卡 |
| 74 | NVLink 错误 | 检查 NVLink 连接和拓扑 |
| 79 | 温度/功耗问题 | 检查散热和电源 |
| 95 | 内存分页错误 | 可能是 OOM 或硬件故障 |
| 119 | 已纠正 ECC 错误 | 监控，达到阈值更换 |

排查命令：

```bash
nvidia-smi -q | grep -A 5 "ECC Mode"
nvidia-smi -q -d ECC
# 查看 Xid 历史
dmesg | grep -i xid
```

## 8.6 CUDA OOM 排查

CUDA OOM 是训练/推理最常见的问题之一。排查思路：

1. **确认真实占用**：
   ```python
   torch.cuda.memory_allocated()
   torch.cuda.memory_reserved()
   torch.cuda.max_memory_allocated()
   ```
2. **区分 allocated vs reserved**：reserved 包含缓存池，可能远大于 allocated；
3. **检查 activation checkpointing**：大模型训练可以通过重计算减少激活显存；
4. **检查 batch size 和序列长度**：长上下文对 KV Cache 影响巨大；
5. **查看是否有 zombie 进程占用**：`nvidia-smi` 看是否有未释放显存。

## 8.7 NCCL 超时与通信问题

多卡训练常见错误：

```text
NCCL operation failed: unhandled system error
NCCL timeout
```

排查清单：

1. **确认所有 GPU 在同一 NVLink/IB 域内**，拓扑是否最优；
2. **检查 NCCL 环境变量**：
   - `NCCL_DEBUG=INFO`
   - `NCCL_IB_DISABLE=0/1`
   - `NCCL_SOCKET_IFNAME`
3. **检查网络**：IB 端口是否 up，RoCE 是否启用 PFC/ECN；
4. **检查 CUDA 版本与 NCCL 版本匹配**；
5. **查看是否有慢节点拖慢整体**。

## 8.8 Nsight 性能分析

NVIDIA 提供两套主要性能分析工具：

- **Nsight Systems（nsys）**：系统级时间线，看 CPU-GPU 同步、kernel 启动、通信 overlap；
- **Nsight Compute（ncu）**：单个 kernel 深度分析，看 occupancy、memory throughput、Tensor Core 利用率。

常用命令：

```bash
# 采集整个应用时间线
nsys profile -o report python train.py

# 分析单个 kernel
ncu -o kernel_report python train.py
```

## 8.9 本节小结

生产 GPU 管理的核心：

1. **训练看算力+互联，推理看带宽+显存+延迟**；
2. **MIG/MPS/Time-slicing 按隔离性需求选择**；
3. **DCGM + Prometheus/Grafana 是监控基座**；
4. **Xid 错误码是硬件健康的重要信号**；
5. **OOM 和 NCCL 超时是最常见的两类故障**，需要系统化排查。

下一节，我们总结写高效 CUDA kernel 和运维 GPU 集群的最佳实践。

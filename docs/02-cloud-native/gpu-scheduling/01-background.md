# 1. 背景

> 一句话理解：**K8s 原生调度器是为 CPU/内存设计的“可分配即可调度”，而 GPU 是 all-or-nothing、拓扑敏感、显存硬墙、多租户争抢的稀缺资源**——不理解 AI 负载的这四条特征，就无法解释为什么 Device Plugin、GPU Operator、Gang 调度、队列调度会相继出现。

## 1.1 AI 训练与推理的四个本质特征

### all-or-nothing：要么全员就位，要么全部白跑

分布式训练作业（DDP、FSDP、Megatron、DeepSpeed）通常由若干 worker 组成，每个 worker 都需要一张或多张 GPU。如果 scheduler 一个个地分配，会出现：

```text
worker-0  worker-1  worker-2  worker-3  worker-4  worker-5  worker-6  worker-7
   ✓         ✓         ✓         ✓         ✓         ✓         ✓         ✗
```

前 7 个 Pod 已经拿到卡开始初始化，第 8 个因为集群没卡而永远 Pending。前 7 个要么 hang 在 `init_process_group`，要么把显存占着却没有任何有效计算。这就是 **Gang 调度**要解决的问题：8 个 Pod 必须**同时**被调度，否则一个都不调。

### 显存墙：OOM 不是“内存不够”，而是“任务进不来”

GPU 显存（VRAM）是硬资源。一张 80GB 的 A100 在加载 70B 模型时，权重、优化器状态、激活值、KV Cache 会把显存吃得干干净净：

```text
模型参数      优化器状态      激活值      KV Cache      可用余量
   │             │            │            │              │
   ▼             ▼            ▼            ▼              ▼
 70 GB          14 GB        8 GB         6 GB           2 GB  ← 余量极小
```

K8s 原生只认识 `nvidia.com/gpu: 1`，不认识“这张卡还剩多少显存”。两个都请求 1 卡的 Pod 可以落在同一张卡上，但如果它们各自都需要 48GB，而卡只有 80GB，就会出现 CUDA OOM。解决方向有两个：

1. 在 Pod 里显式声明显存需求（通过 Device Plugin 的扩展资源或第三方调度器）。
2. 使用 MIG 等硬切分，把一张物理卡切成多张逻辑卡，每张逻辑卡有固定显存。

### 拓扑敏感：NCCL 性能不是只看卡数

多机训练的性能由 NVLink、PCIe switch、NUMA、NIC 位置共同决定：

| 拓扑因素 | 影响 |
|---|---|
| NVLink | 同一 NVLink domain 内的 GPU 之间带宽最高，适合张量并行 |
| PCIe Switch / Root Complex | 跨 switch 的 P2P 带宽下降，延迟上升 |
| NUMA | GPU 与 CPU 内存、NIC 是否在同一 NUMA node，影响数据拷贝 |
| NIC 位置 | GPU Direct RDMA 要求 GPU 与 RDMA NIC 在同一 PCIe switch 下或同一 NUMA node |

原生 K8s scheduler 看不到这些拓扑信息，它只数“这张节点有几张卡”。结果一个需要 8 卡 NVLink 亲和的训练 Job 可能被拆到两台 4 卡机器上，或者 8 张卡跨了两个 PCIe switch，NCCL 性能大打折扣。

### 多租户公平性：训练 Job 与推理服务抢同一张卡

AI 平台往往同时跑：

- 长时间、高优先级、需要多卡的训练 Job；
- 短生命周期、低延迟要求、需要快速扩缩容的推理服务；
- 开发调试用的 Jupyter Notebook。

如果没有任何排队与配额机制，就会出现“谁手快谁抢到卡”。训练 Job 把资源占满，推理服务 Pending；推理服务把资源占满，训练 Job 永远排不上。平台需要的不是“先到先得”，而是：

- **队列（Queue）**：把未满足的资源需求按优先级和配额排队。
- **公平调度（Fair Sharing）**：保证不同团队/业务按权重获得资源。
- **抢占（Preemption）**：高优先级任务可以抢占低优先级任务。
- **资源预留/借用（Lending）**：团队 A 的空闲配额可以借给团队 B，但 A 有任务时收回。

## 1.2 原生 Kubernetes 调度为什么不够

Kubernetes 的默认调度器非常擅长 CPU/内存调度：它看 `requests/limits`，跑 Filter → Score → Bind， kubelet 负责实际执行。但面对 GPU，它缺少以下能力：

| 缺失能力 | 原生行为 | GPU 场景需要的 |
|---|---|---|
| 设备发现 | 不认识 GPU | 通过 Device Plugin 把 GPU 注册为 `nvidia.com/gpu` |
| 显存感知 | 只数卡，不看显存 | 知道每张卡还剩多少显存，或按 MIG 实例分配 |
| 拓扑感知 | 看不到 NUMA/PCIe/NVLink | 把 Pod 调度到拓扑最优的 GPU 组合 |
| Gang 调度 | 逐个 Pod 调度 | 一组 Pod 同时满足才绑定 |
| 队列公平 | 没有队列概念 | 多租户排队、配额、抢占、借用 |
| 动态切分 | 资源是整数 | MIG/MPS/time-slicing 的细粒度共享 |
| 故障隔离 | 节点级 | 单卡故障时不要把新 Pod 调度到该卡 |

这些缺口不是 K8s 设计错误，而是 K8s 故意把“异构资源怎么暴露”交给 Device Plugin，把“复杂调度规则怎么实现”交给调度框架扩展点。GPU 调度主题就是研究怎么把这些扩展点串起来。

## 1.3 GPU 在 K8s 上的演进路线

```text
2016  Kubernetes 1.4   Device Plugins 设计讨论开始
2017  Kubernetes 1.8   Device Plugins alpha
2018  Kubernetes 1.10  Device Plugins beta
2018  Kubernetes 1.11  scheduler-plugins / Coscheduling 雏形
2019  Kubernetes 1.14  Device Plugins GA
2019  Volcano 0.1      面向 AI/HPC 的批处理调度器
2020  NVIDIA GPU Operator 1.0   自动化节点 GPU 组件
2021  scheduler-plugins NodeResourceTopology
2022  Kueue 0.1        面向 Job 的队列与公平调度
2023  Kueue 进入 Kubernetes SIG-scheduling 子项目
2024+ DRA（Dynamic Resource Allocation）逐步成熟，可能替代部分 Device Plugin 语义
```

这条演进线可以分成三层：

1. **设备发现与分配层**：Device Plugin 让 kubelet 能“看见”GPU 并分配给容器。
2. **节点组件自动化层**：GPU Operator 把驱动、container-toolkit、Device Plugin、监控、MIG 配置等组件打包成节点就绪流水线。
3. **调度策略增强层**：scheduler-plugins、Volcano、Kueue 分别在默认调度器之上或之外提供 Gang、拓扑、队列能力。

## 1.4 AI Infra 视角：为什么 GPU 调度格外重要

### 训练场景

| 场景 | 调度需求 | 相关技术 |
|---|---|---|
| 大模型预训练（千卡级） | Gang、拓扑、容错 | Volcano / Kueue + NodeResourceTopology |
| 微调（数十卡） | 队列、抢占、显存切分 | Kueue + MIG / MPS |
| 分布式 RL | 多角色 PodGroup、异构资源 | Volcano Job + PodGroup |
| 开发/调试 Notebook | 单卡、快速借用、低优先级 | Kueue LocalQueue + 抢占 |

### 推理场景

| 场景 | 调度需求 | 相关技术 |
|---|---|---|
| 大模型单实例多卡推理 | 拓扑、NVLink | NodeResourceTopology + exclusive GPU |
| 小模型高密度推理 | GPU 共享、隔离、Latency SLO | time-slicing / MPS + HPA |
| Serverless 推理 | 缩容到零、快速扩容 | Kueue + Knative / KServe |
| 多租户隔离 | 硬隔离、配额、排队 | MIG + Kueue ClusterQueue |

一张 GPU 卡的价格往往是同代 CPU 服务器的数倍。如果调度做得不好，要么利用率低（卡闲着），要么效率低（Job 跑得慢），要么公平性差（团队互相抢）。这三种浪费都会直接转化为成本。

## 1.5 本章小结

| 阶段 | 问题 | 解决方案 |
|---|---|---|
| K8s 早期 | 不认识 GPU | Device Plugin（1.14 GA）把 GPU 注册为扩展资源 |
| 节点运维 | 驱动/toolkit/plugin 手动安装困难 | NVIDIA GPU Operator 自动化节点组件 |
| 调度语义 | 只数卡、无 Gang、无拓扑 | scheduler-plugins / Volcano / Kueue |
| 多租户 | 抢资源、无配额公平 | Kueue Queue + Volcano Queue + 抢占机制 |
| 未来 | 更细粒度、更动态的资源模型 | DRA、显存感知 Device Plugin、AI-aware scheduler |

GPU 在 K8s 上的落地，本质上是在**“K8s 通用资源抽象”与“GPU 异构硬件现实”之间搭一座桥**。下一章我们将进入这座桥的核心概念：extended resource、Device Plugin、GPU 切分模型与调度语义。

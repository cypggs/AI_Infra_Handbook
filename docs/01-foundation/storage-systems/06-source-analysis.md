# 6. 源码分析

存储源码很多，但不需要全读完。本节聚焦一个对 AI 训练 checkpoint 至关重要的机制：**PyTorch Distributed Checkpoint (DCP)**。

## 6.1 为什么选 DCP

PyTorch 传统 `torch.save` 在分布式训练中有明显缺陷：

- 所有 rank 都把状态写到同一个文件，单机多卡时争用严重；
- 大模型 checkpoint 可能达到数 TB，单文件写入容易成为瓶颈；
- 恢复时需要所有 rank 都从同一个文件读取，灵活性差。

DCP 的设计目标是：

- 每个 rank 只保存自己负责的部分状态；
- 支持分片、异步保存、不同并行策略下的灵活加载；
- 使用 `fsspec` 等存储后端，统一本地文件系统、S3、GCS 等。

## 6.2 DCP 核心抽象

```mermaid
flowchart LR
    A[StateDict] -- Planner --> B[SavePlan]
    B -- StorageWriter --> C[分布式存储后端]
    C -- StorageReader --> D[LoadPlan]
    D -- Planner --> E[恢复后的 StateDict]
```

| 组件 | 作用 |
|---|---|
| `Planner` | 决定每个 rank 保存/加载哪些状态 |
| `SavePlan` / `LoadPlan` | 保存/加载计划，包含 tensor 的 shard 信息 |
| `StorageWriter` | 把计划写入存储后端 |
| `StorageReader` | 从存储后端读取计划 |
| `fsspec` | 统一文件系统抽象 |

## 6.3 保存流程源码概览

```python
# torch.distributed.checkpoint
from torch.distributed.checkpoint import save_state_dict

save_state_dict(
    state_dict=state_dict,
    storage_writer=FileSystemWriter("/path/to/checkpoint"),
    planner=DefaultSavePlanner(),
)
```

### DefaultSavePlanner

`DefaultSavePlanner` 会遍历 state_dict 中的每个 tensor，根据 tensor 的 `__dcp_storage_info__` 或 sharding 信息决定如何分片。

### FileSystemWriter

`FileSystemWriter` 使用 `fsspec` 把每个 shard 写成独立文件，同时写入一个 `.metadata` 文件记录所有 shard 的映射关系。

```text
checkpoint/
├── .metadata          # 全局元数据：每个 tensor 的 shard 位置
├── rank_0/            # rank 0 负责的状态
│   ├── model.layers.0.weight
│   └── optimizer.param_groups
├── rank_1/
│   └── model.layers.1.weight
```

## 6.4 加载流程源码概览

```python
from torch.distributed.checkpoint import load_state_dict

load_state_dict(
    state_dict=state_dict,
    storage_reader=FileSystemReader("/path/to/checkpoint"),
    planner=DefaultLoadPlanner(),
)
```

`DefaultLoadPlanner` 根据当前并行策略和 checkpoint 的 `.metadata`，决定每个 rank 需要读取哪些 shard。这样即使保存和加载时的并行度不同，也能正确恢复。

## 6.5 关键设计思想

| 设计 | 收益 |
|---|---|
| 每个 rank 写独立 shard | 消除单文件锁竞争 |
| `.metadata` 统一索引 | 加载时不需要所有 rank 读取完整文件 |
| 与并行策略解耦 | FSDP/TP/PP 变化后仍能加载 |
| fsspec 后端 | 本地 NVMe、S3、GCS 统一接口 |

## 6.6 异步保存：2025 年的关键演进

DCP 从 2.4 起支持 `async_save`，把保存拆成两阶段：

```python
from torch.distributed.checkpoint import AsyncCheckpointerType
from torch.distributed.checkpoint.state_dict_saver import async_save

# 阶段 1：GPU → CPU（训练仅在此短暂阻塞，1856 GPU 实测约 0.78s）
# 阶段 2：后台进程把 CPU 缓冲写入存储（训练继续跑）
fut = async_save(
    state_dict,
    storage_writer=FileSystemWriter("/path/to/checkpoint"),
    async_checkpointer_type=AsyncCheckpointerType.PROCESS,  # 独立进程，消除 GIL 竞争
)
fut.result()  # 需要确认持久化完成时（如训练收尾）再等待
```

2025 年 4 月 Meta/Crusoe 在 1856 张 H200 上实测 Llama3-70B 训练，两个优化把后台处理时间从约 436 秒压到约 67 秒（约 6.5 倍）：

| 优化 | 解决的问题 |
|---|---|
| 进程化异步 checkpoint（`AsyncCheckpointerType.PROCESS`） | 后台写盘线程与训练线程争抢 Python GIL，导致 checkpoint 完成后训练 TPS 仍持续下跌 |
| save plan 缓存（`DefaultSavePlanner(enable_plan_caching=True)`） | 每次保存都重新做全局 plan collective；实际只有数据在变，plan 可以复用 |

来源：[PyTorch Blog: 6x faster Async Checkpointing](https://pytorch.org/blog/6x-faster-async-checkpointing/)、[Reducing Model Checkpointing Times by Over 10x](https://pytorch.org/blog/reducing-checkpointing-times/)。

```mermaid
flowchart LR
    A[async_save] -- GPU→CPU 0.78s --> B[训练继续]
    A -- 后台进程写盘 --> C[本地 NVMe]
    C -- 异步 --> D[S3 / 并行 FS]
```

2026 年的研究进一步追问：阶段一的 GPU→CPU 拷贝为什么还要阻塞？GoCkpt 的思路是把这次传输拆散到约 7 个训练步中，与梯度传输共用 PCIe 带宽，并把梯度一起传到 CPU 维持部分 checkpoint 的一致性，训练中断时间再降约 86.7%（来源：[GoCkpt, arXiv:2511.07035](https://arxiv.org/html/2511.07035)）。换言之，DCP 解决了"怎么写"，异步化解决了"何时写"，多步重叠正在解决"还要不要停"。

## 6.7 备选：EBS CSI driver

如果想深入 K8s 存储，可以研究 AWS EBS CSI driver 的 gRPC 调用链：

```mermaid
flowchart LR
    A[CreateVolume] -- controller --> B[EBS API 创建卷]
    C[ControllerPublishVolume] -- controller --> D[attach 到节点]
    E[NodeStageVolume] -- node --> F[格式化并全局挂载]
    G[NodePublishVolume] -- node --> H[bind mount 到容器]
```

这套调用链是理解 `PVC → PV → attach → mount` 的绝佳入口。

## 6.8 一句话总结

**PyTorch DCP 把 checkpoint 从"单文件、全 rank 竞争"变成"分片、独立写入、元数据驱动加载"，再叠加上两阶段异步保存与进程化写盘，把训练阻塞从分钟级压到秒级，是支撑大模型分布式训练的关键存储优化。**

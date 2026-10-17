# 3. 架构设计

vLLM 的架构围绕 "如何高效地调度请求、管理 KV Cache、执行模型推理" 展开。整体可以分为控制路径与执行路径两层。

从 vLLM 0.6+ 开始，社区并行开发了新的 **V1 引擎**（`vllm.v1`），对调度器、执行器、KV cache 管理进行了重构，目标是更低的调度开销、更好的 chunked prefill / prefix caching / speculative decoding 支持。2025 年起 V1 成为默认引擎；2026 年 9 月发布的 v0.29.0 又把 **Model Runner V2（MRV2）** 设为所有模型的默认执行层（MRV1 计划在 v0.32 移除），进一步降低了单步执行开销、支持 PP 下的 MTP/EAGLE 推测解码与双 batch 重叠。本章在介绍经典架构的同时，会标注 V1 / MRV2 的变化。

## 整体架构图

```mermaid
flowchart TB
    subgraph API["API Layer"]
        OpenAI["OpenAI-Compatible API Server"]
        LLMEngine["LLMEngine / AsyncLLMEngine"]
    end

    subgraph Control["Control Path"]
        Scheduler["Scheduler"]
        BlockManager["BlockManager / KVCacheManager"]
        Tokenizer["Tokenizer"]
        EngineCore["EngineCore (V1)"]
    end

    subgraph Execution["Execution Path"]
        Worker["Worker"]
        ModelRunner["Model Runner"]
        CacheEngine["Cache Engine"]
        Attention["Attention Backend"]
        Sampler["Sampler"]
        InputBatch["InputBatch (V1)"]
    end

    subgraph Storage["KV Cache Storage"]
        GPU["GPU Memory"]
        CPU["Host Memory (Offload Tier)"]
        Remote["NVMe / S3 / Remote P2P"]
    end

    User["User Request"] --> OpenAI
    OpenAI --> LLMEngine
    LLMEngine --> Scheduler
    LLMEngine --> EngineCore
    Scheduler --> BlockManager
    EngineCore --> ModelExecutor
    Scheduler --> Worker
    Worker --> ModelRunner
    ModelRunner --> InputBatch
    ModelRunner --> CacheEngine
    ModelRunner --> Attention
    ModelRunner --> Sampler
    CacheEngine --> GPU
    CacheEngine -.->|"KV Connector (V1)"| CPU
    CPU -.-> Remote
    Sampler --> LLMEngine
    LLMEngine --> User
```

## 各组件职责

### 1. API Server

接收 HTTP / gRPC 请求，提供 OpenAI 兼容的 `/v1/completions` 和 `/v1/chat/completions` 接口。负责：

- 请求解析与参数校验
- 请求封装为 `SequenceGroup`
- 流式/非流式响应返回

### 2. LLMEngine / AsyncLLMEngine

整个推理引擎的控制中心。

- `LLMEngine`：同步接口，适合离线批处理
- `AsyncLLMEngine`：异步接口，支持高并发在线服务

职责：
- 维护请求队列
- 驱动 Scheduler 进行每轮调度
- 收集 Worker 输出并返回给 API Server

### 3. Scheduler

决定每一轮 iteration 中哪些 Sequence 进入 GPU 执行。核心功能：

- 维护 `Waiting`、`Running`、`Swapped` 三个队列（经典引擎）
- 根据 token 预算和显存预算选择可执行的 Sequence
- 实现 Continuous Batching
- 支持 preemption（抢占）和 recomputation（重算）

在 **V1 引擎** 中，调度器进行了重构：

- 不再区分 prefill / decode 阶段，而是统一处理 `num_computed_tokens` 和 `num_tokens_with_spec`
- 调度器输出 `SchedulerOutput`，包含每个请求本轮应计算的 token 数
- 通过 `token_budget` 控制每轮总计算量，天然支持 chunked prefills

### 4. BlockManager / KVCacheManager

管理 GPU 上的 KV Cache Block。核心功能：

- Block 分配与回收
- Block Table 维护
- Copy-on-Write 支持
- Prefix Caching（前缀缓存）

V1 中由 `KVCacheManager` 管理 `KVCacheBlock`，支持 hybrid block sizes（内存分配块大小与 kernel 块大小可以不同）。

### 5. Worker / Model Runner

Worker 是模型执行的实际工作者。每个 Worker 可能对应一个 GPU。Model Runner 负责：

- 加载模型权重
- 执行 forward（prefill / decode）
- 调用 Attention Backend 计算注意力
- 调用 Sampler 采样下一个 token

V1 的 `GPUModelRunner` 维护一个 `InputBatch` 对象，根据每轮的 `SchedulerOutput` 重新构建输入张量，并调用高度优化的 attention kernel。v0.29.0（2026-09-09）起默认的 **Model Runner V2** 在此基础上进一步降低了 CPU 侧单步开销，支持流水线并行下的 MTP/EAGLE 推测解码与双 batch 重叠（prefill 与 decode 计算交叠）。

### 6. Cache Engine

管理 KV Cache 在 GPU 显存中的物理布局。负责：

- 为当前 iteration 准备 KV Cache
- Block 之间的拷贝与 swap
- CPU offloading（可选）

### 7. KV Connector / KV Cache Offloading（V1）

V1 引擎通过 **KV Connector** 抽象（`vllm/distributed/kv_transfer/`）把 KV Cache 的传输与分层卸载做成插件化接口，是 2025–2026 年生产落地的重点方向：

- **PD 分离传输**：`NixlConnector`（基于 NVIDIA NIXL，GPU 显存 P2P / RDMA 直传）、`MooncakeStoreConnector` / `MooncakeConnector`（Mooncake 分布式 KV 池）、`LMCacheConnector` 等，用于 prefill 实例与 decode 实例之间的 KV 交接，以及跨请求的前缀复用。
- **分层 Offloading**：自 v0.22 起，vLLM 原生支持把被驱逐的 KV 数据经 CPU 内存（LRU/ARC 缓存）级联到文件系统、S3 对象存储与 P2P 远端节点，命中时直接加载而避免重算（官方博客 2026-09-10）。
- **MultiConnector**：把多个 Connector 串联（如 NIXL 负责 P/D 交接、Mooncake Store 负责跨请求复用）。
- **KV Events**：向外部系统（如 llm-d 路由器）广播 KV 存储/驱逐事件，用于全局缓存感知调度。

### 8. Attention Backend

vLLM 支持多种注意力实现，并按 GPU 架构、模型类型（GQA / MLA / Mamba 混合架构）、是否使用 prefix caching / chunked prefill 自动选择：

- FlashAttention / FlashAttention-3
- FlashInfer
- FlashMLA（DeepSeek 系列 MLA 模型）
- Triton、CUTLASS 等通用后端

### 9. Tokenizer

将文本输入转换为 token ID，并将模型输出的 token ID 解码为文本。

## 分布式推理

vLLM 支持多种分布式并行策略：

### Tensor Parallelism（TP，张量并行）

把模型层的计算切分到多个 GPU 上。vLLM 采用 Megatron-LM 的 tensor parallel 算法，默认使用 PyTorch 的 distributed tensor。适用于单节点多 GPU。

配置方式：

```bash
python -m vllm serve meta-llama/Llama-3.1-8B --tensor-parallel-size 2
```

### Pipeline Parallelism（PP，流水线并行）

把模型按层切分到多个 GPU 上，适合超大规模模型跨节点部署。可以与 TP 组合使用：

```python
llm = LLM(
    model="meta-llama/Llama-3.3-70B-Instruct",
    tensor_parallel_size=4,
    pipeline_parallel_size=2,
)
```

### 其他并行

- **Data Parallelism（DP）**：每个 GPU 持有模型副本，处理不同数据 batch；对 MoE 模型，vLLM 支持 DP + EP 组合与 DP Attention（attention 层按 DP 切分、MoE 层按 EP 切分），减少 activation 通信。
- **Expert Parallelism（EP，专家并行）**：把 MoE 的各专家分布到不同 GPU，配合 **EPLB**（Expert Load Balancing，源自 DeepSeek-V3 论文的实践）均衡专家负载。vLLM 官方博客（2025-12-17）展示了宽 EP（wide-EP）部署 DeepSeek 达到单 H200 2.2k tok/s 的大规模 serving 案例；v0.31.0 又引入 MoonEP 均衡 EP all2all 后端。
- **Context Parallelism（CP）**：针对长上下文 prefill 阶段，把序列切分到多 GPU 并行计算（v0.31.0 起支持 prefill context parallelism）。

### TP vs PP 的选择

| 维度 | TP | PP |
|---|---|---|
| 切分粒度 | 层内 | 层间 |
| 通信量 | 大（每层 all-reduce） | 小（stage 间传激活） |
| 适用场景 | 单节点多 GPU | 跨节点大模型 |
| 主要 overhead | 通信延迟 | Pipeline bubble |

对 MoE 大模型，2025–2026 年的生产趋势是 **EP 为主、DP Attention 辅助**（decode 阶段专家计算占比高，EP 的 all2all 通信可被 NVLink/RDMA 承受），而非单纯堆 TP。

## 本章小结

vLLM 的架构清晰分层：API 层负责接入，控制层负责调度与显存管理，执行层负责模型推理。BlockManager 与 Scheduler 是 vLLM 区别于其他推理引擎的核心；2025–2026 年的架构增量集中在 KV Connector（PD 分离与分层 offloading）和面向 MoE 的 EP/DP Attention 并行上。

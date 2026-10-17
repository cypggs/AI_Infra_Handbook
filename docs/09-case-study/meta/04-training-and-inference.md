# 4. 训练与推理

本章拆解 Meta 在 Llama 3 / Llama 4 上的**训练生命周期**与**推理工程**。训练侧聚焦"如何让 16k–32k GPU 的同步任务高效且可靠地跑下去"；推理侧聚焦"如何用 MoE / GQA / iRoPE / FP8 把前沿模型的部署成本打下来"，并通过 Llama Stack 与 vLLM 标准化服务接口。

## 4.1 训练生命周期：一个 step 的完整链路

一个 Llama 规模的数据并行（DP）训练 step，在 Meta 集群上经历以下阶段：

```mermaid
sequenceDiagram
    participant Loader as 数据加载<br/>(Tectonic FUSE)
    participant GPU as 数千 GPU<br/>(DP/TP/PP)
    participant Coll as 集合通信<br/>(NCCL/HCCL)
    participant Opt as 优化器<br/>(FP16 master + FP8)
    participant Ckpt as Checkpoint<br/>(Tectonic)
    Loader->>GPU: 1. 取 batch (数据/模型/流水线并行切分)
    GPU->>GPU: 2. 前向传播 (FP8 计算)
    GPU->>Coll: 3. 反向传播触发 AllReduce 梯度同步
    Coll-->>GPU: 4. 梯度就绪
    GPU->>Opt: 5. 优化器更新 (FP16 master weights)
    Note over Ckpt: 周期性: 跨数千 rank 数百 ms 存 checkpoint
    Note over Loader,Coll: 故障: 检测 → 回滚到最近 ckpt → auto-restart
```

### 4.1.1 三种并行：DP / TP / PP

Meta 的 Llama 训练同时使用三类并行：

- **数据并行（Data Parallelism, DP）**：把 batch 切给多个 rank，每个 rank 持有完整模型副本，反向传播后 AllReduce 梯度。FSDP/FSDP2 进一步把**模型参数、梯度、优化器状态分片**到各 rank，降低单卡显存占用。
- **张量并行（Tensor Parallelism, TP）**：把单层矩阵乘法切到多卡，需要层内高频 AllReduce。
- **流水线并行（Pipeline Parallelism, PP）**：把模型按层切成多个 stage，micro-batch 流水执行，需要 bubble-optimizing 调度。

三者的组合（3D parallelism）让 Meta 能在显存有限的 H100 上训 405B（Llama 3）/ ~2T（Llama 4 Behemoth）规模模型。

### 4.1.2 FP8 训练 + FP16 master weights

Llama 4 全程使用 **FP8 精度训练**（前向/反向计算与激活），同时维护 **FP16 master weights** 保存优化器状态——这是"低精度计算 + 高精度累积"的经典范式：

- **FP8**：把矩阵乘法的计算量与显存带宽需求降下来，提升 TFLOPS 与吞吐。
- **FP16 master**：用更高精度累加梯度与更新权重，避免低精度带来的数值发散。

成果：Llama 4 Behemoth 用 FP8 + 32k GPU 训练，达到 **390 TFLOPS/GPU**。Llama 3 在 16k GPU 上达到 **>400 TFLOPS/GPU**、有效训练时间 >95%、相比 Llama 2 约 3 倍效率提升。

### 4.1.3 AllGather 调优：把利用率从波动推到 90%+

FSDP 每个 step 都需要 AllGather（收集分片参数）。在大规模集群上，AllGather 的带宽利用率直接决定 MFU。Meta 的调优要点：

1. **拓扑感知调度**：把 DP 组调度到网络距离最近的 GPU 子集。
2. **NCCL 路由协同**：让 collective 通信感知 fat-tree 拓扑，多路径均衡。
3. **ring vs tree 算法选择**：根据组规模选最优 collective 算法。

优化前，大规模集群的 AllGather 带宽利用率在 **10%–90% 剧烈波动**；优化后**稳定到 90%+**。

### 4.1.4 Checkpoint 与恢复

同步训练的 checkpoint 不是"定期存档"那么简单——它要在故障时**快速、一致地**恢复数万 rank 的状态：

- **延迟**：跨数千 rank 在**数百毫秒**内保存/加载 checkpoint（依赖 Tectonic 的 Flash 优化吞吐）。
- **PyTorch 进程组初始化**：从**数小时降到数分钟**——这是冷启动恢复的关键瓶颈，Meta 通过缓存与并行初始化大幅压缩。
- **恢复策略**：故障 → 检测 → 隔离故障节点 → 从最近 checkpoint 重建进程组 → auto-restart。

### 4.1.5 可观测性：定位"为什么集群变慢/挂了"

大规模同步训练的调试极难——一个慢节点、一次路由抖动、一次 SDC 都会让全局停顿。Meta 的可观测性工具：

- **desync debug**：定位哪些 rank 与参考不同步。
- **distributed collective flight recorder**：记录每次集合通信的元数据（类似航空黑匣子），故障后回放定位瓶颈 rank。

### 4.1.6 性能调试平台化：Zoomer（2025-11）

2025-11-21 Meta 公开 **Zoomer**（engineering.fb.com）——把"AI 性能调试与优化"从专家手艺变成中央化、自动化的平台，覆盖从 Llama 训练到广告推荐、**100k+ GPU 规模**的工作负载（同时支持 NVIDIA / AMD / MTIA 三种硅）：

- **三层架构**：基础设施层（Manifold BLOB 存 trace，数千宿主机的容错流水线）→ 分析引擎（整合 Kineto GPU trace、NVIDIA DCGM、StrobeLight CPU profiling、dyno 遥测，自动识别反模式并给出建议）→ 可视化（交互时间线、热力图、Perfetto 集成）。
- **核心能力**：分布式训练 **straggler 检测**、PyTorch 应用关键路径分析、推理 **一键 QPS 优化**（+2% ~ +50%）、超大 trace（单 rank 2GB+）的高级处理。
- **公开战果**：广告相关性模型训练时间 **-75%**（功耗 -78%）；一次修复低效内存拷贝的一行代码带来 **+20% QPS**；32k GPU 基准一天内 **+30%**、64k GPU 配置 **+25%**；自动参数调优降低功耗 10–45%。

Zoomer 代表了一条重要经验：**当集群规模到万卡级，"找不到瓶颈"本身就是最大的瓶颈**——性能工程必须平台化、自动化，这与本手册 [AI SRE](/07-ai-sre/) 的可观测性主题直接呼应。

## 4.2 Llama 3 / Llama 4 训练细节

### Llama 3

- **架构**：decoder-only transformer；GQA（grouped query attention）用于 8B 与 70B；128K 词表 tokenizer（比 Llama 2 少 15% token）；8192 token 序列 + 文档边界 masking。
- **数据**：15T+ token 预训练（7× Llama 2、4× 代码、>5% 非 English 覆盖 30+ 语言）；多级数据过滤（启发式、NSFW、语义去重、Llama 2 训分类器）。
- **后训练**：SFT → rejection sampling → PPO → DPO。
- **基础设施产出**：两个 24k H100 集群；>400 TFLOPS/GPU；>95% 有效训练时间。

### Llama 4

- **架构**：原生多模态（early fusion）+ **MoE**（mixture of experts）。Scout：17B active / 16 experts / 109B total；Maverick：17B active / 128 experts / 400B total（alternating dense + MoE 层，shared expert + 1/128 routed expert）；Behemoth：288B active / 16 experts / ~2T total。
- **长上下文**：**iRoPE**（interleaved attention，部分层无位置编码 + 推理期 attention 温度缩放）→ Scout 支持 10M 上下文（256K 预训练 + 后训练扩展）。
- **训练精度**：FP8 + FP16 master；Behemoth FP8 + 32k GPU → 390 TFLOPS/GPU。
- **数据**：>30T token（2× Llama 3）；200 语言（>100 种 >1B token，多语言 token 是 Llama 3 的 10×）。
- **后训练新范式**：lightweight SFT → online RL → lightweight DPO（发现 SFT/DPO 过度约束会限制 online RL 探索）；移除 >50% 简单数据；continuous online RL + 自适应难度过滤。
- **蒸馏**：Maverick 从 Behemoth **codistill**，采用动态加权 soft/hard target 的新型蒸馏损失。
- **Behemoth 的异步 RL**：全新**完全异步 online RL 训练框架**，把不同模型灵活分配到不同 GPU（而非全塞进内存），训练效率比上一代提升约 **10×**。

> **2026 年起**：Meta 的前沿训练转向 Muse 系列（Meta Superintelligence Labs，闭源、细节未公开）；Llama 3/4 的训练工程（本节的 3D 并行、FP8、AllGather 调优、checkpoint 体系）仍是公开资料中最完整的超大规模训练样本，且整套 PyTorch 工程栈（FSDP2、TorchTitan、Helion）继续服务新一代模型。MTIA 300 则把 R&R 训练带入自研硅时代（见 [第 5 章](05-core-modules)）。

## 4.3 推理工程：让前沿模型便宜地服务

训练解决"造得出"，推理解决"用得起"。Meta 的推理工程围绕**降低激活参数与精度**展开。

### MoE：只激活一部分参数

Llama 4 Maverick 有 400B 总参数，但每个 token 只激活 17B（shared expert + 1 个 routed expert）。这意味着：

- **存储**：所有参数驻留显存。
- **计算**：每个 token 只过 17B 参数的矩阵乘 → 推理 FLOPS 与 dense 17B 模型相当。

Maverick 可部署在**单个 H100 DGX host**（8 GPU），大幅降低部署门槛。

### GQA：降低 KV cache 与注意力开销

Llama 3 的 GQA（grouped query attention）让多个 query 共享一组 key/value，降低 KV cache 显存与 attention 计算开销，直接提升推理吞吐与长上下文经济性。

### iRoPE 与长上下文

Llama 4 Scout 的 iRoPE 通过"部分层无位置编码 + 推理期温度缩放"实现**长度泛化**——256K 预训练的模型能外推到 10M 上下文，而不需要在 10M 上重新预训练。

### 低精度推理

推理侧同样用 FP8/Int4 等低精度（Scout 可在单个 H100 上用 Int4 量化部署），与训练侧的"低精度计算 + 高精度累积"一脉相承。MTIA 400/450/500 的 MX4/MX8 微缩放格式正是为低精度推理设计。

### 2026：Muse 时代的推理栈——开放权重 + 开放 kernel

2026-10-15 发布的 **Muse Spark Open**（816B total / 42B active MoE，256 experts / 每 token 激活 8 个，1M 上下文）是观察 Meta 推理工程的最佳样本（pytorch.org 官方博客，2026-10-15）：

- **跨引擎开放优化**：官方同时优化 **SGLang 与 vLLM**（以及 TensorRT-LLM、llama.cpp），覆盖 NVIDIA / AMD / Intel——推理引擎不再二选一，兼容性矩阵成为发布的一部分。
- **Helion kernel 成为发布物**：模型附带 RoPE、RMSNorm、量化等算子的 **Helion（PyTorch 原生 kernel DSL）**实现，在 GB300 上比 CUDA/CuTe DSL 手写 kernel 快 **1.03–3.95×**，同一套 kernel 直接移植 AMD MI350（端到端再 +3%）；SGLang 中还有全 Helion 编写的 **megakernel**（多算子融合为单一 persistent kernel，服务低延迟推理）。
- **部署门槛下探**：NVFP4 量化版可在 **两台 Apple M5 Ultra Mac Studio**（各 512GB，MLX 框架）上运行；或 4 张 Blackwell Ultra GPU / 8 张 H200——MoE 的低激活参数特性再次兑现"前沿能力、平民部署"。
- **微调闭环**：**TorchTitan** 官方提供 Muse Spark Open 模型定义，开箱支持多轮 SFT、LoRA 与 RL（TitanRL）——从推理到 post-training 的全链路都留在 PyTorch 生态内。

## 4.4 服务接口：Llama Stack 与 vLLM

Meta 不只开放权重，还把**服务接口标准化**：

### Llama Stack

Llama Stack 提供 9 类标准化 API（Inference、Safety、Agentic、Memory、Eval、Telemetry、Post-training、Toolchain、RAG），让 Llama 模型在**任何云、任何硬件、任何框架**上都有统一的调用方式。这与本手册 [LLM Gateway](/04-llmops/llm-gateway/) 的"统一入口"理念一致。

> **2026 年现状**：随着 Meta 开发者入口转向 Muse 系列与 Meta Model API（dev.meta.ai 模型中心已只列 Muse 家族），Llama Stack 作为开放 API 层的遗产仍随 Llama 4 权重可用，其"标准化服务接口"的思想也被 Meta 新栈继承（Muse Spark Open 的多引擎兼容矩阵本质上解决同一问题）。

### vLLM 作为推理事实标准

vLLM（PagedAttention、continuous batching）是 Llama 系列推理的事实标准，Meta 的 MTIA 为此提供 **vLLM plugin backend**：

- 替换 FlashAttention / fused LayerNorm 等 kernel 为 MTIA 优化版本。
- 作为 torch.compile backend。
- 支持 prefill-decode 分离（disaggregation）与 continuous batching。

2026 年之后这一格局演进为"**双引擎 + 开放 kernel**"：Muse Spark Open 同时官方优化 SGLang 与 vLLM（见 4.3 节），Helion kernel 可在两引擎间移植——让"在 MTIA / NVIDIA / AMD 上跑模型"在应用层几乎无差别，这正是 PyTorch 原生栈的价值。

## 4.5 训练 vs 推理：可靠性约束的差异

一个值得注意的对称性：**训练与推理在 SDC 上都脆弱，但失败模式不同**。

| 维度 | 训练 SDC | 推理 SDC |
|---|---|---|
| 表现 | NaN 传播 / 梯度方差污染 → 全局停顿或静默发散 | 输出错结果 → 影响数以千计的推理消费者 |
| 检测 | reductive triage、deterministic training、hyper-checkpointing | divergence detection（神经元分布图） |
| 恢复 | 回滚 checkpoint + auto-restart | 隔离故障节点 + 重试 |

详见 [第 5 章](05-core-modules) 的 SDC 治理模块与 [第 8 章](08-production-practice) 的生产实践。

## 小结

Meta 的训练与推理工程有一条清晰的主线：**用低精度（FP8/Int4/NVFP4）+ 并行（3D parallelism）+ 拓扑优化把效率推到极致，用 MoE/GQA/iRoPE 把部署成本降下来，用开放 kernel（Helion）+ 双引擎（SGLang/vLLM）把服务接口标准化，用 checkpoint/恢复 + SDC 治理 + 平台化性能调试（Zoomer）把可靠性兜住**。训练解决"大规模可靠地造"，推理解决"便宜标准化地用"——两端共同构成了 Meta 开放权重（2026 年起为"选择性开放"）范式的工程闭环。

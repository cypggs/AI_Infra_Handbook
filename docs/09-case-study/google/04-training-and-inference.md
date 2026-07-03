# 4. 训练与推理

本章聚焦 Google TPU 栈上**训练**与**推理**两条 workload 的具体流程。训练侧讲清"一个跨 Pod 的训练步如何被编译、分片、调度、checkpoint"；推理侧讲清 JetStream 的服务化机制、投机解码的加速原理、Gemma 3 的架构选择，以及 Gemini 的服务形态。

---

## 4.1 训练：从单设备 JAX 到跨 Pod 同步训练

### 4.1.1 并行策略：GSPMD 的"标注即并行"

Google 训练的并行不是手写集合通信，而是**编译器推导**。用户在 JAX 里写单设备程序，用 `Mesh` + `PartitionSpec`（或 `with_sharding_constraint`）给少数张量标注分片，XLA 的 **GSPMD pass** 自动：

- 把标注**传播**到每个算子，推断每个中间张量的分片；
- 插入所需的跨设备集合通信（`AllReduce`/`AllGather`/`ReduceScatter`）；
- 生成 per-device 程序。

这一套覆盖**数据并行、张量并行（"W-sharding"）、流水线并行（经"manual"轴）、FSDP** 的"混合范式"。GSPMD 论文报告：在多达 2048 个 Cloud TPUv3 核心上，对最高万亿参数模型达到 **50%–62% 计算利用率**。

关键前提是 JAX 的**函数式、可追踪**设计：程序是数组的纯函数、无隐藏副作用，XLA 能追踪全图、看到每个张量形状，从而从少量标注自动推断分片。带副作用或不透明算子会破坏推断——这是"标注即并行"的底层约束。

### 4.1.2 训练库：MaxText

**MaxText**（`AI-Hypercomputer/maxtext`）是 Google 的纯 Python/JAX 高性能 LLM 训练参考实现，定位是"可读、几乎'免优化'（无 C++/CUDA）"，靠 JAX + XLA 拿到高 MFU。它支持 Gemma 1–4、Llama 2/3/4、Qwen、DeepSeek、GPT-OSS 等家族的预训练与后训练（SFT/GRPO/GSPO via Tunix）。

一个 MaxText 训练步的关键环节（详见 [第 6 章 源码分析](06-source-analysis) 的真实代码）：

1. **建 Mesh**：`create_device_mesh` → `Mesh(devices_array, mesh_axes, axis_types=...)`，把（可能多 slice 的）TPU 设备组织成命名轴网格（如 `data`/`fsdp`/`tensor`/`pipeline`）。
2. **逻辑轴规则**：YAML 里的 `logical_axis_rules` 把张量的逻辑轴（batch/length/head/dim）映射到物理 mesh 轴，合并 base + per-model + CLI 覆盖。
3. **JIT + 分片**：用带 `in_shardings`/`out_shardings` 的 `jax.jit`（旧 API 的 `pjit` 已并入 `jit`）编译 `train_step`，输入数据用 `with_sharding_constraint` 提示/强制分片。
4. **步循环**：每步 `load_next_batch` → 在 mesh + 逻辑轴规则下跑 `p_train_step` → 周期性 checkpoint。
5. **FSDP**：用一个名为 `fsdp` 的 mesh 轴表达；前向前 all-gather 权重（`remove_fsdp_sharding` 把 `fsdp`/`fsdp_transpose` 轴置 None 即复制），反向后分片回各设备。

这套设计让"换一种并行策略"变成"改几行 YAML 的逻辑轴规则"，而非重写通信代码。

### 4.1.3 跨 Pod：Multislice

单个 Pod（ICI 域）受物理规模限制（v4 = 4096 芯片）。**Multislice** 让一个训练 run 跨多个 slice/Pod，靠 DC-GN/Jupiter 互联：

- **并行模型分层**：激活走 ICI，梯度走 DCN 归约；XLA 自动把一个 all-reduce 分解为"ICI 内归约 → DCN 跨 slice 归约 → ICI 内广播"的层次集合通信。
- **新分片维度**：Multislice 引入"跨 DCN 的分片轴"，支持 FSDP/模型/流水线并行跨 slice。
- **指标**：在 TPUv4 上对几十亿参数生成式模型达到 **58.9% MFU**；"多 slice 的 MFU 与单 slice 相当"（编译器优化使然）；弱扩展（GPT-3 175B on TPU v5e）随 Pod 增加近线性。
- **故障恢复**：单 slice 故障时从上一个 checkpoint 自动重启；配合 GKE 进一步改善恢复体验。

Multislice 的本质：把"ICI 域内的高速集合通信"与"DCN 跨域的较慢集合通信"显式分层，让编译器在两层上各自优化。

### 4.1.4 checkpoint：Orbax

训练进度由 **Orbax** 周期性持久化：MaxText 构造一个 Orbax `CheckpointManager`（同步或异步），用 `PyTreeCheckpointHandler`（默认 OCDBT + Zarr3），保留最近 N 个 checkpoint。每步调用 `maybe_save_checkpoint`，由 Orbax 按 `save_interval_steps` 决定是否真正落盘。这是 NSDI'24 双路径恢复中 reconfigure"从最近 checkpoint 恢复"的物理基础——checkpoint 间隔直接决定回滚损失（见 [Mini Demo](07-mini-demo)）。

### 4.1.5 可靠性：NSDI'24 双路径在生产训练中的角色

大规模同步训练对故障零容忍（"任一芯片宕机中断整个训练"）。生产中靠 NSDI'24 的体系兜底（详见 [第 8 章](08-production-practice)）：

- **检测**：`healthd` 持续监控 + 两类 preflight（end-to-end check / intent-driven checker）。
- **恢复 Path 1（reconfigure）**：机器/ICI 故障 → OCS 迁移到空闲健康 cube → 从 checkpoint 恢复。
- **恢复 Path 2（reroute）**：OCS 故障 → 保留分配、重载容错路由表、继续跑，承受 0.5–8.6% 步时惩罚。
- **结果**：99.98% 系统可用率，约 1% 训练作业受硬件中断影响。

---

## 4.2 推理：JetStream、投机解码、Gemma、Gemini

### 4.2.1 JetStream（→tpu-inference）：TPU 原生推理引擎

**JetStream** 是面向 XLA/TPU 的"吞吐与内存优化"LLM 推理引擎，与 vLLM/TRT-LLM（GPU/CUDA 优先）的区别在于**TPU 原生、XLA 编译**——权重与 KV 状态作为 XLA 编译、GSPMD 分片的数组跨 TPU 主机管理。核心机制（来自 JetStream/MaxText engine 文档）：

- **权重分片跨 TPU 主机**：三条独立并行轴——`ici_fsdp_parallelism`（FSDP/ZeRO-3 式权重分片）、`ici_autoregressive_parallelism`（流水线式解码分片）、`ici_tensor_parallelism`（层内张量并行）。
- **连续批处理 / 在线服务**：以 `maxengine_server` 在线运行，`per_device_batch_size` 为每芯片解码 batch，支持请求实时交错。
- **HBM 上的 KV cache 管理**：显式 `max_target_length`/`max_prefill_predict_length` 边界 + `quantize_kvcache`（int8 KV cache）把 cache 压进 HBM。
- **量化**：int8 动态范围、int8 仅权重、混合精度（如 4-bit Q/K）AQT checkpoint，全部 XLA 编译。

> **生态变动（重要）**：JetStream 已挂"归档通知"——核心功能迁移到新仓库 **`tpu-inference`**（服务于 `tpu.vllm.ai`），JetStream 本体于 2026-02-01 起只读（仍可 fork/clone）。当前 TPU 推理工作应指向 `tpu-inference`（即 DFlash 投机解码落地的 vLLM-TPU 项目）。

### 4.2.2 投机解码：DFlash 与 ~3× 加速

标准投机解码用小"draft"模型预测若干未来 token，大"target"模型一次性并行验证。Google Developers 博客（2026-05）披露了在 TPU 上的 **DFlash**（block-diffusion drafter，UCSD 张昊组）：

- **block painting**：用离散扩散（dLLM）drafter 一次前向"画"出整块 draft token，把传统 O(K) 串行 drafting 降到 O(1)——"完美契合 TPU 高带宽 MXU"。
- **K-Flat 验证**：在 TPU v5p 上"验证 1024 个 token 的代价几乎等同于验证 16 个"，因为时间被权重加载主导、而非 attention 计算——验证宽度"几乎免费"，瓶颈转向 draft 质量。
- **MXU 饱和 + 双 cache**：DFlash 映射到 TPU MXU 与 Pallas paged-attention kernel，target 用 paged KV cache、draft 用静态 on-device JAX 数组，调和非因果 block 扩散与 paged attention。
- **实测**：独立 JAX 基准（Qwen3-4B target + DFlash draft，K=16）平均 **3.13×**，数学任务峰值近 6×；端到端服务（Llama-3.1-8B on vLLM-TPU）**DFlash 2.29× vs EAGLE-3 1.30×**。实现提交到 vLLM `tpu-inference` 仓库。

这组结果同时揭示了 TPU 的一个推理特性：**权重加载主导验证成本**，使得"宽验证"几乎免费——这是 TPU 上投机解码尤其划算的结构性原因。

### 4.2.3 Gemma 3：开放权重模型

**Gemma 3**（arXiv:2503.19786）是 Google 的开放权重模型族，体现"在 TPU 上训练、开放发布"的闭环：

- **家族**：1B / 4B / 12B / 27B（decoder-only transformer）。
- **架构**：GQA + QK-norm；**local/global 混合注意力（5:1，每 5 个 local 层 1 个 global，首层为 local）**——local 层用 **1024 token 滑窗**，仅 global 层 attend 全上下文；全局层 RoPE 基频从 10k 提到 1M。
- **上下文**：4B/12B/27B 为 **128K**（1B 为 32K）。
- **多模态**：4B/12B/27B 带 **400M SigLIP 视觉编码器**（896×896 图像 → 256 soft token）；推理时 **Pan & Scan** 自适应处理非方/高分辨率图。
- **训练量**：27B 训练 **14T tokens**、12B **12T**、4B **4T**、1B **2T**（技术报告原文）；全程用**知识蒸馏**。
- **训练基础设施**（技术报告 Table 2）：27B 用 TPUv5p 6144 芯片、12B 用 TPUv4 6144、4B 用 v5e 2048、1B 用 v5e 512；多 Pod 训练用 Pathways + JAX 单控制器 + GSPMD + MegaScale XLA。
- **许可/下载**：Gemma Terms of Use（权重非 Apache）；Kaggle / Hugging Face。
- **负责任 AI**：记忆率低于所有前代 Gemma/Gemini，记忆输出扫描未发现超阈个人信息。

### 4.2.4 Gemini 服务形态

Gemini 前沿模型经三条面对开发者的途径服务（均跑在 TPU 后端）：

- **Gemini API**（ai.google.dev）：程序化访问最新 Gemini（文本/图像/音频/视频入，文本/代码/多模态出）。
- **Vertex AI**（cloud.google.com/vertex-ai）：企业/GCP 托管的 Gemini 服务，带安全、治理、模型花园、微调。
- **Google AI Studio**：免费浏览器 IDE，用于原型与获取 API key。

Gemini 原生多模态出入，并嵌入消费侧（Gemini app、Search AI Mode、Android、Workspace、NotebookLM）。

---

## 4.3 训练 vs 推理：同一套栈的两种用法

| 维度 | 训练 | 推理 |
|---|---|---|
| 主导计算 | 稠密矩阵乘（前向+反向）+ 稀疏嵌入 | 矩阵乘（前向）+ KV cache 访问 |
| 并行 | GSPMD 混合并行（数据/FSDP/张量/流水线） | 权重分片（FSDP/自回归/张量三轴）+ 连续批处理 |
| 跨 Pod | Multislice（ICI + DCN 分层归约） | 通常单 slice/单 Pod；跨副本水平扩展 |
| 可靠性 | NSDI'24 双路径 + checkpoint-restart | 副本冗余 + 负载均衡；单副本故障转移 |
| 代表软件 | MaxText + Pathways + Orbax | JetStream/tpu-inference + 投机解码 |
| 模型 | Gemini（闭源权重）/ 自研 | Gemini（API）/ Gemma（开放权重） |

训练与推理共享同一套底层（TPU + ICI/OCS + XLA/GSPMD），差异在"如何分片、如何批处理、如何容错"——这正是垂直整合的好处：一套硬件 + 编译器栈，覆盖两类 workload。

下一章 [核心模块](05-core-modules) 将逐个剖析支撑这些流程的关键模块。

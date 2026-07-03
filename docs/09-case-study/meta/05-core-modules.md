# 5. 核心模块

本章逐个拆解 Meta AI 基础设施的核心组件，每个模块讲清楚**它解决什么问题、怎么设计、关键参数**。这些模块是 [第 3 章](03-architecture) 架构的实体化。

## 5.1 计算模块

### 5.1.1 Grand Teton — OCP 开放 GPU 平台

Grand Teton 是 Meta 自研、通过 OCP 开放的 GPU 平台，定位是**整机柜级别的单体集成**。

| 维度 | 设计 |
|---|---|
| 集成 | GPU + CPU + 电源 + 控制 + 网络织物 → 单体机柜 |
| 动机 | 减少机柜内线缆、简化供电与远程管理、可规模化复制 |
| 开放性 | 设计通过 OCP 公开，供应链可围绕统一规范优化 |

### 5.1.2 Catalina — GB200 Blackwell 机柜

Catalina 是与 NVIDIA 协同设计的 Blackwell（GB200）机柜，是 Meta 上液冷的代表。

| 维度 | 参数 |
|---|---|
| 结构 | 6-rack pod：中间 2 机柜装 72 个 Blackwell GPU |
| 功耗 | ~140 kW/pod（约为传统风冷机柜的 8×） |
| 算力 | ~360 PFLOPS FP16/pod |
| 冷却 | 4 个 **AALC（Air-Assisted Liquid Cooling）** 机柜（风液混合） |
| 后续 | GB300 在规划中 |

### 5.1.3 MTIA — 自研训练/推理 ASIC

MTIA（Meta Training and Inference Accelerator）与 Broadcom 合作，遵循 **"High velocity / Inference First / PyTorch Native"** 三原则，cadence 约 6 个月一代。下表汇总四代（基于官方《Four MTIA Chips in Two Years》）：

| 代次 | 定位 | 关键提升 |
|---|---|---|
| **MTIA 300** | ranking/recommendation 训练（R&R） | 内置 NIC chiplet + message engine + 近存 reduction；1 compute chiplet + 2 network chiplet + HBM；PE 含 2 个 RISC-V 向量核 + Dot Product Engine + SFU + Reduction Engine + DMA |
| **MTIA 400** | 推理 | FP8 FLOPS +400%、HBM 带宽 +51%（vs 300）；2 compute chiplet；72 加速器 scale-up 域（switched backplane）；MX8/MX4 |
| **MTIA 450** | 推理（含 LLM） | HBM 带宽 2×（vs 400）；MX4 FLOPS +75%；硬件加速 attention/FFN（Softmax、FlashAttention）；MX4 FLOPS 是 FP16 的 6×；2027 初量产 |
| **MTIA 500** | 推理 | HBM 带宽 +50%、HBM 容量 +80%、MX4 FLOPS +43%（vs 450）；2×2 compute chiplet + HBM + 2 network chiplet + SoC chiplet（PCIe）；2027 量产 |

从 MTIA 300 到 500：**HBM 带宽 4.5×、计算 FLOPS 25×（MX8→MX4）**。400/450/500 共用同一 chassis/rack/network（drop-in 升级）。

> **MTIA 已有论文**：ISCA'23（MTIA 100）与 ISCA'25（MTIA 200，原名 MTIA 1 / MTIA 2i）。MTIA 已大规模部署服务广告（ads）推理。

## 5.2 网络模块

| 组件 | 用途 |
|---|---|
| **Arista 7800** | RoCE 集群的 spine/核心交换机 |
| **Wedge 400 / Minipack2** | OCP 开放的 ToR/leaf 交换机（RoCE 集群） |
| **NVIDIA Quantum-2** | InfiniBand 集群的交换机 |
| **拓扑** | rail-optimized fat-tree，400 Gbps 端点 |

网络模块的关键不是单台交换机，而是**拓扑 + 调度 + NCCL 协同**（见 [第 3 章](03-architecture) 3.3 节）。

## 5.3 存储模块

| 组件 | 角色 |
|---|---|
| **Tectonic** | DC 级分布式 FS，Flash 优化，EB 级；承载训练数据与 checkpoint |
| **FUSE API** | 自研 Linux FUSE 接口，跑在 Tectonic 上，给训练提供文件语义 |
| **Hammerspace** | 并行 NFS，交互式调试与数据探索 |
| **YV3 Sierra Point + E1.S SSD** | 高密度存储服务器 + EDSFF SSD |

存储模块的 SLA 核心：**checkpoint 跨数千 rank 数百毫秒存取**（依赖 Tectonic Flash 吞吐）。

## 5.4 集群管理与调度模块

| 组件 | 角色 |
|---|---|
| **Twine** | 集群管理器（cluster manager），把数据中心抽象成资源池；从推荐系统时代延续 |
| **MAST** | 训练/通用调度器；支撑 Prometheus 的长距离地理分布式训练 |

> ⚠️ Meta 公开资料无"Titanium 调度器"；集群管理用 Twine，训练调度用 MAST。

## 5.5 可靠性模块：SDC 三件套

这是 Meta 在 GenAI 时代最具辨识度的工程。硬件故障分三类：

| 类别 | 特征 | 治理 |
|---|---|---|
| **Static** | 开机即坏的二元故障（不枚举/不上电） | 健康检查 + 维修，规模大但易 triage |
| **Transient** | 热失控、不可纠正错误的间歇故障 | 用人造负载在非生产期复现 + "sticky" 状态遥测 |
| **Silent（SDC）** | 硬件算错但不留痕迹，硅缺陷导致；约每 1000 设备 1 个故障（软错误的 1000×） | 三层检测（见下） |

### SDC 三层检测

| 机制 | 工作方式 | 覆盖周期 | 局限 |
|---|---|---|---|
| **Fleetscanner** | 维护期（固件升级/维修）跑定向微基准，把签名纳入遥测 | 45–60 天扫一遍全集群 | 专用测试 host，对部分 SDC 太慢 |
| **Ripple** | 与负载同机共存，跑 ms–s 级测试，跨核/线程重叠指令 | 几天扫一遍全集群 | 比 Fleetscanner 快 |
| **Hardware Sentinel** | 内核态，评估应用异常，test-agnostic | 持续（分析面） | 比 testing-based 方法高 41% 覆盖率 |

### 训练 SDC 的两种失败模式

1. **NaN 传播**：SDC 把一个合法值推成 NaN → 感染后续计算 → 扩散到整个 accelerator domain → host → 整个集群停顿。源往往只是单个加速器上的几次特定计算，但在集群规模下难以定位。
2. **梯度方差污染（corrupted gradient variance）**：SDC 影响梯度计算（爆炸/塌缩/陷局部最优），但数值在界内、被当作正确，在同步训练里作为"真值"交换 → 训练看似在前进实则没进步。比 NaN 更难检测，可能数周/数月才显现。

### SDC 治理手段

**基础设施策略（infrastructure，集群级 triage）**：

- **Reductive triage**：二分搜索 + mini-training 迭代，逐步缩小集群隔离 NaN 源；用新节点重组集群从 checkpoint 恢复。
- **Deterministic training**：跑已知有效模型几步，验证非数据相关的计算故障。
- **Hyper-checkpointing**：提高 checkpoint 频率，把 NaN 困在特定 accelerator/host，加速 triage。

**栈策略（stack，与 workload 协同）**：

- **Gradient clipping**：限制梯度范围，把超界值裁剪、检测 NaN。
- **Algorithmic fault tolerance**：把容错融进训练算法，降低对检测/triage 的依赖（CPU 训练已验证）。
- **Tri-variate computational training**：用 shadow node 在随机迭代重复训练 step，shadow 与 live 不一致则只调查那批节点。
- **Parameter vulnerability factors（PVF）**：识别脆弱层 vs 韧性层，把脆弱层映射到韧性硬件。
- **Divergence detection**：为每个神经元维护分布图，检测推理期腐败（采样率可控）。

### 工厂到机队（Factory-to-Fleet）

Meta 把 SDC 治理延伸到硅的全生命周期：设计期（RAS 架构、telemetry、debug hook）→ 验证/集成期（yield 分析、制造诊断、机队签名反馈）→ 部署期（用户态诊断、周期测试、覆盖图）→ 运营期（Hardware Sentinel 大规模分析、固件 hook）。叠加**栈级韧性**（firmware/compiler/kernel/OS），把可靠性做成"贯穿硅生命周期 + 软硬协同"的体系工程。

## 5.6 服务模块：Llama Stack

Llama Stack 把 Llama 的服务标准化为 9 类 API：

| API | 作用 |
|---|---|
| Inference | 统一推理接口（跨硬件/框架） |
| Safety | Llama Guard / Prompt Guard 集成 |
| Agentic | tool-calling / memory / shielding |
| Memory | 会话/长期记忆 |
| Eval | 标准化评测 |
| Telemetry | 可观测性 |
| Post-training | 微调 |
| Toolchain | 构建/打包 |
| RAG | 检索增强 |

Llama Stack 与 [LLM Gateway](/04-llmops/llm-gateway/)、[Agent Runtime](/05-agent/agent-runtime/) 的理念相通：用开放协议把"换底层实现不影响上层应用"标准化。

## 5.7 开放安全工具

Meta 把安全工具全部开源，与 [安全篇](/08-security/) 互补：

| 工具 | 作用 |
|---|---|
| **Llama Guard 2** | 输入/输出安全分类器，基于 MLCommons 风险分类法 |
| **Prompt Guard** | 检测 jailbreak 与 prompt injection |
| **CyberSecEval 2** | 网络安全风险评估 |
| **Code Shield** | 代码安全（防不安全代码生成） |
| **GOAT** | Generative Offensive Agent Testing，模拟多轮中技能对抗者，自动化红队 |

## 小结

Meta 的核心模块围绕"大规模同步训练 + 开放发布"组织：计算用 Grand Teton / Catalina / MTIA / MI300 异构组合；网络用 RoCE + InfiniBand 双织物 + fat-tree；存储用 Tectonic + Hammerspace；调度用 Twine + MAST；可靠性用 SDC 三件套 + factory-to-fleet；服务用 Llama Stack；安全用 Llama Guard/Prompt Guard/CyberSecEval。每个模块都既是"工程产物"，又是"开放标准"——这正是 Meta 基础设施的双重身份。

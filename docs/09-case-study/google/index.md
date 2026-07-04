# Google 案例研究

如果说 OpenAI 的故事是"把规模做到极致并产品化"、Anthropic 的故事是"把安全与可解释性写进模型全生命周期"、Meta 的故事是"开放权重 + 硬件协同设计"，那么 Google 的基础设施故事代表了第四条、也是纵向最深的范式：**用全栈自研的领域专用硅（TPU）+ 可重配光路拓扑（OCS + 3D-torus）+ 编译器驱动的自动并行（XLA/GSPMD）+ 单控制器的跨 Pod 编排（Pathways），把"造一台为 ML 而生的超级计算机"这件事从芯片晶圆一直做到数据中心电网**。

研究 Google，是在前三个案例之外补齐"**垂直整合 + 软件开源**"这条主线——它不仅自研 TPU 硅（从 2015 年 v1 到 2025 年 Ironwood），还把支撑这些芯片的**整套软件栈**（JAX、XLA/OpenXLA、MaxText、JetStream）和**开放权重模型**（Gemma）都开源出来。Google 因此成为主要实验室里唯一一个"把跑在自己加速器上的编译 + 训练 + 服务软件栈都开放"的玩家——硬件闭源、软件全开。

## 一句话理解

> Google 的基础设施故事，是用 **领域专用硅（TPU/MXU/SparseCore）+ 可重配光路织物（OCS × 3D-torus）+ 可靠性即设计（NSDI'24 双路径恢复 / 99.98% 可用）+ 编译器自动并行（XLA/GSPMD）+ 跨 Pod 单控制器编排（Pathways/Multislice）+ 全开源软件栈（JAX/XLA/MaxText/JetStream）** 六条主线，把"为 ML 而生的超算"从晶圆做到电网的工程实践史。

## 学习目标

读完本主题后，你应该能够：

- 描述 TPU 的演进脉络：从 2015 年 v1（28nm、256×256 INT8 脉动阵列、仅推理）到 v2/v3（BF16、可训练、2D-torus）、v4（7nm、4×MXU、3D-torus + OCS、4096 芯片 Pod、SparseCore）、v5e/v5p，再到 Trillium 与 Ironwood（3nm、原生 FP8、192GB HBM、9216 芯片 Pod ≈ 42.5 Exaflops）。
- 解释**脉动阵列（systolic array / MXU）**的权重驻留原理，以及为什么"矩阵乘法过程中无需访存"是 TPU 能效的根因（v1 相对当代 GPU/CPU 快 15–30×、TOPS/W 高 30–80×）。
- 区分 Google 网络织物的四层：**ICI**（Pod 内 3D-torus，50 GBps/链路）、**OCS**（Palomar 光路交换，按需重配拓扑、<5% 成本 <3% 功耗）、**DC-GN/Jupiter**（跨 Pod/跨 DC）、**Falcon**（主机 NIC 硬件传输，200 Gbps / 120 Mops，Swift 拥塞控制）。
- 理解为什么 **3D-torus + OCS** 是 Google 区别于 NVIDIA（fat-tree + NVLink）/ Meta（fat-tree）的拓扑选择：torus 把 AllReduce 延迟项从 2·(N−1) 压到 2·Σ(dᵢ−1)，OCS 让逻辑拓扑与物理放置解耦并提供"cube 级备用+替换"的故障单元。
- 掌握 NSDI'24《Resiliency at Scale》的**两条真实恢复路径**：**reconfigure**（OCS 重配 + 迁移到空闲健康 cube，从 checkpoint 恢复，用于机器/ICI 故障）与 **reroute**（保留分配、重载容错 ICI 路由表 wild-first routing，不回滚但承受 0.5–8.6% 持续步时惩罚，用于 OCS 故障，95% 作业 opt-in）——并理解 99.98% 系统可用率如何在大规模同步训练下达成。
- 理解 **XLA/GSPMD** 的"标注即并行"哲学：用户写单设备 JAX，用少量 `PartitionSpec`/`with_sharding_constraint` 标注，编译器自动推断每个算子的分片并插入跨设备集合通信（FSDP/张量/流水线混合并行）。
- 解释 **Pathways** 为何用单控制器 + 异步分片数据流（sharded dataflow of futures）+ 成组派发（grouped dispatch）来 gang-schedule 数千 TPU，以及在万亿参数、跨 Pod 训练上的意义。
- 区分 Google 的开放姿态：**软件栈全开**（JAX/XLA/MaxText/JetStream，Apache-2.0）、**权重开放**（Gemma），但 **TPU 硬件闭源**（仅 GCP 可用）——并与 OpenAI/Anthropic（全闭）、Meta（权重 + OCP 硬件开放、软件栈第三方）对照。
- 用 JetStream/tpu-inference + 投机解码（DFlash，~3×）+ Gemma 3（local/global 混合注意力、128K 上下文、SigLIP 多模态）理解 Google 的推理栈与开放模型定位。

## 与相邻主题的关系

| 相邻主题 | 与 Google 案例的关系 |
|---|---|
| [AI 平台 / 算力底座](/03-ai-platform/) | TPU + GCP 是三大算力底座之一（GPU/TPU/自建）；Cloud TPU Multislice 是跨 Pod 弹性算力的代表。 |
| [AI SRE](/07-ai-sre/) | NSDI'24 的双路径恢复、`healthd`、preflight 检查、99.98% 可用率是 AI SRE 的硬核案例，与 Meta 的 SDC 治理对照。 |
| [LLMOps / 推理服务](/04-llmops/) | JetStream（→tpu-inference）是 TPU 原生推理引擎；投机解码（DFlash）是推理加速的代表技术。 |
| [RAG / 向量检索](/06-rag/) | SparseCore 专为稀疏嵌入加速（v4 起），与大规模嵌入/检索 workload 直接相关。 |
| [安全](/08-security/) | Frontier Safety Framework（Critical Capability Levels）、AI Principles、PSP 传输加密是 Google 的安全治理代表。 |
| [Meta 案例研究](/09-case-study/meta/) | 对照"开放权重 + OCP 硬件 + PyTorch"与"开放软件栈 + 自研 TPU 硅 + JAX"两条开放路线。 |
| [OpenAI 案例研究](/09-case-study/openai/) | 对照"闭源规模 + 通用 GPU"与"垂直整合自研硅 + 软件全开"。 |
| [Anthropic 案例研究](/09-case-study/anthropic/) | 对照“闭源对齐”与“开放生态 + 安全框架”。 |
| [计算机网络](/01-foundation/computer-networks/) | Google 的 OCS、3D-torus、Falcon NIC、Swift 拥塞控制是计算机网络主题中数据中心网络与 RDMA 的经典案例。 |
| [存储系统](/01-foundation/storage-systems/) | Google 的 Orbax/OCDBT/Zarr3 checkpoint 格式与 fsspec 后端是存储系统主题中分布式 checkpoint 的经典案例。 |
| [分布式系统基础](/01-foundation/distributed-systems/) | Borg/Paxos、3D-torus 路由、NSDI'24 双路径恢复、Pathways 单控制器都是分布式系统共识、复制、分区容错与协调的经典案例。 |

## 章节导航

1. [背景：为什么研究 Google](01-background) — TPU 十年演进（v1→Ironwood）、领域专用硅的设计动机、垂直整合 + 软件开源的独特姿态。
2. [核心思想](02-core-ideas) — 领域专用硅、可重配光路拓扑、可靠性即设计、编译器自动并行、开放软件栈五大支柱。
3. [架构设计](03-architecture) — 芯片（MXU/SparseCore/HBM/ICI）→ Pod（3D-torus + OCS）→ 跨 Pod（DC-GN/Jupiter）→ 主机传输（Falcon）→ 调度（Borg）→ 软件（JAX/XLA/GSPMD/Pathways）分层架构。
4. [训练与推理](04-training-and-inference) — GSPMD 分片、MaxText 训练循环、Multislice 跨 Pod（58.9% MFU）、Orbax checkpoint；JetStream 推理、投机解码（~3×）、Gemma 3、Gemini 服务。
5. [核心模块](05-core-modules) — MXU、SparseCore、ICI、OCS、3D-torus、Jupiter、Falcon、Borg/`healthd`、JAX Mesh、XLA/GSPMD、Pathways、Orbax、JetStream。
6. [源码与生态分析](06-source-analysis) — MaxText 真实代码（注意力分片、Mesh+pjit、训练循环、FSDP）、Pathways 架构、GSPMD、JetStream、开源状态表。
7. [Mini Demo](07-mini-demo) — 3D-torus 分维 AllReduce 延迟模型 + NSDI'24 双路径恢复（reconfigure vs reroute）模拟器。
8. [企业生产实践](08-production-practice) — NSDI'24 生产可靠性、Borg 调度协同、Multislice 规模化、可持续性（PUE 1.09 / 24/7 CFE / 2030 净零）、AI Principles + Frontier Safety、开放生态。
9. [最佳实践](09-best-practices) — 可复用的设计原则与检查清单。
10. [面试题](10-interview-questions) — 初/中/高级 Google 基础设施面试题。
11. [延伸阅读](11-further-reading) — 论文、仓库、博客、OCP 与交叉引用。

## 一句话总结

Google 把"为 ML 造超算"做成了从晶圆到电网的垂直整合：用脉动阵列 MXU 把矩阵乘法做成"无需访存"的能效极致，用 OCS 让 3D-torus 拓扑可按需重配并成为故障单元，用 NSDI'24 的双路径恢复把 4096 芯片同步训练的可用率推到 99.98%，用 XLA/GSPMD 把并行从"手写集合通信"降级为"几行分片标注"，用 Pathways 把单控制器程序 gang-schedule 到数千 TPU——最后把支撑这一切的 JAX/XLA/MaxText/JetStream 软件栈和 Gemma 权重全部开源，唯独留下 TPU 硅本身。这是"硬件闭源、软件全开"的范式，也是它与 OpenAI/Anthropic（全闭）、Meta（权重 + 硬件开放、软件栈第三方）的根本分野。

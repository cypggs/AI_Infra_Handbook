# 1. 背景：为什么研究 Google

## 1.1 一条与 GPU 完全不同的路

2015 年，当大多数深度学习算力还建立在 NVIDIA GPU + CUDA 之上时，Google 内部已经走完了一条"为 ML 自研硅"的闭环：自己设计芯片（TPU）、自己设计 Pod 级互联拓扑、自己写编译器（XLA）、自己写分布式运行时（Pathways）、自己造数据中心（Jupiter）、自己写集群管理器（Borg）。十年后回看，**这条全栈垂直整合的路是三大实验室里走得最深的一条**，它给出的不是"如何用通用 GPU 训练更大的模型"，而是"如何为矩阵乘法这种特定计算形态造一台专用超级计算机"。

研究 Google 案例的价值，正是在于它把**领域专用架构（Domain-Specific Architecture, DSA）**的逻辑推到了极致：从晶圆上的脉动阵列，到机柜间的光路交换，再到跨数据中心的梯度归约——每一层都针对 ML 的计算特征（稠密矩阵乘、稀疏嵌入、同步集合通信、对间歇性故障零容忍）做了协同设计。

## 1.2 设计动机：为什么通用计算不够用

TPU 的设计动机可以归结为三句话（来自 Google 的 TPU 架构文档与 Jouppi et al. 2017）：

1. **推理/训练的计算核是矩阵乘法。** 深度网络前向与反向 90%+ 的算力消耗在大型矩阵乘（GEMM）上。通用 CPU 的乱序执行、分支预测、大容量缓存层次对 GEMM 几乎没有价值——它们是为不规则、控制密集的 workload 设计的。GPU 用大量线程并发隐藏延迟，但每个线程仍要取指、译码、访问寄存器堆。
2. **脉动阵列把"计算过程中不访存"做到极致。** TPU 的核心 **MXU（Matrix Multiply Unit）** 是一个权重驻留（weight-stationary）的脉动阵列：权重预先载入，激活沿阵列流动，每个 MAC 单元在数据流过时完成乘加，**矩阵乘进行期间无需任何存储访问**。Google 的架构文档原话："No memory access is required during the matrix multiplication process." 这是 TPU 能效的根因——v1 相对当代 GPU/CPU 快 15–30×、TOPS/W 高 30–80×。
3. **规模要求专用互联。** 当一个训练任务需要 4096 颗芯片同步更新权重，任何一颗掉队或宕机都会停顿整个任务（NSDI'24 原文："all TPU processes must be simultaneously up to synchronously update their weights via ICI collectives. A single failed, or interrupted process will interrupt the whole training process"）。这要求互联不仅是"高带宽"，还要"可重配、可容错、可调度"——通用以太网 fat-tree 很难同时满足。

## 1.3 TPU 十年演进：从推理专用到 Exascale 训练

下表是 TPU 十年演进的骨架（数字来自 Google 官方博客、Cloud TPU 文档与架构文档；制程节点等 Google 未在主文档披露的项标注为二手来源）：

| 代次 | 年份 | 关键变化 | 规模 / 性能 |
|---|---|---|---|
| **TPU v1** | 2015 | 28nm，256×256 INT8 脉动阵列，**仅推理**；PCIe 接入，无芯片间互联 | 92 TOPS，28 MiB 统一缓冲 |
| **TPU v2 / v3** | 2017 / 2018 | BF16 训练；引入 **2D-torus** 芯片间互联；v3 液冷 | v3 Pod 1024 芯片 |
| **TPU v4** | 2021 | 7nm，4× MXU；**3D-torus + OCS** 光路交换；引入 **SparseCore**；4096 芯片 Pod | OCS <5% 成本、<3% 功耗 |
| **TPU v5e / v5p** | 2023 | 成本优化（v5e）与性能（v5p）；更大 Pod | v5p Pod 8960 芯片 |
| **Trillium / v6e** | 2024 | 256×256 MXU，918 TFLOPS BF16；v6e 成本档 | — |
| **Ironwood（第 7 代）** | 2025 | 3nm，**原生 FP8**，192GB HBM（7.37 TB/s），液冷 ~10MW；9216 芯片 Pod | 单芯片 4614 TFLOPS FP8；Pod ≈ **42.5 Exaflops**；ICI 1.2 TBps 双向（= 9.6 Tbps 双向 / 4.8 Tbps 单向） |

> **单位提示**：Google 对 Ironwood ICI 写的是 "1.2 TBps bidirectional"——大写 B 指**字节**，bidirectional 指双向合计。换算为比特：1.2 TBps × 8 = **9.6 Tbps 双向**，即每方向 4.8 Tbps。不要误读成"每条链路 1.2 Tbps"。

这条演进线的三个转折点值得记住：

- **v1→v2（推理→训练）**：v1 只能推理，且芯片间无互联；v2 引入 BF16 与 2D-torus，第一次让 TPU 能训练。这是 TPU 从"推理加速卡"变成"训练超算组件"的关键。
- **v3→v4（电气互联→光电可重配）**：v4 用 **OCS（Optical Circuit Switch）** 在光层动态重配拓扑，让逻辑拓扑与物理放置解耦。这是 NSDI'24 整套可靠性设计（cube 级备用 + 替换）的物理基础。
- **v4→Ironwood（INT8/BF16→原生 FP8 + Exascale）**：Ironwood 原生支持 FP8，把单 Pod 推到 ~42.5 Exaflops，直接对标当代最大规模的训练需求。

## 1.4 SparseCore：为稀疏嵌入而生的第二条数据通路

从 v4 起，每颗 TPU 除了做稠密矩阵乘的 MXU，还集成了一组 **SparseCore**——面向稀疏计算（嵌入查表、动态稀疏路由）的数据流处理器。v4 论文的原话："accelerate models that rely on embeddings by 5x–7x yet use only 5% of die area and power." 不同代次的 SparseCore 数量不同（v5p/Ironwood 每芯片 4 个，v6e 每芯片 2 个）。这是 Google 针对推荐系统、检索增强（RAG）、MoE 这类"稠密计算 + 稀疏嵌入"混合 workload 的协同设计——稠密部分走 MXU，稀疏部分走 SparseCore，避免稀疏访存拖慢脉动阵列。

## 1.5 垂直整合 + 软件开源：Google 的独特姿态

理解 Google 案例的关键，是它**纵向最深的垂直整合**与**横向最宽的软件开源**同时存在：

- **纵向**：从 TPU 硅（MXU/SparseCore/HBM）、到封装与液冷、到 Pod 级 OCS/ICI、到数据中心网络（Jupiter）、到主机传输（Falcon）、到集群管理（Borg）、到编译器（XLA/GSPMD）、到分布式运行时（Pathways）、到训练库（MaxText）、到推理引擎（JetStream）——**全自研**。
- **横向**：把支撑 TPU 的**整套软件栈开源**——JAX（`jax-ml/jax`）、XLA/OpenXLA（`openxla/xla`）、MaxText（`AI-Hypercomputer/maxtext`）、JetStream（→`tpu-inference`）、Gemma 权重。Apache-2.0 许可，活跃维护。

这让 Google 在主要实验室里独此一家：**硬件闭源（TPU 仅 GCP 可用），软件全开**。对照：

| 实验室 | 开放什么 | 闭源什么 |
|---|---|---|
| **Google** | **完整软件栈**（JAX/XLA/MaxText/JetStream）+ 开放权重（Gemma） | TPU 硬件（仅 GCP）；Gemini 前沿权重 |
| **OpenAI** | 仅 API | 权重、训练代码、服务栈 |
| **Anthropic** | 仅 API | 权重、训练代码、服务栈 |
| **Meta** | 开放权重（Llama）+ OCP 硬件设计 | 训练数据/配方；软件栈是第三方（vLLM/PyTorch） |

Meta 在**权重 + 硬件**层开放，Google 在**系统软件**层开放——这是两条不同维度的"开放"，也是本案例与 Meta 案例最核心的对照点。

## 1.6 本案例的研究主线

后续章节将围绕五条主线展开，它们对应 Google 基础设施最具辨识度、也最值得工程借鉴的设计决策：

1. **领域专用硅**（[第 2、3、5 章](02-core-ideas)）：脉动阵列 MXU、SparseCore、HBM/ICI 协同——为什么"矩阵乘不访存"是能效的根因。
2. **可重配光路拓扑**（[第 3、5 章](03-architecture)）：OCS + 3D-torus——为什么 torus 把 AllReduce 延迟项压到 fat-tree 难以企及的水平，以及 OCS 如何让拓扑成为"可调度资源"。
3. **可靠性即设计**（[第 8 章](08-production-practice)，[Mini Demo](07-mini-demo)）：NSDI'24 的双路径恢复——reconfigure vs reroute，以及 99.98% 可用率如何在 4096 芯片同步训练下达成。
4. **编译器自动并行**（[第 4、6 章](04-training-and-inference)）：XLA/GSPMD 的"标注即并行"——把并行从手写集合通信降级为几行分片标注。
5. **开放软件栈**（[第 6 章](06-source-analysis)）：JAX/XLA/MaxText/JetStream + Gemma——为什么 Google 选择"把跑在自己芯片上的软件栈全开"。

下一章 [核心思想](02-core-ideas) 将把这五条主线展开为可对照的设计原则。

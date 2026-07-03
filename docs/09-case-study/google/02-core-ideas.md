# 2. 核心思想

## 一句话理解

> Google 用**领域专用硅（脉动阵列）+ 可重配光路织物（OCS × 3D-torus）+ 可靠性即设计（双路径恢复）+ 编译器自动并行（XLA/GSPMD）+ 跨 Pod 单控制器编排（Pathways）+ 全开源软件栈（JAX/XLA/MaxText/JetStream）** 六条主线，把"为 ML 而生的超算"工程化。

这六条主线不是孤立的技术选型，而是**一组互相强化的设计决策**：脉动阵列要求专门的互联，专门的互联催生了可重配光路，可重配光路又成为可靠性设计的基础设施，而要把这套硬件用起来，又必须有能自动并行的编译器和跨 Pod 的运行时。本章把这六条主线提炼成可对照的核心思想，并在每条后面点明它解决了什么根本问题、与相邻方案的区别、以及它在后续哪一章被深入展开。

---

## 2.1 领域专用硅：让矩阵乘"不访存"

**问题**：深度学习 90%+ 算力消耗在大型稠密矩阵乘上，而通用 CPU/GPU 的微架构（乱序执行、缓存层次、取指译码、线程并发隐藏延迟）对规则的大规模 GEMM 几乎没有杠杆——算力和能耗大量浪费在与"乘加"无关的环节。

**Google 的答案**：**权重驻留的脉动阵列（systolic array），即 MXU**。权重预先载入阵列的每个 MAC 单元并固定，激活从阵列一侧流入，部分和沿另一方向流动，每个 MAC 单元在数据经过时完成一次乘加。其结果是——

> "No memory access is required during the matrix multiplication process." —— Google TPU 架构文档

矩阵乘进行期间，计算单元**完全不访问主存**。这是 TPU 能效的根因：v1（256×256 INT8，65536 个 8-bit MAC，28 MiB 统一缓冲）相对当代 GPU/CPU 快 15–30×、TOPS/W 高 30–80×。

从 v4 起还增加了 **SparseCore**——面向稀疏嵌入/动态路由的数据流处理器，"用 5% 的面积和功耗换取 5×–7× 的嵌入加速"，让稠密部分走 MXU、稀疏部分走 SparseCore，互不拖累。

**与相邻方案的区别**：GPU 用大量并发线程隐藏访存延迟（仍是"访存 + 计算"交替），TPU 直接把"访存"从热路径里删掉。这是 DSA（领域专用架构）相对 GPGPU 的本质差异。

> 详见 [第 3 章 架构设计](03-architecture) 与 [第 5 章 核心模块](05-core-modules)。

---

## 2.2 可重配光路织物：把拓扑变成"可调度资源"

**问题**：超大规模同步训练需要专用互联（ICI），但物理上把 4096 颗芯片布成某种固定拓扑后，一旦某颗芯片/某条链路坏了，整张拓扑就出现破洞；而且不同作业想要不同的拓扑形状（ring、mesh、torus）。

**Google 的答案**：**3D-torus 作为电气拓扑 + OCS（Optical Circuit Switch）作为光电重配层**。

- **3D-torus**：每颗芯片有 6 个最近邻链路（±x ±y ±z，带回绕）。torus 的关键数学性质是——把一次 AllReduce 沿三个维度拆成短 ring，**延迟项 = 2·Σ(dᵢ−1)**，按**边长**线性增长；而把所有 N 颗芯片串成单一大环的延迟项是 2·(N−1)，按**芯片总数**指数增长。对 16×16×16 = 4096 芯片：torus 延迟项 = 90，单环 = 8190——torus 约为单环的 1.1%。这是 Google 选 torus 而非 fat-tree + 单一集合通信的拓扑根因（详见 [Mini Demo](07-mini-demo) 的定量演示）。
- **OCS**：每个 Pod 配 48 台 128 端口的 Palomar MEMS 光路交换机，在光层按需把 cube（4×4×4 = 64 芯片）交叉连接成作业想要的 torus/扭曲 torus 形状。这让**逻辑拓扑与物理放置解耦**——Borg 不再需要担心 TPU 资源的物理连续性，"任意一组空闲 cube 都能通过 OCS 交叉连接给某个作业"。代价极低：OCS + 光纤 < 一台 v4 Pod 总资本成本的 5%，功耗 < 3%。

**与相邻方案的区别**：NVIDIA 用 NVLink（机柜内）+ InfiniBand fat-tree（机柜间）的固定拓扑；Meta 用 fat-tree。Google 的 torus + OCS 用"线性增长的布线/交换 + 光路可重配"换来了更低的 AllReduce 延迟和更强的容错弹性。

> 详见 [第 3 章](03-architecture)、[第 5 章](05-core-modules)，定量演示见 [Mini Demo](07-mini-demo)。

---

## 2.3 可靠性即设计：两条恢复路径 + 99.98% 可用

**问题**：大规模同步训练对故障零容忍——"任一芯片宕机都会中断整个训练"。而 4096 颗芯片的 Pod，期望 MTBF 被压到"小时甚至分钟"级（NSDI'24 原文）。传统"等修好再继续"的恢复方式会让作业长时间停摆。

**Google 的答案**：NSDI'24《Resiliency at Scale》披露的**两条自动化恢复路径**（注意：论文里**没有** "cherry-pick" 一词，下面是论文的真实术语）：

| 路径 | 机制 | 代价 | 用于 |
|---|---|---|---|
| **reconfigure**（Path 1） | OCS 重配，把作业**迁移到空闲健康 cube**，从最近 checkpoint 恢复 | 一次性迁移停机 + 回滚重跑 + 被放弃坏 cube 后台修复期间闲置（fleet 代价）；恢复后**零持续惩罚** | 机器级 / ICI 链路级故障（小 blast radius） |
| **reroute**（Path 2，"fault-tolerant ICI routing"） | **保留分配**，libtpunet 重载预计算的容错路由表（wild-first routing），让流量绕开坏链路 | 几乎不停机、不回滚；但此后**每步承受持续步时惩罚**（实测 0.5–8.6%，可累积） | OCS 故障（大 blast radius）；95% 作业 opt-in，任意时刻仅 <2% 作业处于此态 |

配合 `healthd` 守护进程（每台机器实时监控 24 条 ICI 链路 + 4 颗 TPU ASIC + PCIe）和两类 preflight 检查（**end-to-end check** 跑一个迷你样本 workload；**intent-driven checker** 把物理指标对照一组 golden "within spec" 阈值），整套系统在 fleet 规模上达到 **99.98% 系统可用率**、仅约 1% 训练作业受硬件中断影响。

**核心洞察**：两条路径的本质是一个**双轴权衡**——reconfigure 付"迁移停机"，reroute 付"持续步时惩罚"。只要 reroute 的单次步时惩罚低于某临界值（NSDI 实测 0.5–8.6% 远低于该临界），其"不停机、不回滚"就压倒 reconfigure——这正是 reroute 成为默认路径（95% opt-in）的原因，也是 Google 对 OCS 故障**优先修复**（以缩短 reroute 时长、控制 tax）的动机。

> 详见 [第 8 章 企业生产实践](08-production-practice)，定量演示见 [Mini Demo](07-mini-demo)。

---

## 2.4 编译器自动并行：把并行从"手写"降级为"标注"

**问题**：万亿参数模型在数千芯片上训练，需要数据并行、张量并行、流水线并行、FSDP 的复杂混合。传统做法（MPI 风格、手写 `AllReduce`/`AllGather`）要求工程师为每个并行组合、每个算子手写跨设备通信——规模一上去就不可维护。

**Google 的答案**：**XLA 编译器的 GSPMD pass**。用户像写单设备程序一样写 JAX，只在少数张量上给出分片标注（`PartitionSpec` / `with_sharding_constraint`），GSPMD 自动把标注**传播到每个算子**，推断每个中间张量的分片，并自动插入所需的跨设备集合通信。GSPMD 论文报告：在多达 2048 个 Cloud TPUv3 核心上，对最高万亿参数的模型达到 50%–62% 计算利用率。

**为什么 JAX 能做到**：因为 JAX 是**函数式、可追踪（traceable）**的——程序是数组的纯函数，没有隐藏副作用，XLA 能追踪整个计算图、看到每个张量的形状，从而从少量标注自动推断分片。带副作用或不透明的算子会破坏这种推断。这正是"标注即并行"的底层前提。

**与相邻方案的区别**：PyTorch 的 `DistributedDataParallel`/FSDP 是**显式**库调用（用户写通信）；JAX/XLA/GSPMD 是**隐式**编译器推导（用户写约束，编译器插通信）。两者在 MaxText（JAX）与 PyTorch FSDP 中各有体现，Google 的路线把"可扩展的并行策略"变成了编译器问题。

> 详见 [第 4 章 训练与推理](04-training-and-inference) 与 [第 6 章 源码分析](06-source-analysis)。

---

## 2.5 跨 Pod 单控制器编排：Pathways

**问题**：SPMD（单程序多数据）/ MPI 风格的执行假设"所有加速器跑同一个程序、lockstep 同步"，这在 Pod 内尚可，但跨 Pod、跨异构、跨稀疏（MoE、流水线）模型时就力不从心——单一并行策略被迫套到整个程序上，且同步 barrier 浪费资源。

**Google 的答案**：**Pathways**——异步分布式数据流运行时。核心思想：

- **单控制器**：一个客户端程序描述整个（可能跨 Pod 的）计算，而非每个设备跑一份程序。
- **异步派发（asynchronous dispatch）**：控制面在数据面之前就跑起来，利用编译函数静态已知的资源占用，把大量主机端工作**并行**派发而非串行，从而追平多控制器的性能。
- **分片数据流（sharded dataflow of futures）**：计算图里每个节点是一个已编译、已分片的 XLA 函数，边是 future；用"每分片计算一个节点"的紧凑表示避免 M×N 边爆炸。
- **成组派发（grouped dispatch）/ gang scheduling**：一个可静态调度的子图用**单条消息**描述，调度器把整组 shard 串起来执行。

Pathways 的 headline 结果：在 2048 颗 TPU 上跑 SPMD 达到约 100% 加速器利用率，同时对跨 16 级流水线或跨两个 island 的 Transformer 仍能给出与 SPMD 相当的吞吐。Pathways 之上有 **Multislice**：用 DC-GN（Jupiter）把多个 Pod/slice 串起来，激活走 ICI、梯度走 DCN 归约，XLA 自动把一个 all-reduce 分解为"ICI 内 → DCN 跨 slice → ICI 内"的层次集合通信，在 TPUv4 上对几十亿参数模型达到 **58.9% MFU**，且"多 slice 的 MFU 与单 slice 相当"。

**与相邻方案的区别**：大多数分布式训练框架是多控制器（每进程一份程序 + 集合通信）。Pathways 的单控制器 + 异步数据流是为了让"一个程序跨数千 TPU"在控制面上可扩展。

> 详见 [第 3 章](03-architecture)、[第 4 章](04-training-and-inference)、[第 6 章](06-source-analysis)。

---

## 2.6 开放软件栈：硬件闭源、软件全开

**问题**：自研硬件容易形成封闭生态，让外部无法学习、复现、贡献。

**Google 的答案**：把支撑 TPU 的**整套软件栈开源**：

- **JAX**（`jax-ml/jax`）：NumPy 式前端 + 自动微分 + XLA 编译 + 自动并行，是 Google ML 栈的地基。
- **XLA / OpenXLA**（`openxla/xla`）：把 HLO 降低为优化的 CPU/GPU/TPU 代码；GSPMD 是其中的分片 pass。
- **MaxText**（`AI-Hypercomputer/maxtext`）：纯 Python/JAX 的高性能、可读 LLM 训练参考实现，"无 C++/CUDA"，靠 JAX + XLA 拿到高 MFU。
- **JetStream**（→`tpu-inference`）：面向 XLA/TPU 的吞吐与内存优化推理引擎。
- **Gemma**：开放权重模型族（1B–27B，多模态，128K 上下文）。

这是 Google 区别于其它实验室的根本姿态：**唯一把跑在自己加速器上的"编译 + 训练 + 服务"软件栈都开放的玩家**，即便那些加速器（TPU）本身闭源。

**与相邻方案的区别**：见 [第 1 章](01-background) 的对照表——Meta 在权重 + OCP 硬件层开放，Google 在系统软件层开放。

> 详见 [第 6 章 源码与生态分析](06-source-analysis)。

---

## 2.7 六条主线的相互关系

```
领域专用硅(MXU/SparseCore) ──要求专门的互联──▶ 可重配光路织物(OCS×3D-torus)
        │                                              │
        │ 提供高能效稠密/稀疏计算                        │ 提供可重配、可容错的拓扑
        ▼                                              ▼
编译器自动并行(XLA/GSPMD) ◀──把硬件用起来─── 可靠性即设计(NSDI双路径)
        │                                              │
        │ 生成已分片的 XLA 函数                          │ 保证 4096 芯片同步训练 99.98% 可用
        ▼                                              │
跨Pod单控制器编排(Pathways/Multislice) ◀──gang-schedule──┘
        │
        ▼
开放软件栈(JAX/XLA/MaxText/JetStream + Gemma) ──让这一切可学习、可复现
```

这六条主线构成了 Google 基础设施的"设计闭环"。接下来的章节将按层次展开：[第 3 章](03-architecture) 给出分层架构总览，[第 4 章](04-training-and-inference) 讲训练与推理流程，[第 5 章](05-core-modules) 逐个剖析核心模块，[第 6 章](06-source-analysis) 进源码，[第 7 章](07-mini-demo) 用可运行的 Demo 验证两个核心机制。

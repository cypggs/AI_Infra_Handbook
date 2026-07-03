# 10. 面试题

本章用初/中/高级三档问答检验对 Google TPU 基础设施的理解。答案紧扣前述章节，标注出处，避免论文中不存在的术语。

---

## 初级（概念与事实）

### Q1. TPU 的计算核心是什么？它为什么比通用 CPU/GPU 更适合矩阵乘？

**答**：核心是 **MXU（Matrix Multiply Unit）**——一个权重驻留（weight-stationary）的脉动阵列。权重预先载入每个 MAC 单元并固定，激活沿阵列流动，矩阵乘进行期间**完全不访存**（Google 架构文档："No memory access is required during the matrix multiplication process"）。通用 CPU 的乱序/缓存/分支预测、GPU 的取指译码/线程隐藏延迟对规则 GEMM 没有杠杆。v1 相对当代 GPU/CPU 快 15–30×、TOPS/W 高 30–80×。（[1. 背景](01-background)、[2. 核心思想](02-core-ideas)）

### Q2. SparseCore 是什么？解决什么问题？

**答**：从 v4 起每颗 TPU 除 MXU 外集成的**稀疏计算数据流处理器**，面向嵌入查表/动态稀疏路由。v4 论文："用 5% 的晶圆面积和功耗，把依赖嵌入的模型加速 5×–7×"。它让稠密（MXU）与稀疏（SparseCore）走两条数据通路，避免稀疏访存拖慢脉动阵列，对推荐系统/RAG/MoE 尤为关键。（[1. 背景](01-background)、[5. 核心模块](05-core-modules)）

### Q3. TPUv4 Pod 有多少颗芯片？用什么拓扑？

**答**：**4096 颗**，组织成 **3D-torus**（带回绕的 3D mesh），由 64 个 4×4×4 cube（每 cube 64 芯片）构成。每颗芯片 6 条 ICI 链路（±x ±y ±z），每条 50 GBps 单向。一个 Pod 是"一个 ICI 域"，任意两颗 TPU 可 RDMA 互达。（[3. 架构](03-architecture)、[5. 核心模块](05-core-modules)）

### Q4. OCS 是什么？为什么需要它？

**答**：**Optical Circuit Switch**（Palomar MEMS 光路交换）。每个 v4 Pod 配 48 台 128 端口 OCS、6144 条光 ICI 链路。它在光层按需把 cube 交叉连接成作业想要的 torus 形状，**解耦逻辑拓扑与物理放置**——让 Borg 不必担心物理连续性，"任意一组空闲 cube 都能交叉连接给作业"。代价 <5% 资本成本、<3% 功耗。它也让 cube 成为故障域 blast radius。（[3. 架构](03-architecture)、[5. 核心模块](05-core-modules)）

### Q5. Google 开源了什么、闭源了什么？

**答**：**开源完整软件栈**——JAX、XLA/OpenXLA、MaxText、JetStream（→tpu-inference）、T5X、Paxml，以及开放权重 Gemma。**闭源 TPU 硬件**（仅 GCP 可用）与 Gemini 前沿权重。Google 是主要实验室里唯一"把跑在自己加速器上的编译+训练+服务软件栈都开放"的玩家。（[1. 背景](01-background)、[6. 源码分析](06-source-analysis)）

---

## 中级（机制与设计权衡）

### Q6. 为什么 Google 选 3D-torus 而非 fat-tree + 单一大 ring AllReduce？

**答**：因为 AllReduce 延迟项。把一次 AllReduce 沿 torus 三维拆成短 ring，**延迟项 = 2·Σ(dᵢ−1)**，按**边长**线性增长；单一大环是 2·(N−1)，按**芯片总数**指数增长。对 16×16×16 = 4096：torus 延迟项 90，单环 8190（约 1.1%）。带宽项两者渐近相同，故延迟主导（频繁小 AllReduce）时 torus 优势最大。详见 [Mini Demo](07-mini-demo) 的定量验证。（[2. 核心思想](02-core-ideas)、[7. Mini Demo](07-mini-demo)）

### Q7. NSDI'24 披露的两条恢复路径分别是什么？何时用哪条？

**答**：**Path 1 reconfigure**（"reconfigure jobs to use spare healthy cubes"）：OCS 把作业迁到空闲健康 cube，从最近 checkpoint 恢复。代价 = 一次性迁移停机 + 回滚重跑 + 坏 cube 后台修复期间闲置；恢复后零持续税。**用于机器/ICI 故障**（小 blast radius）。**Path 2 reroute**（"fault-tolerant ICI routing"，wild-first routing）：保留分配、重载预计算容错路由表、不回滚、继续跑。代价 = 几乎不停机，但此后每步承受 0.5%–8.6% 持续步时惩罚。**用于 OCS 故障**（大 blast radius）。OCS 故障被优先修复以缩短 reroute 时长。（注意论文无 "cherry-pick" 一词。）（[2. 核心思想](02-core-ideas)、[8. 生产实践](08-production-practice)）

### Q8. reroute 的步时惩罚 0.5%–8.6% 是怎么来的？为什么 95% 作业 opt-in？

**答**：reroute 让流量绕开坏链路，造成局部拥塞。NSDI'24 Table 3 实测各 workload 步时减速 0.5%–8.6%（如 RM-1 0.5%、RM-4 8.6%、LLM-1 2.6%、BERT-1 1.2%）；all-reduce workload 影响更大（最近邻通信承受 50% 吞吐打击），all-to-all 影响小。95% opt-in 是因为：只要单次步时惩罚低于某临界值（Demo 显示本配置约 30%），reroute"不停机、不回滚"就压倒 reconfigure 的迁移停机——0.5%–8.6% 远低于临界，故 reroute 是默认。（[7. Mini Demo](07-mini-demo)、[8. 生产实践](08-production-practice)）

### Q9. GSPMD 是什么？"标注即并行"为什么可行？

**答**：GSPMD 是 **XLA 编译器的分片 pass**——从少数用户标注（`PartitionSpec`/`with_sharding_constraint`）传播分片到每个算子，自动插入跨设备集合通信，生成 per-device 程序。可行是因为 JAX **函数式、可追踪**：程序是数组纯函数、无隐藏副作用，XLA 能追踪全图、看到每个张量形状，从而从少量标注自动推断分片。带副作用/不透明算子会破坏推断。指标：2048 TPUv3 核心上万亿参数模型 50%–62% 利用率。（[2. 核心思想](02-core-ideas)、[6. 源码分析](06-source-analysis)）

### Q10. Multislice 如何让 MFU 跨 Pod 不掉？

**答**：把集合通信分两层——**激活走 ICI、梯度走 DCN 归约**；XLA 自动把一个 all-reduce 分解为"ICI 内归约 → DCN 跨 slice 归约 → ICI 内广播"的层次集合通信；引入跨 DCN 的新分片维度，支持 FSDP/模型/流水线并行。结果是"多 slice 的 MFU 与单 slice 相当"（编译器优化使然），TPUv4 上几十亿参数模型 58.9% MFU。（[4. 训练与推理](04-training-and-inference)、[8. 生产实践](08-production-practice)）

### Q11. Borg 在 TPUv4 上加了哪些专用扩展？为什么不用 vanilla K8s？

**答**：Borg Prime（优先级调度 + 反碎片化抢占/迁移）、borglet（每机代理跑 `healthd`）、Pod Manager（管 OCS）、libtpunet（设 ICI 网络 + 加载容错路由表），共用 datacenter model DB 作为真相源。不用 vanilla K8s 是因为它开箱即用缺乏 TPUv4 所依赖的 cube/OCS/ICI 协同调度、配额即容量规划、cell 级 gang/抢占语义。Borgmaster 实测 99.99% 可用。（[3. 架构](03-architecture)、[8. 生产实践](08-production-practice)）

### Q12. Falcon 相对 RoCE 的关键区别是什么？

**答**：Falcon 是"在有丢包、无需特殊交换机支持的通用以太网上，第一个支持多 ULP（RDMA/NVMe）与异构 workload 的硬件传输"。关键区别：**不依赖 PFC**（不像 RoCE 需要无损网络），靠硬件重传在有损以太网上可靠；Swift 血缘的延迟拥塞控制 + PLB 多路径；200 Gbps/120 Mops；拥塞下完成时间比 CX-7 RoCE 低最多 8×、有丢笔下 goodput 高最多 65%。（[3. 架构](03-architecture)、[5. 核心模块](05-core-modules)）

---

## 高级（系统设计与深度）

### Q13. 如果你要设计一个支持 99.98% 可用率的 4096 芯片同步训练系统，关键设计决策有哪些？

**答**：（1）**可重配拓扑**：OCS 让逻辑拓扑与物理放置解耦，cube 作故障域，使"换一组空闲 cube"成为快速恢复原语——把主机可用率要求从 99.9% 降到 99%。（2）**双路径恢复分工**：机器/ICI 故障 reconfigure（迁移 + checkpoint 重启），OCS 故障 reroute（绕行 + 步时税），对症优先修复。（3）**检测先于调度**：`healthd` 持续监控 + preflight（end-to-end check + intent-driven golden 阈值）在调度前排除亚健康。（4）**故障序列与可用率建模**：每组件每日故障率（机器 0.08%、ICI 缆 0.005%、OCS 0.04%）× fleet 规模 → MTBF 小时/分钟级，必须自动化。（5）**checkpoint 权衡**：间隔决定 reconfigure 回滚损失。（6）**监控 reroute 活跃率** <2%。（详见 [8. 生产实践](08-production-practice)、[Mini Demo](07-mini-demo)）

### Q14. Pathways 为什么要用单控制器 + 异步分片数据流，而不是多控制器 SPMD？

**答**：SPMD/MPI 的 lockstep 同步在跨 Pod、跨异构、跨稀疏（MoE/流水线）模型上力不从心——单一并行策略被迫套到整个程序、同步 barrier 浪费资源。Pathways 用单控制器（一个程序描述整个跨 Pod 计算）+ **异步派发**（利用编译函数静态资源占用，把主机端工作并行而非串行派发，追平多控制器性能）+ **分片数据流 of futures**（每分片计算一个节点，避免 M×N 边爆炸）+ **成组派发**（一个静态可调度子图用单条消息描述）。结果：2048 TPU 上 SPMD 约 100% 利用率，跨 16 级流水线/跨两 island Transformer 吞吐与 SPMD 相当。（[2. 核心思想](02-core-ideas)、[6. 源码分析](06-source-analysis)）

### Q15. 在 TPU 上做投机解码为什么尤其划算？

**答**：因为 TPU 上**验证成本由权重加载主导**，而非 attention 计算——"验证 1024 个 token 的代价几乎等同于验证 16 个"（K-Flat 验证）。这意味着验证宽度"几乎免费"，瓶颈转向 draft 质量。DFlash 用 block-diffusion drafter 把传统 O(K) 串行 drafting 降到 O(1)（一次前向"画"整块），契合 MXU 高带宽；实测 Qwen3-4B + DFlash 平均 3.13×（数学峰值近 6×），端到端 Llama-3.1-8B on vLLM-TPU 2.29× vs EAGLE-3 1.30×。（[4. 训练与推理](04-training-and-inference)）

### Q16. MaxText 如何用"逻辑轴规则"表达 FSDP？换并行策略要改什么？

**答**：MaxText 用一个名为 `fsdp`（及 `fsdp_transpose`）的 mesh 轴表达 FSDP。`remove_fsdp_sharding` 遍历分片树，把每个 `fsdp`/`fsdp_transpose` PartitionSpec 项替换为 `None`（即复制/all-gather），Zero-1 包装在 apply 前 all-gather 权重、apply 后释放。YAML 的 `logical_axis_rules` 把张量逻辑轴（batch/length/head/dim）映射到物理 mesh 轴（`data`/`fsdp`/`tensor`/`pipeline`），合并 base + per-model + CLI 覆盖。**换并行策略只需改 `logical_axis_rules` 这几行 YAML**，不动通信代码——这是"标注即并行"的可维护性红利。（[6. 源码分析](06-source-analysis)）

### Q17. Google 的"开放软件栈 + 闭源硬件"与 Meta 的"开放权重 + 开放硬件"各自的战略含义？

**答**：Google 在**系统软件层**开放（JAX/XLA/MaxText/JetStream），把 ML 系统研究变成社区公共知识，加速生态对"编译器自动并行""TPU 原生推理"的采纳，把护城河留在 TPU 硅（资本密集、差异化）。Meta 在**权重 + 硬件层**开放（Llama 权重 + OCP 硬件设计），但软件栈是第三方（vLLM/PyTorch），训练数据/配方闭源。两种切法都"开放以建生态"，但开放的层不同：Google 让"如何用它的芯片"可学习，Meta 让"如何复现它的模型与机柜"可学习。共同点：都不开放"最前沿的差异化资产"（Google 的硅与 Gemini 权重、Meta 的训练配方）。（[1. 背景](01-background)、[9. 最佳实践](09-best-practices)）

### Q18. 如果 reroute 的步时惩罚在生产中持续高于临界，你会如何应对？

**答**：（1）**优先修复**触发 reroute 的组件（NSDI'24 对 OCS 正是这么做），缩短 reroute 时长以控税；（2）**切换到 reconfigure**：若税持续超临界（Demo ~30%），迁移到健康 cube、从 checkpoint 重启、恢复零税（付一次性迁移停机）；（3）**检查 reroute 路径质量**：wild-first routing 的离线 ILP 是否仍最优，是否需要重算路由表；（4）**监控 reroute 活跃率**：生产应 <2%，超阈值告警；（5）**评估热备 cube**（NSDI'24 未来工作方向）：预配 hot-standby cube，迁移加速器状态而无需持久 checkpoint。（[8. 生产实践](08-production-practice)、[7. Mini Demo](07-mini-demo)）

---

下一章 [延伸阅读](11-further-reading) 给出论文、仓库、博客与交叉引用。

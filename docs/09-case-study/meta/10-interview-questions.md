# 10. 面试题

本章按初/中/高级整理 Meta 基础设施相关的面试题，覆盖同步训练可靠性、网络织物、硬件协同设计、自研硅、开放生态等主题。每题给出考察点与答题思路。

## 10.1 初级（概念与动机）

### Q1. 为什么 Meta 的 AI 训练集群不能用"传统数据中心的容错思路"？

**考察点**：同步训练的可靠性模型。

**思路**：传统数据中心（Memcache/Twine 时代）依赖"硬件不可靠没关系，软件重试到另一台"。但分布式数据并行训练是**同步**的——每个 step 所有 rank 做 AllReduce/AllGather，任一 rank 故障或变慢（straggler）都会停顿整个任务。所以一个 N-GPU 任务的可靠性 ≈ 单 GPU 可靠性的 N 次方，集群越大越脆弱。这迫使 Meta 必须把单点故障率压到极低、恢复做到极快。

### Q2. 什么是"有效训练时间（effective training time）"？Meta 的目标是多少？

**考察点**：可靠性北极星指标。

**思路**：有效训练时间 = 持久前进的计算 / 总挂钟时间（含故障恢复开销）。Meta 的 Llama 3 目标是 **>95%**，即在 16k GPU 上 >400 TFLOPS/GPU。这意味着"花在训练上的钱 95% 没白花"——可靠性本身就是成本优化。

### Q3. Meta 为什么同时建 RoCE 和 InfiniBand 两个集群？

**考察点**：双网络织物的动机。

**思路**：两个理由——(1) 供应链韧性（RoCE 基于开放以太网多供应商，对冲 NVIDIA InfiniBand 单一供应商锁定）；(2) 技术验证（在两套截然不同的织物上训练同一代模型，暴露隐式假设；Llama 3 在 RoCE 集群跑通本身就是行业级证明）。

### Q4. 开放权重（open weights）对 Meta 的工程链路有什么影响？

**考察点**：train-to-release 范式。

**思路**：权重要部署到所有主流云、硬件、推理引擎，倒逼出高度标准化的跨硬件兼容性测试矩阵；安全责任转移给部署方（所以 Meta 开放 Llama Guard/Prompt Guard 等工具）；并催生 Llama Stack 标准化服务接口。

## 10.2 中级（架构与实现）

### Q5. 解释 fat-tree 拓扑与"rail-optimized"的含义，以及它为什么适合大规模训练。

**考察点**：网络拓扑。

**思路**：fat-tree 保证上层链路总带宽 ≥ 下层链路总带宽之和，任意两个叶子节点间有无阻塞全带宽路径。"rail-optimized" 指把每个节点的多条上行链路（rail）分到不同 spine 域，让 AllReduce/AllGather 通信在多条等价路径间均衡，避免拥塞热点。适合大规模训练是因为 collective 通信（尤其 AllGather）对任意节点对带宽极敏感。

> ⚠️ 易错：fat-tree/rail-optimized 是 Meta H100 集群特征；3D-torus + ICI 光互连是 Google TPU pod 特征。

### Q6. Meta 怎么把大规模集群的 AllGather 带宽利用率从 10%–90% 波动稳定到 90%+？

**考察点**：拓扑感知调度 + NCCL 协同。

**思路**：(1) 拓扑感知作业调度——把训练任务调度到网络距离最近的 GPU 子集；(2) NCCL 路由协同优化——让 collective 通信感知底层拓扑选最优路径；(3) collective 算法选择（ring vs tree）。三者配合把利用率稳定到 90%+。

### Q7. SDC（静默数据损坏）对训练有哪两种典型失败模式？为什么比硬故障更危险？

**考察点**：SDC 的训练影响。

**思路**：(1) NaN 传播——SDC 把合法值推成 NaN，感染整个集群导致停顿（虽可见但难定位源）；(2) 梯度方差污染——数值在界内被当正确，同步训练里作为"真值"交换，训练看似前进实则没进步，可能数周/月才显现。比硬故障危险因为"不停顿"——硬故障至少会触发恢复，SDC 静默毁掉训练质量且难追溯。

### Q8. 描述 Meta 的 SDC 三层检测机制及其权衡。

**考察点**：SDC 检测体系。

**思路**：
- Fleetscanner：维护期定向微基准，45–60 天扫全集群，专用 host，对部分 SDC 太慢。
- Ripple：与负载同机共存，ms–s 级，几天扫全集群，更快。
- Hardware Sentinel：内核态，评估应用异常，test-agnostic，比 testing-based 高 41% 覆盖率。
权衡：覆盖速度 vs 侵入性 vs 准确率，三者组合提供最佳机队覆盖。

### Q9. FP8 训练 + FP16 master weights 的设计动机是什么？

**考察点**：低精度训练范式。

**思路**：FP8 做前向/反向计算与激活，降低计算量与显存带宽需求提升吞吐；FP16 master weights 高精度累加梯度与更新，避免低精度数值发散。这是"低精度计算 + 高精度累积"的经典范式。Llama 4 Behemoth 用此在 32k GPU 上达 390 TFLOPS/GPU。

### Q10. FSDP 每个 step 触发几次 AllGather？为什么这决定 MFU？

**考察点**：FSDP 与 collective 性能。

**思路**：至少两次（前向聚合参数 + 反向聚合参数）。由于每 step 都触发，AllGather 带宽利用率直接决定模型 FLOPS 利用率（MFU）。这就是为什么 Meta 投入拓扑感知调度与 NCCL 协同优化来稳定 AllGather 利用率。

## 10.3 高级（生产落地与 trade-off）

### Q11. 你要设计一个 100k-GPU 训练集群的可靠性方案，从检测到恢复画出完整闭环，并量化关键 SLA。

**考察点**：综合可靠性工程。

**思路**：闭环 = 检测（硬件遥测 + SDC 三件套）→ triage（reductive triage/deterministic training/hyper-checkpointing）→ 隔离故障节点 → 从 checkpoint 恢复（跨数千 rank 秒级）→ 重建进程组（分钟级）→ auto-restart。关键 SLA：有效训练时间 >95%、checkpoint 延迟秒级、进程组初始化分钟级、SDC 焊死率近 0（验证先于 checkpoint）。强调 factory-to-fleet + 栈级韧性。

### Q12. checkpoint 间隔应该怎么设？给出量化 trade-off。

**考察点**：Mini Demo 的核心 trade-off。

**思路**：小间隔→故障丢失工作少但 checkpoint 开销高；大间隔→反之，且 SDC 更可能焊死。最佳间隔应与 MTBF 匹配（远小于 MTBF 时回滚浪费低），并保证 validation_interval ≤ ckpt_interval。在 Meta 规模下 Tectonic Flash 吞吐让"小间隔 + 低开销"同时成立。可用 Mini Demo 量化：回滚浪费% + checkpoint 开销% 的总和最小处。

### Q13. 如果 SDC 率随硅密度持续上升（~1/1000 且可能更高），纯检测够吗？还该投资什么？

**考察点**：算法级容错（前瞻）。

**思路**：纯检测有覆盖盲区（unknown unknowns）。应同时投资**算法级容错**（algorithmic fault tolerance）、**tri-variate computational training**（shadow node 冗余）、**parameter vulnerability factors**（脆弱层映射到韧性硬件）、**factory-to-fleet**（从硅设计就嵌入 RAS 与 telemetry）。把可靠性做成"硅生命周期 + 软硬协同"的体系工程，而非只靠运行时检测。

### Q14. Meta 自研 MTIA 的"PyTorch Native"原则在工程上意味着什么？相比自研独立软件栈有何优劣？

**考察点**：自研硅的软件栈策略。

**思路**：意味着 MTIA 接 PyTorch（torch.compile/torch.export），图编译器复用 TorchInductor + Triton + MLIR + LLVM，通信库 HCCL 接口对齐 NCCL，驱动/固件用 Rust。优势：kernel/并行策略可跨 NVIDIA/AMD/MTIA 复用，生态红利大；劣势：受限于 PyTorch 抽象，某些硬件特性需在编译器层暴露。整体上"Native"让 MTIA 不另起炉灶，是开放哲学在自研硅上的兑现。

### Q15. 开放权重 + Llama Stack 的组合，对行业生态有什么外部性？

**考察点**：开放生态的系统效应。

**思路**：(1) 标准化服务接口降低应用层碎片化；(2) 跨硬件/云兼容让"换底层不影响上层"；(3) 开放安全工具让部署方能自建策略；(4) 开放硬件设计（OCP）让供应链围绕统一标准优化。本质是把"造 AI 数据中心"变成公共知识，整个行业（含竞争对手的硬件商）都能受益并反哺优化——开放成为规模化的杠杆，而非零和让利。

## 小结

Meta 的面试题集中在三个层次：**理解同步训练为何改变可靠性模型（初级）、掌握网络/SDC/低精度的具体机制（中级）、能在 GW 级规模上做可靠性工程与生态决策（高级）**。贯穿所有题目的主线，是 Meta 把"开放 + 协同设计 + 可靠性即设计"作为规模化杠杆的工程哲学。

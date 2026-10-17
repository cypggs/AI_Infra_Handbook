# 延伸阅读

## 一手论文与官方来源（按主题分组，全部附一手 URL）

### 故障统计与可靠性测量

- Kokolis et al., **Revisiting Reliability in Large-Scale Machine Learning Research Clusters**, HPCA 2025（Meta；1,024 卡作业 MTTF 7.9 h 的原始出处；IEEE Xplore 检索标题，HPCA 2025 会议论文集 pp. 1259-1274）。
- Meta, **The Llama 3 Herd of Models**, 2024-07（§3.3 训练基础设施：466 次中断/54 天、78% 硬件、SDC 6 次、>90% 有效训练时间）。https://arxiv.org/abs/2407.21783
- Dixit et al., **Silent Data Corruption at Scale**, DSN 2021（Facebook 内存 SDC 大规模研究）。https://arxiv.org/abs/2102.11245

### 恢复系统与热备

- **TrainMover: An Interruption-Resilient and Reliable ML Training Runtime**, Meta，arXiv 2024-12（8,192 卡冷重启 6.47 min 拆解；热备 ~20 s；恢复经济学）。https://arxiv.org/abs/2412.12636
- Wan et al., **Robust LLM Training Infrastructure at ByteDance (ByteRobust)**, 2025-09（97% ETTR；检测 2s/10s/30s；热备热更新 46-65 s；每步分层 checkpoint <0.9%；EUD 召回率 ~70%）。https://arxiv.org/abs/2509.16293
- Google, **TPU v4: An Optically Reconfigurable Supercomputer for ML with Hardware Support for Embeddings**, NSDI 2024（99.98% 可用率；双路径恢复；故障率表）。https://www.usenix.org/system/files/nsdi24-zu.pdf

### Straggler 与 fail-slow

- Wu et al., **FALCON: Pinpointing and Mitigating Stragglers for Large-Scale Hybrid-Parallel Training**, 2024-10（Alibaba + HKUST；>10K 卡；检测 >99%；缓解 60.1%）。https://arxiv.org/abs/2410.12588

### SDC 与数值正确性

- **Understanding Silent Data Corruptions in LLM Training**, ACL 2025（真实不健康节点对照实验；XLA 确定性执行）。https://aclanthology.org/2025.acl-long.996/
- Hoke et al., **Cores That Don't Count**, HotOS 2021（Google；CPU 静默错误的生产观测）。

### Checkpoint 工程

- Mohan, Phanishayee, Chidambaram, **CheckFreq: Frequent, Fine-Grained DNN Checkpointing**, FAST 2021（两阶段高频 checkpoint）。https://www.usenix.org/conference/fast21/presentation/mohan
- Wang et al., **Gemini: Fast Failure Recovery in Distributed Training with In-Memory Checkpoints**, SOSP 2023（内存 checkpoint + Raft 恢复）。https://arxiv.org/abs/2302.08472
- **Optimizing Frequent Checkpointing via Low-Cost Differential for Distributed Training Systems**, 2025-09（差量 checkpoint）。https://arxiv.org/abs/2509.04084

### 工具链官方文档

- PyTorch DCP 文档（2.14）：https://docs.pytorch.org/docs/2.14/distributed.checkpoint.html
- torchrun / PyTorch Elastic 文档（2.14）：https://docs.pytorch.org/docs/2.14/elastic/run.html
- NVIDIA nvidia-resiliency-ext（experimental；fault_tolerance / inprocess / checkpointing 子包）：https://github.com/NVIDIA/nvidia-resiliency-ext

### 前沿追踪（2026）

- **AIReSim: A Discrete Event Simulator for Large-scale AI Cluster Reliability Modeling**, 2026-03。https://arxiv.org/abs/2603.07041
- **Leto: Fast In-Place Recovery for LLM Training on Surviving Hardware**, 2026-09。https://arxiv.org/abs/2610.00687
- **TierCheck: Tiered Checkpointing for Fault Tolerance in LLM Training**, 2026-05。https://arxiv.org/abs/2605.17821

## 相关章节

| 章节 | 为什么相关 |
|---|---|
| [AI SRE](/07-ai-sre/) | 训练可靠性是 AI SRE 的 SLO / 事故响应 / 错误预算思想在训练侧的垂直实现。 |
| [Benchmark + Evaluation](/07-ai-sre/benchmark-evaluation/) | ETTR、MTTR、误报率都是可回归评估的指标；可靠性改进的有效性验证借评估工程方法。 |
| [分布式系统基础](/01-foundation/distributed-systems/) | 故障模型、幂等重试、共识与恢复语义的理论底座。 |
| [存储系统](/01-foundation/storage-systems/) | checkpoint 是训练对存储最苛刻的负载：分层带宽、原子写、恢复读放大。 |
| [xAI 案例](/09-case-study/xai/) | Colossus 122 天建成、19 天开训：建设期压缩如何转移运行期可靠性成本。 |
| [Google 案例](/09-case-study/google/) | NSDI'24 双路径恢复（reconfigure vs reroute）深度展开；cube 故障域与 OCS 拓扑。 |
| [DeepSeek 案例](/09-case-study/deepseek/) | DualPipe 流水线调度对训练故障域的切分思路；万卡集群的架构层可靠性。 |
| [RL Post-Training](/04-llmops/rl-post-training/) | RL 训练的 checkpoint 特殊性：rollout 状态、reward 模型版本与异步流水线的恢复语义。 |

## 阅读顺序建议

1. 先读 Llama 3 论文 §3.3 与 ByteRobust——建立对"故障有多频繁、系统长什么样"的直觉。
2. 用 TrainMover 的 Table 1 与经济学章节做恢复时间线的定量骨架。
3. CheckFreq → Gemini → 差量 checkpoint 串起 checkpoint 工程演进。
4. 想深入架构层，转 [Google 案例](/09-case-study/google/) 与 [xAI 案例](/09-case-study/xai/)。

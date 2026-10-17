# GPU 故障与大规模训练可靠性工程：Training Reliability & Fault Tolerance

万卡级训练的真实瓶颈不是算力，而是可靠性。当 16,384 张 GPU 同步更新一次权重时，任何一张卡宕机、任何一条链路抖动、任何一个比特静默翻转，都会让整个作业停摆。本主题系统讲清楚大规模训练中的故障统计、静默数据损坏、checkpoint 工程、弹性恢复、straggler 缓解与有效训练时间的成本账。

## 一句话理解

> 训练可靠性工程是万卡集群的"保险业"：用检测、checkpoint、热备与冗余计算，把"每小时都有硬件在坏"的物理现实，兑换成"有效训练时间占比超过 95%"的合同指标（ETTR）。

## 学习目标

读完本主题后，你应该能够：

- 用一手数据解释为什么万卡训练的瓶颈是可靠性而非算力（Llama 3 的 466 次中断、Meta 1,024 卡作业 7.9 小时 MTTF）。
- 建立故障 taxonomy：fail-stop / fail-slow / SDC 三态模型，硬件、网络、主机、软件、数据的分类与占比。
- 推导 MTBF 随规模线性恶化的规律，并用它解释为什么 10 万卡集群必须把 MTTR 压到分钟级。
- 设计 checkpoint 策略：同步 vs 异步、分层存储、差量/增量、间隔优化（Daly 公式与精确解）。
- 讲清弹性恢复全链路：检测 → 定位 → 决策 → 热备替换/回滚重启 → 复盘，以及 Gang 调度语义带来的约束。
- 选择生产工具链：PyTorch DCP、torchrun elastic、NVIDIA nvidia-resiliency-ext、Megatron-LM 容错与云厂商托管方案。
- 算清可靠性成本账：ETTR、MTTR 经济学、热备池的 P99 二项模型、10 万卡的多维可靠性预算。

## 与相邻主题的关系

| 相邻主题 | 与训练可靠性的关系 |
|---|---|
| [AI SRE](/07-ai-sre/) | 训练可靠性是 AI SRE 在训练侧的最大战场：SLO、事故响应、错误预算全部适用。 |
| [Benchmark + Evaluation](/07-ai-sre/benchmark-evaluation/) | 可靠性目标本身需要被度量与回归：ETTR、MTTR、误报率都是可评估指标。 |
| [GPU + CUDA](/01-foundation/gpu-cuda/) | Xid 错误、ECC、HBM 健康度是故障检测的第一手信号源。 |
| [分布式系统基础](/01-foundation/distributed-systems/) | 故障模型、幂等、重试、共识与恢复语义的理论底座。 |
| [存储系统](/01-foundation/storage-systems/) | checkpoint 是训练对存储系统最苛刻的负载：高并发小写、强一致元数据、分层带宽。 |
| [Kubernetes](/02-cloud-native/kubernetes/) | Gang 调度、节点健康检查、Pod 重调度是弹性训练的运行时载体。 |
| [Google 案例](/09-case-study/google/) | NSDI'24 双路径恢复（reconfigure vs reroute）是"可靠性即设计"的标杆。 |
| [xAI 案例](/09-case-study/xai/) | Colossus 122 天建成、19 天上电开训的建设期可靠性教训。 |

## 章节导航

1. [背景：万卡训练的瓶颈是可靠性](01-background)
2. [核心概念](02-core-ideas)
3. [架构设计](03-architecture)
4. [故障与恢复工作流程](04-failure-recovery-workflow)
5. [核心模块](05-core-modules)
6. [源码与生态分析](06-ecosystem-analysis)
7. [Mini Demo](07-mini-demo)
8. [企业生产实践](08-production-practice)
9. [最佳实践](09-best-practices)
10. [面试题](10-interview-questions)
11. [延伸阅读](11-further-reading)

## 一句话总结

万卡训练里硬件每小时都在坏；训练可靠性工程的全部工作，就是用"检测快一点、回滚少一点、恢复短一点、冗余巧一点"，把物理世界的不确定性兑换成可承诺的有效训练时间。

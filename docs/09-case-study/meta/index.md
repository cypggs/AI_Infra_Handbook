# Meta 案例研究

如果说 OpenAI 的故事是"把规模做到极致并产品化"、Anthropic 的故事是"把安全与可解释性写进模型全生命周期"，那么 Meta 的基础设施故事代表了第三条截然不同的范式：**用开放权重（open weights）+ 硬件协同设计（hardware co-design）+ 从训练到发布的全栈开源，构建支撑数十亿用户的超大规模 AI 基础设施**。

研究 Meta，是在前两个案例之外补齐"开放生态"这条主线——它不仅训练 Llama 系列模型，还通过 OCP（开放计算项目）开放硬件设计、通过 PyTorch/Triton 开源软件栈、通过 Llama Stack 标准化模型服务接口，把"如何造一个 AI 数据中心"这件事本身变成可复用的公共知识。

## 一句话理解

> Meta 的基础设施故事，是用 **开放权重 + 硬件协同设计（Grand Teton / Catalina / MTIA）+ 双网络织物（RoCE 与 InfiniBand 并行验证）+ 可靠性即设计（SDC 治理 / >95% 有效训练时间）+ PyTorch 原生软件栈** 五条主线，把"超大规模同步训练 + 开放发布"工程化的实践史。

## 学习目标

读完本主题后，你应该能够：

- 描述 Meta AI 基础设施的演进脉络：从 LAMP/Memcache 时代到 GPU 推荐系统，再到 24k/129k H100 GenAI 集群与 Prometheus（1GW）/Hyperion（5GW）路线。
- 解释为什么"同步训练"（synchronous training）从根本上改变了可靠性模型：任何单点故障或 straggler 都会停顿整个任务，并理解 Meta 如何把中断率降低约 50 倍、把有效训练时间推到 >95%。
- 区分三种硬件故障（static / transient / silent）与 Silent Data Corruption（SDC）对训练的独特危害（NaN 传播、梯度方差污染），并掌握 Fleetscanner / Ripple / Hardware Sentinel 三层检测体系。
- 理解 Meta 的硬件协同设计哲学：Grand Teton（OCP 开放 GPU 平台）、Catalina（GB200 机柜，AALC 液冷）、MTIA 300–500（与 Broadcom 合作的推理/训练 ASIC）以及 AMD MI300 的异构组合。
- 对比 RoCE 与 InfiniBand 两种 400 Gbps 网络织物，理解"双织物并行验证"为何是降低供应链与单点依赖风险的关键决策。
- 掌握 Meta 软件栈的"PyTorch 原生"定位：FSDP、torch.compile、Triton、torchtune、ExecuTorch、Llama Stack、HCCL（MTIA 通信库）与 Rust 用户态驱动/固件。
- 用开放权重 + Llama Stack 的"从训练到发布"范式，理解 Meta 与 OpenAI（闭源规模）、Anthropic（闭源对齐）的本质区别。

## 与相邻主题的关系

| 相邻主题 | 与 Meta 案例的关系 |
|---|---|
| [LLMOps / vLLM](/04-llmops/vllm/) | Meta 是 PyTorch 主要贡献者；vLLM 是 Llama 系列推理事实标准；MTIA 提供 vLLM plugin backend。 |
| [LLM Gateway](/04-llmops/llm-gateway/) | Llama Stack Inference API 提供跨云、跨硬件、跨框架的统一推理入口。 |
| [Agent Runtime](/05-agent/agent-runtime/) | Llama Stack Agent API 把 tool-calling、memory、shielding 标准化为开放协议。 |
| [安全](/08-security/) | Llama Guard 2、Prompt Guard、CyberSecEval 2、Code Shield 是开放权重安全治理的代表。 |
| [AI SRE](/07-ai-sre/) | 同步训练的可靠性工程（SDC、~50x 中断下降、auto-restart）是 AI SRE 的硬核案例。 |
| [OpenAI 案例研究](/09-case-study/openai/) | 对照"闭源规模"与"开放权重 + 硬件协同设计"两条路线。 |
| [Anthropic 案例研究](/09-case-study/anthropic/) | 对照“闭源对齐”与“开放发布 + 自研硅”两条路线。 |
| [计算机网络](/01-foundation/computer-networks/) | Meta 的 RoCE 与 InfiniBand 双织物、fat-tree 拓扑是计算机网络主题中数据中心网络与 RDMA 的经典案例。 |

## 章节导航

1. [背景：为什么研究 Meta](01-background) — 从 LAMP 到 GenAI 的基础设施演进、同步训练的可靠性挑战、规模路线（4k→24k→129k→1GW→5GW）。
2. [核心思想](02-core-ideas) — 开放权重、硬件协同设计、双网络织物、可靠性即设计、PyTorch 原生软件栈五大支柱。
3. [架构设计](03-architecture) — 计算/网络/存储/软件/数据中心分层架构，RoCE 与 InfiniBand 双织物，fat-tree 拓扑。
4. [训练与推理](04-training-and-inference) — 3D 并行、FP8 + FP16 master weights、AllGather 调优、checkpoint/恢复、Llama 3/4 训练细节、MoE/iRoPE 推理效率。
5. [核心模块](05-core-modules) — Grand Teton、Catalina、MTIA、网络交换机、Tectonic/Hammerspace 存储、Twine/MAST 调度、SDC 检测、Llama Stack。
6. [源码与生态分析](06-source-analysis) — PyTorch/FSDP、torch.compile、Triton、torchtune、Llama Stack、MTIA 软件栈与 Rust 驱动。
7. [Mini Demo](07-mini-demo) — 训练集群可靠性 + checkpoint-restart + SDC 检测模拟器。
8. [企业生产实践](08-production-practice) — 大规模训练可靠性、SDC 治理、双织物选型、异构硅、开放权重发布流水线、电力与选址。
9. [最佳实践](09-best-practices) — 可复用的设计原则与检查清单。
10. [面试题](10-interview-questions) — 初/中/高级 Meta 基础设施面试题。
11. [延伸阅读](11-further-reading) — 官方博客、论文、OCP、Llama Stack 与交叉引用。

## 一句话总结

Meta 把"造 AI 数据中心"本身变成了开放标准：用 OCP 开放硬件、用 PyTorch 开放软件、用 Llama 开放权重、用 Llama Stack 开放服务接口，再用 >95% 的有效训练时间和自研 MTIA 硅证明——开放不意味着低效，反而让"硬件工程师有标准 workload 可优化"成为规模化的杠杆。

# RL Post-Training 基础设施

> 一句话理解：**RL Post-Training 基础设施是把"环境交互 → 奖励计算 → 策略更新"这条强化学习闭环，跑在上千张 GPU 上的工程系统**。它决定了 o1/R1 之后大模型能力上限能爬多高、爬多快。

## 什么是 RL Post-Training

大模型的训练分为两个阶段：

1. **Pre-Training（预训练）**：用海量无标注语料做 next-token prediction，学到"语言能力"。
2. **Post-Training（后训练）**：在预训练模型之上，用 SFT（Supervised Fine-Tuning）和 **RL（Reinforcement Learning，强化学习）** 把模型对齐到人类偏好与具体任务。

RL Post-Training 是后训练的核心手段，代表算法包括：

- **RLHF**（Reinforcement Learning from Human Feedback，OpenAI InstructGPT/ChatGPT 的路线）
- **RLAIF**（RL from AI Feedback，Anthropic Constitutional AI 的路线）
- **RLVR**（RL with Verifiable Rewards，DeepSeek-R1 / Qwen3 的路线，用可验证奖励替代人类偏好模型）
- **DPO / GRPO / PPO**（具体策略优化算法）

## 为什么 RL Post-Training 是"基础设施"问题

RL 训练与 SFT/预训练有本质区别：

| 维度 | SFT / Pre-training | RL Post-Training |
|---|---|---|
| 数据 | 静态语料，预先准备 | **在线生成**（Rollout），模型边训练边产出 |
| 计算图 | 单次 forward + backward | **Generate + Score + Train** 三段式，循环往复 |
| 关键瓶颈 | 算力（MFU） | **生成吞吐 × 训练效率 × 调度协调** |
| 状态一致性 | 单一模型 | **多模型共存**：Policy、Reference、Reward、Critic |
| 资源占用 | 训练集群独占 | 训练 + 推理 + 评分**三种负载混合** |

这意味着：**你不能直接用预训练那套 Megatron-LM/DeepSpeed 跑 RL**。必须有一套专门的基础设施，把"推理引擎、训练引擎、奖励服务、调度器"四种异构系统焊在一起。

## 2024-2026 年为什么爆发

- **2024-09**：OpenAI o1 发布，证明 RL 可以让模型获得"推理能力"（reasoning），突破 SFT 天花板。
- **2025-01**：DeepSeek-R1 开源，证明 **纯 RL（GRPO）+ 可验证奖励** 可以在数学/代码上达到 o1 水平，且**不需要 Reward Model**。
- **2025-2026**：Qwen3、Kimi K2、GLM-4.5、Claude 4、Gemini 2.5 全部把 RL Post-Training 作为标配；字节 Seed、阿里通义、腾讯混元、Meta、NVIDIA 都公开了自家 RL 训练栈。
- **Agentic RL**：让模型在真实环境（终端、浏览器、代码执行器）中多轮交互学习，成为 2026 年的下一个主战场。

RL Post-Training 从"OpenAI 内部秘方"变成了"所有一线实验室的基础设施必备件"。

## 本主题结构

1. [背景](01-background)：为什么需要 RL Post-Training，为什么不能复用预训练基建
2. [核心思想](02-core-ideas)：Rollout/Train 分离、On-Policy、可验证奖励
3. [架构设计](03-architecture)：四大组件与三种主流拓扑
4. [Runtime 工作流程](04-runtime-workflow)：一次 RL step 的完整时序
5. [核心模块](05-core-modules)：Rollout Worker、Trainer、Reward Service、Controller
6. [源码分析](06-source-analysis)：veRL / OpenRLHF / TRL / NeMo-RL
7. [工程实践：Mini Demo](07-mini-demo)：纯 Python 实现 GRPO + Rollout/Train 分离
8. [企业生产实践](08-production-practice)：DeepSeek、字节 Seed、阿里、NVIDIA 的实战
9. [最佳实践](09-best-practices)：性能调优、稳定性、成本
10. [面试题](10-interview-questions)
11. [延伸阅读](11-further-reading)

## 学习目标

读完本主题后，你应该能够：

- 解释为什么 RL Post-Training 不能用传统预训练框架直接跑
- 画出 Rollout/Train 分离架构的数据流与控制流
- 说明 PPO / GRPO / DPO 在工程上的关键差异
- 定位 veRL / OpenRLHF 的核心抽象与扩展点
- 在生产环境中规划一个 RL 训练集群的资源配比
- 评估 Agentic RL 给基础设施带来的新挑战

## 相关主题

- [大模型从 0 到 1](/01-foundation/llm-from-zero/)：预训练与后训练的全景图
- [vLLM](/04-llmops/vllm/)：RL Rollout 的主流推理引擎
- [SGLang](/04-llmops/sglang/)：RadixAttention 让多轮 Agentic Rollout 更高效
- [Ray](/03-ai-platform/ray/)：veRL、OpenRLHF 的分布式底座
- [Kubernetes](/02-cloud-native/kubernetes/)：RL 集群的调度底座
- [GPU 在 Kubernetes 上的调度](/02-cloud-native/gpu-scheduling/)：Rollout 与 Train 混合负载的调度挑战
- [Agent Runtime](/05-agent/agent-runtime/)：Agentic RL 的环境侧
- [AI SRE](/07-ai-sre/)：RL 训练的可观测性与稳定性

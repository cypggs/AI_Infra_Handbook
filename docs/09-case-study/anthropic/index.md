# Anthropic 案例研究

Anthropic 是当代最独特的 AI 实验室之一——它由一群同样坚信"规模化假设"、却更早把"安全"写进公司治理结构的工程师创立。从 Claude 的宪法对齐（Constitutional AI / RLAIF），到机制可解释性研究（transformer-circuits、dictionary learning、Circuit Tracing），再到以 Trainium 为核心的异构算力布局（Project Rainier 与 Colossus），以及把 prefix caching 工程化为产品级能力的 prompt caching，Anthropic 给"如何负责任地把大模型做成基础设施"提供了一套自洽的工程答案。

研究 Anthropic，是在 OpenAI 的"规模与产品化"叙事之外，补充"对齐、可解释性与安全治理"这条同样重要、甚至更具长期价值的主线。

## 一句话理解

> Anthropic 的基础设施故事，是用 **宪法对齐 + 机制可解释性 + 异构分层算力 + 治理化扩展（RSP/ASL）** 四条主线，把安全要求工程化进大模型全生命周期的实践史。

## 学习目标

读完本主题后，你应该能够：

- 描述 Anthropic 的算力布局：AWS Trainium（Project Rainier，>100 万芯片、5GW）与 SpaceXAI Colossus（22 万 GPU）的异构协同。
- 解释 Constitutional AI / RLAIF 的两阶段流程，以及它与 RLHF 的本质区别。
- 理解 Anthropic 的可解释性路线（induction heads → dictionary learning / 稀疏自编码器 → Circuit Tracing）及其工程意义。
- 掌握 Claude 推理工程的关键优化：prompt caching（prefix hash + 20-block lookback、5m/1h TTL、pre-warm）、extended thinking、Batch API、computer use。
- 用 Responsible Scaling Policy（ASL-1~5）框架，理解前沿 AI 风险治理如何落地为可审计的工程承诺。

## 与相邻主题的关系

| 相邻主题 | 与 Anthropic 案例的关系 |
|---|---|
| [vLLM](/04-llmops/vllm/) | Claude 推理同样依赖 continuous batching、KV/prefix cache；prompt caching 是工程化 prefix cache 的代表。 |
| [LLM Gateway](/04-llmops/llm-gateway/) | Claude API + Bedrock/Vertex/Foundry 多云入口、"三云同款模型"策略。 |
| [Agent Runtime](/05-agent/agent-runtime/) | computer use、tool use、extended thinking 是 Claude 智能体的核心能力。 |
| [安全](/08-security/) | RSP/ASL、Constitutional AI、红队、Risk Reports 是企业安全治理的标杆。 |
| [AI SRE](/07-ai-sre/) | run-rate $30B、消费级增长冲击可靠性——典型的容量规划与 SRE 案例。 |
| [OpenAI 案例研究](/09-case-study/openai/) | 同为前沿实验室，对照"规模驱动"与"对齐驱动"两条工程路线。 |

## 章节导航

1. [背景：为什么研究 Anthropic](01-background) — 公司起源、Claude 演进、算力规模与工程挑战。
2. [核心思想](02-core-ideas) — HHH、宪法对齐、可解释性优先、安全即工程、治理化扩展。
3. [架构设计](03-architecture) — 异构算力、训练、对齐、推理、安全治理的分层架构。
4. [训练与推理流水线](04-training-and-inference) — 从数据到宪法对齐再到在线服务的完整链路。
5. [核心模块](05-core-modules) — Trainium 集群、Constitutional AI 管线、可解释性工具、推理优化、RSP 治理。
6. [源码与可解释性生态](06-source-analysis) — transformer-circuits、dictionary learning 开源代码与 Claude API 设计。
7. [Mini Demo](07-mini-demo) — 一个 prompt caching 模拟器 + Constitutional critique-revise 循环。
8. [企业生产实践](08-production-practice) — 三云托管、成本优化、RSP 合规与容量治理。
9. [最佳实践](09-best-practices) — 可复用的设计原则与检查清单。
10. [面试题](10-interview-questions) — 初/中/高级 Anthropic 基础设施与对齐面试题。
11. [延伸阅读](11-further-reading) — 官方论文、博客、RSP、transformer-circuits 与交叉引用。

## 一句话总结

Anthropic 把"AI 安全"从口号变成工程：用宪法对齐训练模型，用稀疏自编码器解剖模型，用 prompt caching 优化推理，用 RSP/ASL 治理规模化风险——为整个行业示范了"安全"如何与"规模"同速演进。

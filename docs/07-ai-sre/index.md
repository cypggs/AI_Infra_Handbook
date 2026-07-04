# AI SRE 篇

AI SRE 负责让 AI 系统在生产环境中跑得稳、看得清、修得快。它把传统 SRE 的可用性、延迟、容量、变更管理，与 AI 系统特有的不确定性、模型漂移、幻觉、成本爆炸结合起来，形成一套可度量的可靠性工程体系。

## 一句话理解

> AI 系统不仅要跑得快，还要跑得稳；AI SRE 负责在不确定性中建立可度量的可靠性。

## 学习目标

读完本主题后，你应该能够：

- 解释 AI 系统与传统服务在可靠性上的核心差异。
- 设计覆盖 trace、metrics、logs 的 AI 可观测性方案。
- 为 LLM/Agent 服务定义 SLI/SLO/Error Budget 并配置多窗口 burn-rate 告警。
- 构建基于 OpenTelemetry 的 AI 应用 instrumentation 与数据 pipeline。
- 理解 AIOps 在异常检测、根因分析、辅助修复中的定位与局限。
- 制定 AI 生产事故的响应流程、runbook 与事后复盘机制。

## 与相邻主题的关系

| 相邻主题 | 与 AI SRE 的关系 |
|---|---|
| [LLM Gateway](/04-llmops/llm-gateway/) | Gateway 是 AI 服务的流量入口，是 latency、error rate、token 成本等核心 SLI 的来源。 |
| [vLLM / SGLang / TensorRT-LLM / Triton](/04-llmops/) | 推理引擎的 metrics（TTFT、ITL、queue time、KV cache）是 AI SRE 监控的关键信号。 |
| [Agent Runtime](/05-agent/agent-runtime/) | Agent 循环的每一步都需要 trace 与可观测，AI SRE 负责把这些 trace 转化为 SLO 与告警。 |
| [RAG](/06-rag/) | RAG 流水线的检索延迟、召回率、生成质量需要专门的可观测性与评估指标。 |
| [Memory](/05-agent/memory/) | 记忆系统的读写延迟、一致性与漂移影响 Agent 可靠性。 |
| [Agent OS](/05-agent/agent-os/) | Agent OS 提供进程隔离与资源治理，是 AI SRE 执行降级、重试、沙箱策略的底座。 |
| [安全](/08-security/) | 安全事件是可观测性的一部分；trace、metrics、audit log 是检测与溯源的基础。 |
| [Linux 系统与性能调优](/01-foundation/linux-systems/) | CPU、memory、I/O、network 指标都来自 Linux 内核；Linux 调优是 AI SRE 根因分析的基础。 |

## 章节导航

1. [背景：为什么 AI 系统需要专门的 SRE](01-background)
2. [核心概念](02-core-ideas)
3. [架构设计](03-architecture)
4. [AI SRE 工作流程](04-ai-sre-workflow)
5. [核心模块](05-core-modules)
6. [源码与生态分析](06-source-analysis)
7. [Mini Demo](07-mini-demo)
8. [企业生产实践](08-production-practice)
9. [最佳实践](09-best-practices)
10. [面试题](10-interview-questions)
11. [延伸阅读](11-further-reading)

## 一句话总结

AI SRE 是用可观测性、SLO、AIOps 和事故响应机制，把 AI 系统从“能跑”变成“可信任”的工程学科。

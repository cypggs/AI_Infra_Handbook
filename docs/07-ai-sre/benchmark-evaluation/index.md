# Benchmark + Evaluation：Agent / 可观测性 / 可评估性

AI 系统上线后，"能跑"不等于"对"、"快"不等于"稳"。Benchmark + Evaluation 负责用可复现的基准、自动化的评估与可观测的反馈闭环，把模型、Prompt、Agent 与 RAG 的质量、成本、安全风险变成可度量、可追踪、可改进的工程对象。

## 一句话理解

> Benchmark + Evaluation 是 AI 系统的"质量 CI"：它定义"什么是对"、持续度量"有多对"、并把评估结果反馈给模型、Prompt、工具链与部署流程。

## 学习目标

读完本主题后，你应该能够：

- 解释为什么传统监控无法覆盖 AI 系统的质量与风险。
- 设计覆盖正确性、事实性、工具使用、延迟、成本、安全、鲁棒性的评估维度。
- 区分离线评估、在线评估、LLM-as-judge、人工复核的适用场景与局限。
- 搭建从 Agent / App → 埋点 → 评估引擎 → Benchmark Registry → 评分 → 告警 / 人工复核 → CI/CD 的端到端框架。
- 选择并对比 OpenAI Evals、LM Evaluation Harness、LangSmith、Phoenix、Ragas、DeepEval、Promptfoo、MLflow Evaluate 等主流工具。
- 在生产环境中落地 CI 评估门、影子评估、A/B 评估、成本预算与失败模式归因。

## 与相邻主题的关系

| 相邻主题 | 与 Benchmark + Evaluation 的关系 |
|---|---|
| [AI SRE](/07-ai-sre/) | AI SRE 提供 trace、metrics、logs、SLO 与事故响应；Evaluation 把这些可观测数据转化为质量评分与回归检测。 |
| [Agent Runtime](/05-agent/agent-runtime/) | Agent 的多步骤决策、工具调用与循环需要在 trace 上被逐层评估。 |
| [Tool Use](/05-agent/tool-use/) | 工具调用是否正确、参数是否合法、结果是否被正确消费，是评估的核心维度。 |
| [MCP](/05-agent/mcp/) | MCP 统一了工具描述与调用协议，为 trace-based 工具评估提供标准化输入。 |
| [RAG](/06-rag/) | RAG 的检索召回率、片段相关性、答案忠实度需要专门的 benchmark 与指标。 |
| [LLMOps](/04-llmops/) | LLMOps 管理模型版本、Prompt、实验与部署；Evaluation 为 LLMOps 提供质量门与回归信号。 |
| [Security](/08-security/) | 安全评估（越狱、PII、有害内容）是 Benchmark + Evaluation 不可或缺的子集。 |

## 章节导航

1. [背景：为什么部署 + 监控仍然不够](01-background)
2. [核心概念](02-core-ideas)
3. [架构设计](03-architecture)
4. [评估工作流程](04-evaluation-workflow)
5. [核心模块](05-core-modules)
6. [源码与生态分析](06-source-analysis)
7. [Mini Demo](07-mini-demo)
8. [企业生产实践](08-production-practice)
9. [最佳实践](09-best-practices)
10. [面试题](10-interview-questions)
11. [延伸阅读](11-further-reading)

## 一句话总结

Benchmark + Evaluation 把 AI 系统的不确定性转化为可度量的质量信号，并通过持续反馈闭环让系统越评估越可靠。

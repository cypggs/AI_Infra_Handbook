# Agent Runtime 总览

> 一句话理解：**Agent Runtime 是大模型与外部世界交互的执行容器**，它把“用户目标”反复拆解成“思考 → 行动 → 观察”，并在循环中管理工具、记忆、状态、权限、可观测与恢复。

## 学习目标

阅读完本主题后，你应该能够：

1. 解释为什么 Agent 需要独立的 Runtime，而不是直接调用 LLM API。
2. 说清楚 Agent Runtime 与 workflow engine、LLM Gateway、MCP、Agent OS、Multi-Agent Framework 的边界。
3. 画出典型 Agent Runtime 架构，并说明各模块职责。
4. 描述一个任务从进入 Runtime 到完成的完整生命周期。
5. 对比 OpenAI Agents SDK、LangGraph、CrewAI、Smolagents、PydanticAI 的设计取舍。
6. 跑通并扩展本主题的 Mini Demo，理解 ReAct 循环与工具注册机制。
7. 回答生产部署、沙箱、护栏、可观测、状态持久化相关的面试问题。

## Agent Runtime 与其他主题的关系

| 主题 | 解决的核心问题 | 与 Agent Runtime 的关系 |
|---|---|---|
| [vLLM](/04-llmops/vllm/) / [SGLang](/04-llmops/sglang/) | 单个模型如何跑得快 | Runtime 通过 LLM Client 调用这些推理引擎 |
| [LLM Gateway](/04-llmops/llm-gateway/) | 多供应商/多引擎统一接入 | Runtime 通常位于 Gateway 之后，使用其暴露的统一模型接口 |
| **Agent Runtime** | 如何安全、可观测、可扩展地执行 Agent 任务 | 承上启下，把模型能力转化为任务执行能力 |
| [MCP](/05-agent/mcp/) | 工具发现与调用协议 | Runtime 可通过 function calling 直接调用工具，也可按需接入 [MCP](/05-agent/mcp/) 实现标准化能力发现 |
| [Memory](/05-agent/memory/) | 长期记忆与上下文管理 | Runtime 负责在循环中读写 Memory，具体存储/检索/持久化由 Memory 主题负责 |
| [Planning](/05-agent/planning/) | 任务分解与重规划 | Runtime 内嵌轻量 Planner，复杂规划由 Planning 主题负责 |
| [Tool Use](/05-agent/tool-use/) | 工具定义、调用与执行 | Runtime 调用 Tool Use 层完成工具注册、解析、校验、执行与结果反馈 |
| [Agent OS](/05-agent/agent-os/) | 运行时操作系统 | Runtime 是 Agent OS 的核心执行组件；Agent OS 在 Runtime 之上提供进程管理、调度、沙箱与资源治理 |
| [Multi-Agent](/05-agent/multi-agent/) | 多 Agent 协作 | 本主题聚焦单 Agent Runtime，Multi-Agent 在其之上做协调与调度 |
| RAG | /06-rag/ | RAG 把 Retriever 作为工具接入 Runtime 的 ReAct 循环。 |
| AI SRE | /07-ai-sre/ | AI SRE 为 Runtime 提供 trace、metrics、SLO 与事故响应体系。 |

## 本章结构

1. [背景](01-background) — 从 prompt engineering 到 Agent 的演进与 Runtime 必要性。
2. [核心思想](02-core-ideas) — ReAct、工具调用、记忆、规划、护栏、可观测、恢复。
3. [架构设计](03-architecture) — 模块分层、控制面/数据面、部署形态。
4. [Runtime 工作流程](04-runtime-workflow) — 任务生命周期详解。
5. [核心模块](05-core-modules) — Task Parser、Planner、Executor、Tool Registry、Memory、State、LLM Client、Guardrails、Observer、Recovery。
6. [源码分析](06-source-analysis) — OpenAI Agents SDK、LangGraph、Smolagents、PydanticAI。
7. [工程实践](07-mini-demo) — 纯 Python 可运行的 Mini Demo。
8. [企业生产实践](08-production-practice) — 部署、持久化、沙箱、评测、与 LLM Gateway 集成。
9. [最佳实践](09-best-practices) — 模型选择、工具设计、可观测、沙箱、评测、避免过度编排。
10. [面试题](10-interview-questions) — 初级/中级/高级面试题。
11. [延伸阅读](11-further-reading) — 官方文档、论文、工程文章。

## 一句话总结

Agent Runtime 不是又一个 LLM 调用库，而是**把“模型会回答问题”变成“模型会执行任务”的工程底座**；它让业务方定义目标，让 Runtime 负责思考、调用工具、管理状态并在失败时恢复。

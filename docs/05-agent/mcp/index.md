# MCP 总览

> 一句话理解：**MCP 是 AI 应用与外部工具、数据、提示之间的开放 USB-C 接口**，通过统一的 JSON-RPC 协议让 Host、Client、Server 三方解耦。

## 学习目标

阅读完本主题后，你应该能够：

1. 解释为什么 Function Calling 之后还需要 MCP，以及 MCP 解决了哪些工程问题。
2. 说清楚 MCP 中 Host、Client、Server 各自的职责与边界。
3. 描述 MCP 协议的生命周期：initialize、能力交换、发现、调用、通知、关闭。
4. 画出 MCP 的五层架构，并说明控制面与数据面的分离方式。
5. 对比 stdio、SSE、Streamable HTTP 三种 Transport 的适用场景与取舍。
6. 跑通并扩展本主题的 Mini Demo，理解协议消息流转与 Mock LLM 决策。
7. 回答企业落地 MCP 时的注册中心、网关、认证、多租户、版本兼容与可观测问题。

## MCP 与其他主题的关系

| 主题 | 解决的核心问题 | 与 MCP 的关系 |
|---|---|---|
| [Agent Runtime](/05-agent/agent-runtime/) | Agent 如何安全、可观测、可扩展地执行 | Runtime 通过 MCP Client 接入外部 Server，也可以直接 function calling |
| [Memory](/05-agent/memory/) | 长期记忆与上下文管理 | MCP Resource 可暴露记忆存储；Memory 主题负责语义检索与持久化 |
| [Multi-Agent](/05-agent/multi-agent/) | 多 Agent 协作 | 多个 Agent 可共享同一组 MCP Server，通过 Capability 协商避免冲突 |
| [Reflection](/05-agent/reflection/) | Agent 自我反思与纠错 | Reflection 可调用 MCP Tool/Resource 获取评估数据 |
| **MCP** | 工具/资源/提示的发现与调用协议 | 承上启下，把外部能力以标准接口暴露给 Agent |
| [Planning](/05-agent/planning/) | 任务分解与重规划 | Planner 通过 MCP 发现可用能力并生成调用计划 |
| [Tool Use](/05-agent/tool-use/) | 工具调用与执行 | MCP 是 Tool Use 的协议化延伸，关注能力发现与跨模型互操作 |
| [Agent OS](/05-agent/agent-os/) | 运行时操作系统 | MCP Host 是 Agent OS 中负责外部能力接入与安全控制的组件；Agent OS 在 Host 之上做进程/调度/沙箱治理 |
| Tool Use（后续主题） | 工具定义与执行细节 | MCP 是 Tool Use 的协议化延伸，关注发现与互操作 |
| RAG | /06-rag/ | Retriever 与知识库可封装为 MCP Server。 |
| AI SRE | /07-ai-sre/ | AI SRE 观测 MCP Server/Client 的调用延迟与错误。 |
| 安全 | /08-security/ | MCP Server 暴露的工具/资源/提示需要 capability 协商、调用授权与审计。 |

## 本章结构

1. [背景](01-background) — 从 Function Calling 到 MCP 的演进与协议必要性。
2. [核心思想](02-core-ideas) — Host / Client / Server 三角角色、Primitives、Capability negotiation、Transport 无关性。
3. [架构设计](03-architecture) — 五层架构、控制面/数据面、本地与远程部署形态。
4. [协议工作流程](04-protocol-workflow) — 生命周期、initialize、发现、调用、通知、错误码、关闭。
5. [核心模块](05-core-modules) — Server Registry、Capability Manager、Transport Adapter、Session Manager、Message Router、Handlers、Auth/Gateway、Observer。
6. [源码分析](06-source-analysis) — 官方 Python/TypeScript SDK、参考 Servers、Claude Code / Claude Desktop、OpenAI Agents SDK MCP 支持。
7. [工程实践](07-mini-demo) — 纯 Python 可运行的 MCP Client-Server Demo。
8. [企业生产实践](08-production-practice) — Server 注册中心、Transport 选型、认证授权、网关、限流、多租户、版本兼容、审计与可观测。
9. [最佳实践](09-best-practices) — Tool/Resource/Prompt 设计、Capability 声明、错误处理、Tracing、测试策略。
10. [面试题](10-interview-questions) — 初/中/高级面试题。
11. [延伸阅读](11-further-reading) — 官方 Spec、SDK、参考 Servers、集成文档与学习路径。

## 一句话总结

MCP 不是又一个工具调用框架，而是**把“每个 Agent 都要手写一遍工具集成”变成“一次实现、到处复用”的开放协议层**；它让 Server 只关心能力实现，让 Client 只关心按需调用，让 Host 做最终决策与安全控制。

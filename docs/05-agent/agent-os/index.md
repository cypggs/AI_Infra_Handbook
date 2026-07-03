# Agent OS 总览

> 一句话理解：**Agent OS 是位于 Agent Runtime、Memory、Planning、Tool Use、MCP 与 Multi-Agent 之上的“操作系统层”**，负责把 Agent 当作可调度、可隔离、可治理、可观测的进程来管理。

如果说 Agent Runtime 解决了“单个 Agent 如何跑起来”，那么 Agent OS 解决的是“成百上千个 Agent 如何在同一套基础设施上安全、高效、可审计地跑起来”。它借鉴传统操作系统的进程、调度、文件系统、IPC、权限、审计等概念，为 Agent 提供生命周期、资源隔离、能力注册、消息通信与治理框架。

## 学习目标

阅读完本主题后，你应该能够：

1. 解释为什么 Agent 需要 OS 层，而不仅仅是 Runtime 或编排框架。
2. 说明 Agent OS 与 Agent Runtime、Memory、Planning、Tool Use、MCP、Multi-Agent 的边界与协作关系。
3. 画出 Agent OS 的分层架构，并说明 Process Manager、Scheduler、Sandbox、Capability Manager、Workspace、Registry、Message Bus、Policy Engine、Observer 等核心模块的职责。
4. 描述 Agent 从 spawn、schedule、execute、observe、checkpoint/rollback 到 terminate 的完整生命周期。
5. 对比 AIOS、Agent libOS、Quine、AgentRM、HiveMind、MCP Host、OpenAI Agents SDK Runner 等代表性实现的设计取舍。
6. 理解 Mini Demo 的设计意图、目录结构与运行方式，识别其与生产系统的关键差距。
7. 回答生产环境中关于多租户隔离、沙箱策略、调度策略、可观测、成本核算、升级与恢复的面试问题。

## Agent OS 与其他主题的关系

| 主题 | 解决的核心问题 | 与 Agent OS 的关系 |
|---|---|---|
| [Agent Runtime](/05-agent/agent-runtime/) | 单个 Agent 如何执行 ReAct 循环、调用工具、管理状态 | Agent OS 把 Runtime 作为“用户态进程”来调度与隔离，Runtime 只关心单任务执行，OS 关心多任务与资源 |
| [Memory](/05-agent/memory/) | 长期/短期记忆的存储、检索与向量化 | Agent OS 提供 per-agent 的 working memory 与共享 blackboard，Memory 主题负责具体存储引擎与检索算法 |
| [Planning](/05-agent/planning/) | 任务分解、计划生成与动态重规划 | Agent OS 为 Planner 提供计划执行所需的调度、checkpoint 与恢复能力；Planning 决定“做什么”，OS 负责“怎么调度执行” |
| [Tool Use](/05-agent/tool-use/) | 单次工具调用的定义、解析、校验与执行 | Agent OS 通过 Capability Manager 管理允许使用的工具集合，Tool Use 负责单次调用的正确性 |
| [MCP](/05-agent/mcp/) | 模型上下文协议，Host/Client/Server 之间的能力发现 | MCP Host 是 Agent OS 的“系统调用门面”；OS 负责 Host 层面的能力协商、权限审计与生命周期治理 |
| [Multi-Agent](/05-agent/multi-agent/) | 多 Agent 协作、角色定义与团队协调 | Agent OS 提供 Agent 间 IPC、命名空间与隔离；Multi-Agent 在其之上实现协作协议与团队语义 |
| [Reflection](/05-agent/reflection/) | Agent 自我反思、评估与改进 | Reflection 产生的新策略/约束会写入 Agent OS 的 Policy Engine，影响后续调度与权限决策 |
| RAG | /06-rag/ | Agent OS 为 RAG 检索任务提供进程隔离与资源调度。 |

## 本章结构

1. [背景](01-background) — 从单 Agent 脚本到多 Agent 生产系统，为什么需要 Agent OS。
2. [核心思想](02-core-ideas) — Agent as process、生命周期、调度、沙箱、能力、工作区、注册表、消息、HITL、恢复。
3. [架构设计](03-architecture) — 分层架构、控制面/数据面、与相邻主题的边界。
4. [Agent OS 工作流程](04-agent-os-workflow) — 从 spawn 到 terminate 的完整生命周期。
5. [核心模块](05-core-modules) — Process Manager、Scheduler、Sandbox、Capability Manager、Workspace/Store、Registry、Message Bus、Policy Engine、Observer、Recovery/Human Gate。
6. [源码分析](06-source-analysis) — AIOS、Agent libOS、Quine、AgentRM/HiveMind、MCP Host、OpenAI Agents SDK Runner、AutoGen Runtime、开源 AgentOS 项目对比。
7. [工程实践：Mini Demo](07-mini-demo) — Mini Demo 的设计、目录、运行方式与生产差异。
8. [企业生产实践](08-production-practice) — 部署拓扑、多租户、沙箱、调度、可观测、安全、成本、升级、恢复。
9. [最佳实践](09-best-practices) — 清单与反模式。
10. [面试题](10-interview-questions) — 初级/中级/高级面试题。
11. [延伸阅读](11-further-reading) — 论文、规范、博客与学习路径。

## 一句话总结

Agent OS 不是又一个 Agent 框架，而是**让 Agent 从“可运行”走向“可治理、可扩展、可共享”的基础设施层**；它用操作系统的抽象（进程、调度、沙箱、文件系统、IPC、权限、审计）把多 Agent 生产系统的复杂度纳入可控范围。

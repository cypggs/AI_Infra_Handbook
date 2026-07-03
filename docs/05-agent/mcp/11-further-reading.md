# 11. 延伸阅读

> 一句话理解：MCP 的官方 Spec、SDK、参考 Servers、主流 Host 集成文档与对比文章，是持续深入的最佳起点。

## 官方文档

- [Model Context Protocol Specification](https://modelcontextprotocol.io/specification/2025-06-18)
  - 权威协议文档，覆盖架构、生命周期、消息格式、Primitives、Transport、错误码。
- [Introduction to MCP](https://modelcontextprotocol.io/introduction)
  - Anthropic 官方的 MCP 介绍，适合快速建立整体认知。
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
  - 官方 Python SDK 源码与 README。
- [MCP TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk)
  - 官方 TypeScript SDK 源码与 README。
- [MCP Reference Servers](https://github.com/modelcontextprotocol/servers)
  - 官方参考 Server 集合：filesystem、fetch、sqlite、postgres、github、slack 等。

## Anthropic / Claude 生态

- [Anthropic: Model Context Protocol](https://www.anthropic.com/news/model-context-protocol)
  - Anthropic 发布 MCP 时的官方博客。
- [Anthropic Engineering: Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)
  - Anthropic 关于如何构建有效 Agent 的工程文章，其中涉及工具与协议选型。
- [Claude Code MCP Docs](https://docs.anthropic.com/en/docs/claude-code/mcp)
  - 在 Claude Code 中配置与使用 MCP Server 的指南。

## OpenAI 生态

- [OpenAI Agents SDK MCP](https://openai.github.io/openai-agents-python/mcp/)
  - OpenAI Agents SDK 中 `MCPServerStdio` 与 `MCPServerSse` 的使用文档。

## 工程文章与对比

- [从 Function Call 到 MCP → SKILLS](https://crossoverjie.top/2026/02/03/AI/MCP-Skills-intro/)
  - 中文文章，讨论 Function Calling、MCP 与 Skills 的演进关系。

## 本章节交叉引用

| 主题 | 与本主题的关系 | 链接 |
|---|---|---|
| Agent Runtime | MCP Client 通常运行在 Runtime 内 | [Agent Runtime 总览](/05-agent/agent-runtime/) |
| Memory | MCP Resource 可暴露记忆数据 | [Memory 总览](/05-agent/memory/) |
| Multi-Agent | 多 Agent 可共享同一组 MCP Server | [Multi-Agent 总览](/05-agent/multi-agent/) |
| Reflection | Reflection 可调用 MCP Tool/Resource 获取评估数据 | [Reflection 总览](/05-agent/reflection/) |

## 推荐学习路径

如果你是 MCP 初学者，建议按以下顺序阅读：

1. 先读 [MCP 总览](index) 建立整体框架。
2. 再读 [背景](01-background) 与 [核心思想](02-core-ideas)，理解为什么需要 MCP 以及它的角色模型。
3. 接着看 [架构设计](03-architecture) 与 [协议工作流程](04-protocol-workflow)，把抽象概念对应到协议消息。
4. 跟着 [工程实践](07-mini-demo) 跑一遍 Mini Demo，亲手观察 initialize、list、call 的消息流转。
5. 读到 [核心模块](05-core-modules)、[企业生产实践](08-production-practice)、[最佳实践](09-best-practices) 时，结合自己业务思考落地方式。
6. 最后通过 [源码分析](06-source-analysis) 与 [延伸阅读](11-further-reading) 深入官方实现。

## 本章小结

MCP 是一个快速发展的开放协议，官方 Spec 和 SDK 是最权威的学习资料；Anthropic 与 OpenAI 的集成文档则展示了协议在真实产品中的应用方式。结合本主题其他章节与 AI Infra Handbook 的 Agent Runtime、Memory、Multi-Agent、Reflection 等主题，可以形成完整的 Agent 基础设施知识体系。

**参考来源**

- [Model Context Protocol Specification](https://modelcontextprotocol.io/specification/2025-06-18)
- [Introduction to MCP](https://modelcontextprotocol.io/introduction)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [MCP TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk)
- [MCP Reference Servers](https://github.com/modelcontextprotocol/servers)
- [Anthropic: Model Context Protocol](https://www.anthropic.com/news/model-context-protocol)
- [Anthropic: Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)
- [Claude Code MCP Docs](https://docs.anthropic.com/en/docs/claude-code/mcp)
- [OpenAI Agents SDK MCP](https://openai.github.io/openai-agents-python/mcp/)
- [从 Function Call 到 MCP → SKILLS](https://crossoverjie.top/2026/02/03/AI/MCP-Skills-intro/)

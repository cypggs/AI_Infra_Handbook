# 11. 延伸阅读

> 一句话理解：MCP 的官方 Spec、SDK、参考 Servers、主流 Host 集成文档与对比文章，是持续深入的最佳起点。

## 官方文档

- [Model Context Protocol Specification（2026-07-28）](https://modelcontextprotocol.io/specification/2026-07-28)
  - 当前稳定版权威协议文档：无状态核心、`server/discover`、MRTR、扩展框架、授权基线。
- [Model Context Protocol Specification（2025-06-18）](https://modelcontextprotocol.io/specification/2025-06-18)
  - 2025 时代规范：握手生命周期、Primitives、Transport 细节，理解存量实现与 Mini Demo 的基础。
- [Introduction to MCP](https://modelcontextprotocol.io/introduction)
  - Anthropic 官方的 MCP 介绍，适合快速建立整体认知。
- [官方 MCP Registry](https://registry.modelcontextprotocol.io)
  - Server 发现的权威来源，以 `server.json` manifest 发布。
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
  - 官方 Python SDK；v2 迁移见 [migration.md](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/migration.md)。
- [MCP TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk)
  - 官方 TypeScript SDK，已重构到 Web Standards，可运行于 Node.js / Bun / Deno / Workers。
- [MCP Reference Servers](https://github.com/modelcontextprotocol/servers)
  - 官方参考 Server（filesystem、fetch、git、memory 等），教育性质示例。

## Anthropic / Claude 生态

- [Anthropic: Model Context Protocol](https://www.anthropic.com/news/model-context-protocol)
  - Anthropic 发布 MCP 时的官方博客。
- [Anthropic Engineering: Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)
  - Anthropic 关于如何构建有效 Agent 的工程文章，其中涉及工具与协议选型。
- [Claude Code MCP Docs](https://docs.anthropic.com/en/docs/claude-code/mcp)
  - 在 Claude Code 中配置与使用 MCP Server 的指南。

## OpenAI 生态

- [OpenAI Agents SDK MCP](https://openai.github.io/openai-agents-python/mcp/)
  - OpenAI Agents SDK 中 `MCPServerStdio` / `MCPServerStreamableHttp` 的使用文档。

## 规范解读与迁移指南

- [Cloudflare: The next generation of MCP](https://blog.cloudflare.com/mcp-v2)
  - 2026-07-28 规范最系统的第三方解读：无状态核心、MRTR、授权强化、TS SDK Web Standards 化。
- [Appwrite: What's new in the MCP 2026-07-28 specification](https://appwrite.io/blog/post/mcp-goes-stateless-in-the-2026-07-28-specification)
- [Python SDK v2 迁移指南](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/migration.md)
  - FastMCP → MCPServer 更名、统一 Client、`mcp-types` 拆包等破坏性变化。

## 治理与安全

- [Anthropic 将 MCP 捐入 Linux Foundation Agentic AI Foundation](https://shahvatsal.com/news/agentic-ai-foundation-mcp-linux-foundation-open-standard)
- [CSA: MCP Security Crisis — Systemic Design Flaws](https://labs.cloudsecurityalliance.org/research/csa-research-note-mcp-security-crisis-20260504-csa-styled/)
- [CSA: MCP Tool Poisoning — Adversarial Hijacking of AI Agent Workflows](https://labs.cloudsecurityalliance.org/research/csa-research-note-mcp-tool-poisoning-ai-agent-exfiltration-2/)
- [CSA: Agentic MCP Security Best Practices](https://labs.cloudsecurityalliance.org/agentic/agentic-mcp-security-best-practices-v1/)
- [Obsidian Security: When MCP Meets OAuth](https://www.obsidiansecurity.com/blog/when-mcp-meets-oauth-common-pitfalls-leading-to-one-click-account-takeover)
- [OX Security: MCP STDIO Command Injection Advisory](https://www.ox.security/blog/mcp-supply-chain-advisory-rce-vulnerabilities-across-the-ai-ecosystem/)

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
| Planning | Planner 通过 MCP 发现可用能力并生成调用计划 | [Planning 总览](/05-agent/planning/) |
| Tool Use | MCP 是 Tool Use 的协议化延伸，提供标准化能力发现与调用 | [Tool Use 总览](/05-agent/tool-use/) |
| Agent OS | MCP Host 是 Agent OS 中负责外部能力接入与安全控制的组件 | [Agent OS 总览](/05-agent/agent-os/) |
| RAG | /06-rag/ | Retriever 与知识库可封装为 MCP Server。 |
| AI SRE | /07-ai-sre/ | AI SRE 观测 MCP Server/Client 的调用延迟与错误。 |
| Benchmark + Evaluation | /07-ai-sre/benchmark-evaluation/ | 评测 MCP Server 的工具调用正确性、Capability 协商与端到端 Agent 表现。 |

## 推荐学习路径

如果你是 MCP 初学者，建议按以下顺序阅读：

1. 先读 [MCP 总览](index) 建立整体框架。
2. 再读 [背景](01-background) 与 [核心思想](02-core-ideas)，理解为什么需要 MCP 以及它的角色模型。
3. 接着看 [架构设计](03-architecture) 与 [协议工作流程](04-protocol-workflow)，把抽象概念对应到协议消息。
4. 跟着 [工程实践](07-mini-demo) 跑一遍 Mini Demo，亲手观察 initialize、list、call 的消息流转。
5. 读到 [核心模块](05-core-modules)、[企业生产实践](08-production-practice)、[最佳实践](09-best-practices) 时，结合自己业务思考落地方式。
6. 最后通过 [源码分析](06-source-analysis) 与 [延伸阅读](11-further-reading) 深入官方实现。

## 本章小结

MCP 是一个快速发展的开放协议：2026-07-28 无状态规范是当前部署基线，2025 时代规范在弃用窗口内仍广泛运行。官方 Spec、SDK 与 Registry 是最权威的学习资料；Cloudflare、Appwrite 等的规范解读与 CSA、OWASP 的安全材料则是工程落地的必读补充。结合本主题其他章节与 AI Infra Handbook 的 Agent Runtime、Memory、Multi-Agent、Reflection 等主题，可以形成完整的 Agent 基础设施知识体系。

**参考来源**

- [Model Context Protocol Specification（2026-07-28）](https://modelcontextprotocol.io/specification/2026-07-28)
- [Introduction to MCP](https://modelcontextprotocol.io/introduction)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [MCP TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk)
- [MCP Reference Servers](https://github.com/modelcontextprotocol/servers)
- [Anthropic: Model Context Protocol](https://www.anthropic.com/news/model-context-protocol)
- [Anthropic: Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)
- [Claude Code MCP Docs](https://docs.anthropic.com/en/docs/claude-code/mcp)
- [OpenAI Agents SDK MCP](https://openai.github.io/openai-agents-python/mcp/)
- [Cloudflare: The next generation of MCP](https://blog.cloudflare.com/mcp-v2)
- [从 Function Call 到 MCP → SKILLS](https://crossoverjie.top/2026/02/03/AI/MCP-Skills-intro/)

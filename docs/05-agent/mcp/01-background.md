# 1. 背景

> 一句话理解：**从“每个 Agent 手写工具调用”到“标准化协议”**，MCP 解决了工具发现、跨模型复用与供应商锁定问题。

## 为什么需要 MCP？

大模型应用的发展大致经历了三个阶段：

```text
Prompt Engineering → RAG → Agent → Agent Ecosystem
```

- **Prompt Engineering**：模型只负责生成文本。
- **RAG**：模型基于检索结果回答。
- **Agent**：模型自主调用工具、分解任务、多轮迭代。
- **Agent Ecosystem**：大量 Agent、工具、数据源需要互操作。

当进入 Agent Ecosystem 阶段后，每个 Agent 都手写工具集成，会带来几个问题：

1. **重复集成**：每个 Agent 都要为同一个数据库/API/文件系统写一遍封装。
2. **发现困难**：Agent 不知道当前环境有哪些可用工具，只能硬编码。
3. **跨模型复用差**：OpenAI 的 function schema、Claude 的 tool use、Gemini 的 function calling 格式略有不同。
4. **供应商锁定**：工具实现与某个框架或模型供应商深度绑定，迁移成本高。
5. **权限与审计分散**：每个 Agent 自己管认证、限流、日志，安全策略难以统一。

MCP 想要做的，就是给这些外部能力定义一个统一的“接口形状”，让能力提供方（Server）和能力消费方（Client/Host）解耦。

## 从 Function Calling 到 MCP

```mermaid
flowchart LR
    A[Function Calling] --> B[MCP]
    B --> C[Skills]
```

- **Function Calling**：模型直接输出 JSON 调用请求，由应用层解析执行。最灵活，但发现、注册、复用都靠手写。
- **MCP**：在 Function Calling 之上增加标准化的发现、协商、调用、通知协议，Server 可以独立进程/服务运行。
- **Skills**：更工程化的能力封装，把 auth、telemetry、sandbox 打包，可直接在 Runtime 内复用。可以看作 MCP 在 Runtime 内的“轻量本地化”形态。

MCP 没有替代 Function Calling，而是把 Function Calling 的发现与调用过程标准化。

## MCP 与相关概念的区别

| 概念 | 核心问题 | 与 MCP 的关系 |
|---|---|---|
| **REST / OpenAPI** | 人类/程序如何调用 HTTP API | MCP Server 内部可以用 REST 实现，但 MCP 关注“模型视角”的能力发现与调用 |
| **A2A（Agent-to-Agent）** | Agent 之间如何协作通信 | A2A 解决多 Agent 协作，MCP 解决 Agent 与外部能力连接；两者互补。2026 年起两者同归 Linux Foundation AAIF 治理：A2A v1.0（2026-03）已合并 IBM 的 ACP，与 MCP 构成“垂直工具连接 + 水平 Agent 协作”的协议栈 |
| **Skills** | Runtime 内如何封装能力单元 | Skills 可在 Runtime 内原生运行，MCP 强调跨进程/跨服务的协议互操作 |
| **Function Calling** | 模型如何表达工具调用 | MCP 复用 function calling 的 JSON schema 思想，并扩展了发现与生命周期 |
| **LLM Gateway** | 多模型统一接入 | Gateway 在模型侧，MCP 在工具/资源侧，两者可在 Agent 架构中并存 |
| **Agent Runtime** | Agent 如何执行 | Runtime 可通过 MCP Client 接入 Server，也可直接 function calling |

> 一句话：MCP 是模型视角的“能力 USB-C”，不是替代 REST 或 Function Calling，而是让它们对模型更可发现、可复用。

## MCP 解决的关键问题

1. **标准化发现**：Server 启动后通过 `tools/list`、`resources/list`、`prompts/list` 告诉 Client 自己能做什么。
2. **动态协商**：Client 与 Server 在 `initialize` 阶段交换 capability，双方只启用都支持的能力。
3. **解耦实现**：Server 可以是本地 Python 脚本、Docker 容器、远程 HTTP 服务，Client 不感知实现细节。
4. **跨 Host 复用**：同一个 Server 可以被 Claude Desktop、Cursor、Cline、OpenAI Agents SDK 同时使用。
5. **安全集中**：Host 掌握最终决策权，决定哪些 Server 能运行、哪些 Tool 能调用、哪些 Resource 能读取。

## 主流生态

| 产品/项目 | MCP 角色 | 说明 |
|---|---|---|
| **Claude Desktop / Claude Code** | Host | 官方 Host，支持通过配置文件添加 MCP Server |
| **Cursor** | Host | IDE 内置 MCP，可直接调用文件、数据库、搜索等 Server |
| **Cline** | Host | VS Code 插件，支持 MCP Server 扩展 |
| **OpenAI Agents SDK** | Client/Host | 通过 `MCPServerStdio` / `MCPServerStreamableHttp` 接入 MCP Server（`MCPServerSse` 仅限旧版 Server） |
| **registry.modelcontextprotocol.io** | Registry | 官方 Server Registry，2025-09 预览上线，2026 年成为 Server 发现的权威来源，API 保持 v0.1 口径持续收录 |
| **modelcontextprotocol/servers** | Server 集合 | 官方参考 Server：filesystem、fetch、git、memory 等（完整目录已迁至官方 Registry） |
| **python-sdk / typescript-sdk** | SDK | 官方提供的 Server/Client 开发包；2026-07-28 起进入 v2 时代（Python `mcp` 2.x，2026-10 最新 2.3.0；TS SDK 1.30+ 重构到 Web Standards，最新 1.32.1） |
| **ToolHive（Stacklok）** | 运行平台/网关 | 开源（Apache-2.0）一体化 MCP 平台：容器隔离运行任意 Server，内置 Gateway、可自托管 Registry Server 与 K8s Operator，2026-10 已迭代至 v0.54 |

```mermaid
flowchart LR
    H1[Claude Desktop] -->|stdio/HTTP| S1[MCP Server: filesystem]
    H2[Cursor] -->|stdio/HTTP| S2[MCP Server: fetch]
    H3[OpenAI Agents SDK] -->|stdio/HTTP| S3[MCP Server: sqlite]
    S1 --> FS[本地文件系统]
    S2 --> WEB[网络请求]
    S3 --> DB[SQLite 数据库]
```

## 为什么现在 MCP 变得重要？

1. **Agent 数量爆炸**：每个业务线都在做 Agent，工具集成不能重复造轮子。
2. **模型供应商多样化**：企业同时使用 Claude、OpenAI、Gemini、自研模型，需要跨模型复用工具。
3. **安全与治理需求**：工具调用涉及数据访问、代码执行、外部 API，需要统一的认证、审计、审批。
4. **生态成熟度**：Anthropic 开源 MCP 后，官方 SDK、参考 Server、主流 IDE 快速跟进，生态已经越过“概念验证”阶段。
5. **治理中立化**：2025 年 12 月，Anthropic 把 MCP 捐入 Linux Foundation 下的 **Agentic AI Foundation（AAIF）**（由 Anthropic、Block、OpenAI 联合发起，Google、Microsoft、AWS、Cloudflare、Bloomberg 等参与），MCP 从“某家公司的协议”变成社区治理的开放标准。2026 年 8 月，Google 的 A2A 协议也正式加入 AAIF，MCP 与 A2A 在同一治理框架下分工互补。
6. **协议进入无状态时代**：2026-07-28 规范是 MCP 发布以来最大的一次修订——核心协议彻底无状态化，远程 Server 可以跑在普通负载均衡器或无服务器运行时后面，企业级部署成本大幅下降。

## 生态规模（截至 2026 年 10 月）

- 捐入 AAIF 时，MCP SDK 月下载量已超 **9700 万**，活跃 Server 约 **1 万**；独立普查在各类 Registry 中索引到的 Server 总数超 **1.7 万**。
- **官方 MCP Registry**（`registry.modelcontextprotocol.io`）于 2025 年 9 月预览上线，由 Anthropic、GitHub、Microsoft、PulseMCP 联合建设，2026 年已成为 Server 发现的权威来源；Registry API（v0.1）持续收录，2026-10 抽样分页统计条目已达 **数千个量级**，Smithery、mcp.so、Glama 等第三方目录作为补充发现层。
- 官方 `modelcontextprotocol/servers` 仓库转型为“少量参考实现”的教育仓库，完整 Server 目录已迁移到官方 Registry。
- 在“运行与治理”侧，Stacklok 开源的 **ToolHive**（Apache-2.0，2026-10 最新 v0.54.0）把容器隔离运行时、网关与可自托管私有 Registry 打包成一体化平台，成为企业自建 MCP 基础设施的主流开源起点。

## 2026-07-28 规范：一次代际升级

2025-11-25 规范仍是大量 Host 的实现基线（也是本主题 Mini Demo 的基础），但 2026-07-28 规范做了发布以来最大修订，要点如下：

| 变化 | 2025 时代 | 2026-07-28 |
|---|---|---|
| 会话模型 | `initialize` 握手 + `Mcp-Session-Id` 有状态会话 | 彻底无状态，每个请求自带协议版本/身份/能力（`_meta`） |
| 能力发现 | 握手时一次性协商 | 可选的 `server/discover` + 可缓存的 list（`ttlMs`/`cacheScope`） |
| 服务端反问 | Sampling / Roots / elicitation 走长连接 | **MRTR**（多轮往返请求）：返回 `input_required` + `requestState`，客户端补齐后重试 |
| 路由 | 网关必须解析 JSON body 才能路由 | 强制 `Mcp-Method` / `Mcp-Name` / `MCP-Protocol-Version` 头 |
| 传输 | stdio / SSE / Streamable HTTP | SSE 早已弃用（2025-03-26 起标记），Streamable HTTP 成为远程标准 |
| 废弃项 | — | Roots、Sampling、Logging、DCR 进入 12 个月弃用期（最早 2027-07-28 之后移除）；`ping`、`logging/setLevel` 直接移除 |
| 事件推送 | `resources/subscribe` + HTTP GET 事件端点 | `subscriptions/listen` 单条长连接 POST 流，Client 按需订阅变更类型 |
| 扩展 | 新能力直接进核心协议 | 正式扩展框架（反向 DNS 命名、独立版本），官方扩展已包括 MCP Apps、Tasks、OAuth Client Credentials、企业托管授权与 Skills over MCP |

> 本节后续章节会同时讲清“2025 时代协议”（理解存量实现与 Mini Demo 的基础）与“2026-07-28 无状态协议”（面向未来的部署基线）两条线。

## 本章小结

MCP 的产生是 Agent 生态演进的必然结果：当外部能力（文件、数据库、API、提示模板）越来越多、Agent 越来越普及时，就必须有一个开放协议来统一能力的声明、发现与调用。它不是替代 Function Calling 或 REST，而是站在模型视角，把“每个 Agent 自己写工具集成”变成“一次实现、到处复用”。

**参考来源**

- [Model Context Protocol Specification（2026-07-28）](https://modelcontextprotocol.io/specification/2026-07-28)
- [MCP 2026-07-28 Changelog（官方变更清单）](https://modelcontextprotocol.io/specification/2026-07-28/changelog)
- [MCP Deprecated Features（官方弃用登记表）](https://modelcontextprotocol.io/specification/2026-07-28/deprecated)
- [MCP Extensions Overview（官方扩展清单）](https://modelcontextprotocol.io/extensions/overview)
- [Introduction to MCP](https://modelcontextprotocol.io/introduction)
- [Anthropic: Model Context Protocol](https://www.anthropic.com/news/model-context-protocol)
- [Claude Code MCP Docs](https://docs.anthropic.com/en/docs/claude-code/mcp)
- [OpenAI Agents SDK MCP](https://openai.github.io/openai-agents-python/mcp/)
- [Cloudflare: The next generation of MCP（2026-07-28 规范解读）](https://blog.cloudflare.com/mcp-v2)
- [Appwrite: What's new in the MCP 2026-07-28 specification](https://appwrite.io/blog/post/mcp-goes-stateless-in-the-2026-07-28-specification)
- [Anthropic 将 MCP 捐入 Linux Foundation Agentic AI Foundation](https://shahvatsal.com/news/agentic-ai-foundation-mcp-linux-foundation-open-standard)
- [从 Function Call 到 MCP → SKILLS](https://crossoverjie.top/2026/02/03/AI/MCP-Skills-intro/)
- [Building Effective Agents — Anthropic Engineering](https://www.anthropic.com/engineering/building-effective-agents)

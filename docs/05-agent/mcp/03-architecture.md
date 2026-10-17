# 3. 架构设计

> 一句话理解：典型 MCP 架构分为 Host 应用层、Client 连接层、Transport 层、Protocol 层、Server 能力层五层。

> 版本说明：本章架构图以 2025 时代协议为参考实现；第 6 节补充 2026-07-28 无状态规范带来的架构变化。

## 1. 五层架构

```mermaid
flowchart TB
    subgraph HostLayer["Host 应用层"]
        UI[用户界面 / Agent Runtime]
        PM[权限与审批 Policy Manager]
        TM[Trace / Metrics / Logs]
    end

    subgraph ClientLayer["Client 连接层"]
        CM[Connection Manager]
        SM[Session Manager]
        CapM[Capability Manager]
    end

    subgraph TransportLayer["Transport 层"]
        Stdio[stdio Adapter]
        HTTP[Streamable HTTP Adapter]
        SSE[SSE Adapter（2025 时代，已弃用）]
    end

    subgraph ProtocolLayer["Protocol 层"]
        JSONRPC[JSON-RPC 2.0]
        Router[Message Router]
        Handler[Request/Notification Handler]
    end

    subgraph ServerLayer["Server 能力层"]
        Registry[Tools/Resources/Prompts Registry]
        Exec[Tool Executor]
        Res[Resource Provider]
        Prompt[Prompt Template]
    end

    UI -->|发起调用| CM
    PM -->|审批| CM
    TM -->|记录| CM
    CM -->|选择 transport| Stdio
    CM -->|选择 transport| SSE
    CM -->|选择 transport| HTTP
    Stdio -->|字节流| JSONRPC
    SSE -->|字节流| JSONRPC
    HTTP -->|字节流| JSONRPC
    JSONRPC -->|解析消息| Router
    Router -->|分发| Handler
    Handler -->|调用| Registry
    Registry -->|执行| Exec
    Registry -->|读取| Res
    Registry -->|渲染| Prompt
```

各层职责：

| 层级 | 职责 | 关键组件 |
|---|---|---|
| **Host 应用层** | 用户交互、权限审批、最终决策、可观测 | UI、Policy Manager、Observer |
| **Client 连接层** | 创建/维护与 Server 的连接，管理会话状态 | Connection Manager、Session Manager、Capability Manager |
| **Transport 层** | 把 JSON-RPC 消息映射到具体传输通道 | stdio / Streamable HTTP Adapter（SSE 为 2025 时代遗留） |
| **Protocol 层** | JSON-RPC 编解码、消息路由、请求/通知分发 | JSON-RPC、Router、Handler |
| **Server 能力层** | 实现 Tools、Resources、Prompts、Sampling 等能力 | Registry、Executor、Provider |

## 2. 控制面与数据面

MCP 架构可以进一步拆分为控制面和数据面：

```mermaid
flowchart LR
    subgraph Control["控制面"]
        Init[initialize / initialized]
        Cap[Capability 协商]
        List[tools/list / resources/list / prompts/list]
        Notify[Notification 订阅与推送]
        Close[notifications/closed]
    end

    subgraph Data["数据面"]
        Call[tools/call]
        Read[resources/read]
        Get[prompts/get]
        Sample[sampling/createMessage]
    end

    Control -->|先协商| Data
```

- **控制面**：负责连接建立、能力发现、变更通知、生命周期管理。消息量小、频率低、必须可靠。
- **数据面**：负责实际能力调用与数据流动。消息量大、可能包含大文本/二进制、需要流控与超时。

> **2026-07-28 变化**：控制面被大幅简化——`initialize`/`initialized` 握手与 `Mcp-Session-Id` 会话被移除，能力发现收敛为可选的 `server/discover` 与可缓存的 list（`ttlMs`/`cacheScope`）；控制面与数据面共享同一条无状态 HTTP 通道，网关上靠 `Mcp-Method` / `Mcp-Name` 头区分。

生产建议：

- 控制面与数据面可以使用同一条 Transport，但在网关/代理层应分别设限。
- 数据面的大资源传输应考虑分片、压缩、流式返回。
- 控制面的 capability 变更应触发 Client 重新发现。

## 3. 本地 stdio 部署形态

stdio 是最常见的 MCP 部署方式，特别适合本地工具：

```mermaid
sequenceDiagram
    participant H as Host
    participant C as Client
    participant S as MCP Server 子进程
    participant FS as 本地文件系统

    H->>C: 启动 Server 子进程
    C->>S: fork + exec
    C->>S: initialize
    S-->>C: initialized
    C->>S: tools/list
    S-->>C: tools
    H->>C: tools/call: read_file
    C->>S: tools/call
    S->>FS: read
    FS-->>S: content
    S-->>C: result
    C-->>H: result
    H->>C: 关闭连接
    C->>S: notifications/closed
```

特点：

- **进程隔离**：Server 作为独立进程运行，崩溃不影响 Host。
- **简单部署**：无需网络配置，适合本地文件、数据库、脚本工具。
- **权限依赖 OS**：Server 继承启动用户的权限，需要 Host 控制启动参数与环境。

## 4. 远程 Streamable HTTP 部署形态

远程部署适合共享服务、多 Host 复用：

```mermaid
flowchart LR
    H1[Claude Desktop] -->|Streamable HTTP| GW[MCP Gateway]
    H2[Cursor] -->|Streamable HTTP| GW
    H3[OpenAI Agents SDK] -->|HTTP| GW
    GW -->|负载均衡| S1[Server A]
    GW -->|负载均衡| S2[Server B]
    S1 -->|读取| DB[(Postgres)]
    S2 -->|调用| API[内部 API]
```

特点：

- **共享能力**：多个 Host 可以复用同一组 Server。
- **集中治理**：网关层统一做认证、限流、审计、路由。
- **网络开销**：相比 stdio，远程调用有延迟与序列化成本。
- **安全边界**：Server 与 Host 不在同一机器，需要 TLS、OAuth/API Key 等机制。

> **2026-07-28 变化**：远程部署的标准形态是**单个 `/mcp` 端点的 Streamable HTTP**，旧 HTTP+SSE 双端点模式已弃用；由于协议无状态，Server 不再依赖 Redis 等会话存储，任何实例都能处理任何请求，网关也无需 sticky session，路由与粗粒度授权直接基于 `Mcp-Method` / `Mcp-Name` 头完成。2025 时代基于 SSE 的架构在弃用期（2025-03-26 起标记，最早移除时间为 SEP-2596 达到 Final 后三个月）内仍需兼容支持。

## 5. 与 Agent Runtime 集成的参考架构

Agent Runtime 可以通过 MCP Client 接入外部 Server：

```mermaid
flowchart TB
    subgraph Runtime["Agent Runtime"]
        ReAct[ReAct Loop]
        Planner[Planner]
        Mem[Memory]
        Guard[Guardrails]
        Obs[Observer]
    end

    subgraph MCPClient["MCP Client 层"]
        CM[Connection Manager]
        Discovery[Capability Discovery]
        Cache[Schema Cache]
    end

    subgraph Servers["MCP Servers"]
        S1[filesystem]
        S2[fetch]
        S3[sqlite]
        S4[自定义业务 Server]
    end

    ReAct -->|发现工具| Discovery
    Planner -->|读取资源| Discovery
    Discovery -->|tools/list| S1
    Discovery -->|resources/list| S2
    ReAct -->|tools/call| CM
    CM -->|JSON-RPC| S1
    CM -->|JSON-RPC| S2
    CM -->|JSON-RPC| S3
    CM -->|JSON-RPC| S4
    Guard -->|审批| ReAct
    Obs -->|记录| CM
```

集成要点：

- **Schema 缓存**：发现阶段把 Tool/Resource/Prompt schema 缓存起来，避免每次调用都重新 list。
- **权限前置**：Runtime 的 Guardrails 在调用前检查 Tool 权限与参数白名单。
- **错误回传**：Tool 执行失败的信息作为 observation 回传给模型，让模型决定重试或放弃。
- **观测打通**：MCP Client 层把请求/响应、 capability 变更、连接事件汇入 Runtime 的 trace。

## 6. 2026-07-28：无状态架构与扩展框架

2026-07-28 规范对五层架构的核心改变集中在 Client 连接层与 Protocol 层：

```mermaid
flowchart TB
    subgraph HostLayer["Host 应用层"]
        UI[用户界面 / Agent Runtime]
        PM[权限与审批 Policy Manager]
    end

    subgraph ClientLayer["Client 连接层（简化）"]
        Cache[Schema 缓存（ttlMs / cacheScope）]
        MRTR[MRTR 状态机：requestState 管理]
    end

    subgraph TransportLayer["Transport 层"]
        Stdio[stdio Adapter]
        HTTP[Streamable HTTP Adapter<br/>Mcp-Method / Mcp-Name 头]
    end

    subgraph ServerLayer["Server 能力层（无状态）"]
        Registry[Tools/Resources/Prompts Registry]
        Ext[Extensions：Apps / Tasks / 企业托管授权]
    end

    UI --> Cache
    UI --> MRTR
    Cache --> Stdio
    Cache --> HTTP
    Stdio --> Registry
    HTTP --> Registry
    Registry --> Ext
```

三个结构性变化：

1. **Session Manager 消失**：没有握手、没有会话 ID，Client 连接层退化为“请求构造 + 缓存 + MRTR 状态跟踪”。请求的所有上下文（协议版本、身份、能力）都放在 `_meta` 里随请求走。
2. **网关角色变重**：`Mcp-Method` / `Mcp-Name` 头让网关在不解析 body 的情况下完成路由、限流、粗粒度授权；缓存提示（`ttlMs`/`cacheScope`）让网关可以缓存能力目录，显著降低 `tools/list` 风暴。
3. **扩展成为一等公民**：新能力不再塞进核心协议，而是通过正式扩展框架发布——反向 DNS 命名（如 `io.modelcontextprotocol/tasks`）、独立版本号、在 capabilities 的 `extensions` 字段中双向声明（双方都声明才启用）。截至 2026-10，官方扩展清单包括 **MCP Apps**（`io.modelcontextprotocol/ui`，在对话内渲染交互式 UI，Claude Desktop、VS Code Copilot、Cursor 等已支持）、**Tasks**（异步任务，从实验性核心协议迁出，改为 `tasks/get` 轮询 + `tasks/update` 补充输入）、**OAuth Client Credentials**（机器对机器认证）、**企业托管授权**（Enterprise-Managed Authorization，经企业 IdP 集中授权），以及 2026 年下半年新加入的 **Skills over MCP**（`io.modelcontextprotocol/skills`，经 MCP 发现与读取 Agent Skills，ChatGPT 已部分支持）；另有一批 `experimental-ext-*` 实验扩展在孵化。

迁移形态上，官方 SDK 支持“一个 Server 同时服务两代客户端”：同一个 `/mcp` 端点既接待 2025 时代（握手 + 会话）客户端，也接待 2026-07-28 无状态客户端，由 SDK 自动区分处理。

## 本章小结

MCP 架构通过五层分层（Host/Client/Transport/Protocol/Server）把复杂的协议交互拆成可替换、可扩展的模块；通过控制面与数据面的分离，把能力协商与实际调用分开治理；通过 stdio 与 Streamable HTTP 两种部署形态，覆盖本地隔离与远程共享两种场景（SSE 为 2025 时代遗留，已弃用）。与 Agent Runtime 集成时，MCP Client 层承担发现、缓存、调用、观测的职责，让 Runtime 专注于 ReAct 循环与策略控制。2026-07-28 规范进一步把会话状态从架构中拿掉，让 MCP Server 真正云原生化。

**参考来源**

- [MCP Specification: Architecture（2026-07-28）](https://modelcontextprotocol.io/specification/2026-07-28/architecture)
- [MCP Specification: Transports（2025-06-18）](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)
- [Cloudflare: The next generation of MCP](https://blog.cloudflare.com/mcp-v2)
- [Anthropic: Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)
- [从 Function Call 到 MCP → SKILLS](https://crossoverjie.top/2026/02/03/AI/MCP-Skills-intro/)

# 6. 源码分析

> 一句话理解：拆解官方 Python/TypeScript SDK、参考 Servers、Claude Code / Claude Desktop 集成、OpenAI Agents SDK MCP 支持，可以帮助我们理解协议落地时的工程取舍。

> 版本说明：2026-07-28 规范发布同日，官方 SDK 进入 v2 时代（Python `mcp` 2.x，从 1.29 直接跳号；TypeScript SDK 重构到 Web Standards）。本节先讲 v1 经典结构（存量代码与 Mini Demo 的基础），再讲 v2 的关键变化。

## 1. 官方 Python SDK

[MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) 是 Anthropic 官方维护的 Python 实现，包名为 `mcp`。

### 包结构

```text
mcp/
├── server/
│   ├── __init__.py
│   ├── server.py          # Server 主类与生命周期
│   ├── session.py         # ServerSession
│   ├── tools.py           # @tool 装饰器、schema 生成
│   ├── resources.py       # Resource 注册与读取
│   ├── prompts.py         # Prompt 注册与渲染
│   ├── sampling.py        # Sampling 处理
│   └── stdio.py           # stdio Server 启动
├── client/
│   ├── __init__.py
│   ├── client.py          # Client 主类
│   ├── session.py         # ClientSession
│   └── stdio.py           # stdio Client 启动
├── shared/
│   ├── __init__.py
│   ├── session.py         # 共享会话逻辑
│   ├── memory.py          # 内存消息队列
│   └── version.py         # 协议版本
├── types.py               # 协议类型定义
└── transport/
    ├── stdio.py           # stdio Transport
    ├── sse.py             # SSE Transport
    └── streamable_http.py # Streamable HTTP Transport
```

### Server 入口

```python
from mcp.server import Server
from mcp.server.stdio import stdio_server

server = Server("my-server")

@server.tool()
async def read_file(path: str) -> str:
    with open(path) as f:
        return f.read()

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
```

### Client 入口

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

params = StdioServerParameters(command="python", args=["server.py"])
async with stdio_client(params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        result = await session.call_tool("read_file", {"path": "README.md"})
```

工程取舍：

- Python SDK 用装饰器把函数注册为 Tool/Resource/Prompt，schema 由类型注解自动生成。
- `Server.run` 内部处理 initialize 握手与消息循环，开发者只需关心业务 Handler。
- stdio transport 用 `anyio` 处理异步 I/O，天然支持协程并发。

### v2 时代的变化（mcp 2.0，2026-07-28 发布）

2026-07-28 规范发布同日，`mcp` Python SDK 的 **2.0.0 stable** 上线（`pip install mcp` 默认安装 2.x）；官方承诺 v2 支持 2026-07-28 修订版并**从同一个 Server 服务所有更早修订版**。v1 维护线以 **1.30.0（2026-09-07）** 收官，之后仅接收安全修复。关键变化：

- **`FastMCP` 更名为 `MCPServer`**，模块从 `mcp.server.fastmcp` 移到 `mcp.server.mcpserver`——旧导入路径直接报 `ModuleNotFoundError` 并提示迁移指南（不是软弃用）。注意第三方 `fastmcp` 包（jlowin 维护）不受影响，仍导出 `FastMCP`。
- **一等公民 `Client`** 取代 v1 的“transport + `ClientSession` + `initialize()`”分层，直接连接 URL、stdio 子进程，或内存中的 Server 对象（`Client(mcp)`，测试极方便）：

```python
from mcp.server.mcpserver import MCPServer

mcp = MCPServer("my-server")

@mcp.tool()
async def read_file(path: str) -> str:
    with open(path) as f:
        return f.read()

# 内存直连测试：没有进程、没有网络
from mcp import Client
async with Client(mcp) as client:
    tools = await client.list_tools()
```

- **协议类型独立成 `mcp-types` 包**（`import mcp_types`），Python 侧字段统一 snake_case（`input_schema`、`is_error`），线上 JSON 仍是 camelCase。
- **一个 Server 同时服务两代客户端**：`MCPServer` 自动区分 2025 时代握手客户端与 2026 无状态客户端，迁移期不需要拆端点。
- **MRTR 与 `Resolve` 依赖注入**：Server 不能再反向调用 Client，需要用户输入时在 Tool 参数里声明 `Resolve(fn)`，由 SDK 填充；`ctx.elicit()` 不再可用。

v2 的迭代节奏（截至 2026-10-02 的 **2.3.0**）也体现了“默认安全”的方向：

- **2.1.0（2026-08-24）**：`Client` 直接接受 `StdioServerParameters`，`Client(StdioServerParameters(command="uv", args=[...]))` 一步连接 stdio Server。
- **2.2.0（2026-09-07）**：HTTP 客户端**只在同源（同 scheme/host/port）内跟随重定向**，跨源重定向直接失败——堵 open-redirect 一类漏洞；4 MiB 请求体上限扩展到 SSE 传输与 OAuth 端点。
- **2.3.0（2026-10-02）**：带非法 `x-mcp-header` 注解的工具在**注册时**直接抛 `InvalidSignature`，而不是启动后才报错；依赖 `httpx2>=2.10.0`。

## 2. 官方 TypeScript SDK

[MCP TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk) 提供 Node.js 与浏览器环境支持。

### 包结构

```text
src/
├── server/
│   ├── index.ts           # Server 主类
│   ├── mcp.ts             # McpServer 高阶封装
│   ├── stdio.ts           # stdio Server
│   └── sse.ts             # SSE Server
├── client/
│   ├── index.ts           # Client 主类
│   ├── stdio.ts           # stdio Client
│   └── sse.ts             # SSE Client
├── shared/
│   ├── protocol.ts        # 共享协议处理
│   └── transport.ts       # Transport 抽象
└── types.ts               # 协议类型
```

### Server 入口

```typescript
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

const server = new Server({ name: "my-server", version: "1.0.0" }, {
  capabilities: { tools: {} },
});

server.setRequestHandler("tools/list", async () => ({
  tools: [{ name: "read_file", description: "...", inputSchema: { ... } }],
}));

server.setRequestHandler("tools/call", async (request) => {
  // 执行业务逻辑
});

const transport = new StdioServerTransport();
await server.connect(transport);
```

工程取舍：

- TypeScript SDK 更接近协议原语，需要手动设置 request handler。
- 提供了 `McpServer` 高阶封装，可以用 `.tool()` / `.resource()` / `.prompt()` 方法简化注册。
- Transport 抽象清晰，`server.connect(transport)` 即可切换 stdio/SSE/HTTP。

**2026 年的变化**：TypeScript SDK 已从 Node.js API 重构到 **Web Standards**（Fetch、Web Streams），同一套代码可运行于 Node.js、Bun、Deno 与 Cloudflare Workers 等边缘运行时——这正是无状态 MCP Server 可以跑在任意边缘平台上的前提。新版提供 `createMcpHandler`，一个函数即产出符合 2026-07-28 规范的 HTTP 处理器。版本上，**1.30.0（2026-07-27，规范发布前夕）** 开启新线，截至 2026-10 最新为 **1.32.1（2026-10-05）**——注意 TS SDK 没有跟随 Python 跳大版本号，1.30+ 即“v2 架构”。

## 3. 官方参考 Servers 与 Registry

2025–2026 年，官方对 Server 分发作了一次大调整：

- `modelcontextprotocol/servers` 仓库**转型为教育性质的参考实现仓库**，只保留 Everything、Fetch、Filesystem、Git、Memory、Sequential Thinking、Time 等少量参考 Server，README 明确声明这些是“演示协议特性与 SDK 用法”的示例，不是生产就绪方案。
- 原来的 github、slack、postgres、sqlite、google-drive 等 Server 被移入 `servers-archived` 仓库或由厂商接管（如 Slack 官方版由 Zencoder 维护）。
- **完整 Server 目录迁移到官方 MCP Registry**（`registry.modelcontextprotocol.io`，以 `server.json` manifest 发布），第三方目录（Smithery、mcp.so、Glama）作为补充发现层。

现存的官方参考 Server 与学习价值：

| Server | 能力 | 学习价值 |
|---|---|---|
| **filesystem** | 读/写本地文件 | Tool + Resource 结合，URI 设计，路径白名单 |
| **fetch** | 发起 HTTP 请求 | 网络 Tool，参数校验，错误处理 |
| **git** | 本地 Git 操作 | 子进程封装，输出解析 |
| **memory** | 知识图谱式记忆 | Resource + 图数据建模 |
| **sequentialthinking** | 分步推理工具 | 渐进式结构化输出 |
| **everything** | 协议特性全集 | 各原语与通知的完整示范 |

以 filesystem Server 为例：

- 启动时读取 `--allowed-dir` 参数，限定可访问路径。
- 提供 `read_file`、`write_file`、`list_directory` 等 Tool。
- 同时把文件暴露为 Resource，URI 形如 `file:///allowed-dir/foo.md`。
- 写操作默认需要 Host 审批，体现了 MCP 的安全模型。

### 生态工程实现：ToolHive

如果说官方 SDK 解决“怎么实现一个 Server”，[ToolHive](https://github.com/stacklok/toolhive)（Stacklok 开源，Apache-2.0，2026-10 最新 v0.54.0）解决的是“怎么把一堆 Server 安全地跑进生产”。它的架构是三个组件：

- **Runtime**：每个 MCP Server 跑在隔离容器中，带最小权限声明（不需要本地凭证），本地 Server 也能获得容器级隔离——直接回应了 2026 年多起 STDIO 命令注入 CVE 的防御需求。
- **Gateway**：对外暴露受控端点，集中做认证（OIDC/OAuth 对接 IdP）、授权、审计，支持把多个工具编排成“虚拟 MCP”，并可用语义化工具搜索按需下发工具定义、压缩上下文 token。
- **Registry Server**：可自托管的私有 Registry，企业内部白名单分发 Server，终结“开发者私自接公共 Server”的影子 MCP 问题。

此外还有 Kubernetes Operator（把 Server 声明成 CRD 管理）、OTel 观测、桌面与 CLI 双入口。对平台团队而言，ToolHive 是理解“MCP 生产化需要哪些组件”的最佳开源样本。

## 4. Claude Code / Claude Desktop 集成

Claude Code 和 Claude Desktop 是官方 Host，通过配置文件加载 MCP Server。

### Claude Code 配置

Claude Code 的配置文件通常位于项目根目录或用户目录：

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/Users/case/projects"]
    },
    "fetch": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-fetch"]
    }
  }
}
```

[Claude Code MCP 文档](https://docs.anthropic.com/en/docs/claude-code/mcp)

### Claude Desktop 配置

Claude Desktop 使用 `claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "sqlite": {
      "command": "uvx",
      "args": ["mcp-server-sqlite", "--db-path", "/path/to/db.sqlite"]
    }
  }
}
```

集成特点：

- Host 负责启动 Server 子进程（stdio），管理其生命周期。
- 用户在对话中授权每次 Tool 调用，体现 Host 最终决策权。
- 支持通过 `claude` CLI 命令行工具添加/查看 MCP Server。

## 5. OpenAI Agents SDK 的 MCP 支持

[OpenAI Agents SDK](https://openai.github.io/openai-agents-python/mcp/) 从 2025 年开始支持 MCP，提供了 `MCPServerStdio`、`MCPServerStreamableHttp` 与 `MCPServerSse`（遗留）三种接入方式。

### MCPServerStdio

```python
from agents import Agent, Runner
from agents.mcp import MCPServerStdio

async with MCPServerStdio(
    name="filesystem",
    params={"command": "python", "args": ["fs_server.py"]},
) as server:
    await server.connect()
    tools = await server.list_tools()

    agent = Agent(name="assistant", tools=tools)
    result = await Runner.run(agent, "读取 README.md")
```

### MCPServerSse

```python
from agents.mcp import MCPServerSse

async with MCPServerSse(
    name="remote-server",
    url="https://mcp.example.com/sse",
) as server:
    await server.connect()
    tools = await server.list_tools()
```

> **注意**：HTTP+SSE 传输已在 2026-07-28 规范中弃用，`MCPServerSse` 只应用于连接遗留 Server；新接入远程 Server 应使用 `MCPServerStreamableHttp`。

集成特点：

- OpenAI Agents SDK 把 MCP Server 当成 Agent 的 tool 来源，自动把 `tools/list` 结果转换成 Agent 可调用的 `Tool` 对象。
- 连接生命周期由 `MCPServerStdio` / `MCPServerStreamableHttp` / `MCPServerSse` 上下文管理器封装。
- 适合把已有 MCP Server 快速接入 OpenAI Agents 生态。

## 6. SDK 对比

| 维度 | Python SDK | TypeScript SDK | OpenAI Agents SDK |
|---|---|---|---|
| 定位 | 官方 Server/Client 实现 | 官方 Server/Client 实现 | 在 Agents 框架内消费 MCP |
| 抽象层次 | 中 | 中（偏协议原语） | 高 |
| 注册方式 | 装饰器 | 装饰器或手动 handler | 通过 `MCPServer` 对象 |
| Transport | stdio / Streamable HTTP | stdio / Streamable HTTP | stdio / Streamable HTTP（SSE 仅限遗留） |
| 2026 状态 | v2：2.3.0（2026-10-02），`MCPServer` + 统一 `Client`，双协议时代兼容；v1 止于 1.30.0 | 1.30+ 重构到 Web Standards（最新 1.32.1，2026-10-05），可跑边缘运行时 | `MCPServerStreamableHttp` 为远程推荐方式 |
| 适用场景 | 自研 Server/Client | Node.js / 边缘生态 | 快速接入 OpenAI Agents |

## 本章小结

官方 Python/TypeScript SDK 是理解 MCP 协议落地最直接的途径：它们把 JSON-RPC 生命周期、Transport 适配、Tool/Resource/Prompt 注册封装成开发者友好的接口。参考 Servers 与官方 Registry 则展示了生态治理的演进——从“一个仓库装所有 Server”到“Registry 作为权威目录”。Claude Code/Desktop 与 OpenAI Agents SDK 的集成体现了 MCP 作为“开放 USB-C”的价值：同一个 Server 可以被不同 Host 复用。2026-07-28 之后，SDK 的主线叙事变成了无状态化：`MCPServer` 一个类同时服务两代客户端，迁移成本被压到一次依赖升级；Python SDK 2.x（2.3.0）与 TS SDK 1.30+（1.32.1）的后续小版本几乎都在收紧默认安全（同源重定向限制、请求体上限、注册期 header 校验）。而在 SDK 之外，ToolHive 这类一体化平台补上了“容器隔离运行、私有 Registry、网关治理”的生产拼图。

**参考来源**

- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [MCP Python SDK v2 迁移指南](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/migration.md)
- [MCP TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk)
- [MCP Reference Servers](https://github.com/modelcontextprotocol/servers)
- [官方 MCP Registry](https://registry.modelcontextprotocol.io)
- [ToolHive（开源 MCP 运行平台）](https://github.com/stacklok/toolhive)
- [Claude Code MCP Docs](https://docs.anthropic.com/en/docs/claude-code/mcp)
- [OpenAI Agents SDK MCP](https://openai.github.io/openai-agents-python/mcp/)
- [Anthropic: Model Context Protocol](https://www.anthropic.com/news/model-context-protocol)

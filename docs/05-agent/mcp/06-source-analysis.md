# 6. 源码分析

> 一句话理解：拆解官方 Python/TypeScript SDK、参考 Servers、Claude Code / Claude Desktop 集成、OpenAI Agents SDK MCP 支持，可以帮助我们理解协议落地时的工程取舍。

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

## 3. 官方参考 Servers

[modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers) 仓库提供了一系列参考实现：

| Server | 能力 | 学习价值 |
|---|---|---|
| **filesystem** | 读/写本地文件 | Tool + Resource 结合，URI 设计，路径白名单 |
| **fetch** | 发起 HTTP 请求 | 网络 Tool，参数校验，错误处理 |
| **sqlite** | 操作 SQLite 数据库 | 有状态 Server，SQL 注入防护 |
| **postgres** | 操作 PostgreSQL | 连接池管理，只读/读写权限控制 |
| **github** | GitHub API 调用 | OAuth 认证，API 限流处理 |
| **slack** | Slack 消息 | 第三方 SaaS 集成，token 管理 |

以 filesystem Server 为例：

- 启动时读取 `--allowed-dir` 参数，限定可访问路径。
- 提供 `read_file`、`write_file`、`list_directory` 等 Tool。
- 同时把文件暴露为 Resource，URI 形如 `file:///allowed-dir/foo.md`。
- 写操作默认需要 Host 审批，体现了 MCP 的安全模型。

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

[OpenAI Agents SDK](https://openai.github.io/openai-agents-python/mcp/) 从 2025 年开始支持 MCP，提供了 `MCPServerStdio` 与 `MCPServerSse` 两种接入方式。

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

集成特点：

- OpenAI Agents SDK 把 MCP Server 当成 Agent 的 tool 来源，自动把 `tools/list` 结果转换成 Agent 可调用的 `Tool` 对象。
- 连接生命周期由 `MCPServerStdio` / `MCPServerSse` 上下文管理器封装。
- 适合把已有 MCP Server 快速接入 OpenAI Agents 生态。

## 6. SDK 对比

| 维度 | Python SDK | TypeScript SDK | OpenAI Agents SDK |
|---|---|---|---|
| 定位 | 官方 Server/Client 实现 | 官方 Server/Client 实现 | 在 Agents 框架内消费 MCP |
| 抽象层次 | 中 | 中（偏协议原语） | 高 |
| 注册方式 | 装饰器 | 装饰器或手动 handler | 通过 `MCPServer` 对象 |
| Transport | stdio/SSE/HTTP | stdio/SSE/HTTP | stdio/SSE |
| 适用场景 | 自研 Server/Client | Node.js 生态 | 快速接入 OpenAI Agents |

## 本章小结

官方 Python/TypeScript SDK 是理解 MCP 协议落地最直接的途径：它们把 JSON-RPC 生命周期、Transport 适配、Tool/Resource/Prompt 注册封装成开发者友好的接口。参考 Servers 则展示了不同业务场景下的实现模式。Claude Code/Desktop 与 OpenAI Agents SDK 的集成则体现了 MCP 作为“开放 USB-C”的价值：同一个 Server 可以被不同 Host 复用。

**参考来源**

- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [MCP TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk)
- [MCP Reference Servers](https://github.com/modelcontextprotocol/servers)
- [Claude Code MCP Docs](https://docs.anthropic.com/en/docs/claude-code/mcp)
- [OpenAI Agents SDK MCP](https://openai.github.io/openai-agents-python/mcp/)
- [Anthropic: Model Context Protocol](https://www.anthropic.com/news/model-context-protocol)

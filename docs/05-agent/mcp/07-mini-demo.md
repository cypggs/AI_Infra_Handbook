# 7. 工程实践：Mini MCP

> 一句话理解：一个纯 Python 可运行的 MCP Client-Server Demo，展示 initialize、tools/list、tools/call、resources/read、prompts/get 与 Mock LLM 决策。

## Demo 设计

真实 MCP 系统（Claude Desktop、Cursor、OpenAI Agents SDK）通常包含大量抽象与集成；为了在不依赖外部 LLM key、不依赖外部 MCP Server 的情况下讲清楚协议核心，本 Demo 采用纯 Python 模拟：

- **protocol.py**：MCP 协议消息类型、JSON-RPC 封装、类型定义。
- **transport.py**：stdio Transport 实现，负责进程启动与字节流读写。
- **server.py**：MCP Server 主类，注册 Tool/Resource/Prompt，处理请求。
- **client.py**：MCP Client 主类，管理连接、initialize 握手、发现、调用。
- **session.py**：会话层，维护请求-响应关联与生命周期。
- **llm_client.py**：Mock LLM，根据当前可用工具决定调用哪个 Tool。
- **demo.py**：入口脚本，运行完整端到端示例。

## 目录结构

```text
docs/05-agent/mcp/mini-demo/
├── pyproject.toml
├── mcp_mini/
│   ├── __init__.py
│   ├── protocol.py        # JSON-RPC 与 MCP 消息类型
│   ├── transport.py       # stdio Transport 适配器
│   ├── server.py          # MCPServer：注册能力、处理请求
│   ├── client.py          # MCPClient：连接、发现、调用
│   ├── session.py         # Session：请求关联、生命周期
│   ├── llm_client.py      # MockLLMClient：模拟 LLM 决策
│   └── demo.py            # 入口演示
└── tests/
    ├── test_protocol.py
    ├── test_transport.py
    ├── test_server.py
    ├── test_client.py
    └── test_session.py
```

## 核心能力一览

| 能力 | 文件 | 说明 |
|---|---|---|
| JSON-RPC 编解码 | `protocol.py` | Request/Response/Notification 类型与序列化 |
| stdio Transport | `transport.py` | 启动子进程、stdin 写、stdout 读 |
| Server 注册 | `server.py` | Tool/Resource/Prompt 注册与 Handler 分发 |
| Client 发现 | `client.py` | initialize、list_tools、list_resources、list_prompts |
| 请求关联 | `session.py` | 维护 pending requests，匹配响应 |
| Mock LLM 决策 | `llm_client.py` | 根据 prompt 内容返回 tool_calls 或最终答案 |

## 快速运行

### 1. 安装依赖

```bash
cd docs/05-agent/mcp/mini-demo
pip install -e ".[dev]"
```

`pyproject.toml` 中定义了 console script：

```toml
[project.scripts]
mcp-demo = "mcp_mini.demo:run_demo"
```

### 2. 运行 Demo

```bash
mcp-demo
# 或
python -m mcp_mini.demo
```

Demo 会依次执行：

1. 启动 `MCPServer` 子进程，通过 stdio 建立连接。
2. Client 与 Server 完成 `initialize` 握手。
3. Client 发现可用 Tool、Resource、Prompt。
4. Mock LLM 根据用户问题决定调用 `read_file` Tool。
5. Client 调用 Tool 并返回结果。
6. Client 读取 Resource、获取 Prompt 模板。
7. 正常关闭连接，发送 `notifications/closed`。

### 3. 运行测试

```bash
pytest tests/ -v
```

### 4. 作为库使用

```python
import asyncio
from mcp_mini.client import MCPClient
from mcp_mini.transport import StdioTransport
from mcp_mini.llm_client import MockLLMClient

async def main():
    transport = StdioTransport(command=["python", "-m", "mcp_mini.server"])
    async with MCPClient(transport) as client:
        await client.initialize()
        tools = await client.list_tools()

        llm = MockLLMClient()
        decision = await llm.decide(
            "读取项目 README",
            tools=[t.model_dump() for t in tools],
        )
        result = await client.call_tool(decision.name, decision.arguments)
        print(result)

asyncio.run(main())
```

## 关键代码片段

### Tool 注册

```python
from mcp_mini.server import MCPServer

server = MCPServer(name="mini-server", version="0.1.0")

@server.tool(name="read_file", description="读取本地文件")
def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
```

### initialize 握手

```python
# Client 发送
await client.send_request(
    "initialize",
    {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "mini-client", "version": "0.1.0"},
    },
)

# Server 回复 capability
# Client 发送 notifications/initialized
await client.send_notification("notifications/initialized")
```

### tools/call 调用

```python
result = await client.call_tool("read_file", {"path": "README.md"})
# result 包含 content 列表与 isError 标志
```

### Mock LLM 决策

```python
class MockLLMClient:
    async def decide(self, prompt: str, tools: list[dict]) -> LLMDecision:
        if "README" in prompt:
            return LLMDecision(name="read_file", arguments={"path": "README.md"})
        return LLMDecision(name="final_answer", arguments={"answer": "无法处理"})
```

## 测试结果示例

```text
$ mcp-demo
[INIT] Client <-> Server handshake completed
[DISCOVER] tools=[read_file, list_directory], resources=1, prompts=1
[LLM] decide: read_file(path=README.md)
[TOOL] read_file result: # AI Infra Handbook\n...
[RESOURCE] file:///project/README.md: text/markdown, 1024 bytes
[PROMPT] summarize: 2 messages
[CLOSE] notifications/closed sent
```

## Demo 与生产差异说明

| 维度 | Mini Demo | 生产系统 |
|---|---|---|
| Transport | 仅 stdio | stdio / SSE / Streamable HTTP |
| 并发 | 单连接串行 | 多连接、异步并发 |
| 错误恢复 | 简单重抛 | 重试、熔断、降级 |
| 认证授权 | 无 | OAuth/API Key/mTLS、权限策略 |
| 可观测 | print | OpenTelemetry、Prometheus、结构化日志 |
| LLM | Mock | 真实 LLM Gateway |
| Schema 生成 | 手写 | 由 SDK 自动生成 |

## 本章小结

Mini MCP Demo 用纯 Python 实现了一个最小可用的 MCP Client-Server 系统，覆盖了协议握手、能力发现、Tool/Resource/Prompt 调用、Mock LLM 决策与连接关闭。它的价值不在于替代官方 SDK，而在于把协议消息流转与模块边界以可读、可运行、可扩展的方式呈现出来，为理解生产级 MCP 系统打下基础。

**参考来源**

- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [MCP Specification: Lifecycle](https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle)
- [MCP Specification: Transports](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)
- [OpenAI Agents SDK MCP](https://openai.github.io/openai-agents-python/mcp/)

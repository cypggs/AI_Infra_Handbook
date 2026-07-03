# 源码与协议对比

本章从工程师视角对比主流平台与框架的 Tool Use 实现。虽然各家 API 形态不同，但底层都遵循“定义工具 → 绑定工具 → 模型生成调用 → 执行 → 反馈结果”的循环。

## OpenAI Function Calling

OpenAI 的 Function Calling 分为 Chat Completions API 与 Responses API 两条线，字段命名略有差异。

### Chat Completions API

```python
from openai import OpenAI
client = OpenAI()

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取指定城市的当前天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名，如北京"},
                    "unit": {"type": "string", "enum": ["c", "f"]},
                },
                "required": ["city"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    }
]

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "北京今天天气怎么样？"}],
    tools=tools,
    tool_choice="auto",
)

if response.choices[0].message.tool_calls:
    for tc in response.choices[0].message.tool_calls:
        args = json.loads(tc.function.arguments)
        result = get_weather(**args)
        # 把结果作为 role=tool 消息回传
```

### Responses API

```python
response = client.responses.create(
    model="gpt-4o",
    input="北京今天天气怎么样？",
    tools=[
        {
            "type": "function",
            "name": "get_weather",
            "description": "获取指定城市的当前天气",
            "parameters": {...},
            "strict": True,
        }
    ],
    tool="auto",
)
```

**特点**：

- `strict: True` 可显著提升参数格式遵循率。
- `tool_choice` 支持 `auto` / `none` / `required` / `{"type": "function", "function": {"name": "..."}}`。
- `parallel_tool_calls: False` 可禁用并行调用。

## Anthropic Tool Use

Anthropic 把工具调用与结果都表达为消息内容块（content block）。

```python
from anthropic import Anthropic
client = Anthropic()

tools = [
    {
        "name": "get_weather",
        "description": "获取指定城市的当前天气",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string"},
                "unit": {"type": "string", "enum": ["c", "f"]},
            },
            "required": ["city"],
        },
    }
]

response = client.messages.create(
    model="claude-sonnet-4-20251001",
    max_tokens=1024,
    messages=[{"role": "user", "content": "北京今天天气怎么样？"}],
    tools=tools,
    tool_choice={"type": "auto"},
)

for block in response.content:
    if block.type == "tool_use":
        result = get_weather(**block.input)
        # 回传 tool_result 块
        tool_result = {
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": str(result),
        }
```

**特点**：

- 工具参数 schema 字段名为 `input_schema`。
- 工具结果通过 `tool_result` 块回传，需匹配 `tool_use_id`。
- 支持 `disable_parallel_tool_use` 与 `tool_choice: {type: "any"}` / `{type: "tool", name: "..."}`。

## Google Gemini Function Calling

Gemini 使用 `function_declarations` 定义工具，通过 `tool_config` 控制调用模式。

```python
import google.generativeai as genai

weather_tool = genai.protos.Tool(
    function_declarations=[
        genai.protos.FunctionDeclaration(
            name="get_weather",
            description="获取指定城市的当前天气",
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "city": genai.protos.Schema(type=genai.protos.Type.STRING),
                    "unit": genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        enum=["c", "f"],
                    ),
                },
                required=["city"],
            ),
        )
    ]
)

model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    tools=[weather_tool],
    tool_config={
        "function_calling_config": {
            "mode": "AUTO",  # AUTO / ANY / NONE
        }
    },
)

response = model.generate_content("北京今天天气怎么样？")
for part in response.parts:
    if part.function_call:
        fc = part.function_call
        result = get_weather(**dict(fc.args))
        # 通过 function_response part 回传
```

**特点**：

- Schema 使用 protobuf 风格封装，参数类型为枚举常量。
- 工具选择模式为 `AUTO` / `ANY` / `NONE`。
- 结果通过 `function_response` part 回传。

## LangGraph

LangGraph 把工具抽象为 Python 函数，通过装饰器注册，并用预构建节点处理工具调用。

```python
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph import StateGraph, MessagesState

@tool
def get_weather(city: str, unit: str = "c") -> str:
    """获取指定城市的当前天气。"""
    return f"{city} 今天晴天，25{unit}。"

graph = StateGraph(MessagesState)
graph.add_node("agent", call_model)
graph.add_node("tools", ToolNode([get_weather]))
graph.add_edge("__start__", "agent")
graph.add_conditional_edges("agent", tools_condition)
graph.add_edge("tools", "agent")
app = graph.compile()
```

**特点**：

- `@tool` 自动从函数签名与 docstring 生成 schema。
- `bind_tools` 把工具绑定到模型。
- `ToolNode` 自动执行工具调用，`tools_condition` 自动判断是否需要进入工具节点。
- 适合快速原型，复杂权限与沙箱需要自己扩展。

## OpenAI Agents SDK

OpenAI Agents SDK 是一个高阶框架，内置工具循环、跟踪与交接（handoff）。

```python
from agents import Agent, function_tool, Runner

@function_tool
def get_weather(city: str) -> str:
    """获取指定城市的当前天气。"""
    return f"{city} 今天晴天。"

agent = Agent(
    name="weather_assistant",
    instructions="你是一个天气助手。",
    tools=[get_weather],
    model="gpt-4o",
)

result = Runner.run_sync(agent, "北京今天天气怎么样？")
print(result.final_output)
```

**特点**：

- `@function_tool` 自动 schema 生成。
- `Runner` 内部负责工具循环、结果反馈、跟踪（trace）。
- 支持 `handoff` 把任务转交给其他 Agent。
- 对需要深度定制的生产系统，仍需自行封装 Registry、权限、熔断等。

## AutoGen

AutoGen 把函数包装为 `FunctionTool`，再绑定到 `AssistantAgent`。

```python
from autogen_core.tools import FunctionTool
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient

async def get_weather(city: str) -> str:
    return f"{city} 今天晴天。"

weather_tool = FunctionTool(
    get_weather,
    description="获取指定城市的当前天气",
)

agent = AssistantAgent(
    name="weather_assistant",
    model_client=OpenAIChatCompletionClient(model="gpt-4o"),
    tools=[weather_tool],
    system_message="你是一个天气助手。",
)
```

**特点**：

- 工具与 Agent 解耦，便于复用。
- `AssistantAgent` 自动处理工具循环。
- v0.4+ 基于 `autogen-core` 重新设计，强调异步与模块化。

## MCP（Model Context Protocol）

MCP 不是某一厂商的 SDK，而是一套开放协议，用于标准化模型与外部能力之间的发现与调用。

```json
// tools/list 响应示例
{
  "tools": [
    {
      "name": "get_weather",
      "description": "获取指定城市的当前天气",
      "inputSchema": {
        "type": "object",
        "properties": {
          "city": {"type": "string"},
          "unit": {"type": "string", "enum": ["c", "f"]}
        },
        "required": ["city"]
      },
      "annotations": {
        "title": "Get Weather",
        "readOnlyHint": true
      }
    }
  ]
}

// tools/call 请求示例
{
  "name": "get_weather",
  "arguments": {"city": "北京", "unit": "c"}
}
```

**特点**：

- 通过 `tools/list` 动态发现，通过 `tools/call` 调用。
- JSON-RPC 2.0 传输，支持 stdio、SSE、HTTP。
- `inputSchema` 字段与 JSON Schema 对齐，便于跨厂商复用。
- `annotations` 提供可读提示、破坏性提示、只读提示等元信息。

## 综合对比表

| 项目 | Schema 字段 | Tool Choice | 并行调用 | 结果格式 | 循环责任 | 适合场景 |
| --- | --- | --- | --- | --- | --- | --- |
| OpenAI Chat Completions | `function.parameters` | `tool_choice` + `parallel_tool_calls` | 支持 | `role: tool` + `tool_call_id` | 应用代码 | 通用生产 |
| OpenAI Responses API | `parameters` | `tool` | 支持 | 输出项中 `type: function_call` | 应用代码 | 新 API 路线 |
| Anthropic Messages | `input_schema` | `tool_choice` + `disable_parallel_tool_use` | 支持 | `tool_use` / `tool_result` 块 | 应用代码 | Claude 生态 |
| Google Gemini | `function_declarations[].parameters` | `tool_config.function_calling_config.mode` | 支持 | `function_call` / `function_response` part | 应用代码 | Gemini 生态 |
| LangGraph | `@tool` 自动生成 | `bind_tools` + `tools_condition` | 支持 | 内部消息对象 | 框架内置 | 快速编排 |
| OpenAI Agents SDK | `@function_tool` 自动生成 | 默认自动，可强制 | 支持 | 内部封装 | Runner 内置 | 快速 Agent 原型 |
| AutoGen | `FunctionTool` 包装 | Agent 配置 | 支持 | 内部消息对象 | Agent 内置 | 多 Agent 系统 |
| MCP | `inputSchema` | 由客户端/模型层决定 | 取决于客户端 | JSON-RPC result/error | 客户端实现 | 开放生态 / 插件 |

## 工程选型建议

- **直接与 LLM 厂商集成**：如果团队只需要支持一家模型，直接使用厂商 SDK 最简单，严格模式与原生跟踪都可用。
- **需要切换多家模型**：在内部建立统一的 `ToolDefinition` 与 `SchemaManager`，再适配到各厂商格式。
- **快速原型与编排**：LangGraph 或 OpenAI Agents SDK 能显著降低样板代码。
- **开放插件生态 / 多租户**：采用 MCP 作为外部能力接入标准，Tool Use 层负责语义映射与权限治理。

无论选择哪种方案，生产系统都需要在框架之上补充 Registry、Validator、Permission、Executor、Observer 等模块，不能把所有治理逻辑都交给模型或框架默认实现。

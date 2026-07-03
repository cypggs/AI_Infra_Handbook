# 核心概念

Tool Use 的核心可以概括为一句话：**用结构化契约（JSON Schema）描述外部能力，让模型在自然语言驱动下生成符合契约的调用请求，再由运行时安全地执行并反馈结果。** 本章拆解这一过程中的关键概念。

## 工具定义（Tool Definition）

一个工具定义通常包含三个要素：

- **name**：机器可读的唯一标识。建议用小写英文、下划线分隔，例如 `get_weather`。
- **description**：自然语言描述，告诉模型这个工具是干什么的、在什么场景下使用。描述质量直接影响工具选择准确率。
- **parameters / input_schema**：JSON Schema，描述工具接受的参数名称、类型、是否必填、取值范围、示例等。

> 经验法则：模型对 description 的敏感度往往高于 name。名字再规范，如果描述含糊，模型仍会选错工具。

## JSON Schema 的方言差异

不同厂商对工具定义的字段命名略有不同，但底层都是 JSON Schema。下表对比了主流方案：

| 平台/协议 | 工具数组字段 | 名称字段 | 描述字段 | 参数 Schema 字段 | 严格模式 |
| --- | --- | --- | --- | --- | --- |
| OpenAI Chat Completions | `tools` | `function.name` | `function.description` | `function.parameters` | `strict: true` |
| OpenAI Responses API | `tools` | `name` | `description` | `parameters` | `strict: true` |
| Anthropic Messages | `tools` | `name` | `description` | `input_schema` | 依赖模型遵循 schema |
| Google Gemini | `tools` | `function_declarations[].name` | `function_declarations[].description` | `function_declarations[].parameters` | 可通过模式约束 |
| MCP | `tools/list` 返回 | `name` | `description` | `inputSchema` | 由服务端实现 |

工程上建议建立一个 **Schema Manager**，把不同方言归一化为内部标准模型，再反向序列化为各厂商需要的格式。这样可以在切换模型时最小化改动。

## Tool Choice：谁来决定调不调用

Tool Choice 控制模型是否有权调用工具、必须调用工具、或必须调用某个特定工具。主要模式包括：

| 模式 | 含义 | 典型场景 |
| --- | --- | --- |
| `auto` / `AUTO` | 模型自行决定是否调用工具 | 通用对话，可能直接回答 |
| `required` / `ANY` | 模型必须至少调用一个工具 | 强制走工具链路，避免模型“偷懒” |
| `none` / `NONE` | 禁止调用工具 | 只需要文本生成 |
| forced / named | 强制调用指定工具 | 流程中已知必须用某工具 |

OpenAI 提供 `tool_choice` 与 `parallel_tool_calls` 两个控制位；Anthropic 提供 `tool_choice` 和 `disable_parallel_tool_use`；Google 提供 `tool_config.function_calling_config.mode`。

## 并行工具调用（Parallel Tool Calls）

当多个工具调用之间没有依赖关系时，模型可以在一次响应中返回多个调用请求。运行时可以并发执行这些调用，再把结果合并后一起送回模型。

**适用条件**：调用之间无状态依赖、无执行顺序要求。例如同时查询北京和上海的天气。

**不适用条件**：后续调用的参数依赖前一次调用的结果。例如先查用户 ID，再查订单。这种情况下需要 [Planning](/05-agent/planning/) 模块编排顺序，或采用 ReAct 式的多轮循环。

## 工具结果格式

工具执行完成后，需要把结果包装成模型能理解的格式回传。不同厂商的结果格式不同：

- **OpenAI**：`role: "tool"` 消息，携带 `tool_call_id` 与 `content`（通常为字符串或 JSON 字符串）。
- **Anthropic**：`tool_result` 内容块，携带 `tool_use_id` 与 `content`。
- **Google Gemini**：`function_response` part，包含 `name` 与 `response`。
- **MCP**：JSON-RPC 调用返回 `result` 或 `error`。

Result Formatter 的职责就是把这些结果映射回当前对话厂商需要的消息结构，并在必要时进行截断、摘要或压缩。

## 完整生命周期

一次工具调用通常经历以下阶段：

```text
Register / Discover → Model Decision → Parse → Validate → Execute → Format → Feedback → Next Turn
```

1. **Register / Discover**：工具在启动时静态注册，或通过 [MCP](/05-agent/mcp/) 在运行时动态发现。
2. **Model Decision**：模型根据用户意图和可用工具，决定是否调用、调用哪些、参数是什么。
3. **Parse**：把模型输出解析为规范化的调用对象 `{tool_name, arguments, call_id}`。
4. **Validate**：按 JSON Schema 校验参数，结合权限策略进行二次校验。
5. **Execute**：调用真实实现，可能是本地函数、HTTP API、RPC 或另一个 Agent。
6. **Format**：把执行结果转换为当前厂商要求的消息格式。
7. **Feedback**：把结果加入对话历史，供下一轮模型推理使用。
8. **Next Turn**：模型基于新信息继续生成，直到任务完成或达到终止条件。

## 静态工具 vs 动态工具

- **静态工具**：在 Agent 启动时已知，通常直接编码在配置文件或代码里。适用于稳定的内部能力。
- **动态工具**：在运行时通过 MCP Server、Agent 注册中心或用户上传发现。适用于插件生态、多租户 SaaS、多 Agent 协作。

动态工具对 Schema Manager 和权限模块提出更高要求：必须在运行时发现、校验、沙箱化，并防止恶意 schema 导致的注入或过度授权。

## 与 MCP、Planning 的边界

Tool Use 不是孤立存在的，它与相邻主题有明确分工：

- **Tool Use**：负责“单次调用”的语义——理解意图、选择工具、构造参数、消费结果。
- **MCP**：负责外部能力的标准化发现与传输协议，包括 schema、鉴权、生命周期管理。
- **Planning**：负责多步任务中工具调用的顺序、依赖与组合策略。
- **Agent Runtime**：负责真正执行工具调用，并提供进程、网络、沙箱等基础设施。

如果把一次复杂任务比作做菜，Planning 决定菜谱步骤，Tool Use 决定每一步用哪把刀、切什么，MCP 是刀具柜的标准接口，Agent Runtime 是实际握刀的手。

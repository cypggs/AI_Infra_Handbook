# 10. 面试题

> 一句话理解：MCP 面试题覆盖协议概念、实现细节、安全治理与生产落地四个层面。

## 初级

### Q1：MCP 与 Function Calling 有什么区别？

**参考答案**：

- Function Calling 是模型输出 JSON 调用请求的能力，由应用层解析执行。
- MCP 是在 Function Calling 之上的标准化协议，增加了能力发现（list）、协商（initialize）、通知（notification）、生命周期管理。
- MCP 让 Server 可以独立进程/服务运行，被多个 Host 复用；Function Calling 通常需要每个应用自己实现工具注册与发现。

### Q2：MCP 中的 Host、Client、Server 分别是什么？

**参考答案**：

- **Host**：发起连接、管理多个 Client、做最终安全决策的应用，例如 Claude Desktop、Cursor。
- **Client**：维持与单个 Server 的连接，转发请求/通知，管理会话生命周期。
- **Server**：暴露 Tools、Resources、Prompts、Sampling、Roots 等能力的后端服务或进程。

### Q3：MCP 支持哪些 Transport？

**参考答案**：

- **stdio**：本地子进程，stdin/stdout 传输 JSON-RPC。
- **SSE**：基于 HTTP Server-Sent Events，适合远程 Server。
- **Streamable HTTP**：在 SSE 基础上进一步标准化的双向流式传输。

### Q4：MCP 的五大原语是什么？

**参考答案**：

Tools（可调用能力）、Resources（URI 标识的数据）、Prompts（提示模板）、Sampling（请求 Host 调用 LLM）、Roots（作用域边界）。

## 中级

### Q5：MCP 会话的生命周期是什么？

**参考答案**：

1. Transport 建立连接。
2. Client 发送 `initialize`，Server 回复 capability。
3. Client 发送 `notifications/initialized`。
4. Client 调用 `tools/list`、`resources/list`、`prompts/list` 发现能力。
5. 进入请求-响应与通知循环。
6. 关闭时 Client 发送 `notifications/closed`，Server 清理资源。

### Q6：为什么 MCP 强调 Host 拥有最终决策权？

**参考答案**：

因为 Server 可能执行写文件、访问数据库、调用外部 API 等敏感操作。Host 作为用户代理，必须决定是否允许调用、是否转发 Sampling 请求、是否暴露某个 Resource。MCP 的安全模型是“Server 声明能力，Host 授权使用”。

### Q7：MCP 中业务错误和协议错误分别应该怎么返回？

**参考答案**：

- **协议错误**：用 JSON-RPC error，例如参数错误返回 `-32602`，方法不存在返回 `-32601`。
- **业务错误**：用 `tools/call` 的 `isError=true`，把错误信息放在 `content` 里返回给模型，让模型决定重试或换策略。

### Q8：stdio Server 崩溃后 Client 应该怎么做？

**参考答案**：

- 检测子进程退出信号。
- 清理当前 session 的 pending requests。
- 根据策略决定是否重连/重启 Server。
- 记录错误事件到 Observer。
- 通知 Host，让用户决定是否继续。

### Q9：MCP Gateway 需要解决哪些问题？

**参考答案**：

认证、授权、限流、路由、审计、协议转换、多租户隔离、版本管理。

## 高级

### Q10：设计一个企业级 MCP 平台，你会怎么设计？

**参考答案**：

- **Server Registry**：集中注册 Server，缓存 schema，支持版本管理。
- **MCP Gateway**：统一认证、授权、限流、审计、路由。
- **Transport 适配**：同时支持 stdio（本地敏感能力）和 SSE/HTTP（远程共享能力）。
- **Session Manager**：管理连接生命周期，支持取消、重连、心跳。
- **Capability Manager**：协商协议版本与能力，处理动态变更。
- **Observer**：OpenTelemetry trace + Prometheus metrics + 结构化日志。
- **HITL 审批**：高风险 Tool 需要人工确认。
- **多租户**：按租户隔离 Server 列表、Resource URI、配额、审计日志。
- **测试与评测**：单元测试、协议测试、集成测试、安全测试、影子运行。

### Q11：MCP 与 A2A（Agent-to-Agent）有什么区别和联系？

**参考答案**：

- **MCP**：解决 Agent 与外部工具/数据/提示之间的连接与发现。
- **A2A**：解决 Agent 与 Agent 之间的协作通信。
- 两者互补：一个 Agent 可以通过 MCP 发现自己能用的能力，通过 A2A 与其他 Agent 协作完成任务。

### Q12：如何保证 MCP Server 的 Tool 调用安全？

**参考答案**：

- 参数校验：严格校验 JSON Schema，拒绝非法输入。
- 权限标签：给 Tool 打标签，Host 按标签授权。
- 路径/范围白名单：例如文件 Server 只能访问 `--allowed-dir` 目录。
- HITL：高风险操作需要人工确认。
- 沙箱：危险操作在隔离环境中执行。
- 审计：记录所有调用、参数、结果、审批事件。
- 最小权限：Server 进程以最小权限运行。

### Q13：MCP 的 Capability Negotiation 有什么工程意义？

**参考答案**：

- 确保 Client 与 Server 使用兼容的协议版本。
- 只启用双方都支持的能力，避免功能缺失或行为不一致。
- 支持能力动态变更，Server 升级后老 Client 仍可工作。
- 为 Gateway 和 Host 提供决策依据，例如是否允许订阅、是否支持 Sampling。

### Q14：为什么 MCP 协议要区分 Request/Response 和 Notification？

**参考答案**：

- Request/Response 用于需要确认的操作，例如 Tool 调用。
- Notification 用于单向事件，例如 Server 主动通知 Resource 更新、Client 通知 initialized/closed。
- Notification 不需要等待回复，可以降低延迟、简化事件推送。

## 本章小结

MCP 面试题通常围绕四个层面展开：**协议概念**（Host/Client/Server、Primitives、Transport）、**协议流程**（initialize、list、call、notification、close）、**安全治理**（Host 决策权、认证授权、HITL、参数校验）、**生产落地**（Gateway、Registry、可观测、多租户、版本管理）。掌握本章问题，基本可以覆盖中级到高级面试场景。

**参考来源**

- [MCP Specification](https://modelcontextprotocol.io/specification/2025-06-18)
- [MCP Introduction](https://modelcontextprotocol.io/introduction)
- [Anthropic: Model Context Protocol](https://www.anthropic.com/news/model-context-protocol)
- [Claude Code MCP Docs](https://docs.anthropic.com/en/docs/claude-code/mcp)

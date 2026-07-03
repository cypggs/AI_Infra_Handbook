# 核心模块详解

本章把架构图中的每个模块展开为可落地的接口与职责。这些模块不必都部署为独立服务，但在代码边界上应当清晰，以便测试、扩展和故障定位。

## Tool Registry

**职责**：维护所有可用工具的元数据，支持静态注册、动态发现、版本管理与按上下文过滤。

**输入**：

- 启动配置（静态工具列表、文件路径）。
- MCP Server 的 `tools/list` 响应。
- 运行时注册/反注册请求。
- 查询条件（namespace、tag、权限身份）。

**输出**：

- 工具元数据列表：`[{name, description, schema, version, source, annotations, authz_scope}]`。
- 单个工具详情。

**关键接口（示意）**：

```python
class ToolRegistry:
    def register(self, tool: ToolMetadata) -> None: ...
    def discover_from_mcp(self, mcp_client) -> list[ToolMetadata]: ...
    def list(self, context: RequestContext, query: ToolQuery) -> list[ToolMetadata]: ...
    def get(self, name: str, version: str | None = None) -> ToolMetadata: ...
    def deregister(self, name: str, version: str | None = None) -> None: ...
```

**设计要点**：

- 同名多版本工具需要版本号隔离，默认行为应可配置（最新版 / 显式指定）。
- 动态发现时要校验 schema 合法性，防止恶意 MCP Server 注入非法定义。
- 根据请求上下文过滤工具：不同租户、不同用户、不同会话可见的工具集可能不同。

## Schema Manager

**职责**：把不同厂商的 schema 方言归一化，提供校验、转换、严格模式生成和文档压缩能力。

**输入**：

- 原始工具定义（OpenAI / Anthropic / Google / MCP 格式）。
- JSON Schema Draft 版本要求。

**输出**：

- 内部标准模型 `ToolDefinition`。
- 序列化后的各厂商格式。
- 校验报告（通过 / 失败详情）。

**关键接口（示意）**：

```python
class SchemaManager:
    def normalize(self, raw: dict, source: Provider) -> ToolDefinition: ...
    def to_openai(self, tool: ToolDefinition, strict: bool = False) -> dict: ...
    def to_anthropic(self, tool: ToolDefinition) -> dict: ...
    def to_mcp(self, tool: ToolDefinition) -> dict: ...
    def validate(self, tool: ToolDefinition, arguments: dict) -> ValidationReport: ...
```

**设计要点**：

- 严格模式（strict mode）会禁用模型对 schema 的“自由发挥”，但要求 schema 可被编译为 constrained grammar。复杂 schema 需要降级处理。
- 对 description 进行压缩或分片，避免 prompt 过长导致工具选择质量下降。
- 记录 schema 版本变更，支持向后兼容检测。

## Parser / Validator

**职责**：把模型原始输出解析为规范化调用对象，并完成语法与语义校验。

**输入**：

- LLM 响应消息。
- 当前可用工具集（用于校验工具名是否存在）。

**输出**：

- `list[ToolInvocation]` 或 `ParseError` / `ValidationError`。

**关键接口（示意）**：

```python
class ToolParser:
    def parse(self, response: ModelResponse) -> list[ToolInvocation] | ParseError: ...

class ToolValidator:
    def validate(self, invocations: list[ToolInvocation], registry: ToolRegistry) -> list[ValidatedInvocation] | ValidationError: ...
```

**设计要点**：

- Parser 必须支持厂商差异，例如 OpenAI 的 `tool_calls` 与 Anthropic 的 `tool_use` 块。
- 对模型偶尔产生的多余字段应宽容处理（记录警告）还是严格拒绝，需要在工程上明确策略。
- 语义校验应尽早暴露具体错误信息，便于模型自我修正。

## Permission / Policy

**职责**：在调用执行前判定是否允许，处理敏感操作的人机确认（HITL）。

**输入**：

- 调用对象。
- 请求上下文（用户身份、角色、租户、会话）。
- 历史调用记录。

**输出**：

- `ALLOW` / `DENY` / `REQUIRE_APPROVAL`。
- 若拒绝，返回可读原因。

**关键接口（示意）**：

```python
class PolicyEngine:
    def evaluate(self, invocation: ToolInvocation, context: RequestContext) -> PolicyDecision: ...

class HITLGate:
    async def request_approval(self, invocation: ToolInvocation, reason: str) -> ApprovalResult: ...
```

**设计要点**：

- 策略应是可组合的：RBAC + 风险评分 + 数据敏感度 + 调用频率。
- 对“不可逆操作”应默认进入 HITL，避免自动删除、扣款、发送外部消息。
- 审批结果需要持久化，便于审计与回放。

## Tool Executor

**职责**：真正执行工具调用，管理并发、超时、重试、熔断、降级与沙箱。

**输入**：

- 已校验的调用对象。
- 执行配置（timeout、retry、circuit_breaker、concurrency）。

**输出**：

- 执行结果或执行异常。

**关键接口（示意）**：

```python
class ToolExecutor:
    async def execute(self, invocation: ValidatedInvocation, cfg: ExecutionConfig) -> ExecutionResult: ...
    async def execute_batch(self, invocations: list[ValidatedInvocation], cfg: ExecutionConfig) -> list[ExecutionResult]: ...
```

**设计要点**：

- 独立调用应默认并发，依赖调用应串行。
- 超时分为连接超时与整体调用超时，配置粒度应到工具级别。
- 重试策略应区分可重试错误（5xx、超时）与不可重试错误（4xx、权限拒绝）。
- 熔断器状态需要暴露为指标，供监控与自动恢复使用。

## Result Formatter

**职责**：把执行结果转换为当前对话厂商要求的消息格式，并在必要时压缩、摘要、脱敏。

**输入**：

- 执行结果（任意结构化数据或异常）。
- 目标厂商类型（OpenAI / Anthropic / Google / MCP）。
- 对应 `call_id` / `tool_use_id`。

**输出**：

- 标准化的消息块或消息对象。

**关键接口（示意）**：

```python
class ResultFormatter:
    def format(self, result: ExecutionResult, target: Provider, call_id: str) -> MessageBlock: ...
    def compress(self, result: ExecutionResult, max_tokens: int) -> CompressedResult: ...
```

**设计要点**：

- 错误信息不要直接暴露内部堆栈，应返回用户可读、模型可理解的摘要。
- 超长结果应截断或摘要，避免撑爆上下文窗口。
- 对二进制结果（图片、PDF）考虑转换为文本描述或嵌入链接。

## Observer / Tracer

**职责**：记录调用全链路，输出指标、日志、Trace，用于调试、成本分析与持续优化。

**输入**：

- 调用开始/结束事件。
- 解析/校验/权限/执行各阶段结果。
- Token 使用量与延迟。

**输出**：

- OpenTelemetry Span。
- Prometheus / CloudWatch 指标。
- 结构化日志。

**关键接口（示意）**：

```python
class ToolObserver:
    def on_invoke_start(self, invocation: ToolInvocation) -> Span: ...
    def on_invoke_end(self, span: Span, outcome: InvokeOutcome) -> None: ...
    def record_metric(self, name: str, value: float, labels: dict) -> None: ...
```

**设计要点**：

- Trace 应贯穿模型调用、解析、校验、执行、格式化全阶段。
- 核心指标：调用延迟、成功率、schema 违规率、工具选择错误率、重试率、降级率、token 成本。
- 日志中不要记录敏感参数，必要时做脱敏或分级存储。

## Error Handler

**职责**：统一分类错误，决定重试、降级、返回错误、终止循环或上报。

**输入**：

- 各阶段异常（ParseError、ValidationError、PermissionDenied、ExecutionError、TimeoutError、CircuitOpenError）。
- 当前重试次数与调用历史。

**输出**：

- 处理决策：`RETRY` / `FALLBACK` / `RETURN_ERROR` / `TERMINATE` / `ESCALATE`。

**关键接口（示意）**：

```python
class ErrorHandler:
    def decide(self, error: ToolError, ctx: ErrorContext) -> ErrorDecision: ...
```

**设计要点**：

- 错误分类应基于错误类型与下游状态码，避免统一重试导致幂等性问题。
- 对连续同类型错误应触发熔断或终止，防止无限循环。
- 返回给模型的错误信息应简洁且包含可行动作，例如“参数 `city` 应为字符串，请修正”。

## 模块协作模式

在实际实现中，上述模块通常由 Orchestrator 按以下流程串联：

```text
Orchestrator
  → Registry.list(context)          # 获取可用工具
  → LLM.call(messages, tools)       # 模型决策
  → Parser.parse(response)          # 解析
  → Validator.validate(...)         # 校验
  → PolicyEngine.evaluate(...)      # 权限
  → Executor.execute(...)           # 执行
  → Formatter.format(...)           # 格式化
  → Memory.write(...)               # 持久化
  → Observer.record(...)            # 观测
  → 下一轮 LLM.call
```

不同项目可以根据规模合并模块（例如 Parser 与 Validator 合并），但职责边界不应模糊。

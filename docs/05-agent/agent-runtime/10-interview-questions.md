# 10. 面试题

## 初级

### Q1：Agent Runtime 与 LLM Gateway 有什么区别？

**参考答案**：

- LLM Gateway 解决“调哪家模型”的问题：路由、限流、重试、多供应商统一接入。
- Agent Runtime 解决“怎么让模型持续执行任务”的问题：ReAct 循环、工具调用、状态管理、护栏、可观测。
- 典型关系：`Agent Runtime → LLM Gateway → LLM`。

### Q2：什么是 ReAct？

**参考答案**：

ReAct = Reasoning + Acting。模型在每一步先进行推理（Thought），然后决定执行什么动作（Action），Runtime 执行动作后把观察结果（Observation）回传给模型，循环直到任务完成。

### Q3：Agent Runtime 为什么需要状态管理？

**参考答案**：

因为 Agent 任务通常是多轮的，需要记录当前处于 planning/acting/observing/done/error 哪个状态，还要支持 checkpoint 与断点续跑。

## 中级

### Q4：工具调用时如何防止模型参数幻觉？

**参考答案**：

- 给工具提供清晰的 JSON Schema 和描述。
- Runtime 对参数做类型校验和范围检查。
- 参数错误时让模型重试，但限制重试次数。
- 对枚举值、路径等做白名单校验。

### Q5：Agent 无限循环怎么解决？

**参考答案**：

- 设置 `max_steps` 上限。
- 检测重复工具调用（相同 name + 相同参数）。
- 检测状态是否长期没有进展。
- 对模型提示“如果无法推进，请承认失败”。

### Q6：长时任务如何保证可恢复？

**参考答案**：

- 每轮循环后 checkpoint：保存 state、messages、plan、trace_id。
- 使用外部持久化（Redis/Postgres）存储 checkpoint。
- 失败或进程重启后从最近 checkpoint 恢复。
- HITL 请求本身也是状态机的一部分。

### Q7：Agent Runtime 中 Guardrails 应该放在哪些位置？

**参考答案**：

- 输入层：过滤敏感/越权请求。
- 工具前置：检查参数、权限、调用次数。
- 工具后置：检查结果是否合规。
- 输出层：校验最终答案。
- 资源层：限制迭代次数、超时、token 预算。

## 高级

### Q8：设计一个生产级 Agent Runtime，你会怎么设计？

**参考答案**：

- **数据面无状态**：Runtime worker 可水平扩展，状态外置。
- **状态持久化**：checkpoint 到 Redis/Postgres，支持断点续跑。
- **任务队列**：接收任务后入队，worker 异步消费。
- **LLM Client**：通过 LLM Gateway 调用多模型，支持 fallback。
- **Tool Registry**：声明式注册，自动生成 schema，带权限标签。
- **Executor**：危险工具进沙箱，超时隔离。
- **Guardrails**：多层策略，HITL 高风险操作。
- **Observer**：OpenTelemetry trace + Prometheus metrics + 结构化日志。
- **Eval**：固定评测集 + 影子运行 + A/B 测试。

### Q9：LangGraph 与 OpenAI Agents SDK 的主要区别是什么？

**参考答案**：

- **OpenAI Agents SDK**：SDK 式，Agent/Runner/Tool 抽象，快速落地；构建在 Responses API 上，2026-04 起支持任意 Chat Completions 兼容模型、原生沙箱与 subagents。
- **LangGraph**：图编排式，StateGraph/Node/Edge，显式状态管理 + checkpoint/durable execution，强持久化与可观测，适合复杂生产工作流；2025-10 已 GA。
- 选型：简单任务、SDK 平台化能力（沙箱/subagents）优先用 Agents SDK；复杂有状态、需要断点续跑与人工介入的任务用 LangGraph。2026 年两者都可对接 Temporal 等 durable 引擎与 OTel 可观测。

### Q10：Agent Runtime 中如何处理工具执行失败？

**参考答案**：

- 参数错误：把错误信息作为 observation 回传，让模型修正后重试。
- 超时/异常：返回统一的 error observation，Runtime 决定是否 fallback。
- 连续失败：触发熔断或进入 error 状态。
- 不可恢复：记录失败 trace，必要时请求 HITL。

### Q11：为什么 Agent 的可观测比传统服务更重要？

**参考答案**：

因为 Agent 的执行路径是模型动态决定的，无法像传统服务那样通过代码路径预测。必须记录完整的 thought-action-observation 链、guardrail 事件、token 成本，才能调试、审计和优化。落地时用 OpenTelemetry GenAI 语义约定做采集层（span 树 `invoke_agent` → `chat` → `execute_tool`），后端可替换 Langfuse / LangSmith / Datadog。

### Q12：什么是 durable execution？为什么 Agent 特别需要它？

**参考答案**：

Durable execution 是把每次执行的输入输出记录到 journal，崩溃后从最后记录重放恢复的执行模型。Agent 特别需要它是因为：任务长（分钟到小时级）、每一步 LLM 调用都要花钱、且有外部副作用（写库、发邮件）。普通 checkpoint 恢复容易重复已完成的调用与副作用；durable 引擎（Temporal / Inngest / Restate / DBOS）通过事件溯源保证 exactly-once 语义。典型模式：Agent 循环作为 workflow，每个 LLM/工具调用作为一个 activity/step。

### Q13：MCP 与 A2A 分别解决什么问题？Runtime 如何使用它们？

**参考答案**：

- **MCP（Model Context Protocol）**：Agent ↔ 工具/数据的协议，解决能力发现与标准化调用；2026-07-28 规范转向无状态核心，部署成本大降，由 Linux Foundation Agentic AI Foundation 治理。
- **A2A（Agent2Agent）**：Agent ↔ Agent 的协作协议，v1.0 于 2026-03 发布（签名 Agent Card、多租户、版本协商）；IBM 的 ACP 已于 2025-08 合并进 A2A。
- Runtime 通过 MCP 接入工具生态（也可继续用 function calling），通过 A2A 与其他组织的 Agent 互通；两者互补，同属一个治理基金会。

## 本章小结

面试中关于 Agent Runtime 的问题通常集中在：**ReAct 循环**、**工具调用与参数校验**、**状态与持久化**、**Guardrails 与 HITL**、**可观测**、**框架对比**。掌握本章问题，基本可以覆盖中级到高级面试场景。

**参考来源**

- [OpenAI Agents SDK Docs](https://platform.openai.com/docs/guides/agents)
- [LangGraph Concepts](https://langchain-ai.github.io/langgraph/concepts/high_level/)
- [ReAct Paper](https://arxiv.org/abs/2210.03629)
- [The Agent Protocol Stack in 2026: MCP, A2A, and ACP](https://www.agenticfabriq.com/blog/agent-protocol-stack-2026)
- [Durable AI agents in 2026](https://www.reactify-solutions.com/articles/durable-ai-agents-2026)

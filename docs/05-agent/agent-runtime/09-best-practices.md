# 9. 最佳实践

> 一句话理解：Agent Runtime 的最佳实践不是追求功能最全，而是**根据任务复杂度选择合适抽象，并在可观测、安全、评测上从第一天就建立底线**。

## 1. 模型选择

- **强模型 + 简单框架 > 弱模型 + 复杂编排**。当 Claude 4.x / GPT-5.x / Gemini 3 能一次调用完成规划与执行时，不要把简单任务拆成多步图。
- **按任务选模型**：简单分类用便宜模型；复杂推理用强模型；代码生成用 coding 模型。
- **不要锁死一家**：通过 LLM Gateway 支持多模型 fallback；2026 年起 OpenAI Agents SDK 等也已支持任意 Chat Completions 兼容模型。

## 2. 工具设计

- **工具数量宁少勿多**。给 Agent 太多工具会降低决策质量。
- **工具描述要清晰**。描述直接决定模型调用准确率。
- **参数命名自解释**。避免 `arg1`、`arg2`。
- **返回结构化结果**。JSON 比自由文本更容易被模型继续消费。
- **危险工具加标签**。例如 `destructive`、`write`、`network`，供 Guardrails 使用。

## 3. ReAct 循环调优

- **设置最大迭代次数**。通常 5~15 步，根据任务复杂度调整。
- **检测循环与重复**。如果模型连续调用同一工具且参数相同，应强制终止或提示。
- **控制上下文长度**。长工具输出应摘要后再回注。
- **让模型在无法完成时承认**。训练/提示模型在信息不足时返回 `I don't know`。

## 4. 记忆与上下文

- **工作记忆保留完整对话**，但超过 token 阈值时摘要。
- **compaction 是一等公民**：按阈值自动触发、在阶段边界主动触发，并保证“有 HITL 待审批时推迟压缩”；压缩事件必须进 trace。
- **长时 subagent 独立管理压缩窗口**（如 Claude Code 的 `autoCompactWindow`），父子生命周期分开，避免压缩打断父子通信。
- **长期记忆按需检索**，不要一次性塞进上下文。
- **敏感信息不入长期记忆**。例如用户密码、Token、PII。
- **多会话共享记忆需要用户授权**。

## 5. 护栏

- **输入护栏**：过滤越狱、提示注入、越权请求。
- **工具前置护栏**：检查参数、调用次数、权限标签。
- **工具后置护栏**：检查结果是否包含敏感信息。
- **输出护栏**：确保最终答案合规。
- **资源护栏**：限制迭代次数、超时、token 预算。

## 6. 人机协同（HITL）

- **高风险操作必须人工确认**：写文件、转账、删除数据、对外发送邮件。
- **HITL 不应阻塞无关任务**：只在需要时中断当前 session。
- **提供清晰的上下文**：人类审批时应看到任务目标、工具、参数、风险说明。

## 7. 可观测

- **从 Day 0 接入 trace**。没有 trace 的 Agent 无法调试。
- **采集层用 OpenTelemetry GenAI 约定，后端可换**（Langfuse / LangSmith / Datadog 任选），避免被某家私有 SDK 格式锁定。
- **记录完整执行路径**：thought、tool call、observation、guardrail 事件。
- **关注关键指标**：任务成功率、平均步数、循环卡死率、工具调用错误率、token 成本。
- **按 tenant/user 拆分大盘**。
- prompt/response 内容采集保持 opt-in。

## 8. 沙箱

- **任何会执行代码或访问外部系统的工具都必须沙箱**；跑不可信 LLM 生成代码的默认选项是 Firecracker microVM（E2B 等），需要 GPU 时考虑 Modal（gVisor）。
- **用快照 fork 放大并行度**：先跑一个探路会话，再 fork 出 N 个并行副本执行独立子任务（E2B v2 fork、Daytona、Vercel 均已支持）。
- **最小权限原则**：只开放必要的路径、网络、API。
- **超时与资源限制**：CPU、内存、网络超时都要设上限。
- **审计日志**：记录沙箱内所有行为。
- **优先采购而非自研**：2026 年起主流 SDK（如 OpenAI Agents SDK）已原生集成多家沙箱供应商，且有 Apache-2.0 自托管选项（如 E2B Embed，2026-09）；自研沙箱只在强合规场景值得。

## 9. 评测

- **建立评测集再调优**。没有评测集的优化是盲调。
- **覆盖成功、失败、边界、安全场景**。
- **用影子运行做回归**：新版本与旧版本并行对比。
- **把评测集成到 CI/CD**：每次代码变更跑一遍 eval。
- **轨迹级归因**：失败定位要到“哪一步、哪个工具、什么参数”，而不是只看最终答案。
- **生产流量异步采样评测**（5–20%），静态 benchmark 会系统性高估线上能力。
- **LLM judge 要校准**：与 200+ 人工标注对齐（kappa > 0.7）、judge 与生成模型不同家族、季度刷新 gold set；主观打分前先跑确定性检查。

## 10. 持久化执行（durable execution）

- **分钟级以内、无外部副作用**：进程内状态机 + Redis checkpoint 足够。
- **长时任务或有外部副作用（写库、发邮件、扣费）**：交给 Temporal / Inngest / Restate / DBOS 这类 durable 引擎，journal + 重放保证“不重复 LLM 调用、不重复副作用”。
- **HITL 暂停即持久化**：等待审批的 session 必须落盘，可被外部事件唤醒。
- 引擎费用通常不到 token 账单的 1%，按架构匹配度选型，不要按价格选型。

## 11. 避免过度编排

- 单 Agent 能解决的问题不要上 Multi-Agent。
- 简单线性任务用 SDK 或轻量 Runtime。
- 复杂有状态任务才用 LangGraph 等图编排框架。
- 不要为了用框架而用框架。

## 最佳实践速查表

| 维度 | 推荐做法 |
|---|---|
| 模型 | 强模型 + 简单框架；按任务选模型；多模型 fallback |
| 工具 | 少而精、描述清晰、参数自解释、危险工具加标签 |
| 循环 | 设 max_steps、检测重复、控制上下文 |
| 记忆 | 工作记忆 + 摘要；compaction 一等公民（自动触发、推迟于 HITL、事件进 trace）；长期记忆按需检索；敏感信息不入记忆 |
| 护栏 | 输入/工具前置/工具后置/输出/资源多层护栏 |
| HITL | 高风险操作必须确认；提供清晰上下文 |
| 可观测 | Day 0 trace；OTel GenAI 约定采集、后端可换；按 tenant 分大盘 |
| 沙箱 | 代码/外部访问必须隔离；Firecracker microVM 优先；最小权限 |
| 评测 | 先建 eval 集；轨迹级归因；在线采样；judge 校准 |
| 持久化 | 长时/有副作用任务用 durable execution 引擎；HITL 暂停即落盘 |
| 编排 | 按需选型，避免过度设计 |

## 本章小结

Agent Runtime 的最佳实践覆盖了模型选择、工具设计、循环调优、记忆、护栏、HITL、可观测、沙箱、评测与编排十个方面。核心原则是：**用 Runtime 把复杂性与风险集中收敛，让业务方只关心“定义目标与工具”**。

**参考来源**

- [OpenAI Agents SDK Best Practices](https://platform.openai.com/docs/guides/agents)
- [LangGraph Production Guide](https://langchain-ai.github.io/langgraph/concepts/production_concepts/)
- [Best AI agent frameworks (2026): How to choose one and add evals — Braintrust](https://www.braintrust.dev/articles/best-ai-agent-frameworks-2026)
- [LLM-as-a-Judge Best Practices in 2026](https://futureagi.com/blog/llm-as-a-judge-best-practices-2026/)
- [Durable Execution for AI Agents in 2026](https://turion.ai/blog/temporal-vs-restate-vs-hatchet-vs-inngest-durable-execution-agents-2026/)
- [Agent Runtime 与 Agent OS — Diors.tech](https://www.diors.tech/blog/099-agent-runtime-os)
- [OpenAI Agents SDK Changelog（v0.19–v0.24）](https://www.gradually.ai/en/changelogs/openai-agents-sdk/)
- [E2B Product Updates](https://e2b.dev/product-updates)

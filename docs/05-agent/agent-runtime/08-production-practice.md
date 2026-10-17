# 8. 企业生产实践

> 一句话理解：生产环境的 Agent Runtime 要解决的不是“能不能跑通 Demo”，而是“能不能在长时任务、多用户、多工具、高风险场景下稳定、安全、可观测地跑”。

## 部署形态

### 形态 1：独立服务

```text
Client → Agent Runtime Service → LLM Gateway → LLM
                  ↓
              Tools / APIs
```

适用：

- 多个业务方共享 Agent 能力。
- 需要统一权限、审计、成本核算。
- 有专职团队运维 Runtime。

高可用要点：

- 多副本部署，状态外置（Redis/Postgres）。
- 任务队列解耦：接收任务后入队，worker 异步执行。
- Checkpoint 持久化，支持断点续跑。

### 形态 2：库 / SDK

```text
业务进程 import agent_runtime
```

适用：

- 低延迟要求极高。
- 每个应用需要高度定制。
- 已有成熟可观测体系。

注意：

- 状态与观测分散，需要统一导出。
- 版本升级需要各应用同步。

### 形态 3：云托管 Runtime

例如 AWS Bedrock AgentCore、Azure AI Agent Service、Vertex AI Agent Engine。

适用：

- 希望减少运维负担。
- 已有云厂商生态。
- 需要按需扩缩。

注意：

- 供应商锁定。
- 自定义工具与策略可能受限。

## 与 LLM Gateway 集成

Agent Runtime 通过 LLM Gateway 统一调用模型：

```text
Agent Runtime → LLM Gateway → OpenAI / Azure / vLLM / Triton
```

好处：

- 利用 Gateway 的多供应商路由、限流、重试、成本追踪。
- Runtime 不需要管理多个模型 key。
- 统一观测 LLM 调用层。

## 长时任务与 Checkpoint

生产任务可能持续数分钟到数小时，必须支持 checkpoint：

```python
state_manager.checkpoint(
    session_id,
    state=current_state,
    messages=messages,
    plan=plan,
    trace_id=trace_id,
)
```

恢复时：

```python
snapshot = state_manager.load_checkpoint(session_id)
runtime.resume(snapshot)
```

Checkpoint 应包含：

- 当前状态。
- 完整 messages。
- 计划/subgoals。
- 已执行 tool calls。
- 未完成的 HITL 请求。

### 进阶：Durable Execution 引擎

2026 年的主流做法是把 checkpoint 升级为 **journal + 重放恢复**，由专门的 durable execution 引擎承担：

| 引擎 | 特点 | 适用 |
|---|---|---|
| Temporal | 事件溯源 + 重放，多语言，生态成熟；OpenAI Agents SDK 集成已 GA | 长时、有副作用、审计要求高的任务 |
| Inngest | Serverless 原生，自带 AgentKit；LLM 调用不占函数计费时钟 | 事件驱动、小团队快速上线 |
| Restate | 单二进制/sidecar，与 Vercel AI SDK / PydanticAI 集成 | 自托管、轻量接入（注意 BSL 协议） |
| DBOS | Postgres 即运行时，MIT 协议 | 已重度使用 Postgres 的团队 |

典型模式：

```text
Agent 循环（每一步 = activity / step）
    ↓ journal 持久化每步输入输出
Durable Engine（Temporal / Inngest / …）
    ↓
外部存储（Postgres / Redis）
```

关键收益：**崩溃恢复时不会重复已完成的 LLM 调用，也不会重复已发生的外部副作用**（发过的邮件不会重发）。在真实负载测算中，引擎费用通常不到 LLM token 账单的 1%，选型主要看架构匹配度。

## 沙箱与权限

Agent 能执行代码或调用 API 时，沙箱是底线。2026 年的事实标准是 **Firecracker microVM**（AWS Lambda 同款技术）：每次执行跑在独立 Linux 内核里，提供硬件级隔离，冷启动约 150–500ms（预热可 <100ms）。

主流沙箱选型：

| 沙箱 | 隔离技术 | 特点 | 适用 |
|---|---|---|---|
| E2B | Firecracker microVM | 冷启动快；支持暂停/恢复（约 4s/GiB）、快照 fork；托管 / BYOC / 自托管（运行时 Apache 2.0 开源）；无 GPU；单会话最长 24h | 跑不可信 LLM 生成代码的默认选项 |
| Modal | gVisor（默认）/ Kata | 有 GPU（A100/H100）；无会话时长限制 | GPU 密集型 Agent 负载 |
| Daytona | Firecracker（2026-06 起闭源） | 开发者环境向 | 团队 devbox 场景 |
| 自研 | Docker + gVisor / Kata Containers | 完全可控 | 有合规与定制需求的团队 |

2026-04 起 OpenAI Agents SDK 已把沙箱做成原生能力（首发集成 E2B、Modal、Cloudflare、Daytona、Blaxel、Runloop、Vercel 等），自建 Runtime 时通常直接采购沙箱 API 而不是自研。

文件、网络、API 三层权限依然要单独收紧：

- **文件访问**：只读挂载、路径白名单、禁止 `..`。
- **网络访问**：egress 白名单、禁止访问内部管理面。
- **API 调用**：按工具配置权限标签，Runtime 校验 caller 身份。

```yaml
tools:
  write_file:
    allowed_paths: ["/tmp/agent-output"]
    requires_approval: true
  query_db:
    allowed_roles: ["data-analyst"]
```

## 评测与 Eval

Agent 上线前需要建立评测集：

| 评测维度 | 说明 |
|---|---|
| **任务成功率** | 是否能完成目标 |
| **步数效率** | 平均需要多少步；**循环卡死占比**（研究表明 WebArena 类环境中约一半失败是陷入循环而非上下文耗尽） |
| **工具调用准确率** | 工具选择、参数是否正确（逐步归因，而不是只看最终答案） |
| **幻觉率** | 是否编造工具结果 |
| **延迟/成本** | 平均耗时与 token 消耗 |
| **安全合规** | 护栏触发率、越权尝试 |

2025–2026 年评测范式的四个变化：

1. **在线评测（online eval）崛起**：静态 benchmark 会高估能力——Online-Mind2Web（2025）显示前沿 Agent 在真实网站上的能力比静态 benchmark 低最多 59%。生产环境应对 5–20% 的真实流量轨迹做异步采样评测。
2. **轨迹级（trajectory-level）评测**：只看最终答案无法定位失败，业界转向逐步分析 tool selection、argument correctness、plan adherence，并对长程任务做 step-level 失败归因。
3. **Agent-as-a-Judge**：复杂开放任务的评测从单次 LLM 打分演进为带工具、多步推理的 Agent 评审；使用时要注意位置偏置与“偏好冗长回答”的偏差。
4. **LLM Judge 校准成为硬要求**：与 200+ 条人工标注 trace 校准（Cohen's kappa > 0.7）、judge 与生成模型不同家族（避免自偏好）、冻结 judge 版本、季度刷新 gold set、主观打分前先跑确定性检查（JSON 合法性、必填字段）。

评测方法组合：

- 固定离线评测集 + 人工标注（回归）。
- 影子运行：新版本与旧版本并行，对比结果。
- A/B 测试：按流量切分模型或策略。
- 在线轨迹采样 + Agent-as-judge（生产质量大盘）。

## 可观测体系

生产 Agent Runtime 需要：

| 类型 | 工具 | 关注点 |
|---|---|---|
| Trace | OpenTelemetry（GenAI 语义约定）+ LangSmith / Langfuse | 每轮 thought、tool call、observation；span 树 `invoke_agent` → `chat` → `execute_tool` |
| Metrics | Prometheus + Grafana | 任务成功率、步数、工具调用分布、token 成本、循环卡死率 |
| Logs | Loki / ELK | 结构化事件、错误堆栈 |
| HITL | 内部审批系统 | 待审批、已审批、已拒绝 |

2026 年的落地要点：

- **采集层用 OpenTelemetry，后端可换**。Langfuse（OTel 原生，可自托管）与 LangSmith（LangGraph 体验最深，2026-07 起支持 OTLP 接入）都支持 GenAI 约定；注意约定整体仍是 Development 状态，升级 collector 时要关注 attribute rename。
- LangSmith 2026 年推出 Engine 做失败轨迹自动聚类；Langfuse 提供 agent graph 视图与工具参数级检查。核心指标都应对齐 tenant/user 维度。
- prompt/response 内容采集保持 opt-in，避免隐私与合规风险。

关键告警：

- 任务失败率 > 阈值。
- 单任务步数异常高。
- 工具调用错误率突增。
- 护栏触发率突增。
- 单个用户 token 消耗异常。

## 多租户与配额

多业务方共享 Runtime 时需要：

- 按 tenant/user 隔离 session。
- 按 tenant 限制并发任务数、最大步数、token 预算。
- 按工具限制权限标签。
- 成本按 tenant 分摊。

## 常见踩坑

| 踩坑 | 原因 | 解法 |
|---|---|---|
| 无限循环 | 模型反复调用同一工具（约半数 Agent 失败源于此） | 设置 max_steps、去重检测、循环卡死监控告警 |
| 上下文爆炸 | 工具输出过长 | 摘要、截断、只保留关键结果 |
| 工具参数幻觉 | 模型编造参数 | JSON Schema + 参数校验 + 重试 |
| 状态丢失 | 进程崩溃 | Checkpoint 持久化；有副作用的任务改用 durable execution 引擎 |
| 崩溃重复副作用 | 恢复时重放已执行的外部调用 | journal + 幂等键；durable 引擎的活动去重 |
| 安全风险 | Agent 执行任意代码 | Firecracker 级沙箱 + 工具权限标签 |
| 可观测缺失 | 没记录 trace | 从 Day 0 接入 OpenTelemetry GenAI 约定 |
| 观测平台锁定 | 直接写死某家 SDK 的私有格式 | 采集层统一 OTLP，后端保持可替换 |
| 过度编排 | 用复杂框架做简单事 | 根据任务复杂度选型 |

## 本章小结

生产级 Agent Runtime 需要在部署形态、LLM Gateway 集成、长时任务 checkpoint（2026 年应优先评估 durable execution 引擎）、沙箱权限（Firecracker microVM 为事实标准）、评测（在线轨迹采样 + 轨迹级归因 + 校准过的 judge）、可观测（OTel GenAI 约定 + 可替换后端）、多租户等方面做系统设计。Runtime 本身不生产模型能力，但它是模型能力能否安全、稳定、经济地转化为业务价值的关键层。

**参考来源**

- [OpenAI Agents SDK — Production](https://platform.openai.com/docs/guides/agents)
- [LangGraph Persistence](https://langchain-ai.github.io/langgraph/concepts/persistence/)
- [E2B Documentation](https://docs.e2b.dev/)
- [E2B vs Modal 2026: Best Code Sandboxes for AI Agents](https://o-mega.ai/articles/where-ai-agents-run-code-e2b-vs-modal-2026)
- [Temporal Durable AI Agents](https://docs.temporal.io/ai)
- [Durable AI agents in 2026: Temporal, Inngest, DBOS, and Restate](https://www.reactify-solutions.com/articles/durable-ai-agents-2026)
- [AI Agent Evaluation (2026): Metrics, Frameworks, and Production Failures — Morph](https://www.morphllm.com/ai-agent-evaluation)
- [LLM-as-a-Judge Best Practices in 2026: Calibration, Bias, and Cost](https://futureagi.com/blog/llm-as-a-judge-best-practices-2026/)
- [Langfuse vs. LangSmith (2026)](https://www.datacamp.com/blog/langfuse-vs-langsmith)
- [AWS Bedrock Agents Developer Guide](https://docs.aws.amazon.com/bedrock/)
- [Azure AI Agent Service](https://learn.microsoft.com/en-us/azure/ai-services/agents/)

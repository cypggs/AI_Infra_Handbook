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

## 沙箱与权限

Agent 能执行代码或调用 API 时，沙箱是底线：

- **代码执行**：Docker、Firecracker、gVisor 隔离。
- **文件访问**：只读挂载、路径白名单、禁止 `..`。
- **网络访问**： egress 白名单、禁止访问内部管理面。
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
| **步数效率** | 平均需要多少步 |
| **工具调用准确率** | 参数是否正确 |
| **幻觉率** | 是否编造工具结果 |
| **延迟/成本** | 平均耗时与 token 消耗 |
| **安全合规** | 护栏触发率、越权尝试 |

评测方法：

- 固定测试集 + 人工标注。
- 影子运行：新版本与旧版本并行，对比结果。
- A/B 测试：按流量切分模型或策略。

## 可观测体系

生产 Agent Runtime 需要：

| 类型 | 工具 | 关注点 |
|---|---|---|
| Trace | OpenTelemetry / LangSmith | 每轮 thought、tool call、observation |
| Metrics | Prometheus + Grafana | 任务成功率、步数、工具调用分布、token 成本 |
| Logs | Loki / ELK | 结构化事件、错误堆栈 |
| HITL | 内部审批系统 | 待审批、已审批、已拒绝 |

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
| 无限循环 | 模型反复调用同一工具 | 设置 max_steps、去重检测 |
| 上下文爆炸 | 工具输出过长 | 摘要、截断、只保留关键结果 |
| 工具参数幻觉 | 模型编造参数 | JSON Schema + 参数校验 + 重试 |
| 状态丢失 | 进程崩溃 | Checkpoint 持久化 |
| 安全风险 | Agent 执行任意代码 | 沙箱 + 工具权限标签 |
| 可观测缺失 | 没记录 trace | 从 Day 0 接入 OpenTelemetry |
| 过度编排 | 用复杂框架做简单事 | 根据任务复杂度选型 |

## 本章小结

生产级 Agent Runtime 需要在部署形态、LLM Gateway 集成、长时任务 checkpoint、沙箱权限、评测、可观测、多租户等方面做系统设计。Runtime 本身不生产模型能力，但它是模型能力能否安全、稳定、经济地转化为业务价值的关键层。

**参考来源**

- [OpenAI Agents SDK — Production](https://platform.openai.com/docs/guides/agents)
- [LangGraph Persistence](https://langchain-ai.github.io/langgraph/concepts/persistence/)
- [AWS Bedrock Agents Developer Guide](https://docs.aws.amazon.com/bedrock/)
- [Azure AI Agent Service](https://learn.microsoft.com/en-us/azure/ai-services/agents/)

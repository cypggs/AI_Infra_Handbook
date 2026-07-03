# 最佳实践

> 一句话理解：**Agent OS 的最佳实践围绕“进程化、最小权限、可观测、可恢复、可治理”展开，避免把 Agent OS 做成另一个紧耦合的编排框架。**

## 进程设计

### ✅ 推荐做法

- 每个任务或每个用户会话对应一个 Agent 进程。
- 为 Agent 进程分配唯一 ID、命名空间与生命周期状态机。
- 进程状态变更（spawn/run/pause/terminate）必须持久化并审计。

### ❌ 反模式

- 把 Agent OS 当作全局单例，所有任务共享同一个 Agent 实例。
- 进程状态只存在内存中，重启后全部丢失。
- 不区分 foreground/background Agent，导致资源争抢。

## 调度

### ✅ 推荐做法

- 对多租户场景使用 Fair Share 或按权重调度。
- 以 Token 作为核心调度资源之一，设置租户级与任务级预算。
- 对长任务支持抢占与 checkpoint，避免霸占资源。
- 准入控制要考虑依赖服务健康状态。

### ❌ 反模式

- 所有 Agent 使用单一 FIFO 队列，忽略优先级与成本。
- 不限制 Token 预算，导致单次任务耗尽整月配额。
- 频繁抢占但不保存上下文，导致任务反复从头执行。

## 沙箱

### ✅ 推荐做法

- 按任务风险选择隔离级别：低风险用进程级，高风险用容器/VM 级。
- 默认拒绝所有网络与文件访问，按需白名单放行。
- Secret 通过 Vault 注入，不进入 Agent 上下文或日志。
- 工具调用次数、执行时间、Token 消耗必须设上限。

### ❌ 反模式

- 所有 Agent 共享同一个工作目录或文件系统。
- 授予 Agent 过高权限（如 root、全量数据库访问）。
- 把沙箱隔离完全交给外部容器，不在 Agent OS 层做能力管理。

## Workspace

### ✅ 推荐做法

- per-agent 工作区与共享 blackboard 分离，访问控制明确。
- 工作区数据按租户隔离，支持按 Agent ID 快速清理。
- checkpoint 与 artifact 分别存储，保留周期不同。
- 大文件/二进制文件放入对象存储，元数据放入数据库。

### ❌ 反模式

- 把 Workspace 当作无限增长的日志仓库。
- 不同 Agent 直接读写对方工作区，绕过 ACL。
- checkpoint 不压缩、不清理，存储成本爆炸。

## Registry

### ✅ 推荐做法

- Agent 类型、技能、工具都注册到 Registry，支持版本管理。
- 使用命名空间区分团队/项目/租户。
- entitlement 与 capability 分离：能力定义在 Registry，授权规则在 Policy Engine。
- 新版本灰度发布，旧版本保留一段时间便于回滚。

### ❌ 反模式

- Agent 类型硬编码在代码中，无法动态注册。
- 工具 schema 变更不通知消费者，导致调用失败。
- 没有版本管理，升级后无法回滚。

## 消息 / IPC

### ✅ 推荐做法

- 使用标准化协议（如 A2A、MCP）进行 Agent 间与 Agent-工具通信。
- 消息总线支持持久化、重放、死信队列。
- Agent 间消息携带 sender/receiver/tenant/trace_id。
- 对敏感消息加密或限制路由。

### ❌ 反模式

- Agent 之间直接调用私有 HTTP 接口，绕过 OS 治理。
- 消息没有 trace_id，无法做端到端追踪。
- 消息总线不做持久化，故障时丢失大量状态。

## 安全与治理

### ✅ 推荐做法

- MCP Host 作为策略执行点，所有工具调用必须经过校验。
- 敏感操作默认需要 HITL，支持按租户/工具/风险等级配置。
- 所有策略决策、工具调用、HITL 事件写入审计日志。
- 定期复盘审计日志，优化策略与 entitlement。

### ❌ 反模式

- 策略校验只在应用层做，Agent OS 层不做二次校验。
- HITL 只在出事后启用，日常全部自动放行。
- 审计日志不结构化，无法按 Agent/租户/工具检索。

## 可观测

### ✅ 推荐做法

- 每个 Agent 生命周期作为一个根 trace，LLM/工具/消息调用作为子 span。
- 定义标准 metrics：活跃 Agent 数、队列等待、Token 消耗、工具成功率、策略拒绝率。
- 日志必须包含 agent_id、tenant_id、event_type、timestamp。
- 保留 reasoning path，支持事后审计与调试。

### ❌ 反模式

- 只有应用层日志，没有 Agent OS 层生命周期事件。
- metrics 只关注 LLM 调用，不关注调度、隔离、治理。
- 把所有日志打印到 stdout，没有集中化与结构化。

## 恢复

### ✅ 推荐做法

- 长任务必须定期 checkpoint。
- 失败恢复分级：工具重试 → 步骤重试 → checkpoint 回滚 → 重新 spawn → HITL。
- 对连续失败的工具/服务启用熔断，避免级联故障。
- 恢复策略应可配置，不同 Agent 类型可设置不同阈值。

### ❌ 反模式

- 任何失败都直接终止任务，不尝试恢复。
- checkpoint 只保存输入输出，不保存权限与工作区状态。
- 无限重试导致 Token 与调用成本失控。

## 成本

### ✅ 推荐做法

- 为每个 Agent/任务/租户设置 Token 与调用预算。
- 实时监控成本，接近阈值时告警或限速。
- 按成本维度拆分账单：Token、工具调用、计算、存储、网络。
- 对低价值任务使用 cheaper 模型或限制工具调用次数。

### ❌ 反模式

- 只关注模型费用，忽略工具调用与计算资源成本。
- 没有预算上限，单任务耗尽配额。
- 所有任务使用最强模型，不做成本分级。

## 检查清单

| 维度 | 检查项 |
|---|---|
| 进程 | 是否有唯一 Agent ID、状态机、生命周期事件？ |
| 调度 | 是否有准入控制、优先级、预算、抢占机制？ |
| 沙箱 | 是否按风险分级隔离、限制资源与网络？ |
| 能力 | 是否通过 Registry 管理工具、版本、授权？ |
| 工作区 | 是否 per-agent 隔离、支持 checkpoint 与共享 blackboard？ |
| 消息 | 是否使用标准化协议、支持持久化与追踪？ |
| 安全 | MCP Host 是否作为策略执行点？敏感操作是否有 HITL？ |
| 可观测 | 是否有 trace、metrics、logs、reasoning path？ |
| 恢复 | 是否有 checkpoint、分级恢复、熔断机制？ |
| 成本 | 是否有 Token/调用/计算预算与实时告警？ |

## 本章小结

- Agent OS 的最佳实践是“进程化、最小权限、可观测、可恢复、可治理”。
- 避免把 Agent OS 做成紧耦合的编排框架或单纯的容器调度器。
- 检查清单覆盖进程、调度、沙箱、能力、工作区、消息、安全、可观测、恢复、成本十个维度。

**参考来源**
- [AIOS: LLM Agent Operating System](https://arxiv.org/abs/2403.16971)
- [Governed MCP: From Technical Specifications to Multi-Agent Governance](https://arxiv.org/abs/2604.16870)
- [MCP Specification](https://modelcontextprotocol.io/specification/2025-03-26/architecture)

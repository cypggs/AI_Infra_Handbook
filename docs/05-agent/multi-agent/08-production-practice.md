# 8. 企业生产实践

> 一句话理解：**生产环境的 Multi-Agent 要解决的不是“能不能协作”，而是“能不能在高并发、长时任务、多租户、高风险场景下稳定、可观测、可恢复地协作”**。

## 部署拓扑

### 拓扑 1：单体 Coordinator + Agent Worker 池

```text
Client → API Gateway → Coordinator Service
                          ↓
              MQ / Message Bus
                          ↓
        ┌─────┬─────┬─────┐
        ↓     ↓     ↓     ↓
      Agent Agent Agent Agent
      Worker Worker Worker Worker
```

适用：中小型系统、角色类型稳定。
要点：Coordinator 可水平扩展但需避免脑裂；Worker 无状态，状态外置。

### 拓扑 2：分域 Coordinator

按业务域划分多个 Coordinator，每个域内部自治，跨域通过联邦 Message Bus 通信。

适用：大型企业、多业务线、需要域内自治。
要点：域间消息需要标准化协议，避免循环依赖。

### 拓扑 3：Serverless Agent

每个 Agent 类型是独立函数/容器，事件驱动触发。

适用：负载波动大、希望按需付费。
要点：冷启动延迟、状态持久化、调试复杂度。

### 拓扑 4：跨组织 A2A 联邦

多个组织的 Agent 通过 A2A 协议互联：各方发布签名的 Agent Card，任务以 Task 为粒度跨组织流转，支持 SSE 流式更新与 gRPC 低延迟通道。

```text
组织 A                        组织 B
┌──────────────┐   A2A    ┌──────────────┐
│ Agent Card    │ ──────→ │ 发现 / 认证   │
│ Orchestrator  │ ←────── │ Task 执行    │
└──────────────┘          └──────────────┘
```

适用：供应链协同、跨平台客服、异构框架互联。
要点：签名 Agent Card 与 OAuth 2.0/mTLS 认证、跨组织审计日志、Task 状态机（含 input-required / auth-required 中断态）的人工恢复。

> 2026 年 Q3 起，托管与互联进一步收敛：Microsoft Agent Framework 发布 `agent-framework-hosting-a2a` 包（2026 年 7 月），可直接把进程内编排的 Agent / Workflow 以 A2A 服务端点暴露（原生 Agent Card 生成、技能发现）；Google ADK 2.0 各语言版（Python 2.0 GA 于 2026 年 5 月，Go 2.0 于 6 月，TypeScript 2.0 于 8 月）也内置了 A2A 暴露能力。“进程内编排 + 协议对外暴露”正在成为框架的默认组合。

## 并发与扩缩容

- **按角色扩容**：搜索 Agent 压力大时只扩容搜索 Agent，不影响其他角色。
- **并发控制**：为每个 Agent 设置最大并发任务数，防止某类 Agent 被压垮。
- **背压机制**：当 Blackboard 或消息队列堆积时，Coordinator 减缓任务分发。
- **优先级队列**：VIP 用户、人工升级任务优先处理。

## 持久化与 Checkpoint

Multi-Agent 任务可能持续数分钟到数小时，必须持久化：

```python
checkpoint.save(
    session_id=session_id,
    state={
        "coordinator_state": coordinator.dump(),
        "blackboard_version": blackboard.version,
        "pending_messages": bus.pending(),
        "agent_assignments": assignments,
    },
)
```

持久化内容应包括：

- Coordinator 当前状态。
- Blackboard 全部记录与版本。
- 未消费消息与在途请求。
- 每个 Agent 的任务分配与执行进度。
- 未完成的 HITL 请求。

2025 年后 **durable execution** 成为框架级能力而非自研负担：LangGraph 1.0（2025 年 10 月 GA）把自动 checkpoint/恢复内置为标配，此后持续增强（1.2.x 已支持跨主机崩溃的 error-handler resume；也有 Temporal 官方插件把图执行托管给 Temporal），Google ADK、Microsoft Agent Framework 同样提供会话级持久化。选型时优先使用框架内置机制，只在有自定义状态存储需求时才自行实现上面的 checkpoint 结构。

## 分布式消息队列

生产环境不要把 Message Bus 放在内存中。常见选择：

| 中间件 | 特点 | 适用 |
|---|---|---|
| Redis Streams | 轻量、低延迟、易集成 | 中小规模、低延迟 |
| RabbitMQ | 路由灵活、ACK 可靠 | 企业内网、复杂路由 |
| Kafka | 高吞吐、可回放 | 大规模、审计需求 |
| NATS JetStream | 云原生、轻量 | K8s 环境、事件驱动 |

## 权限隔离

| 隔离维度 | 做法 |
|---|---|
| **租户隔离** | 不同 tenant 的 Agent、Blackboard、Message Bus topic 物理或逻辑隔离 |
| **角色权限** | 通过 RBAC 限制 Agent 可调用技能与可写黑板区域 |
| **网络隔离** | 高权限 Agent 运行在独立网络段，访问内部 API 需 mTLS |
| **沙箱隔离** | 代码执行、文件写入必须进容器/Firecracker/gVisor |

## 成本与延迟

- **模型分级**：简单聚合用便宜模型，复杂推理用强模型。
- **缓存 Blackboard 读取**：热点数据缓存，减少重复 LLM 调用。
- **批量消息**：多个小消息合并发送，降低网络开销。
- **早停机制**：达到足够好的结果时提前终止，不跑满最大轮次。
- **token 预算**：为整个 Multi-Agent 任务设置总 token 上限。
- **消息与上下文压缩**：handoff 时用摘要而非全文传递历史；长会话启用事件压缩（如 Google ADK Event Compaction——用 LLM 把旧事件压缩为摘要状态；Google 官方公布的基准称可降约 38% token、18% 延迟，属官方口径，缺少独立第三方复现）。
- **拓扑剪枝**：学术研究（AgentPrune、AgentDropout、SafeSieve 等）表明，剪掉冗余 Agent 与通信边可再省 30%~50% token；Q-KVComm 更进一步探索 Agent 之间直接传压缩 KV Cache 而非文本（5~6 倍压缩比），代表“表示级通信”的方向，尚未大规模工程化。

## 人机协同（HITL）

高风险场景必须人工介入：

- 涉及资金、法律、医疗、安全的结论。
- Agent 之间出现无法调和的分歧。
- 需要人类确认的任务分配或 Handoff。

HITL 请求本身也是 Blackboard 的一条记录，所有相关 Agent 可见其状态。

## 失败恢复

| 失败类型 | 恢复策略 |
|---|---|
| 单个 Agent 失败 | 重试、切换到同角色其他 Agent、降级到简单策略 |
| 消息丢失 | 消息队列至少一次投递 + Agent 消费幂等 |
| Blackboard 不一致 | 版本号 + 事件溯源 + 定期快照 |
| Coordinator 宕机 | 从 checkpoint 恢复，选举新 Coordinator |
| 任务卡住 | 心跳检测 + 超时强制终止 + 人工告警 |

## 常见踩坑

| 踩坑 | 原因 | 解法 |
|---|---|---|
| 消息风暴 | Agent 互相频繁发消息 | 批量、限流、合并相似消息 |
| 黑板污染 | Agent 随意写入不可靠信息 | 权限控制、置信度、写前校验 |
| Coordinator 单点瓶颈 | 所有分配都经过 Coordinator | 分域、拍卖、去中心化 |
| 成本爆炸 | 每个 Agent 都调强模型 | 模型分级、缓存、早停 |
| 可观测缺失 | 没有跨 Agent trace | 从 Day 0 接入 OpenTelemetry |
| 无限讨论 | Peer-to-Peer 无终止条件 | 最大轮次 + 共识判定 |
| 步骤重复 / 角色漂移 | 角色描述含糊、Agent 不知该何时停（MAST 最常见失败模式） | 精确编写 role/instructions、显式终止条件、定期对执行轨迹做 MAST 式失败归因分析 |

## 本章小结

生产级 Multi-Agent 需要在部署拓扑、并发控制、持久化 checkpoint、分布式消息队列、权限隔离、成本延迟、HITL、失败恢复等方面做系统设计。Multi-Agent 的价值不是“Agent 越多越好”，而是“在受控的成本与风险下，让多个 Agent 稳定协作”。

**参考来源**

- [LangGraph Production Concepts](https://langchain-ai.github.io/langgraph/concepts/production_concepts/)
- [LangGraph v1 发布说明](https://docs.langchain.com/oss/python/releases/langgraph-v1)
- [AutoGen — Production](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/)
- [CrewAI — Enterprise](https://docs.crewai.com/enterprise/)
- [OpenAI Agents SDK — Tracing](https://openai.github.io/openai-agents-python/tracing/)
- [A2A Protocol 文档](https://a2a-protocol.dev/)
- [Microsoft Agent Framework Releases（hosting-a2a 包）](https://github.com/microsoft/agent-framework/releases)
- [ADK Python Releases（v2.0.0）](https://github.com/google/adk-python/releases)
- [Q-KVComm: Efficient Multi-Agent Communication via Adaptive KV Cache Compression](https://arxiv.org/abs/2512.17914)
- [Why Do Multi-Agent LLM Systems Fail?（MAST）](https://arxiv.org/abs/2503.13657)

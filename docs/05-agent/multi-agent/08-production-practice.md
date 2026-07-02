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

## 本章小结

生产级 Multi-Agent 需要在部署拓扑、并发控制、持久化 checkpoint、分布式消息队列、权限隔离、成本延迟、HITL、失败恢复等方面做系统设计。Multi-Agent 的价值不是“Agent 越多越好”，而是“在受控的成本与风险下，让多个 Agent 稳定协作”。

**参考来源**

- [LangGraph Production Concepts](https://langchain-ai.github.io/langgraph/concepts/production_concepts/)
- [AutoGen — Production](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/)
- [CrewAI — Enterprise](https://docs.crewai.com/enterprise/)
- [OpenAI Agents SDK — Tracing](https://openai.github.io/openai-agents-python/tracing/)

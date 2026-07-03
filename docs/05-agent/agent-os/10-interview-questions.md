# 面试题

> 一句话理解：**Agent OS 面试题围绕“如何把 Agent 当作进程来管理”展开，从基础概念到调度、隔离、治理、可观测与生产实践，层层递进。**

## 初级

### 1. 什么是 Agent OS？它和 Agent Runtime 有什么区别？

**参考答案要点**：

- Agent OS 是位于 Agent Runtime 之上的操作系统层，负责把 Agent 当作进程来管理（生命周期、调度、隔离、通信、治理、可观测）。
- Agent Runtime 负责单个 Agent 的执行循环（ReAct、工具调用、状态管理）。
- Agent OS 负责多个 Agent 的调度、资源隔离、权限治理与审计。

### 2. 把 Agent 抽象为进程有什么好处？

**参考答案要点**：

- 边界清晰：每个 Agent 有独立 ID、状态、工作区，避免状态污染。
- 资源可控：可以为每个进程分配 Token、时间、调用预算。
- 可调度：支持优先级、抢占、暂停/恢复。
- 可恢复：失败时可以重试、回滚或重新 spawn。
- 可审计：完整生命周期可追溯。

### 3. Agent OS 中的 Sandbox 主要做什么？

**参考答案要点**：

- 提供隔离执行环境。
- 限制 Agent 可调用的工具集合（allowlist）。
- 限制资源使用（调用次数、执行时间、Token、网络、文件系统）。
- 拦截并审计越权行为。

### 4. 什么是 Agent OS 中的 Workspace？

**参考答案要点**：

- 为每个 Agent 提供私有工作区。
- 提供共享 blackboard 供多 Agent 协作。
- 支持 checkpoint、artifact 与临时状态存储。
- 与 Memory 主题的区别：Workspace 关注“在哪里存、谁能访问”，Memory 关注“怎么检索、怎么向量化”。

### 5. MCP Host 在 Agent OS 中扮演什么角色？

**参考答案要点**：

- MCP Host 是 Agent 与外部工具/资源之间的中介。
- 负责 MCP Server 的生命周期管理、能力协商、权限边界。
- 在 Agent OS 中，MCP Host 是“系统调用门面”和策略执行点。

## 中级

### 6. 如何设计一个 Agent OS 的调度器？需要考虑哪些因素？

**参考答案要点**：

- 调度目标：公平性、优先级、成本、延迟、成功率。
- 资源维度：Token、调用次数、CPU、内存、网络、时间。
- 策略选择：FIFO、优先级队列、MLFQ、Fair Share、Token-aware。
- 准入控制：系统负载、租户配额、依赖服务健康状态。
- 抢占与恢复：支持暂停/恢复，保存 checkpoint。

### 7. AgentRM 与 HiveMind 的调度思路有什么不同？

**参考答案要点**：

- **AgentRM**：借鉴 OS 的 MLFQ，根据 Agent 历史行为（成功/失败/预算使用）调整优先级。
- **HiveMind**：以 Token 为核心资源，围绕 Token 预算进行准入、调度与抢占。
- 两者可以结合：MLFQ 负责优先级分层，Token 预算负责成本约束。

### 8. 如何在一个多租户 Agent OS 中实现资源隔离？

**参考答案要点**：

- 命名空间隔离：Agent ID、Workspace、Registry 按租户前缀隔离。
- 资源配额：Token、并发数、调用次数上限。
- 网络隔离：Network Policy / VPC。
- 数据隔离：行级安全、分表、独立存储桶。
- 能力隔离：entitlement 控制租户可使用的工具。
- 调度公平性：Fair Share 防止单一租户霸占资源。

### 9. Agent OS 中的 Policy Engine 应该在哪些节点介入？

**参考答案要点**：

- Agent spawn：校验是否允许创建该类型 Agent、是否超出租户配额。
- 工具调用前：校验能力白名单、参数、预算、时间策略。
- 敏感操作：触发 HITL。
- 消息发送：校验跨 Agent/跨租户通信权限。
- 终止时：校验最终状态与审计要求。

### 10. 如何设计 Agent OS 的可观测体系？

**参考答案要点**：

- Trace：Agent 生命周期为根 span，LLM/工具/消息调用为子 span。
- Metrics：活跃 Agent 数、队列等待、Token 消耗、工具成功率、策略拒绝率、HITL 次数。
- Logs：结构化 JSON，包含 agent_id、tenant_id、event_type、timestamp、payload。
- Reasoning Trace：记录 Agent 思考路径，支持审计。
- 与 OpenTelemetry、Prometheus、Loki/ELK 集成。

## 高级

### 11. 比较 AIOS、Agent libOS、Quine 三种 Agent OS 实现路径的优劣。

**参考答案要点**：

- **AIOS**：内核式，系统性强，适合研究与统一调度；但扩展性受限于内核本身。
- **Agent libOS**：库式，低延迟、适合边缘；但隔离性弱，多 Agent 共享进程。
- **Quine**：POSIX 进程式，与 Linux 生态完全兼容，隔离强；但对 Token/上下文等 LLM 特定资源调度不够原生。
- 选型取决于场景：研究/统一调度选 AIOS，边缘/低延迟选 libOS，强隔离/云原生选 Quine。

### 12. 如果 Agent 调用外部工具时陷入死循环，Agent OS 应该如何处理？

**参考答案要点**：

- **预算限制**：Token、调用次数、执行时间上限。
- **调度器抢占**：超过时间片后强制暂停。
- **熔断**：对重复调用同一工具/同一参数进行熔断。
- **检测**：通过 Observer 识别异常模式（如调用次数激增、循环调用）。
- **恢复**：暂停后保存 checkpoint，人工或自动分析原因后恢复。
- **终止**：无法恢复时安全终止并回收资源。

### 13. 如何在大规模 Agent 集群中实现一致性调度状态？

**参考答案要点**：

- 使用共享状态存储（etcd、PostgreSQL、Redis）保存 Agent 状态、队列、配额。
- 调度器可以集中式（单 leader）或分片式（按租户/命名空间）。
- 对状态变更使用乐观锁或分布式锁，避免竞态。
- 关键事件（spawn/terminate/预算耗尽）持久化到消息队列，保证最终一致。
- 控制面多活，数据面分区。

### 14. Governed MCP 与 ProbeLogits 分别从哪个层面增强 Agent 安全？

**参考答案要点**：

- **Governed MCP**：在 MCP Host 层增加治理规则，覆盖能力注册、授权、审计、consent、HITL，是“系统调用级”治理。
- **ProbeLogits**：在 LLM 生成阶段探测 logits，识别有害输出或越权意图，是“模型生成级”治理。
- 两者互补：Governed MCP 管外部能力，ProbeLogits 管模型内部输出。

### 15. 设计一个企业级 Agent OS，你会如何划分模块与边界？

**参考答案要点**：

- 分层：应用层（Runtime/Planning/Multi-Agent）、服务层（Process/Scheduler/Sandbox/Capability/Workspace/Registry/Message/Policy/Observer/Recovery）、内核层（Kernel/Resource/Security/Audit）、基础设施层（MCP/LLM/Persistence/MQ）。
- 边界：
  - Runtime 负责单 Agent 执行，OS 负责多 Agent 管理。
  - Planning 决定“做什么”，OS 负责“怎么调度执行”。
  - MCP Host 是 OS 的工具/资源系统调用门面。
  - Workspace 管存储访问控制，Memory 管内容检索。
- 非功能：多租户、可观测、安全合规、成本核算、高可用、可恢复。

## 本章小结

- 初级题聚焦概念：Agent OS 与 Runtime 的区别、进程抽象、Sandbox、Workspace、MCP Host。
- 中级题聚焦设计：调度器、多租户隔离、Policy Engine、可观测体系。
- 高级题聚焦架构与难点：AIOS/libOS/Quine 对比、死循环处理、一致性调度、Governed MCP/ProbeLogits、企业级模块划分。

**参考来源**
- [AIOS: LLM Agent Operating System](https://arxiv.org/abs/2403.16971)
- [Agent libOS: A Library Operating System for LLM Agents](https://arxiv.org/abs/2606.03895)
- [Quine: LLM agents as native POSIX processes](https://arxiv.org/abs/2603.18030)
- [AgentRM: A Resource Management Framework for LLM Agents](https://arxiv.org/abs/2603.13110)
- [HiveMind: Token-Centric Scheduling for LLM Agents](https://arxiv.org/abs/2604.17111)
- [Governed MCP: From Technical Specifications to Multi-Agent Governance](https://arxiv.org/abs/2604.16870)
- [ProbeLogits: Probing LLM Logits for Safety and Governance](https://arxiv.org/abs/2604.11943)
- [MCP Specification](https://modelcontextprotocol.io/specification/2025-03-26/architecture)

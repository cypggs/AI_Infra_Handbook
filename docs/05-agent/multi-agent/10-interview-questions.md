# 10. 面试题

## 初级

### Q1：Multi-Agent 与单 Agent 有什么区别？

**参考答案**：

- 单 Agent 是一个 LLM 在 ReAct 循环中调用工具、读写记忆。
- Multi-Agent 是多个具有不同角色和技能的 Agent，通过消息传递、协调器调度、共享状态共同完成复杂任务。
- Multi-Agent 解决的是任务拆分、角色专业化、并行与协作问题。

### Q2：什么是 Handoff？

**参考答案**：

Handoff 是当前 Agent 主动把任务和上下文交给另一个 Agent 继续处理。常用于客服升级、阶段移交。关键是上下文必须完整传递，避免接收 Agent 重复询问。

### Q3：Multi-Agent 中为什么需要 Blackboard？

**参考答案**：

Blackboard 是多个 Agent 共享的工作区，保存任务目标、中间结果、假设和最终结论。它解决 Agent 之间的信息不对称问题，但也会带来读写冲突，需要版本控制和权限管理。

## 中级

### Q4：Manager-Worker 与 Peer-to-Peer 各有什么优缺点？

**参考答案**：

- Manager-Worker：职责清晰、易于监控，但 Manager 是瓶颈，Worker 之间缺乏直接沟通。适合任务可拆解、角色清晰的场景。
- Peer-to-Peer：灵活、能多角度碰撞，但容易发散、终止条件难定。适合讨论、评审、头脑风暴。

### Q5：Multi-Agent 中消息总线应该提供哪些能力？

**参考答案**：

点对点投递、广播、请求-回复、消息优先级、TTL、至少一次投递保证、顺序保证、幂等消费、按 task/session 路由。

### Q6：如何避免 Multi-Agent 陷入无限讨论？

**参考答案**：

- 设置最大轮次或最大步数。
- 定义明确的终止条件（共识达成、置信度阈值、目标完成）。
- 检测重复观点或无进展状态。
- 对 Peer-to-Peer 引入主持人或仲裁 Agent。

### Q7：Multi-Agent 的可观测需要记录什么？

**参考答案**：

每个 Agent 的输入输出、工具调用、Agent 之间的消息流转、Blackboard 写入历史、Coordinator 的决策理由、任务整体状态与 trace。

## 高级

### Q8：设计一个生产级 Multi-Agent 系统，你会怎么设计？

**参考答案**：

- **控制面与数据面分离**：控制面管理 Agent 注册、角色策略、权限；数据面负责消息流转与执行。
- **Agent Registry**：动态注册发现，支持版本与状态。
- **Message Bus**：基于 Redis/Kafka/NATS，保证可靠投递与顺序。
- **Blackboard**：结构化共享状态，带版本与权限。
- **Coordinator**：支持多种协作模式，可插拔调度策略。
- **状态持久化**：Checkpoint 到 Postgres/Redis，支持中断恢复。
- **权限隔离**：租户隔离、角色权限、网络隔离、沙箱执行。
- **可观测**：OpenTelemetry trace + Prometheus metrics + 结构化日志。
- **HITL**：高风险或分歧场景请求人工。
- **评测**：固定测试集 + 影子运行 + A/B 测试。

### Q9：LangGraph 与 AutoGen 在 Multi-Agent 上的主要区别是什么？

**参考答案**：

- AutoGen 以“对话/群聊”为核心抽象，Agent 通过消息历史共享状态，适合探索性对话与代码执行场景。
- LangGraph 以“状态图”为核心抽象，Agent 是图节点，共享显式 State，支持 checkpoint、条件边、人工介入，适合复杂生产工作流。

### Q10：如何处理 Agent 之间的冲突？

**参考答案**：

- 低影响冲突：投票或加权投票。
- 专业冲突：按 Agent 可信度加权。
- 重大冲突：引入仲裁 Agent 或人类介入。
- 所有冲突与异议应记录到 Blackboard，保留审计痕迹。

### Q11：Multi-Agent 中如何做成本控制？

**参考答案**：

- 模型分级：简单聚合用便宜模型，复杂推理用强模型。
- 早停机制：结果足够好时提前终止。
- 缓存：热点 Blackboard 数据与 LLM 响应缓存。
- 批量消息：减少网络往返。
- Token 预算：为整个任务设置总 token 上限。
- 避免过度协调：不要为简单任务引入过多 Agent。

## 本章小结

面试中关于 Multi-Agent 的问题通常集中在：**与单 Agent 的区别**、**协作模式对比**、**消息总线与 Blackboard 设计**、**可观测**、**生产架构**、**框架对比**、**冲突解决**与**成本控制**。掌握本章问题，基本可以覆盖中级到高级面试场景。

**参考来源**

- [AutoGen Documentation](https://microsoft.github.io/autogen/stable/)
- [LangGraph Multi-Agent Concepts](https://langchain-ai.github.io/langgraph/concepts/multi_agent/)
- [CrewAI Documentation](https://docs.crewai.com/)
- [OpenAI Agents SDK — Handoffs](https://openai.github.io/openai-agents-python/handoffs/)

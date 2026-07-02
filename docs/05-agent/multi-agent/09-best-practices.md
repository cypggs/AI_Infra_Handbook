# 9. 最佳实践

> 一句话理解：**Multi-Agent 的最佳实践不是“Agent 越多越好”，而是“角色边界清晰、消息契约稳定、协调恰到好处、可观测贯穿始终、评测驱动迭代”**。

## 1. 角色与技能设计

- **一个 Agent 一个核心职责**。避免“既当架构师又当测试员”的模糊角色。
- **技能宁少勿多**。每个 Agent 的工具数量控制在 3~7 个，过多会降低决策质量。
- **技能输入输出结构化**。用 JSON Schema 定义，避免模型自由发挥。
- **危险技能加标签**。例如 `write`、`delete`、`network`、`financial`，供护栏使用。

## 2. 消息契约

- **消息格式统一**。所有 Agent 之间使用同一套 message schema。
- **必须携带 trace 上下文**。`task_id`、`session_id`、`correlation_id`、`from`、`to` 缺一不可。
- **避免自由文本负载**。能用结构化字段表达就不用长文本。
- **设置 TTL 与优先级**。防止消息堆积拖垮系统。

## 3. 避免过度协调

- **能单 Agent 解决就不要 Multi-Agent**。不要为了用框架而拆角色。
- **Manager-Worker 不要过深**。通常两层 Manager 足够，过深会增加延迟和错误传播。
- **Peer-to-Peer 设置硬终止条件**。否则容易陷入无尽讨论。
- **不要每个决策都走协商**。固定流程用 Pipeline，动态分配用 Auction，减少不必要的协调开销。

## 4. 冲突解决

- **先定义冲突标准**。什么情况下算“分歧”？分数差异、结论矛盾、置信度阈值。
- **低 stakes 用投票，高 stakes 用人工**。不要所有冲突都交给人类。
- **保留异议记录**。即使最终采纳多数意见，也要把少数意见写入 Blackboard 备查。
- **引入仲裁 Agent**。仲裁 Agent 应拥有更高权限和更全面的上下文。

## 5. 可观测优先

- **从 Day 0 设计跨 Agent trace**。没有 trace 的 Multi-Agent 系统无法调试。
- **记录协调器决策理由**。为什么选 Agent A 而不是 Agent B？需要可解释。
- **黑板写入即事件**。每次写入都记录 author、version、timestamp。
- **按 task_id 串联所有事件**。一个任务可能跨多个 Agent、多个服务，trace 必须能串起来。

## 6. 版本管理

- **Agent 定义版本化**。Role、Skill、Prompt、模型配置都要能回滚。
- **Registry 支持多版本并存**。新版本可以先灰度，再全量。
- **协议版本化**。Message schema、Blackboard schema 变更时保持向后兼容。
- **A/B 测试按 Agent 维度切流**。而不是简单按用户随机切。

## 7. 评测指标

| 指标 | 说明 |
|---|---|
| **任务成功率** | 最终是否达成用户目标 |
| **协作效率** | 平均参与 Agent 数、平均消息数、平均步数 |
| **结果一致性** | 多次运行结果是否稳定 |
| **冲突率** | 需要仲裁或人工介入的比例 |
| **延迟/成本** | 端到端耗时与 LLM token 消耗 |
| **安全合规** | 越权调用、敏感信息泄露、护栏触发率 |

## 8. 渐进式落地

- **阶段 1：单 Agent + 工具**。先验证业务价值。
- **阶段 2：双 Agent Handoff**。例如一线客服 → 资深客服。
- **阶段 3：Manager-Worker**。引入任务拆分与结果聚合。
- **阶段 4：多模式混合**。根据场景组合 Pipeline、Auction、Peer-to-Peer。
- **阶段 5：自治优化**。基于历史数据动态调整角色与调度策略。

## 最佳实践速查表

| 维度 | 推荐做法 |
|---|---|
| 角色设计 | 一 Agent 一职责；技能少而精；危险技能加标签 |
| 消息契约 | 统一 schema；带 trace 上下文；结构化负载；TTL + 优先级 |
| 协调策略 | 按需选型，避免过度协调；Peer 设终止条件 |
| 冲突解决 | 低 stakes 投票；高 stakes 人工；保留异议；仲裁 Agent |
| 可观测 | Day 0 trace；记录协调理由；黑板写入即事件 |
| 版本管理 | Agent/Skill/协议版本化；灰度发布；A/B 按 Agent 切流 |
| 评测 | 成功率、协作效率、一致性、冲突率、延迟成本、安全合规 |
| 落地路径 | 单 Agent → Handoff → Manager-Worker → 混合模式 → 自治优化 |

## 本章小结

Multi-Agent 的最佳实践覆盖了角色设计、消息契约、协调策略、冲突解决、可观测、版本管理、评测与渐进落地八个方面。核心原则是：**用清晰的抽象把复杂性收敛到可控模块，让系统从第一天就可观测、可评测、可回滚**。

**参考来源**

- [AutoGen Best Practices](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/)
- [LangGraph Production Guide](https://langchain-ai.github.io/langgraph/concepts/production_concepts/)
- [CrewAI — Best Practices](https://docs.crewai.com/concepts)
- [OpenAI Agents SDK — Best Practices](https://openai.github.io/openai-agents-python/)

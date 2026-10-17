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

- **能单 Agent 解决就不要 Multi-Agent**。MAST 对 1600+ 条执行轨迹的分析显示，多 Agent 系统的失败率远高于预期，协调开销引入的错误常常超过认知增益；上线前应用单 Agent 基线做对照实验。
- **Manager-Worker 不要过深**。通常两层 Manager 足够，过深会增加延迟和错误传播。
- **Peer-to-Peer 设置硬终止条件**。否则容易陷入无尽讨论。
- **不要每个决策都走协商**。固定流程用 Pipeline，动态分配用 Auction，减少不必要的协调开销。
- **控制 Agent 数量**。研究表明多智能体辩论在 4~5 个 Agent 后收益趋于饱和，更多 Agent 主要带来成本与对齐问题。

## 4. 冲突解决

- **先定义冲突标准**。什么情况下算“分歧”？分数差异、结论矛盾、置信度阈值。
- **低 stakes 用投票，高 stakes 用人工**。不要所有冲突都交给人类。
- **保留异议记录**。即使最终采纳多数意见，也要把少数意见写入 Blackboard 备查。
- **引入仲裁 Agent**。仲裁 Agent 应拥有更高权限和更全面的上下文。

## 5. 失败模式驱动设计（MAST 清单）

上线前与每次大改后，用 MAST 失败分类法对执行轨迹做归因自检：

| 检查项 | 对应 MAST 失败模式 | 预防措施 |
|---|---|---|
| 角色/任务描述是否精确无歧义 | 不遵守规范、角色漂移 | 为每个 Agent 写清职责边界与“不做什么” |
| 是否存在步骤重复与死循环 | 步骤重复（最常见，约 15.7%） | 执行轨迹去重检测 + 最大步数硬限制 |
| 对话历史与黑板是否在 handoff 时完整传递 | 丢失对话历史、对话被重置 | handoff 携带摘要 + 校验接收方上下文完整性 |
| Agent 是否知道何时停止 | 不了解终止条件、过早终止 | 显式终止条件写进 instructions，终止前强制自检 |
| 接收方输入是否被认真阅读 | 忽略其他 Agent 输入、不主动澄清 | 关键决策要求引用上游产出；歧义时强制澄清轮 |
| 结论是否经过独立验证 | 验证不完整/错误 | 专门的 verifier Agent 或工具级校验，而非自我宣布完成 |

## 6. 可观测优先

- **从 Day 0 设计跨 Agent trace**。没有 trace 的 Multi-Agent 系统无法调试。
- **记录协调器决策理由**。为什么选 Agent A 而不是 Agent B？需要可解释。
- **黑板写入即事件**。每次写入都记录 author、version、timestamp。
- **按 task_id 串联所有事件**。一个任务可能跨多个 Agent、多个服务，trace 必须能串起来。

## 7. 版本管理

- **Agent 定义版本化**。Role、Skill、Prompt、模型配置都要能回滚。
- **Registry 支持多版本并存**。新版本可以先灰度，再全量。
- **协议版本化**。Message schema、Blackboard schema 变更时保持向后兼容。
- **A/B 测试按 Agent 维度切流**。而不是简单按用户随机切。

## 8. 评测指标

| 指标 | 说明 |
|---|---|
| **任务成功率** | 最终是否达成用户目标 |
| **协作效率** | 平均参与 Agent 数、平均消息数、平均步数 |
| **结果一致性** | 多次运行结果是否稳定 |
| **冲突率** | 需要仲裁或人工介入的比例 |
| **失败归因** | 按 MAST 分类统计失败分布，定位系统性短板 |
| **延迟/成本** | 端到端耗时与 LLM token 消耗 |
| **安全合规** | 越权调用、敏感信息泄露、护栏触发率 |

## 9. 渐进式落地

- **阶段 1：单 Agent + 工具**。先验证业务价值，留下基线指标。
- **阶段 2：双 Agent Handoff**。例如一线客服 → 资深客服，用对照实验验证优于单 Agent。
- **阶段 3：Manager-Worker**。引入任务拆分与结果聚合。
- **阶段 4：多模式混合**。根据场景组合 Pipeline、Auction、Peer-to-Peer，以及 Supervisor/Swarm/Hierarchical。
- **阶段 5：协议互联**。需要跨团队、跨组织协作时，通过 A2A 暴露/发现 Agent，用 MCP 统一工具接入。
- **阶段 6：自治优化**。基于历史数据与失败归因（MAST 式分析）动态调整角色与调度策略。

## 最佳实践速查表

| 维度 | 推荐做法 |
|---|---|
| 角色设计 | 一 Agent 一职责；技能少而精；危险技能加标签 |
| 消息契约 | 统一 schema；带 trace 上下文；结构化负载；TTL + 优先级 |
| 协调策略 | 按需选型，避免过度协调；Peer 设终止条件；Agent 数量控制在 5 个以内，除非对照数据证明更多有收益 |
| 冲突解决 | 低 stakes 投票；高 stakes 人工；保留异议；仲裁 Agent |
| 失败预防 | 对照 MAST 清单做轨迹归因；显式终止条件；handoff 校验上下文完整性 |
| 可观测 | Day 0 trace；记录协调理由；黑板写入即事件 |
| 版本管理 | Agent/Skill/协议版本化；灰度发布；A/B 按 Agent 切流 |
| 评测 | 成功率、协作效率、一致性、冲突率、失败归因、延迟成本、安全合规 |
| 落地路径 | 单 Agent → Handoff → Manager-Worker → 混合模式 → A2A 互联 → 自治优化 |

## 本章小结

Multi-Agent 的最佳实践覆盖了角色设计、消息契约、协调策略、冲突解决、失败模式预防、可观测、版本管理、评测与渐进落地九个方面。核心原则是：**先用单 Agent 建立基线，再以对照数据证明多 Agent 的收益；用清晰的抽象把复杂性收敛到可控模块，让系统从第一天就可观测、可评测、可回滚**。

**参考来源**

- [Why Do Multi-Agent LLM Systems Fail?（MAST）](https://arxiv.org/abs/2503.13657)
- [LangGraph Production Guide](https://langchain-ai.github.io/langgraph/concepts/production_concepts/)
- [LangChain Docs — Handoffs](https://docs.langchain.com/oss/python/langchain/multi-agent/handoffs)
- [AutoGen Best Practices](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/)
- [CrewAI — Best Practices](https://docs.crewai.com/concepts)
- [OpenAI Agents SDK — Best Practices](https://openai.github.io/openai-agents-python/)

# 最佳实践

> 一句话理解：**好的 Planning 不是让计划尽可能完美，而是让计划“足够好、可验证、可调整、不添乱”。**

本章以清单形式总结 Planning 设计与落地的最佳实践，覆盖计划粒度、表示方式、触发器设计、模型选择、测试、与 Reflection 配合等方面。

## 1. 计划粒度：先骨架，后细化

- 初始计划不要过细，用 3-7 个高层步骤描述主路径。
- 每个高层步骤可在执行前再细化为子计划。
- 避免“一个 prompt 生成 50 步”的过度规划，容易 rigid 且成本高。

```
差：
1. 打开文件
2. 读取第 1 行
3. 读取第 2 行
...

好：
1. 读取并解析文件
2. 提取关键字段
3. 生成摘要
```

## 2. DAG 优先

- 能用 DAG 表达的计划，优先用 DAG 而不是列表。
- DAG 能表达并行与依赖，是生产中最通用的计划表示。
- 仅在严格串行、无分支的场景使用列表。

## 3. 把计划当作 artifact

- 计划应能独立存储、展示、审计、回滚。
- 每个计划版本都有 ID、父版本、生成时间、生成原因。
- 计划格式应稳定，便于下游 Runtime 消费。

## 4. 触发器设计要克制

- 不是所有失败都需要重规划。
- 重规划触发器应考虑：失败类型、失败次数、冷却时间、进展程度。
- 设置硬上限，防止风暴。

## 5. 避免过度规划

- 对不确定的环境，保留“执行后再决定”的空间。
- 用骨架计划 + 动态细化，而不是一次性生成完整细节。
- 定期评估：计划对任务成功率提升是否值得其成本。

## 6. 模型选择分层

| 用途 | 推荐模型类型 | 说明 |
|---|---|---|
| 复杂目标解析与重规划 | 强模型 | 需要推理与全局观 |
| 简单步骤填充与格式化 | 轻量模型 | 成本低、延迟低 |
| 计划验证中的语义检查 | 规则 + 小模型 | 可解释、可控 |
| 观测评估 | 规则/LLM-as-judge | 根据输出类型选择 |

不要所有 Planning 决策都走最强模型，成本会失控。

## 7. 计划必须可验证

- 每个步骤都应有明确的完成标准。
- 对模型生成类步骤，定义自动校验规则或 LLM-as-judge 标准。
- 避免“分析原因”“思考一下”这类无法判断成败的步骤。

```
差：分析销售下降原因
好：输出导致销售下降的前 3 个因素，每个因素附带数据证据
```

## 8. 约束前置

- 把安全、合规、业务约束在计划生成阶段就纳入。
- 通过 Plan Validator 在执行前拦截违规计划。
- 约束应可配置，而不是硬编码在 prompt 中。

## 9. 设计可回滚的步骤

- 对可能失败的步骤，提前考虑回滚或补偿方案。
- 高危操作先创建 checkpoint。
- 工具调用尽量幂等，便于重试。

## 10. 与 Reflection 紧密配合

- Reflection 的输出应结构化，便于 Planner 消费。
- 把失败案例写入 Plan Memory，避免重复犯错。
- 对反复出现的失败模式，考虑在 Planner prompt 中加入针对性提示。

## 11. 人机协同有的放矢

- 只在高风险、高不确定性、高影响节点引入 HITL。
- 提供清晰的上下文，让人能快速判断。
- 支持预授权，避免重复审批。

## 12. 测试 Planning

Planning 层需要专门的测试策略：

| 测试类型 | 说明 |
|---|---|
| 单元测试 | 每个模块的输入输出 |
| 集成测试 | Planner → Validator → Executor → Observer → Replan Trigger 完整循环 |
| 模拟测试 | 用模拟 LLM 和工具测试各种失败路径 |
| 回归测试 | 对历史失败案例验证新策略是否改善 |
| 对抗测试 | 构造模糊目标、矛盾约束、工具缺失等边界情况 |
| 成本测试 | 评估不同场景下的 token 与工具调用成本 |

## 13. 监控与可观测性

- 记录每个计划版本的生成原因与 diff。
- 监控重规划频率、失败分类、任务完成率。
- 对异常模式（如连续重规划、计划版本爆炸）自动告警。

## 14. 持续迭代

- Planning 不是一次性设计，需要根据生产数据持续优化。
- 定期复盘：哪些计划经常失败？哪些重规划是有效的？
- 把优化后的模式固化为分解模板或约束规则。

## 15. 推理预算显式化（2025-2026）

- 给 Planner 设置 thinking token 预算、最大扩展轮数、并行采样次数 N，全部纳入 Policy Engine 统一管控。
- 规划是最值得加码计算的阶段：预算紧张时优先保 Planner，砍 Executor/Verifier 的冗余采样。
- 跟踪”单任务推理预算”分布，把它像成本一样监控与告警。

## 16. 规划时搜索、执行时线性

- MCTS/LATS 式树搜索收益显著（HumanEval、WebShop 等基准上成倍提升），但只在**环境可模拟、动作可回滚**时安全。
- 把搜索限制在 plan-time：选出最优路径后交给 Executor 线性执行，不在运行时做树搜索。
- 不可逆动作（发邮件、转账、删库）不进模拟分支，只走显式计划 + HITL。

## 17. 任务分布稳定时，训练专用 Planner

- 当任务分布稳定、调用量大、且有（或可构造）成功轨迹时，用 Plan-and-Act 式合成数据管线或层级 RL 训练专用 Planner，性价比通常优于持续堆提示工程。
- 训练前先确认评测集与数据管线，避免”优化出一个过拟合特定基准的 Planner”。
- 无法训练时，退而求其次：沉淀工作流模板（AWM 思路），从历史成功轨迹中归纳可复用计划骨架注入 Planner 上下文。

## 最佳实践清单

```markdown
- [ ] 计划粒度采用骨架 + 细化
- [ ] 优先使用 DAG 表示依赖
- [ ] 计划作为可审计 artifact
- [ ] 重规划触发器设置冷却与上限
- [ ] 避免过度规划
- [ ] 按任务复杂度分层选择模型
- [ ] 每个步骤定义可验证的完成标准
- [ ] 安全/合规约束前置到计划生成阶段
- [ ] 高危步骤支持回滚或补偿
- [ ] Reflection 输出结构化并沉淀到 Plan Memory
- [ ] HITL 只在关键节点使用
- [ ] 建立 Planning 专用测试体系
- [ ] 完善的监控、告警与审计
- [ ] 基于生产数据持续迭代
- [ ] Planner 推理预算显式化并纳入 Policy
- [ ] 树搜索限制在规划阶段，执行保持线性
- [ ] 任务分布稳定时评估训练式 Planner / 工作流沉淀
```

## 本章小结

- 好的 Planning 强调”足够好、可验证、可调整、不添乱”。
- 计划粒度、DAG 优先、plan-as-artifact、触发器克制、避免过度规划是核心原则。
- 模型选择、约束前置、回滚设计、Reflection 配合、HITL、测试、监控、持续迭代共同构成生产落地的最佳实践。
- 2025-2026 年的新增纪律：推理预算显式化、”规划时搜索、执行时线性”、任务分布稳定时训练专用 Planner 或沉淀工作流。

**参考来源**
- [Planning for Agents - LangChain Blog](https://blog.langchain.dev/planning-for-agents/)
- [Tree of Thoughts: Deliberate Problem Solving with Large Language Models](https://arxiv.org/abs/2305.10601)
- [Language Agent Tree Search Unifies Reasoning Acting and Planning](https://arxiv.org/abs/2310.04406)
- [Scaling Test-Time Compute for LLM Agents](https://arxiv.org/abs/2506.12928)
- [Plan-and-Act: Improving Planning of Agents for Long-Horizon Tasks](https://arxiv.org/abs/2503.09572)
- [Agent Workflow Memory](https://arxiv.org/abs/2409.07429)
- [LangGraph Plans](https://langchain-ai.github.io/langgraph/concepts/plans/)
- [OpenAI Agents SDK Handoffs](https://openai.github.io/openai-agents-python/handoffs/)
- [AutoGen Planning Tutorial](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/planning.html)

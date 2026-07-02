# 9. 最佳实践

> 一句话理解：**好的 Reflection 系统不是让 Agent 多跑几轮，而是让每一轮都“有的放矢”——标准清晰、Critic 聚焦、循环有界、结果可沉淀、策略可迭代**。

## 1. Criteria-First：先定义标准，再写 Critic

在构建 Critic 之前，先把“好答案”的标准写下来。Criteria 应该：

- **可观测**：能通过 draft 本身或外部工具判断，而不是“感觉更好”。
- **可分级**：区分 must-have 和 nice-to-have，避免 Critic 对所有问题一视同仁。
- **可量化**：每个标准最好对应一个可打分维度。

示例（代码生成）：

```markdown
- [must] 代码可编译
- [must] 核心测试用例通过
- [should] 类型注解完整
- [nice] 注释清晰、命名规范
```

Critic 的 prompt 应直接引用这些 criteria，减少自由发挥。

## 2. 让 Critic 足够聚焦

一个什么都批判的 Critic 会让 Generator 无所适从。建议：

- **每轮只聚焦 1~3 个最关键问题**：避免一次性抛出 10 条反馈。
- **按优先级排序**：major 问题先修，minor 问题可以留到后续轮次。
- **给出具体位置**：指出问题出现在 draft 的哪一段、哪一行、哪个函数。
- **提供修改建议**：不仅说“错在哪里”，还说“可以怎么改”。

示例：

```text
问题 1 [major]: 第 3 行缺少错误处理，当 Redis 连接失败时会直接抛异常。
建议：使用 try/except 包装，并添加重试逻辑。
```

## 3. 严格限制循环边界

无限循环是 Reflection 最常见的生产事故之一。必须设置：

- **max_iterations**：硬上限，建议 2~5 轮。
- **score_threshold**：明确通过标准。
- **改进饱和检测**：连续 N 轮 score 提升小于 delta 时终止。
- **重复反馈检测**：本轮 critique 与上一轮高度相似时终止。
- **总体 timeout**：覆盖整个 Reflection Loop。

```python
terminate = (
    score >= threshold
    or iteration >= max_iter
    or improvement_saturated
    or critique_repeated
    or elapsed >= timeout
)
```

## 4. 保留历史最佳版本

Generator 可能会“越改越差”。Loop 应始终记录并保留历史最高分的 draft。

```python
best_draft = max(all_drafts, key=lambda d: d["score"])
```

如果最终未通过，可以返回“最佳尝试 + 已知问题列表”，而不是半成品。

## 5. 人工兜底不可少

即使 Reflection 自动化程度很高，也要为以下场景预留人工入口：

- 连续多轮无法通过。
- 涉及安全、合规、伦理。
- 用户明确反馈不满意。
- 高风险领域（医疗、法律、金融）。

人工反馈要回流到系统，用于优化 criteria、Critic prompt 和 Evaluator 校准。

## 6. 把反思结果持久化

Reflection 的价值不仅在于当前回答更好，还在于长期经验积累：

- **每轮 draft、critique、score 写入 Workspace**。
- **每个 episode 写入 Memory**，包含任务类型、最终答案、关键教训。
- **定期聚类 critique 类型**，发现系统性问题并优化训练数据或 prompt。

## 7. 策略版本管理

Critic 的 criteria、Evaluator 的 rubric、Generator 的 revise prompt 都是“策略”，应该版本化：

- 使用 Git 管理 prompt 和 rubric 的变更。
- A/B 测试不同策略的效果。
- 记录每个 episode 使用的策略版本，便于回溯。

## 8. 外部验证优先

能用外部工具验证的维度，不要让 LLM 自己判断：

| 维度 | 外部工具 |
|---|---|
| 代码正确性 | 编译器、单元测试、类型检查器 |
| 事实准确性 | 检索、数据库、知识图谱 |
| 数值计算 | Python / Wolfram / 计算器 |
| 安全合规 | 规则引擎、敏感词检测、审计系统 |
| 性能 | 基准测试、profiler |

外部验证不仅更客观，还能减少 Critic 的 token 消耗。

## 9. 按任务配置反思策略

不同任务需要不同的 Reflection 策略：

| 任务类型 | 建议策略 |
|---|---|
| 简单问答 | 不开启 Reflection |
| 文本润色 | 1~2 轮，Critic 关注风格与一致性 |
| 代码生成 | 3~5 轮，结合编译器/测试作为 Critic |
| 复杂规划 | 3~5 轮，关注可行性、风险、资源约束 |
| 多 Agent 审稿 | 2~3 轮审稿，多 Critic 投票 |
| 高风险输出 | 强制人工批准 |

避免“一刀切”地给所有任务开启同样配置的 Reflection。

## 10. 监控与告警

Reflection 系统需要专门的监控指标：

| 指标 | 说明 |
|---|---|
| `reflection.iterations` | 每任务平均迭代次数 |
| `reflection.pass_rate` | 最终通过比例 |
| `reflection.score_distribution` | score 分布 |
| `reflection.latency_p99` | 反思阶段 P99 延迟 |
| `reflection.cost_per_task` | 每任务 token 成本 |
| `reflection.human_escalation_rate` | 人工升级比例 |

当 pass_rate 下降或 human_escalation_rate 上升时，应及时检查 Critic 和 Evaluator。

## 11. 避免“为了反思而反思”

Reflection 是手段，不是目的。在引入 Reflection 前，先问自己：

- 单轮 LLM 的错误是否真的能被 Reflection 修复？
- 增加的延迟和成本是否值得？
- 是否有明确的评估标准？
- 是否有高质量 Critic 或验证工具？

如果答案多为否，可能更好的做法是优化 base prompt、增加 few-shot 示例，或引入 Retrieval。

## 本章小结

Agent Reflection 的最佳实践可以总结为：criteria-first、Critic 聚焦、循环有界、保留最佳版本、人工兜底、结果持久化、策略版本化、外部验证优先、按任务配置、持续监控。遵循这些原则，可以避免 Reflection 变成“多轮生成却不见效”的形式主义，真正发挥自我纠错的价值。

**参考来源**

- [Self-Refine: Iterative Refinement with Self-Feedback](https://arxiv.org/abs/2303.17651)
- [Reflexion: Self-Reflective Agents](https://arxiv.org/abs/2303.11366)
- [CRITIC: Large Language Models Can Self-Correct with Tool-Interactive Critiquing](https://arxiv.org/abs/2305.11738)
- [LangGraph Blog — Reflection Agents](https://blog.langchain.dev/reflection-agents/)

# 面试题

> 一句话理解：**Planning 面试题考察的是从“单次模型调用”到“长程自治系统”的设计思维，核心在于目标拆解、计划表示、执行反馈、动态调整与生产落地。**

本章按初、中、高级整理 Planning 相关面试题，涵盖概念、实现与生产落地。

## 初级

### Q1：什么是 Agent Planning？与单次 prompt 有什么区别？

**参考答案**：
Agent Planning 是 Agent 中负责把高层目标拆解为可执行计划，并在执行过程中根据反馈动态调整的层。与单次 prompt 不同，Planning 强调多步、结构化、可观测、可回滚。单次 prompt 适合明确短程任务，Planning 适合长程复杂任务。

### Q2：ReAct 和 Plan-and-Execute 的主要区别是什么？

**参考答案**：
ReAct 把推理与行动交错进行，计划是隐式的，每步只决定下一步行动。Plan-and-Execute 先显式生成完整计划，再按顺序执行，失败时可重规划。ReAct 灵活但缺乏全局视图，Plan-and-Execute 更可解释、可审计。

### Q3：常用的计划表示有哪些？各有什么优缺点？

**参考答案**：
常见计划表示包括列表、DAG、树、状态图。列表简单但无法表达依赖；DAG 能表达并行与依赖，是生产中最常用；树适合分层任务但难以表达跨分支依赖；状态图适合有明确生命周期和分支的任务。

### Q4：Planning 层为什么要和 Runtime 层分离？

**参考答案**：
Planning 负责“做什么”，Runtime 负责“怎么调度执行”。分离后职责清晰，Planning 可以独立演化（如更换 Planner 模型），Runtime 可以专注于并发、超时、重试、生命周期管理。两者通过标准计划格式交互。

### Q5：什么是重规划风暴？如何防护？

**参考答案**：
重规划风暴指系统因同一失败反复触发重规划，导致成本飙升、无进展。防护措施包括设置冷却时间、最大重规划次数、失败分类（可恢复/不可恢复）、进展检测、成本上限、兜底策略。

## 中级

### Q6：设计一个 Plan-Execute-Observe-Replan 循环，画出关键组件与数据流。

**参考答案要点**：

- 组件：Planner、Plan Store、Scheduler、Executor、Observer、Replan Trigger、Policy Engine。
- 流程：Planner 生成计划并存入 Plan Store；Scheduler 按依赖调度；Executor 执行步骤；Observer 评估结果；Replan Trigger 决定是否重规划；Policy Engine 控制终止与兜底。
- 数据流：目标 → 计划 → 执行事件 → 观测结论 → 重规划决策 → 新计划。

### Q7：DAG 计划如何调度执行？如果执行中某个步骤失败，如何处理依赖该步骤的后续步骤？

**参考答案要点**：

- 每次选择所有依赖都已成功的步骤执行；可用拓扑排序或动态就绪检测。
- 若某步骤失败，依赖它的后续步骤应被标记为阻塞或失败，不能执行。
- 根据失败类型决定：局部修复、子计划替换、全局重规划或终止。

### Q8：Observer 的设计需要注意什么？

**参考答案要点**：

- Observer 不能只看是否抛异常，要评估业务目标是否达成。
- 输出应结构化，包含状态、失败分类、是否可恢复、关键指标。
- 对模型生成内容可引入 LLM-as-judge 或规则校验。
- 记录足够上下文供 Reflection 和审计使用。

### Q9：如何选择 Planning 方案？ReAct、Plan-and-Execute、ToT、LangGraph 各适合什么场景？

**参考答案要点**：

- ReAct：短程、工具链简单、允许探索的任务。
- Plan-and-Execute：目标明确、步骤可预见的 SOP 型任务。
- ToT：需要多路径探索的推理、决策、创意任务。
- LangGraph：复杂控制流、条件分支、循环、并行的工作流。

### Q10：Planning 如何与 Reflection 配合？

**参考答案要点**：

- Reflection 从失败中总结根因与改进建议，输出结构化结论。
- Planner 根据 Reflection 建议生成新计划。
- 建议写入 Plan Memory，帮助未来 Planning 避免类似失败。
- 高 confidence 建议自动应用，低 confidence 建议转人工审核。

## 高级

### Q11：设计一个企业级 Planning 层的架构，说明如何与 Runtime、Memory、Reflection、Multi-Agent、MCP、Tool Use 集成并划分边界。

**参考答案要点**：

- Planning 层分为控制面（Goal Parser、Decomposer、Planner、Validator、Replan Trigger、Policy）和数据面（Plan Store、Plan Memory、Checkpoint Store）。
- Runtime 消费计划并负责调度、并发、生命周期；Planning 不干预执行细节。
- Memory 提供上下文与历史，Planning 读写 Plan Store 和 Plan Memory，但不处理向量化。
- Reflection 输出失败分析，Planning 据此重规划。
- Multi-Agent 解决“谁来做”，Planning 解决“做什么”；可采用中央 Planner 或分布式 Planner。
- MCP/Tool Use 提供能力抽象，Planning 通过 Gateway 调用，不直接处理协议细节。

### Q12：如何保证生产环境中 Planning 的可控性与安全性？

**参考答案要点**：

- 计划验证：语法、语义、安全、资源、业务约束检查。
- HITL：关键节点人工审批。
- 重规划防护：冷却、上限、进展检测、失败分类。
- 审计：计划版本、执行状态、重规划原因、人工决策全记录。
- 成本与 SLO：设置预算、监控 token 与工具调用、告警异常模式。

### Q13：Planning 层的模型选择策略是什么？

**参考答案要点**：

- 复杂目标解析与全局重规划用强模型。
- 简单格式化、步骤填充用轻量模型。
- 验证与观测评估用规则 + 小模型/LLM-as-judge。
- 建立模型路由与缓存，避免所有决策都走最强模型。
- 对关键路径可用 ensemble 或规则兜底。

### Q14：如何处理 Planning 中的目标漂移问题？

**参考答案要点**：

- Goal Parser 把目标结构化为可验证的成功标准。
- 关键节点做目标一致性检查，确保执行未偏离原始目标。
- 计划作为 artifact 被审计，可回溯。
- 用户修正目标时显式生成新版本计划，而不是隐式混入当前执行。

### Q15：如果你要为一个现有系统引入 Planning 层，会如何分阶段落地？

**参考答案要点**：

1. **评估**：识别哪些任务需要 Planning，是否满足启用条件。
2. **最小闭环**：用 Plan-and-Execute 实现一个垂直场景，验证价值。
3. **完善模块**：补充 Observer、Replan Trigger、Policy、Validator。
4. **集成周边**：接入 Memory、Reflection、Multi-Agent、MCP。
5. **生产加固**：审计、HITL、成本监控、重规划风暴防护。
6. **持续优化**：基于生产数据迭代分解模板、约束规则与模型策略。

## 本章小结

- 初级题聚焦概念与基础对比。
- 中级题关注循环设计、DAG 调度、Observer、方案选型与 Reflection 配合。
- 高级题要求能设计企业级架构、保证可控安全、处理目标漂移、制定落地方案。

**参考来源**
- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)
- [Planning for Agents - LangChain Blog](https://blog.langchain.dev/planning-for-agents/)
- [Tree of Thoughts: Deliberate Problem Solving with Large Language Models](https://arxiv.org/abs/2305.10601)
- [LangGraph Plans](https://langchain-ai.github.io/langgraph/concepts/plans/)
- [OpenAI Agents SDK Handoffs](https://openai.github.io/openai-agents-python/handoffs/)
- [AutoGen Planning Tutorial](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/planning.html)

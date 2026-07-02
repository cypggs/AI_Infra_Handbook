# 10. 面试题

> 一句话理解：**面试中关于 Reflection 的问题，核心考察你是否理解“生成—批判—评估—修订”的闭环，以及它与 ReAct、Memory、Multi-Agent 的区别与协作方式**。

## 初级

### Q1：什么是 Agent Reflection？

Agent Reflection 是 Agent 在生成输出后，主动对自身输出进行批判、评估和修订的能力。它把“一次性生成”变成“迭代优化”，帮助 Agent 在代码生成、内容创作、规划决策等复杂任务中持续逼近正确解。

### Q2：Reflection 和普通的“多轮对话”有什么区别？

多轮对话通常是与用户交替进行，用户给出下一轮输入；Reflection 是 Agent 内部的自我纠错循环，不依赖用户反馈，由 Generator、Critic、Evaluator 自动完成。

### Q3：Reflection 的核心步骤有哪些？

典型的 Reflection Loop 包括：

1. **Generate**：生成 draft。
2. **Critique**：检查 draft 的问题。
3. **Evaluate**：把 critique 量化为 score/verdict。
4. **Revise**：根据反馈修订 draft。
5. **Terminate**：达到质量标准或触发兜底策略时终止。

### Q4：为什么要限制最大迭代次数？

防止无限循环。Generator 和 Critic 可能陷入“反复修改同一问题”或“越改越差”的死循环，max_iter 是硬性护栏。

### Q5：什么是 Critic？它有什么用？

Critic 是 Reflection 系统中负责检查 draft 的模块。它根据预定义的 criteria 输出问题列表或 LGTM，帮助 Generator 发现自身遗漏或错误。

## 中级

### Q6：Reflection 和 ReAct 有什么关系？

ReAct 是“思考—行动—观察”的循环，强调与外部环境（工具、API）交互；Reflection 是“生成—批判—修订”的循环，强调对内部输出的自我纠错。两者可以结合：ReAct 负责执行，Reflection 负责在执行或生成后检查和修正。

### Q7：如何避免 Critic 过严或过松？

- **过严**：收紧 criteria、降低 Critic 温度、要求 Critic 区分 major/minor 问题。
- **过松**：增加外部验证工具、细化 criteria、引入多 Critic 投票或人工审核。
- 还可以通过人工标注数据集校准 Critic 输出。

### Q8：Reflection 如何与 Memory 集成？

Reflection 产生的 draft、critique、score、最终答案可以写入 Memory：

- 短期：保存在 Workspace 中供当前 loop 使用。
- 长期：作为 episode 写入，支持后续相似任务的检索与复用。
- 策略层：统计 critique 类型，优化 Critic prompt 和训练数据。

### Q9：如何设计一个好的 Evaluator？

好的 Evaluator 应该：

- 基于明确的 rubric 打分。
- 输出可比较的标量 score 和离散 verdict。
- 与人工打分高度一致（通过人工标注校准）。
- 支持多维评分，避免单一维度主导。

### Q10：生产环境什么时候不建议开启 Reflection？

- 延迟敏感型任务（实时对话、流式首句）。
- 创意发散任务，过度反思会降低多样性。
- 评估标准模糊、人工都难以判断的任务。
- 单轮 LLM 已经表现足够好、反思收益有限的任务。

## 高级

### Q11：如何设计一个可扩展的 Reflection 框架？

一个可扩展的 Reflection 框架应包含：

- **可插拔的 Generator / Critic / Evaluator**：支持不同模型和策略。
- **Policy 引擎**：按任务类型动态选择 criteria 和阈值。
- **Workspace**：统一的中间产物存储，支持读写隔离与历史版本。
- **Revision Controller**：编排循环、管理终止条件、处理异常与人工升级。
- **Observer**：记录 trace、metrics、事件，便于调试与监控。
- **Memory 接口**：把反思结果写入长期记忆。

### Q12：Reflection 在多 Agent 系统中如何应用？

群体反思（Group Reflection）中，不同 Agent 扮演不同角色：

- **Generator**：负责生成 draft。
- **Critic(s)**：多个 Agent 从不同角度批判。
- **Evaluator / Aggregator**：汇总评分，决定是否通过。
- **Revision Controller**：协调修订过程。

Multi-Agent 提供通信与协调机制，Reflection 提供“批判—修订”的语义。

### Q13：如何处理“越改越差”的问题？

- 保留历史最佳版本，最终未通过时返回最佳尝试。
- 引入收敛检测，score 连续下降或波动时终止。
- 要求 Generator 逐条回应 critique，避免偏离原意。
- 人工介入高风险修改。

### Q14：外部工具在 Reflection 中扮演什么角色？

外部工具提供客观反馈，弥补 LLM 自评的不足。典型工具：

- 编译器、单元测试、类型检查器（代码生成）。
- 检索、数据库、知识图谱（事实校验）。
- 规则引擎、敏感词检测（合规检查）。

外部验证结果可以作为 Critic 输入或直接作为 Evaluator 的维度。

### Q15：OpenAI o1 / reasoning models 与显式 Reflection 框架有什么异同？

相同点：都通过“思考—反思—修正”提升复杂任务表现。

不同点：

- o1 的反思过程发生在模型内部，通过训练习得，对外不可见、不可控。
- 显式 Reflection 框架把 Generator、Critic、Evaluator 拆分为独立模块，便于定制、监控、干预和审计。

实际系统中可以结合：用 o1 作为 Generator 或 Critic，同时在更高层用显式框架做策略控制和人工兜底。

## 本章小结

Reflection 面试题从概念到架构、从模块设计到生产实践层层递进。回答时抓住三个核心：

1. **闭环**：generate → critique → evaluate → revise → terminate。
2. **边界**：与 ReAct、Memory、Multi-Agent、Planning 的区别与协作。
3. **落地**：Critic 设计、评分校准、终止条件、人工兜底、与 Memory/Runtime 集成。

**参考来源**

- [Self-Refine: Iterative Refinement with Self-Feedback](https://arxiv.org/abs/2303.17651)
- [Reflexion: Self-Reflective Agents](https://arxiv.org/abs/2303.11366)
- [CRITIC: Large Language Models Can Self-Correct with Tool-Interactive Critiquing](https://arxiv.org/abs/2305.11738)
- [Tree of Thoughts: Deliberate Problem Solving with Large Language Models](https://arxiv.org/abs/2305.10601)
- [LangGraph Reflection Tutorial](https://langchain-ai.github.io/langgraph/tutorials/reflection/reflection/)
- [AutoGen Reflection](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/reflection.html)
- [OpenAI o1 / Reasoning Models](https://openai.com/index/learning-to-reason-with-llms/)

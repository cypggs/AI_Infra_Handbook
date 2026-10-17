# 背景

> 一句话理解：**从 prompt engineering、CoT 到 ReAct，再到显式 Planning，Agent 的“思考方式”正在从一次性生成演变为可持久化、可回滚、可重规划的多步计划。**

早期的大模型应用大多是“单轮问答”：用户给一段 prompt，模型直接输出答案。这种方式对开放域闲聊、摘要、翻译等任务有效，但对需要多步操作、依赖外部信息、目标模糊的长程任务则显得力不从心。Agent Planning 的出现，正是为了把“想到哪做到哪”升级为“先规划、再执行、边观察、边调整”。

## 单轮 prompt engineering 的局限

prompt engineering 的核心是“把任务写清楚”。通过角色设定、示例、格式要求、约束条件等，让模型一次性生成理想输出。

典型问题：

- **上下文长度限制**：复杂任务需要大量背景信息，单轮 prompt 难以承载。
- **无法利用中间反馈**：模型无法在执行过程中调用工具、查询数据库或验证中间结果。
- **错误累积**：一旦某一步推理出错，后续输出往往一错到底。
- **目标漂移**：用户目标可能模糊或动态变化，单轮模型难以对齐。

## 多轮 CoT：让模型“一步步想”

Chain-of-Thought（CoT）通过让模型生成中间推理步骤，显著提升了数学、逻辑、代码等任务的准确率。

```text
Q: 一个农场有鸡和兔，头共 35 个，脚共 94 只，问鸡兔各多少？
A: 设鸡 x 只，兔 y 只。x + y = 35，2x + 4y = 94……
```

CoT 的本质是把“黑盒输出”变成“可解释的推理链”。但它仍然是单轮生成，模型一旦落笔就无法回头，也无法与外部环境交互。

## ReAct：把推理与行动交错

ReAct（Reasoning + Acting）把 CoT 与工具调用结合起来，形成“思考 → 行动 → 观察 → 再思考”的交错循环。

```mermaid
graph LR
    Thought[思考] --> Action[行动]
    Action --> Observation[观察]
    Observation --> Thought
```

ReAct 解决了“模型如何与外界交互”的问题，但它的计划是隐式的：每一步的“思考”只决定下一步行动，没有全局任务结构。对于长程复杂任务，这种局部决策容易导致：

- **目标遗忘**：前期目标在后续步骤中被稀释。
- **重复探索**：没有全局路线图，模型可能反复尝试相似路径。
- **难以审计**：计划的“意图”散落在多轮 Thought 中，难以回溯。

## 显式 Planning：把计划作为一等公民

显式 Planning 的核心思想是：在执行前，先把整个任务拆解成结构化的计划；执行过程中，计划可以被观测、被修改、被重规划。

```mermaid
graph TD
    Goal[用户目标] --> Planner[Planner 生成计划]
    Planner --> Plan[结构化计划]
    Plan --> Executor[Executor 执行]
    Executor --> Observer[Observer 观测]
    Observer --> Replan[Replan Trigger 决定是否重规划]
    Replan -->|需要| Planner
    Replan -->|完成| Result[结果输出]
```

这种范式下，计划成为 Agent 的一等公民（first-class artifact），具备以下能力：

- **可解释**：人可以阅读、审核、修改计划。
- **可执行**：每个计划项对应明确的动作或子目标。
- **可观测**：执行状态实时反馈到计划上。
- **可回滚**：失败时可以回退到某个 checkpoint。
- **可重规划**：环境变化时重新生成或局部调整计划。

## Planning 解决的三类问题

| 问题类型 | 说明 | 示例 |
|---|---|---|
| 目标模糊 | 用户只说“帮我优化这个系统”，没有明确指标和约束 | 自动澄清目标、拆解为可验证子任务 |
| 多步依赖 | 后续步骤依赖前一步输出，存在顺序或并行关系 | 用 DAG 表示依赖，调度器按拓扑执行 |
| 动态环境 | 外部状态变化、工具失败、结果不达预期 | 触发器检测异常，Planner 重新生成计划 |

## 典型场景

- **代码助手**：把“帮我重构这段代码”拆成分析、提取函数、替换调用、运行测试、修复错误等步骤。
- **数据分析**：把“分析本季度销售下滑原因”拆成数据提取、清洗、指标计算、归因、可视化、报告生成。
- **运维排障**：把“排查线上告警”拆成查询监控、定位日志、分析链路、假设验证、修复、复盘。
- **旅行规划**：把“安排一次家庭日本游”拆成目的地选择、签证、机票酒店、行程、预算、备选方案。

这些任务的共同点是：无法通过单次模型调用完成，需要显式规划、多步执行、动态调整。

## 2025-2026：推理模型时代的规划新范式

2024 年底以来，以 OpenAI o1/o3、DeepSeek-R1 为代表的**推理模型（Reasoning Model）**把"模型想多久"变成了可伸缩的测试时计算（test-time compute）：通过在推理阶段投入更多计算做自我验证与回溯，数学、代码等任务的规划能力大幅提升。这让业界一度认为"显式 Planning 会被推理模型内化掉"，但 2025-2026 年的基准数据给出了相反结论：

- **简单任务确实在饱和**。斯坦福 HAI《AI Index 2026》显示，计算机操作基准 OSWorld 的 SOTA 从 2024 年的 12.2% 提升到 66.3%（Claude Opus 4.5），已接近 72% 的人类基线；WebArena、GAIA 等基准的最优系统也已达到或超过人类水平。
- **长程任务仍是硬骨头**。面向长程真实任务的 OSWorld 2.0（2026）上，最强系统也仅在 20% 左右。差距不在单步推理，而在**多步计划的质量、错误传播的控制与动态重规划**——这正是显式 Planning 层的价值所在。

与此同时，Planning 本身也在被重新发明，形成几条清晰的技术主线：

1. **规划与执行分离 + 学习化**：不再只靠 prompt 让模型"现场规划"，而是用合成轨迹标注、强化学习直接训练 Planner。Plan-and-Act（ICML 2025）用合成数据训练出专用 Planner，在 WebArena-Lite 上取得 57.6% 成功率；HiPER（ICML 2026）用层级强化学习训练"高层出子目标、低层做执行"的双层策略，在 ALFWorld 上达到 97.4%。
2. **自适应分层规划**：AdaPlan-H（ACL 2026 Findings）先给出粗略全局计划，再按任务复杂度自适应细化，避免"过度规划"造成的浪费与僵化。
3. **搜索式规划**：LATS（ICML 2024）用 MCTS 把推理、行动、规划统一在树搜索中；AFlow（ICLR 2025）进一步用 MCTS 直接搜索"工作流代码"，让 7B 级小模型以约 4.6% 的成本击败 GPT-4o。
4. **测试时计算扩展**：对 Agent 任务的系统研究（2025）表明，并行采样（Best-of-N）、序贯修正、Verifier 合并等手段可稳定提升规划质量——例如 Best-of-N 将 GAIA 平均得分从 55.8% 提升到 63.0%。
5. **神经符号规划**：2025 年的共识是"LLM 负责建模与解释、符号求解器负责校验"——LLM 生成 PDDL 或约束，经典规划器/验证器求解，失败时把错误信息作为结构化反馈驱动有界修复循环。

```mermaid
graph TD
    A[学习式 Planner：Plan-and-Act / HiPER] --> P[高质量计划]
    B[自适应分层：AdaPlan-H] --> P
    C[搜索式规划：LATS / AFlow] --> P
    D[测试时计算扩展：BoN / Verifier] --> P
    E[神经符号校验：PDDL + 有界修复] --> P
    R[推理模型 o1 / R1 / o3] -.提供推理底座.-> A
    R -.提供推理底座.-> C
    P --> X[长程任务成功率]
```

本章后续内容会在这些主线展开：核心思想（02）讲任务分解与计划表示的最新演进，架构（03）与循环（04）讲工程化组件，源码分析（06）对比 ReWOO、LATS、AFlow、Plan-and-Act、HiPER 等方案的取舍。

## 本章小结

- 单轮 prompt 和 CoT 适合明确、短程任务；ReAct 增加了行动与观察，但计划仍是隐式的。
- 显式 Planning 把计划提升为一等公民，解决了目标模糊、多步依赖、动态环境三类核心问题。
- 2025-2026 年的推理模型并没有取代 Planning，反而催生了学习式 Planner、自适应分层、搜索式规划、测试时计算扩展、神经符号校验五条新主线。
- Planning 是 Agent 长程自治的基础，也是后续架构与工程实践的出发点。

**参考来源**
- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)
- [Chain-of-Thought Prompting Elicits Reasoning in Large Language Models](https://arxiv.org/abs/2201.11903)
- [Planning for Agents - LangChain Blog](https://blog.langchain.dev/planning-for-agents/)
- [Understanding the Planning of LLM Agents: A Survey](https://arxiv.org/abs/2402.02716)
- [Plan-and-Act: Improving Planning of Agents for Long-Horizon Tasks](https://arxiv.org/abs/2503.09572)
- [HiPER: Hierarchical Reinforcement Learning with Explicit Credit Assignment for LLM Agents](https://arxiv.org/abs/2602.16165)
- [Scaling Test-Time Compute for LLM Agents](https://arxiv.org/abs/2506.12928)
- [Stanford HAI AI Index Report 2026](https://hai.stanford.edu/assets/files/ai_index_report_2026.pdf)
- [OSWorld 2.0: Benchmarking Computer Use Agents on Long-Horizon Real-World Tasks](https://arxiv.org/abs/2606.29537)

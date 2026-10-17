# 企业生产实践

> 一句话理解：**在生产中启用 Planning 层，不是为了“让 Agent 更聪明”，而是为了让长程复杂任务可预测、可控制、可审计、可回滚。**

本章讨论 Planning 在企业落地时的关键问题：何时启用独立 Planning 层、如何与相邻模块集成、如何防止重规划风暴、如何实现人机协同与审计。

## 何时启用独立 Planning 层

不是所有 Agent 都需要独立 Planning 层。以下场景建议启用：

| 场景特征 | 说明 |
|---|---|
| 任务步骤通常超过 5 步 | 需要显式计划避免目标漂移 |
| 存在复杂依赖或并行 | 需要 DAG/图调度 |
| 工具/Agent 数量多 | 需要 Planner 统一选择与编排 |
| 失败恢复成本高 | 需要 checkpoint、回滚、重规划 |
| 需要人工审批或审计 | 计划必须作为可解释 artifact |
| 目标模糊或可能变化 | 需要动态重规划 |

反之，如果只是简单的“调用一次搜索 API 然后总结”，ReAct 或单次 prompt 就足够了。

## 与 Runtime 集成

Planning 层与 Runtime 层的集成方式决定了系统的灵活性与稳定性。

### 集成模式

| 模式 | 说明 | 适用 |
|---|---|---|
| Planning 生成完整计划，Runtime 只执行 | 简单清晰，Planning 与 Runtime 完全解耦 | 目标明确、计划稳定的任务 |
| Planning 生成骨架计划，Runtime 执行中动态细化 | 平衡灵活性与可控性 | 中等复杂度任务 |
| Planning 与 Runtime 交替运行 | 每执行一步或一个阶段后，Planning 重新评估 | 高动态、长程任务 |

### 接口约定

- Planning 输出标准化计划格式（如 JSON Schema）。
- Runtime 消费计划，按依赖调度执行。
- Runtime 把执行结果与状态回传给 Planning，但不修改计划语义。

```mermaid
graph LR
    P[Planning] -- 计划 schema --> R[Runtime]
    R -- 执行事件 --> P
```

### 框架现状（2025-2026）

- **LangGraph 已成为有状态 Plan-and-Execute 的事实标准**（1.0 alpha 于 2025-09 发布、10 月下旬 GA，之后持续迭代）：图结构即计划，节点是动作、边是控制流；每个 super-step 自动保存 checkpoint，生产环境推荐 Postgres checkpointer 而非内存实现；`interrupt` 系列原语支持在任意节点暂停等人审。
- **checkpoint 不等于 durable execution**：LangGraph 开源版默认单进程，进程崩溃后状态可恢复，但执行不会自动重启。需要进程/机器级容错时，引入 Temporal 等持久化执行层（LangGraph 提供 Temporal 插件；OpenAI Agents SDK 与 Temporal 的集成于 2025-07 公开预览、2026-03-23 GA），或使用托管平台。
- **CrewAI、Pydantic AI 等框架默认缺少原生持久 checkpoint**，长程任务选型时要把"中断恢复"列为硬性需求逐项验证。
- **持久化面也是攻击面**：LangGraph 的 SQLite checkpointer 曾曝出 SQL 注入漏洞（CVE-2025-67644，经 checkpoint 查询的 metadata 过滤键触发，2025-12 披露、3.0.1 修复），checkpoint 存储、计划序列化通道都应纳入安全审计范围。

## 与 Memory 集成

Planning 需要 Memory 提供上下文，也需要把计划写入 Memory。

### 读取 Memory

- 用户偏好：例如常用工具、输出格式、风险容忍度。
- 历史计划：相似任务的成功计划可作为 few-shot 示例。
- 失败教训：Reflection 总结的失败模式可帮助 Planner 避免重复犯错。

### 写入 Memory

- 当前计划版本与执行历史。
- 每个 checkpoint 的状态。
- 重规划的原因与结果。

### 注意点

- 不要一次性把所有记忆塞进 prompt，要进行检索与压缩。
- Plan Memory 与通用 Memory 应分开管理，便于审计。

## 与 Reflection 集成

Reflection 是 Planning 的重要输入源。

```mermaid
graph LR
    EX[执行] -- 结果 --> OB[Observer]
    OB -- 异常 --> RF[Reflection]
    RF -- 根因/建议 --> PL[Planner]
    PL -- 新计划 --> EX
```

### 集成方式

- Reflection 输出结构化的失败分析：`root_cause`、`suggested_fix`、`confidence`、`related_past_cases`。
- Planner 根据建议进行局部修复或全局重规划。
- 对高 confidence 的建议可直接应用，低 confidence 的建议转人工审核。

## 与 Multi-Agent 集成

在多 Agent 系统中，Planning 可以作为中央 Planner，也可以分布到每个 Agent 内部。

### 中央 Planner 模式

```mermaid
graph TD
    CP[Central Planner] -- 子任务 1 --> A1[Agent 1]
    CP -- 子任务 2 --> A2[Agent 2]
    CP -- 子任务 3 --> A3[Agent 3]
    A1 -- 结果 --> CP
    A2 -- 结果 --> CP
    A3 -- 结果 --> CP
```

优点：全局最优、易于审计。
缺点：单点瓶颈、中央 Planner 可能不了解各 Agent 的私有能力。

### 分布式 Planner 模式

每个 Agent 自带 Planner，只负责自己的子目标。上层协调者只负责 handoff 或结果汇总。

优点：各 Agent 可独立演化，扩展性好。
缺点：全局计划碎片化，难以统一回滚。

### 选型建议

- 跨 Agent 依赖强、需要全局优化的任务：中央 Planner。
- Agent 能力差异大、需要高度自治的任务：分布式 Planner。

### 生产案例：Anthropic 多智能体研究系统（2025-06）

Anthropic 在工程博客中公开了其多智能体研究系统的架构与教训，是"中央 Planner + 并行执行"模式的典型样本：

- **架构**：lead agent（lead researcher）负责规划——拆解问题、派生子 agent、综合结果，必要时多轮迭代；子 agent 并行探索；另有独立的 citation agent 负责把结论映射到引用来源。
- **效果**：以 Opus 4 做 lead、Sonnet 4 做子 agent 的配置，在其内部研究评测上比单个 Opus 4 agent 提升约 90%，代价是约 15 倍的 token 成本。
- **可迁移的经验**：
  - 用扩展思考做规划，即"让 lead agent 想久一点"；
  - 给子 agent 写出精确的**目标、输出格式与边界**，比给宽松指令效果好得多；
  - 工具描述的质量直接影响规划质量——Anthropic 用专门的 agent 测试并优化工具描述，据称使后续任务完成时间缩短约 40%；
  - 只有当任务价值足够高时才启用多 agent fanout，否则单 agent + 好规划更划算。

微软的 Magentic-One（AutoGen 生态，2024-11）给出了另一种可复现的实现：Orchestrator 维护任务账本（task ledger）逐步规划与派工，多个专用 Agent（WebSurfer、FileSurfer、Coder、Executor）并行工作，在 GAIA、AssistantBench 等基准上取得了当时有竞争力的成绩。

## 与 MCP / Tool Use 集成

Planning 通过 Tool/MCP Gateway 使用外部能力。

### 工具描述

Planner 需要清晰的工具描述，包括：

- 工具名称与用途
- 输入参数 schema
- 返回值 schema
- 副作用与风险等级
- 典型使用示例

### 工具选择

- 简单场景：Planner 直接生成 tool name。
- 复杂场景：引入工具检索模块，根据目标从工具库中召回候选工具，再交给 Planner 选择。

### 注意点

- 工具描述质量直接影响 Planner 准确率。
- 高危工具应在计划验证阶段被标记，并触发 HITL。

## 计划验证

生产环境中，计划进入执行前必须经过验证。

### 验证维度

| 维度 | 检查内容 |
|---|---|
| 语法 | 步骤 ID 唯一、依赖存在、无环 |
| 语义 | 工具存在、参数类型匹配、必填参数完整 |
| 安全 | 是否调用高危工具、是否越权访问 |
| 资源 | 步骤数、并行度、预估成本是否在预算内 |
| 业务 | 是否满足用户约束、是否覆盖成功标准 |

### 验证失败处理

- 自动修正：对简单问题（如参数缺失）由 Planner 自动重试。
- 人工审核：对安全或业务问题转 HITL。
- 终止：对无法修正的计划直接拒绝。

## 重规划风暴防护

重规划风暴是生产中最常见的问题之一。

### 防护措施

| 措施 | 说明 |
|---|---|
| 冷却时间 | 同一失败原因在 N 分钟内不重复触发 |
| 最大次数 | 设置全局与单步骤的重规划上限 |
| 进展检测 | 如果新计划与旧计划无实质差异，则终止 |
| 失败分类 | 不可恢复错误直接终止，不再重试 |
| 成本上限 | 达到预算后强制终止 |
| 兜底策略 | 重规划耗尽后转人工或返回部分结果 |

### 示例策略

```python
policy = {
    "max_replans": 3,
    "replan_cooldown_seconds": 60,
    "max_plan_versions": 5,
    "cost_limit_usd": 2.0,
    "unrecoverable_errors": ["PermissionDenied", "InvalidConfiguration"],
}
```

## 人机协同

HITL 在生产中不是“能力不足”的标志，而是安全与信任机制。

### HITL 节点

- 计划生成后确认
- 高危操作前审批
- 重规划大幅变更前确认
- 失败兜底前介入

### HITL 模式

| 模式 | 说明 | 适用 |
|---|---|---|
| 同步阻塞 | 等待人工响应后再继续 | 关键审批 |
| 异步通知 | 发送通知，人工可在窗口期内介入 | 非关键但需知情 |
| 预授权 | 用户提前授权某类操作 | 重复性任务 |
| 事后审计 | 操作完成后供人复查 | 低风险高频操作 |

## 审计

Planning 层必须提供完整审计能力。

### 审计内容

- 每个计划版本的内容与生成原因
- 每步执行状态、输入、输出、耗时、成本
- 每次重规划的触发原因、旧计划、新计划
- 人工审批记录
- 失败与兜底处理记录

### 审计用途

- 问题排查与复盘
- 模型效果评估
- 合规与安全审查
- 持续优化 Planning 策略

## 如何评估 Planning 层（2025-2026 基准现状）

给 Planning 层定目标时，需要了解公开基准走到了哪一步，避免用 2023 年的预期考核 2026 年的系统，也避免被饱和的基准误导：

| 基准 | 关注点 | 2025-2026 现状 |
|---|---|---|
| OSWorld | 计算机操作 | SOTA 从 2024 年约 12% 升至 66.3%（Claude Opus 4.5，Stanford AI Index 2026），距约 72% 的人类基线仅 6 个百分点 |
| OSWorld 2.0 | 长程真实任务 | 2026 年新基准（108 个长程工作流），最强系统 Claude Opus 4.8 二元完成率仅 20.6%（部分完成 54.8%），GPT-5.5 约 13%——长程规划仍是主要瓶颈 |
| WebArena | 网页任务 | 2026 年初最优系统 74.3%，距 78.2% 人类基线约 4 个百分点，是模型与人类差距最小的 Agent 基准 |
| GAIA | 通用助理 | 头部系统已达甚至超过人类基线，对前沿模型失去区分度 |

三条评估纪律：

1. **看可靠性而非单次分数**：pass@1 提升快于 pass^k，生产应以"连续 k 次成功率"作为对外承诺口径。
2. **警惕 scaffold 敏感性**：同一模型换 harness、换步数/token 预算，分数可能相差很大；比较方案时固定 scaffold。
3. **关注抗操纵性**：UC Berkeley 的"How We Broke Top AI Agent Benchmarks"研究（2025-06 发布、2026 年持续发酵）用自动化扫描 agent 在 WebArena、GAIA、SWE-bench 等 8 个主流基准上"不解题却拿近满分"（WebArena 约 100%、GAIA 约 98%），手段包括提示注入、配置泄露、评测器与被测 agent 无隔离等；内部评测集应包含对抗样本，且评测器要与 agent 运行环境隔离。

## 成本与 SLO

### 成本模型

Planning 的成本主要来自：

- Planner 调用大模型的 token 消耗（含推理模型的 thinking token）
- 计划生成的并行采样次数（Best-of-N 中的 N）
- 重规划次数
- 工具/MCP 调用费用
- 人工审批成本
- 多 agent fanout 的放大效应（公开案例中多 agent 比单 agent 贵约一个数量级，规划环节单独 fanout 的性价比最高；Cohere 2026-10 的最优异构搭配——强模型领队 + 16 个廉价规划工人——以约 30% 的成本达到全强模型团队 97% 以上的奖励）

### SLO 建议

| 指标 | 说明 |
|---|---|
| 计划生成成功率 | 生成并通过验证的计划占比 |
| 首次执行成功率 | 无需重规划即完成的任务占比 |
| 平均重规划次数 | 反映计划质量 |
| 任务完成率 | 最终成功完成任务占比（建议同时报 pass@1 与 pass^k） |
| 平均任务耗时 | 端到端执行时间 |
| 平均任务成本 | 单次任务的花费（含推理预算） |
| 单任务推理预算 | Planner thinking token、采样数 N 的分布与上限 |
| 人工介入率 | 需要 HITL 的任务占比 |

## 本章小结

- 独立 Planning 层适合长程、多步、高失败成本、需审计的任务。
- 与 Runtime、Memory、Reflection、Multi-Agent、MCP、Tool Use 的集成需要清晰的接口与职责边界；框架选型时重点验证持久 checkpoint 与"崩溃后执行自动重启"两个能力等级。
- 计划验证、重规划风暴防护、人机协同、审计、成本与 SLO 是生产落地的五大支柱。
- 2025-2026 年的新基线：多 agent 规划 fanout 价值已被生产验证（Anthropic 案例 +90% 评测收益/约 15x 成本），推理预算管理与"规划时搜索、执行时线性"成为成本纪律，评估口径转向 pass^k 可靠性。

**参考来源**
- [Planning for Agents - LangChain Blog](https://blog.langchain.dev/planning-for-agents/)
- [LangGraph Plans](https://langchain-ai.github.io/langgraph/concepts/plans/)
- [How we built our multi-agent research system - Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)
- [Magentic-One: A Generalist Multi-Agent System for Solving Complex Tasks](https://arxiv.org/abs/2411.04468)
- [Why Checkpoints Aren't Durable Execution - Diagrid](https://www.diagrid.io/blog/checkpoints-are-not-durable-execution-why-langgraph-crewai-google-adk-and-others-fall-short-for-production-agent-workflows)
- [Stanford HAI AI Index Report 2026](https://hai.stanford.edu/assets/files/ai_index_report_2026.pdf)
- [OSWorld 2.0: Benchmarking Computer Use Agents on Long-Horizon Real-World Tasks](https://arxiv.org/abs/2606.29537)
- [How We Broke Top AI Agent Benchmarks - UC Berkeley RDI](https://rdi.berkeley.edu/blog/trustworthy-benchmarks-cont/)
- [Lessons from scaling teams of coding agents - Cohere](https://cohere.com/blog/lessons-from-scaling-teams-of-frontier-coding-agents)
- [Introducing Temporal and agentic sandboxes: the OpenAI Agents SDK](https://temporal.io/blog/introducing-temporal-and-agentic-sandboxes-openai-agents-sdk)
- [OpenAI Agents SDK Handoffs](https://openai.github.io/openai-agents-python/handoffs/)
- [AutoGen Planning Tutorial](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/planning.html)
- [LLM+P: Empowering Large Language Models with Optimal Planning Proficiency](https://arxiv.org/abs/2304.11477)

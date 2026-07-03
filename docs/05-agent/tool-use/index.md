# Tool Use / 工具使用

一句话理解：**Tool Use 是把自然语言意图映射为结构化、可验证、可执行的外部能力调用的接口层**；它本身不执行代码，真正的执行由 [Agent Runtime](/05-agent/agent-runtime/) 完成。

## 学习目标

读完本主题后，你应该能够：

- 解释 Tool Use 与“让模型直接生成代码”的本质区别，以及它解决的核心问题（知识截止、幻觉、行动能力）。
- 用 JSON Schema 定义工具，并理解 OpenAI、Anthropic、Google、MCP 在字段命名上的差异。
- 描述一次完整工具调用的生命周期：注册发现 → 模型决策 → 解析校验 → 执行 → 格式化 → 反馈 → 下一轮。
- 画出 Tool Use 子系统的模块关系图，明确 Tool Registry、Schema Manager、Executor、Parser/Validator、Permission/Policy 的分工。
- 对比 OpenAI Function Calling、Anthropic Tool Use、Google Gemini、LangGraph、OpenAI Agents SDK、AutoGen、MCP 的 API 形态与适用场景。
- 在生产环境中落地工具调用时，能够处理版本管理、权限授权、超时重试、熔断降级、并发、可观测性、跨厂商兼容等问题。
- 识别常见反模式，并给出工程化的检查清单。

## 与相邻主题的关系

| 相邻主题 | 关系 | 说明 |
| --- | --- | --- |
| [Agent Runtime](/05-agent/agent-runtime/) | 执行者 | Tool Use 生成调用描述，Runtime 负责进程/容器/网络级执行与生命周期治理。 |
| [MCP](/05-agent/mcp/) | 能力发现与协议标准 | MCP 统一外部工具的 schema、鉴权、传输；Tool Use 负责把自然语言映射到 MCP 调用。 |
| [Planning](/05-agent/planning/) | 编排决策 | Planning 决定“先调哪个、后调哪个、如何组合结果”；Tool Use 提供单次调用的原子语义。 |
| [Memory](/05-agent/memory/) | 状态持久 | 工具结果、用户偏好、调用历史回写入 Memory，供后续轮次检索。 |
| [Multi-Agent](/05-agent/multi-agent/) | 能力共享 | 一个 Agent 可以把另一个 Agent 或子服务暴露为工具，实现委托与协作。 |
| [Agent OS](/05-agent/agent-os/) | 运行时操作系统 | Agent OS 为 Tool Use 提供进程、调度、沙箱与资源治理，确保工具调用在受控环境中执行。 |
| [Reflection](/05-agent/reflection/) | 反思依据 | 模型基于工具返回的客观结果进行自我修正，而不是仅依赖内部先验。 |
| RAG | /06-rag/ | 检索器本质上是一种返回文档片段的工具。 |
| AI SRE | /07-ai-sre/ | AI SRE 把工具调用作为关键 span 与 SLI。 |
| 安全 | /08-security/ | Tool Use 是 Agent 越权与数据外泄的高危路径，需要 schema 校验、权限控制与沙箱执行。 |

## 章节导航

1. [背景与动机](01-background.md) — 从纯文本生成到显式工具调用的演进，以及 Toolformer、Gorilla、BFCL 等学术线索。
2. [核心概念](02-core-ideas.md) — 工具定义、JSON Schema 方言、Tool Choice、并行调用、结果格式、生命周期。
3. [架构设计](03-architecture.md) — Tool Use 子系统的分层架构、控制面/数据面与模块边界。
4. [工具调用工作流](04-tool-use-workflow.md) — 端到端生命周期、状态机、终止条件与失败分支。
5. [核心模块详解](05-core-modules.md) — Registry、Schema Manager、Executor、Parser、Validator、Permission、Formatter、Tracer 的职责与接口。
6. [源码与协议对比](06-source-analysis.md) — OpenAI / Anthropic / Google / LangGraph / OpenAI Agents SDK / AutoGen / MCP 的代码形态与差异。
7. [Mini Demo 说明](07-mini-demo.md) — 配套示例的设计思路、目录结构、运行方式与关键代码片段。
8. [生产落地](08-production-practice.md) — 多工具编排、版本、鉴权授权、成本/延迟、可观测性、故障模式与跨厂商兼容。
9. [最佳实践与反模式](09-best-practices.md) — schema 设计、执行、校验、重试、沙箱、可观测性检查清单。
10. [面试题](10-interview-questions.md) — 按初级/中级/高级划分的思考题。
11. [延伸阅读](11-further-reading.md) — 论文、规范、文档、博客与学习路径。

一句话总结：**Tool Use 让模型从“只会说”变成“会调度”，但调度的可靠性取决于 schema 设计、执行隔离与可观测性工程。**

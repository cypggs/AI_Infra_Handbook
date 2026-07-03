# 11. 延伸阅读

> 一句话理解：**Agent Reflection 的理论基础来自 Self-Refine、Reflexion、CRITIC 等论文，工程落地可以参考 LangGraph、AutoGen 等框架的反射教程，同时要与 Agent Runtime、Memory、Multi-Agent 等主题联动学习**。

## 论文

| 论文 | 核心贡献 | 链接 |
|---|---|---|
| **Self-Refine: Iterative Refinement with Self-Feedback** | 提出“生成—反馈—精炼”的通用迭代框架，无需额外训练数据 | [arXiv](https://arxiv.org/abs/2303.17651) |
| **Reflexion: Self-Reflective Agents with Verbal Reinforcement Learning** | 用语言反馈替代强化学习的奖励信号，Agent 通过反思失败经验改进后续行动 | [arXiv](https://arxiv.org/abs/2303.11366) |
| **CRITIC: Large Language Models Can Self-Correct with Tool-Interactive Critiquing** | 引入外部工具交互进行批判，解决 LLM 自评的事实性问题 | [arXiv](https://arxiv.org/abs/2305.11738) |
| **Tree of Thoughts: Deliberate Problem Solving with Large Language Models** | 用树搜索结构组织多步推理与评估，支持回溯和全局决策 | [arXiv](https://arxiv.org/abs/2305.10601) |
| **Language Models Can Teach Themselves to Program Better** | 展示代码生成任务中自我批判与测试反馈结合的效果 | [OpenReview](https://openreview.net/forum?id=r5yEsZo9Qn) |

## 框架与官方文档

| 资源 | 说明 | 链接 |
|---|---|---|
| **LangGraph Reflection Tutorial** | LangGraph 官方反射教程，含代码示例和状态图 | [官方教程](https://langchain-ai.github.io/langgraph/tutorials/reflection/reflection/) |
| **LangGraph Blog — Reflection Agents** | 反射 Agent 的设计模式与实践建议 | [博客](https://blog.langchain.dev/reflection-agents/) |
| **AutoGen Reflection Tutorial** | Microsoft AutoGen 的反思 Agent 教程 | [官方文档](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/reflection.html) |
| **OpenAI o1 / Reasoning Models** | OpenAI 关于推理模型的官方介绍 | [OpenAI](https://openai.com/index/learning-to-reason-with-llms/) |

## 工程文章

- **"Building LLM Systems: Reflection"** — 讨论何时以及如何在生产系统中引入 Reflection。
- **"Self-Correction in LLMs"** — 综述 LLM 自我纠错的研究进展与挑战。
- **"LLM as a Critic"** — 探讨用 LLM 作为 Critic 的 prompt 工程与校准方法。
- **"Test-Time Compute"** — 讨论通过增加推理时计算（包括反思）提升模型性能的趋势。

## 相关主题

| 主题 | 关系 | 链接 |
|---|---|---|
| [Agent Runtime](/05-agent/agent-runtime/) | Runtime 提供执行循环，Reflection 叠加自我纠错 | [阅读](/05-agent/agent-runtime/) |
| [Agent Memory](/05-agent/memory/) | Memory 存储反思产生的经验与 episode | [阅读](/05-agent/memory/) |
| [Multi-Agent](/05-agent/multi-agent/) | 群体反思依赖多 Agent 通信与协调 | [阅读](/05-agent/multi-agent/) |
| [Planning 详解](/05-agent/planning/) | Plan Reflection 在规划层面做批判与重规划 | [阅读](/05-agent/planning/) |
| [Tool Use 详解](/05-agent/tool-use/) | Tool-use Reflection 反思工具选择、参数与调用结果 | [阅读](/05-agent/tool-use/) |
| [Agent OS 详解](/05-agent/agent-os/) | Reflection 结果可触发 Agent OS 的 checkpoint/rollback 或流程升级 | [阅读](/05-agent/agent-os/) |
| Tool Use（后续主题） | 工具结果可作为 Reflection 的外部反馈 | 敬请期待 |
| [MCP](/05-agent/mcp/) | Reflection 可调用外部验证工具；[MCP](/05-agent/mcp/) 提供标准化工具发现 | [阅读](/05-agent/mcp/) |
| RAG | /06-rag/ | Reflection 可基于 RAG 检索结果评估答案忠实度。 |
| AI SRE | /07-ai-sre/ | AI SRE 为 Reflection 质量评估提供数据与告警。 |

## 推荐学习路径

1. **先读论文**：Self-Refine → Reflexion → CRITIC，理解三种典型反思范式。
2. **再看框架**：LangGraph Reflection Tutorial 动手跑一遍代码。
3. **结合本主题**：阅读本主题 01~07 章，理解架构与 Mini Demo。
4. **深入学习**：结合 Agent Runtime、Memory、Multi-Agent 主题，思考 Reflection 在整个 Agent 系统中的位置。
5. **动手实践**：在真实任务中尝试构建一个最小 Reflection 系统，用真实 LLM 替换 Demo 中的 MockLLMClient。

## Mini Demo 本地入口

- [Mini Demo README](./mini-demo/README.md)
- 源码包：`mini-demo/reflection_mini/`
- 测试目录：`mini-demo/tests/`

## 本章小结

Agent Reflection 的延伸阅读覆盖了理论基础、工程框架、相关主题和学习路径。建议从 Self-Refine、Reflexion、CRITIC 三篇论文入手，结合 LangGraph 或 AutoGen 的教程进行实践，再与本主题的架构设计、Mini Demo 和企业生产实践章节对照阅读，形成从理论到落地的完整认知。

**参考来源**

- [Self-Refine: Iterative Refinement with Self-Feedback](https://arxiv.org/abs/2303.17651)
- [Reflexion: Self-Reflective Agents with Verbal Reinforcement Learning](https://arxiv.org/abs/2303.11366)
- [CRITIC: Large Language Models Can Self-Correct with Tool-Interactive Critiquing](https://arxiv.org/abs/2305.11738)
- [Tree of Thoughts: Deliberate Problem Solving with Large Language Models](https://arxiv.org/abs/2305.10601)
- [LangGraph Reflection Tutorial](https://langchain-ai.github.io/langgraph/tutorials/reflection/reflection/)
- [AutoGen Reflection](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/reflection.html)
- [OpenAI o1 / Reasoning Models](https://openai.com/index/learning-to-reason-with-llms/)
- [LangGraph Blog — Reflection Agents](https://blog.langchain.dev/reflection-agents/)

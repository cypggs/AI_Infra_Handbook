# 延伸阅读

本章列出 Tool Use 相关的论文、规范、官方文档、博客与学习路径，并给出相邻主题的交叉引用。

## 学术论文

- **Toolformer: Language Models Can Teach Themselves to Use Tools**
  - 论文地址：https://arxiv.org/abs/2302.04761
  - 价值：自监督学习 API 使用的开山之作，理解模型如何学会“何时调用、如何调用、如何使用结果”。

- **Gorilla: Large Language Model Connected with Massive APIs**
  - 论文地址：https://arxiv.org/abs/2305.15334
  - 价值：展示通过 APIBench 微调模型以生成准确 API 调用，配套 BFCL  leaderboard。

- **Berkeley Function-Calling Leaderboard（BFCL）**
  - 地址：https://gorilla.cs.berkeley.edu/berkeley-function-calling-leaderboard.html
  - 价值：评估模型函数调用能力的权威基准，包含多语言、并行调用、可执行性等维度。

- **ReAct: Synergizing Reasoning and Acting in Language Models**
  - 论文地址：https://arxiv.org/abs/2210.03629
  - 价值：理解 Thought / Action / Observation 循环如何演变为现代 Tool Use。

## 官方规范与文档

- **OpenAI Function Calling Guide**
  - 地址：https://platform.openai.com/docs/guides/function-calling
  - 覆盖：Chat Completions 与 Responses API 的工具定义、strict mode、tool_choice、并行调用。

- **Anthropic Tool Use**
  - 地址：https://docs.anthropic.com/en/docs/build-with-claude/tool-use
  - 覆盖：Claude 的 `tool_use` / `tool_result` 块、tool_choice、disable_parallel_tool_use。

- **Google Gemini Function Calling**
  - 地址：https://ai.google.dev/gemini-api/docs/function-calling
  - 覆盖：`function_declarations`、`tool_config`、并行与串行调用。

- **Model Context Protocol（MCP）Specification**
  - 地址：https://modelcontextprotocol.io/specification
  - 覆盖：`tools/list`、`tools/call`、JSON-RPC、schema、annotations、OAuth。

- **LangGraph Tool Calling**
  - 地址：https://langchain-ai.github.io/langgraph/how-tos/tool-calling/
  - 覆盖：`@tool`、`bind_tools`、`ToolNode`、`tools_condition`。

- **OpenAI Agents SDK**
  - 地址：https://openai.github.io/openai-agents-python/
  - 覆盖：`@function_tool`、Runner、trace、handoff。

- **AutoGen Documentation**
  - 地址：https://microsoft.github.io/autogen/
  - 覆盖：`FunctionTool`、`AssistantAgent`、多 Agent 工具调用。

## 工程博客与文章

- **OpenAI: Function calling and other API updates**
  - 地址：https://openai.com/index/function-calling-and-other-api-updates/
  - 价值：Function Calling 最初发布的官方解读。

- **Anthropic: Tool use overview**
  - 地址：https://docs.anthropic.com/en/docs/build-with-claude/tool-use
  - 价值：Claude 生态工具使用的完整指南。

- **MCP: Introducing the Model Context Protocol**
  - 地址：https://www.anthropic.com/news/model-context-protocol
  - 价值：理解 MCP 的设计动机与开放生态愿景。

## 相邻主题交叉引用

| 主题 | 链接 | 与本主题关系 |
| --- | --- | --- |
| Agent Runtime | /05-agent/agent-runtime/ | Tool Use 生成调用描述，Runtime 负责执行。 |
| MCP | /05-agent/mcp/ | MCP 标准化外部能力发现与调用。 |
| Planning | /05-agent/planning/ | Planning 决定多工具编排顺序。 |
| Memory | /05-agent/memory/ | Memory 保存工具结果与调用历史。 |
| Multi-Agent | /05-agent/multi-agent/ | Agent 之间可通过 Tool Use 互相委托。 |
| Agent OS | /05-agent/agent-os/ | Agent OS 为 Tool Use 提供进程、调度、沙箱与资源治理。 |
| RAG | /06-rag/ | 检索器本质上是一种返回文档片段的工具。 |
| Reflection | /05-agent/reflection/ | Reflection 基于工具结果进行自我修正。 |

## 推荐学习路径

1. **入门**：先读完 OpenAI 与 Anthropic 的官方 Function Calling / Tool Use 文档，动手写一个天气查询 Demo。
2. **进阶**：阅读 Gorilla 论文与 BFCL，理解函数调用能力如何被评估；用 LangGraph 或 OpenAI Agents SDK 搭建多工具 Agent。
3. **深入**：阅读 Toolformer 与 ReAct 论文，理解工具使用的学术脉络；学习 MCP 规范，尝试把内部能力封装为 MCP Server。
4. **生产**：回到本主题第 8、9 章，结合自己业务场景设计 Registry、权限、熔断、可观测性方案。

## 一句话收尾

Tool Use 是连接“语言模型”与“真实世界”的桥梁，而桥梁的稳固程度取决于 schema 设计、执行隔离、权限治理与可观测性工程。

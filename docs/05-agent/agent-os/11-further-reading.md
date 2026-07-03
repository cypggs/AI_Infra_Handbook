# 延伸阅读

> 一句话理解：**Agent OS 是学术研究与工业实践交汇的领域，延伸阅读应覆盖操作系统抽象、LLM Agent 调度、沙箱与隔离、MCP 协议与治理、Multi-Agent 协作五大方向。**

## 论文

### Agent OS 基础

- [AIOS: LLM Agent Operating System](https://arxiv.org/abs/2403.16971)
  - 把 LLM 作为操作系统内核，提出 Agent Scheduler、Context Manager、Memory Manager、Storage Manager、Tool Manager、Access Manager 等模块。
- [LLM as OS, Agents as Apps](https://arxiv.org/abs/2312.03815)
  - 把 LLM 类比为 OS 内核，Agent 类比为应用，讨论新的系统调用抽象。
- [MemGPT: Towards LLMs as Operating Systems](https://arxiv.org/abs/2310.08560)
  - 把 LLM 上下文视为虚拟内存，提出分页、上下文管理、长期记忆机制。

### Agent OS 变体

- [AgentOS: From Application Silos to a Natural Language-Driven Data Ecosystem](https://arxiv.org/abs/2603.08938)
  - 讨论从应用孤岛到自然语言驱动的数据生态系统，强调 Agent 的注册、发现与协作。
- [Agent libOS: A Library Operating System for LLM Agents](https://arxiv.org/abs/2606.03895)
  - 库式 Agent OS，适合边缘与嵌入式场景。
- [Quine: LLM agents as native POSIX processes](https://arxiv.org/abs/2603.18030)
  - 让 Agent 成为原生 POSIX 进程，与 Unix/Linux 生态集成。
- [Agent-OS Blueprint](https://doi.org/10.20944/preprints202509.0077)
  - Agent OS 的蓝图书，系统梳理架构、模块与设计原则。

### 调度

- [AgentRM: A Resource Management Framework for LLM Agents](https://arxiv.org/abs/2603.13110)
  - MLFQ 风格的 Agent 调度，根据历史行为调整优先级。
- [HiveMind: Token-Centric Scheduling for LLM Agents](https://arxiv.org/abs/2604.17111)
  - 以 Token 为核心资源进行调度、预算与抢占。

### 隔离与恢复

- [AgentSys: Building Efficient Multi-Agent Systems with Worker Agents](https://arxiv.org/abs/2602.07398)
  - worker agent 进程隔离，提升多 Agent 系统效率与稳定性。
- [DeltaBox: Checkpoint and Rollback for LLM Agents](https://arxiv.org/abs/2605.22781)
  - Agent 执行状态的 checkpoint 与回滚机制。

### 安全与治理

- [Governed MCP: From Technical Specifications to Multi-Agent Governance](https://arxiv.org/abs/2604.16870)
  - 在 MCP Host 层实现治理：能力注册、授权、审计、consent、HITL。
- [ProbeLogits: Probing LLM Logits for Safety and Governance](https://arxiv.org/abs/2604.11943)
  - 通过探测 LLM logits 识别有害输出与越权意图。

## 规范与协议

- [Model Context Protocol Specification](https://modelcontextprotocol.io/specification/2025-03-26/architecture)
  - MCP 官方规范，定义 Host/Client/Server 架构、生命周期、能力协商、stdio/Streamable HTTP 传输。
- [MCP Official Introduction](https://modelcontextprotocol.io/)
  - MCP 官方介绍与文档入口。
- [Anthropic MCP Announcement](https://www.anthropic.com/news/model-context-protocol)
  - Anthropic 发布 MCP 的官方博客。
- [Google A2A Protocol](https://google.github.io/A2A/)
  - Agent-to-Agent 协议，定义 Agent Card、Task、Message、Artifact 等概念。

## 开源项目

- [agiresearch/AIOS](https://github.com/agiresearch/AIOS)
  - AIOS 论文的开源实现，提供 Agent 调度、记忆、工具管理等功能。
- [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/)
  - OpenAI 的 Agent SDK，包含 Runner、handoff、guardrails、tracing。
- [AutoGen](https://microsoft.github.io/autogen/stable/)
  - Microsoft 的多 Agent 对话框架，包含 Runtime、Group Chat、Human-in-the-Loop。
- [Rivet](https://rivet.gg/)
  - 可视化 Agent 构建与部署平台，提供 agentOS 概念。
- [Framers AgentOS](https://www.framers.ai/)
  - 企业级 Agent 管理平台，强调注册、治理与多环境部署。
- [Microsoft Agent Governance Toolkit](https://www.microsoft.com/en-us/security/blog/2025/05/06/introducing-the-microsoft-agent-governance-toolkit/)
  - 微软 Agent 治理工具包，提供注册、策略、审计、合规能力。

## 博客与工程文章

- [Anthropic MCP Connector Docs](https://docs.anthropic.com/en/docs/build-with-claude/mcp)
  - 在 Claude 中使用 MCP 的连接器文档。
- [Planning for Agents - LangChain Blog](https://blog.langchain.dev/planning-for-agents/)
  - 讨论 Agent Planning 的设计思路。
- [LangGraph Plans](https://langchain-ai.github.io/langgraph/concepts/plans/)
  - LangGraph 中的计划抽象。
- [OpenAI Agents SDK Handoffs](https://openai.github.io/openai-agents-python/handoffs/)
  - Agent 之间 handoff 的实现与最佳实践。

## 相邻主题

- [Agent Runtime](/05-agent/agent-runtime/)：单 Agent 执行容器。
- [Memory](/05-agent/memory/)：长期/短期记忆系统。
- [Planning](/05-agent/planning/)：任务分解与重规划。
- [Tool Use](/05-agent/tool-use/)：单次工具调用层。
- [MCP](/05-agent/mcp/)：模型上下文协议。
- [Multi-Agent](/05-agent/multi-agent/)：多 Agent 协作。
- [Reflection](/05-agent/reflection/)：自我反思与纠错。

## 推荐学习路径

1. **入门**：先读 [AIOS 论文](https://arxiv.org/abs/2403.16971) 与 [LLM as OS, Agents as Apps](https://arxiv.org/abs/2312.03815)，建立“Agent 即进程”的直觉。
2. **协议**：学习 [MCP 官方规范](https://modelcontextprotocol.io/specification/2025-03-26/architecture) 与 [A2A](https://google.github.io/A2A/)，理解 Agent-工具、Agent-Agent 的通信边界。
3. **调度**：读 [AgentRM](https://arxiv.org/abs/2603.13110) 与 [HiveMind](https://arxiv.org/abs/2604.17111)，掌握 MLFQ 与 Token-aware 调度。
4. **隔离与恢复**：读 [AgentSys](https://arxiv.org/abs/2602.07398) 与 [DeltaBox](https://arxiv.org/abs/2605.22781)，理解进程隔离与 checkpoint。
5. **治理**：读 [Governed MCP](https://arxiv.org/abs/2604.16870) 与 [ProbeLogits](https://arxiv.org/abs/2604.11943)，理解 Host 层与模型层的双重治理。
6. **实践**：跑通 [agiresearch/AIOS](https://github.com/agiresearch/AIOS) 与本主题的 Mini Demo，再尝试接入 OpenAI Agents SDK Runner 或 AutoGen Runtime。

## 本章小结

- 论文覆盖 Agent OS 基础、变体、调度、隔离恢复、安全治理五大方向。
- 规范与协议以 MCP 和 A2A 为核心。
- 开源项目代表不同实现路径：AIOS（研究原型）、OpenAI Agents SDK/AutoGen（Runtime/Multi-Agent）、Rivet/Framers/Microsoft（企业治理）。
- 推荐按“基础 → 协议 → 调度 → 隔离 → 治理 → 实践”的顺序学习。

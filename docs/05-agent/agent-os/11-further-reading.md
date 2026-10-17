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
- [Continuum: Efficient and Robust Multi-Turn LLM Agent Scheduling with KV Cache Time-to-Live](https://arxiv.org/abs/2511.02230)
  - ICLR 2026；把 KV Cache 纳入调度资源，工具调用间隙钉住缓存，多轮 Agent 延迟下降 1.12×–3.66×。

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
- [OWASP Top 10 for Agentic Applications（ASI:2026）](https://www.promptfoo.dev/docs/red-team/owasp-agentic-ai/)
  - 十大 Agentic 风险与 Intent Gate、JIT 凭证等控制措施，是 Agent 安全的事实基线。
- [OWASP State of Agentic AI Security and Governance v2.01](https://letsdatascience.com/news/owasp-releases-agentic-ai-security-report-v201-b6926a1d)
  - 把十大风险映射到真实 CVE 与部署架构（2026-06 更新）。
- [AIP: Agent Identity Protocol for Verifiable Delegation Across MCP and A2A](https://arxiv.org/abs/2603.24775)
  - 面向多跳委托链的可验证授权：IBCT + Biscuit 令牌；IETF 侧对应 AIMS/WIMSE/Transaction Tokens 草案。

### 上下文工程与 Agent 层级（2026 新方向）

- [Awesome-Agent-Context-Compression（YerbaPage）](https://github.com/YerbaPage/Awesome-Agent-Context-Compression)
  - 长程 Agent 上下文压缩综述（EMNLP 2026 接收）的配套仓库：按"压缩什么 / 怎么压缩 / 谁来决策"三轴整理，并系统归纳 failure modes。
- [Optimizing Context Compression for Long-horizon LLM Agents](https://arxiv.org/abs/2510.00615)
  - 面向长程任务的上下文压缩优化：压缩策略要按任务阶段与成功率评估，而非单轮指标。
- [Autonomous Memory Management in LLM Agents](https://arxiv.org/abs/2601.07190)
  - Agent 自主管理自身上下文（读/写/删除/归档），代表 agent-controlled 压缩路线。
- [A harness for every task: dynamic workflows in Claude Code](https://claude.com/blog/a-harness-for-every-task-dynamic-workflows-in-claude-code)
  - Anthropic 工程博客：用动态工作流同时编排数十个 subagent，orchestrator-worker 模式的工程化范本。

## 规范与协议

- [Model Context Protocol Specification（2026-07-28）](https://modelcontextprotocol.io/specification/2026-07-28/architecture)
  - MCP 最新规范：无状态核心、`server/discover`、OAuth 2.1 授权、扩展框架（Tasks、MCP Apps）。
- [MCP Official Introduction](https://modelcontextprotocol.io/)
  - MCP 官方介绍与文档入口。
- [Anthropic MCP Announcement](https://www.anthropic.com/news/model-context-protocol)
  - Anthropic 发布 MCP 的官方博客。
- [A2A Protocol（Linux Foundation）](https://a2a-protocol.org/)
  - Agent-to-Agent 协议 v1.0（2026）：Agent Card、Task、Message、Artifact；TSC 含 AWS、Cisco、Google、Microsoft 等。
- [AGNTCY](https://www.partitech.com/en/technical-blog-article/mcp-a2a-and-agntcy-understanding-the-interoperability-of-ai-agents-in-2026)
  - Cisco 发起、Linux Foundation 托管：Agent 目录（OASF）、身份与消息基础设施；自有 ACP 已归档，社区收敛到 A2A。
- [Agent Identity Protocol（IETF draft）](https://www.ietf.org/archive/id/draft-prakash-aip-01.html)
  - 跨 MCP/A2A 的可验证委托草案，与 WIMSE、Transaction Tokens 等 IETF OAuth 草案互为参照。

## 开源项目与宿主

- [agiresearch/AIOS](https://github.com/agiresearch/AIOS)
  - AIOS 论文的开源实现，提供 Agent 调度、记忆、工具管理等功能。
- [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/)
  - OpenAI 的 Agent SDK，包含 Runner、handoff、guardrails、tracing。
- [AutoGen](https://microsoft.github.io/autogen/stable/)
  - Microsoft 的多 Agent 对话框架，包含 Runtime、Group Chat、Human-in-the-Loop。
- [Claude Code 官方文档](https://code.claude.com/docs/en/overview)
  - 装机量最大的"准 Agent OS"参照：CLAUDE.md、Skills、Plugins、Hooks、sub-agents、Agent SDK、Routines 全 surface 机制。
- [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk/overview)
  - 把 Claude Code 引擎开放给自定义编排的 SDK。
- [OpenAI Codex CLI](https://github.com/openai/codex)
  - Apache-2.0 的本地编码 Agent CLI，与 Codex 云端任务共享账号体系；本地+云同构路线的代表。
- [Gemini CLI](https://github.com/google-gemini/gemini-cli)
  - Google 的开源终端 Agent（Apache-2.0）；2026-06-18 起免费层迁移到 Antigravity CLI，转向企业（Vertex AI / Code Assist）定位。
- [Qwen Code](https://github.com/QwenLM/qwen-code)
  - 从 Gemini CLI fork 后独立发展的多协议、多平台开源编码 Agent，支持本地模型（Ollama/vLLM）。
- [Letta](https://github.com/letta-ai/letta) / [Letta Code](https://github.com/letta-ai/letta-code)
  - MemGPT 后继：Apache-2.0 状态化 Agent 服务器，服务端持有 Agent 记忆与状态，客户端可断线重连。
- [Rivet](https://rivet.gg/)
  - 可视化 Agent 构建与部署平台，提供 agentOS 概念。
- [Framers AgentOS](https://www.framers.ai/)
  - 企业级 Agent 管理平台，强调注册、治理与多环境部署。
- [Microsoft Agent Governance Toolkit](https://www.microsoft.com/en-us/security/blog/2025/05/06/introducing-the-microsoft-agent-governance-toolkit/)
  - 微软 Agent 治理工具包，提供注册、策略、审计、合规能力。
- [Amazon Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html)
  - 模块化托管 Agent OS：Runtime（会话级 microVM）、Memory、Gateway（MCP）、Identity、Policy（Dogwood/Cedar）、Registry、Observability、Evaluations。
- [E2B](https://e2b.dev/resources/best-code-execution-sandboxes-for-ai-agents)
  - Apache 2.0 开源 Firecracker 沙箱平台，快照冷启动 5–30ms，提供 OpenAI Agents SDK 沙箱 Provider。

## 博客与工程文章

- [Anthropic MCP Connector Docs](https://docs.anthropic.com/en/docs/build-with-claude/mcp)
  - 在 Claude 中使用 MCP 的连接器文档。
- [Planning for Agents - LangChain Blog](https://blog.langchain.dev/planning-for-agents/)
  - 讨论 Agent Planning 的设计思路。
- [LangGraph Plans](https://langchain-ai.github.io/langgraph/concepts/plans/)
  - LangGraph 中的计划抽象。
- [OpenAI Agents SDK Handoffs](https://openai.github.io/openai-agents-python/handoffs/)
  - Agent 之间 handoff 的实现与最佳实践。
- [Best microVM Sandboxes for AI Code Execution in 2026（Modal）](https://modal.com/resources/best-microvm-sandboxes-ai-code-execution)
  - Firecracker vs gVisor vs 容器在 Agent 沙箱场景的对比较。
- [MCP Authorization: OAuth 2.1, PKCE, and Agent Identity（Aembit）](https://aembit.io/blog/mcp-oauth-2-1-pkce-and-the-future-of-ai-authorization/)
  - MCP 2026-07-28 授权模型的工程解读。
- [AI Agent Identity in 2026: WIMSE, SPIFFE, and OAuth](https://namoid.in/blog/ai-agent-identity-wimse-spiffe-oauth)
  - Agent 身份两层模型与多跳委托开放问题综述。

## 相邻主题

- [Agent Runtime](/05-agent/agent-runtime/)：单 Agent 执行容器。
- [Memory](/05-agent/memory/)：长期/短期记忆系统。
- [Planning](/05-agent/planning/)：任务分解与重规划。
- [Tool Use](/05-agent/tool-use/)：单次工具调用层。
- [MCP](/05-agent/mcp/)：模型上下文协议。
- [Personal AI Agent](/05-agent/personal-agent/)：面向个人用户的 Agent OS 产品形态（Muse / Dots / Siri AI）。
- [Multi-Agent](/05-agent/multi-agent/)：多 Agent 协作。
- [Reflection](/05-agent/reflection/)：自我反思与纠错。

## 推荐学习路径

1. **入门**：先读 [AIOS 论文](https://arxiv.org/abs/2403.16971) 与 [LLM as OS, Agents as Apps](https://arxiv.org/abs/2312.03815)，建立”Agent 即进程”的直觉。
2. **协议**：学习 [MCP 2026-07-28 规范](https://modelcontextprotocol.io/specification/2026-07-28/architecture) 与 [A2A v1.0](https://a2a-protocol.org/)，理解 Agent-工具、Agent-Agent 的通信边界，以及 AGNTCY 在发现/身份层的定位。
3. **调度**：读 [AgentRM](https://arxiv.org/abs/2603.13110)、[HiveMind](https://arxiv.org/abs/2604.17111) 与 [Continuum](https://arxiv.org/abs/2511.02230)，掌握任务级（MLFQ/Token）与推理引擎级（KV Cache TTL）两层调度。
4. **隔离与恢复**：读 [AgentSys](https://arxiv.org/abs/2602.07398) 与 [DeltaBox](https://arxiv.org/abs/2605.22781)，再用 E2B 或 Bedrock AgentCore 跑一个带快照 pause/resume 的沙箱会话。
5. **治理**：读 [Governed MCP](https://arxiv.org/abs/2604.16870)、[ProbeLogits](https://arxiv.org/abs/2604.11943) 与 [OWASP ASI:2026](https://www.promptfoo.dev/docs/red-team/owasp-agentic-ai/)，理解 Host 层与模型层的双重治理；再读 [AIP](https://arxiv.org/abs/2603.24775) 了解多跳委托的未解难题。
6. **上下文与层级**：读 [上下文压缩综述仓库](https://github.com/YerbaPage/Awesome-Agent-Context-Compression) 建立"压缩什么/怎么压缩/谁来决策"的框架，再对照 [Claude Code sub-agents](https://code.claude.com/docs/en/sub-agents) 与 [dynamic workflows 博客](https://claude.com/blog/a-harness-for-every-task-dynamic-workflows-in-claude-code) 看 orchestrator-worker 的工程落地。
7. **实践**：跑通 [agiresearch/AIOS](https://github.com/agiresearch/AIOS) 与本主题的 Mini Demo，再对照 [Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html) 的模块划分检查自己的实现缺了哪些原语。

## 本章小结

- 论文覆盖 Agent OS 基础、变体、调度、隔离恢复、安全治理、上下文工程六大方向。
- 规范与协议以 MCP 和 A2A 为核心。
- 开源项目代表不同实现路径：AIOS（研究原型）、OpenAI Agents SDK/AutoGen（Runtime/Multi-Agent）、Claude Code/Codex CLI/Gemini CLI/Qwen Code（CLI 宿主）、Letta（状态化记忆服务器）、Rivet/Framers/Microsoft（企业治理）。
- 推荐按"基础 → 协议 → 调度 → 隔离 → 治理 → 上下文与层级 → 实践"的顺序学习。

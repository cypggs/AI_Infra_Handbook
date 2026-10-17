# 背景：为什么需要 Agent OS

> 一句话理解：**当 Agent 从“单次调用的脚本”变成“长期运行、多实例、多租户、需要治理的生产系统”时，我们就需要像操作系统管理进程一样来管理 Agent。**

## 从单 Agent 脚本到生产系统

早期的 LLM Agent 通常是一段 Python 脚本：

```python
response = llm.chat("帮我查一下北京天气，然后推荐一家餐厅")
# 手动解析、调用工具、再拼接 prompt
```

这种形式适合原型验证，但很快会遇到问题：

- 多个 Agent 同时运行时，如何分配 CPU/内存/Token 预算？
- Agent 调用外部工具失败或陷入死循环时，如何超时、暂停、回滚？
- 不同 Agent 需要访问不同的工具集合，如何统一授权与审计？
- Agent 之间需要通信与协作，如何避免消息混乱、状态冲突？
- 长程任务需要中断后继续，如何持久化状态并恢复？

这些问题正是传统操作系统解决过的问题：进程调度、资源隔离、文件系统、IPC、权限模型、审计日志。Agent OS 把这些概念迁移到 Agent 世界。

## Ad-hoc 编排的局限

在没有 Agent OS 之前，开发者常用以下方式组合 Agent：

1. **脚本编排**：用 `for` 循环或 DAG 框架（如 Airflow、Prefect）把多个 Agent 串起来。
2. **Workflow 引擎**：把 Agent 当作普通节点，用固定 DAG 描述流程。
3. **消息队列**：用 Kafka/RabbitMQ 做 Agent 间通信。
4. **容器/函数**：每个 Agent 一个 Docker 容器或 Serverless 函数。

这些方案各有优势，但都存在明显局限：

| 方案 | 局限 |
|---|---|
| 脚本编排 | 缺乏统一生命周期、资源限制、失败恢复、审计 |
| Workflow 引擎 | 把 Agent 当作静态节点，难以支持动态规划与重规划 |
| 消息队列 | 只有通信，没有进程隔离、能力注册、权限治理 |
| 容器/函数 | 隔离强但调度粗、启动慢、Token/LLM 调用成本难以精细化控制 |

Agent OS 不是替代这些方案，而是在它们之上增加一层语义：**Agent 作为一等公民的进程抽象**。

## 学术界的动机

### AIOS：LLM Agent Operating System

AIOS（arXiv:2403.16971）明确提出把 LLM 作为操作系统内核，把 Agent 作为应用进程。它设计了：

- **Agent Scheduler**：解决多个 Agent 请求的调度问题。
- **Context Manager**：管理每个 Agent 的上下文窗口。
- **Memory Manager**：提供短期与长期记忆存储。
- **Storage Manager**：持久化 Agent 状态。
- **Tool Manager / Access Manager**：管理工具注册与权限。

AIOS 的核心洞察是：LLM 的上下文窗口、调用延迟、工具访问都是稀缺资源，需要 OS 风格的统一管理。

来源：[AIOS: LLM Agent Operating System](https://arxiv.org/abs/2403.16971)

### LLM as OS, Agents as Apps

该论文（arXiv:2312.03815）把 LLM 类比为操作系统内核，Agent 类比为应用程序。它强调：

- LLM 提供“计算”与“知识”。
- Agent 通过“系统调用”（如工具调用、记忆读写）使用 LLM 能力。
- 需要新的 OS 抽象来管理 Agent 的资源、状态与交互。

来源：[LLM as OS, Agents as Apps](https://arxiv.org/abs/2312.03815)

### Agent libOS 与 Quine

- **Agent libOS**（arXiv:2606.03895）提出把 OS 服务作为库链接到 Agent 中，适合嵌入式/边缘场景。
- **Quine**（arXiv:2603.18030）提出让 LLM Agent 成为原生 POSIX 进程，可以直接使用 fork/exec、信号、文件描述符等机制。

这些工作说明 Agent OS 的形态可以是内核式、库式、进程式，取决于部署场景。

来源：
- [Agent libOS: A Library Operating System for LLM Agents](https://arxiv.org/abs/2606.03895)
- [Quine: LLM agents as native POSIX processes](https://arxiv.org/abs/2603.18030)

## 工业界的动机

### 多 Agent 生产系统的治理需求

随着 Claude、OpenAI、Google 等平台推出 Agent 能力，企业开始部署大量 Agent：

- 客服 Agent、代码 Agent、数据分析 Agent、运维 Agent 同时运行。
- 同一 Agent 的多个实例处理不同租户/用户的请求。
- Agent 调用外部 API、数据库、代码解释器，存在安全风险。
- 需要审计“哪个 Agent、在什么时间、以什么权限、调用了什么工具”。

这些需求催生了工业界的 Agent OS/Agent Governance 实践：

- **Rivet agentOS**、**Framers AgentOS**：面向 Agent 生命周期的管理平台。
- **Microsoft Agent Governance Toolkit**：提供 Agent 注册、策略、审计、consent 管理（2026-04 更新版把 OWASP Agentic 风险映射到能力沙箱与 MCP 安全网关）。
- **agiresearch/AIOS**：开源 AIOS 实现。

### 企业级 Agent 控制面之争（2025 下半年–2026）

2025 下半年起，”Agent OS”从论文概念变成企业软件的营销关键词，各大厂商争夺的对象正是**Agent 运行时/编排/治理控制面**：

- **Microsoft Agent 365**：2026-05-01 GA，把多 Agent 治理控制面嵌入 M365，Agent 以 Entra ID 作为身份主体。
- **Salesforce Agentforce 360**（2025 年底 GA）：CRM 场景的 Agent 平台，预置 50+ 业务 Agent。
- **ServiceNow**：把自己定位为”AI 企业操作系统”——Action Fabric 同时支持 A2A + MCP 协议接入第三方 Agent，AI Control Tower 负责治理；2026-03 收购 Traceloop 补齐 Agent 运行时可观测，MCP Server GA 向第三方 Agent 开放系统。
- **阿里云 Agentic OS**：基于 Alibaba Cloud Linux 衍生，包含 cosh（自然语言 + bash 双模 Shell）、AgentSecCore 安全层与 AgentSight 可观测层。

Gartner 预测到 2026 年底 40% 的企业应用将内嵌任务型 Agent（2025 年不足 5%）。当 Agent 数量到达这个量级，”谁来 spawn、调度、隔离、审计这些 Agent”就从可选优化变成必需品——这正是 Agent OS 的工业定位。

来源：
- [Knowledge 2026: The 7 ServiceNow Announcements Changing AI](https://teivasystems.com/blog/servicenow-knowledge-2026-announcements/)
- [Agent 365 vs Agentforce 360 vs ServiceNow AI（2026-05）](https://andrew.ooo/answers/agent-365-vs-agentforce-360-vs-servicenow-may-2026/)
- [Agentic OS 技术详解（腾讯云）](https://cloud.tencent.com/developer/article/2671167)

### CLI Agent Runtime 的格局收敛（2025–2026）

与"企业级控制面"平行的另一条演进主线是 **CLI/桌面 Agent Runtime 的格局收敛**。2025 年起，Coding Agent 从 IDE 插件走向终端原生，几大厂商的 CLI 在 18 个月内完成了多轮迭代，功能面高度趋同：

- **Claude Code**：终端 + IDE + 桌面 + Web + 移动全 surface；扩展面四层——`CLAUDE.md`（per-project 配置）、**Skills**（可复用工作流包）、**Plugins**（技能+命令+MCP Server 的分发单元）、**Hooks**（在文件编辑/提交等事件前后执行 shell 命令，本质是系统调用拦截器）；**sub-agents**（Task 工具）支持 lead agent 派生并行子 Agent、各自携带隔离上下文；**Agent SDK** 把同一引擎开放给自定义编排；`claude -p` headless 模式可直接嵌入 CI。2026-04-09 与 Claude Cowork GA 同期开放 **Managed Agents** 公测，把云端托管 Agent 变成平台能力。
- **OpenAI Codex**：云端（chatgpt.com/codex，长时程任务跑在云端沙箱）+ 本地 **Codex CLI**（2025-04 以 Apache-2.0 开源）双形态，统一 ChatGPT 账号体系，是"本地+云同构"路线的代表。
- **Gemini CLI**：2025-06 以 Apache-2.0 开源，内置 Google 登录与 Code Assist 订阅通道；2026-06-18 起 Google 把免费层迁移到 Antigravity CLI，Gemini CLI 转向企业（Vertex AI / Code Assist）定位。
- **Qwen Code**：2025 年自 Gemini CLI v0.8.2 fork，v0.1 起停止同步上游独立发展，多协议（OpenAI/Anthropic/Gemini/Qwen API + Ollama/vLLM 本地模型）、多平台（终端/编辑器/桌面/Web/SDK），是开放模型阵营 CLI 的代表。

这些 CLI 已经内置了"准 OS"机制：权限确认（capability）、工作目录约束（workspace）、上下文压缩（context management）、sub-agent 派生（进程 spawn）。但它们是**单用户、单宿主**的——当企业需要同时治理成百上千个这样的会话（谁的 Agent 在跑、跑了多久、花了多少 Token、能不能审计）时，仍然需要独立的 Agent OS 层。CLI Runtime 本身的执行循环属于 [Agent Runtime](/05-agent/agent-runtime/) 主题，本章只讨论它们对 OS 层的需求。

### Cowork 类产品形态：Agent OS 的消费者化

2026 年另一个标志性事件是 **Claude Cowork** 的产品化轨迹：2026-01 以研究预览形式发布（macOS、Max 订阅，面向非开发者的"Claude Code for the rest of your work"，在指定文件夹内自主读写文件、跑定时任务）；2026-02 Windows beta + 企业版；**2026-04-09 GA**（同期开放 Managed Agents 公测与一批企业连接器）；2026-07-07 扩展到移动与 Web（云端 session 默认）；**2026-09-16 Anthropic 宣布 Cowork 并入统一的 Claude 体验**——从 Chat/Cowork/Code 三模式收敛为 Chat + Code 双模式。

Cowork 的意义不在于功能本身，而在于它验证了"**Agent OS 的消费者形态**"：指定工作目录（workspace）、定时任务（scheduler）、云端 session 续跑（checkpoint/resume）、连接器（capability）这套原语，与开发者向 Agent OS 提出的需求完全同构。企业控制面（Agent 365、Agentforce、ServiceNow）与个人宿主（Cowork、Codex、CLI）正在上下合围同一套抽象。

来源：
- [Claude Code 官方文档（Overview）](https://code.claude.com/docs/en/overview)
- [OpenAI Codex CLI（GitHub）](https://github.com/openai/codex)
- [Gemini CLI（GitHub）](https://github.com/google-gemini/gemini-cli)
- [Qwen Code（GitHub）](https://github.com/QwenLM/qwen-code)
- [The Verge：Claude Cowork 登陆移动与 Web](https://www.theverge.com/ai-artificial-intelligence/961978/anthropic-claude-cowork-mobile-web)
- [9to5Mac：Anthropic 合并 Claude Cowork 与 Chat](https://9to5mac.com/2026/09/16/anthropic-merging-claude-cowork-with-chat/)

### MCP 推动的 Host 层治理

MCP（Model Context Protocol）把工具/资源抽象为 Server，Host 负责管理 Client 与 Server 的生命周期、能力协商与权限边界。MCP Host 本质上就是 Agent OS 的”系统调用层”。

2026 年 MCP 规范发生重大修订：**2026-07-28 规范**把协议核心改为**无状态**（取消 initialize/initialized 握手与 `Mcp-Session-Id`，每个请求自带协议版本、Client 身份与能力声明），使 MCP Host 可以无状态水平扩展、直接部署在标准负载均衡与网关之后；同时授权层落地 **OAuth 2.1 精选子集**（强制 RFC 9728 Protected Resource Metadata、RFC 8707 resource 参数、RFC 9207 iss 校验），首次在规范层面给出统一的工具访问授权模型。

Governed MCP（arXiv:2604.16870）进一步提出在 MCP Host 层增加策略引擎，对每一次工具调用进行审批、审计与约束。OWASP Agentic AI Top 10（ASI:2026，2025-12-09 发布）把”工具误用”列为二号风险，建议的”Intent Gate”前置策略执行点与 MCP Host 的治理位置完全重合。

来源：
- [MCP Specification（2026-07-28）](https://modelcontextprotocol.io/specification/2026-07-28/architecture)
- [Governed MCP: From Technical Specifications to Multi-Agent Governance](https://arxiv.org/abs/2604.16870)
- [OWASP Top 10 for Agentic Applications（ASI:2026）](https://www.promptfoo.dev/docs/red-team/owasp-agentic-ai/)

### 沙箱标准的收敛

2026 年 Agent 沙箱出现明显的标准收敛：**Firecracker microVM 成为运行不可信 Agent 生成代码的事实标准**（独立内核、约 125ms 冷启动、接近容器的性能）。代表实践：

- **AWS Bedrock AgentCore**：每个 Agent 会话运行在专用 Firecracker microVM（启动小于 125ms），支持 8 小时长会话与 per-sub-agent 隔离，2025 年底 GA。
- **E2B**：Apache 2.0 开源的 Firecracker 分支，支持快照恢复（冷启动 ~5–30ms），并提供 OpenAI Agents SDK 官方沙箱 Provider。
- **Vercel Sandbox**：2026-01 GA，每个沙箱一个 Firecracker microVM。
- **Perplexity SPACE**：2026-07 公开，内部 Firecracker 运行时支撑全部 Computer Agent 流量，支持 pause/resume/fork 与长达一周的会话快照。

OWASP ASI:2026 的 ASI05（Unexpected Code Execution）明确把沙箱列为强制要求，行业共识是：容器只能跑可信代码，不可信的 LLM 生成代码必须跑在 microVM 里。

来源：
- [Best microVM Sandboxes for AI Code Execution in 2026（Modal）](https://modal.com/resources/best-microvm-sandboxes-ai-code-execution)
- [AWS Bedrock AgentCore 文档](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html)

## 为什么现在需要 Agent OS

Agent OS 的兴起不是偶然，而是由以下趋势共同推动：

1. **Agent 数量爆炸**：从”一个 Agent 做所有事”到”数百个专精 Agent 协作”；Gartner 预测 2026 年底 40% 企业应用将内嵌任务型 Agent。
2. **任务长程化**：Agent 任务从单次问答扩展到小时级、天级的持续执行，会话快照与状态持久化成为基础能力。
3. **调用成本敏感**：LLM Token、工具调用、外部 API 都需要预算控制，调度粒度细化到单次 LLM 推理调用。
4. **安全合规压力**：Agent 访问敏感数据与系统，必须可授权、可审计、可回滚；OWASP ASI:2026 给出了十大 Agentic 风险与对应控制措施。
5. **Multi-Agent 与 MCP 标准化**：Agent 之间、Agent 与工具之间需要统一协议；2026 年 A2A 发布 v1.0（Linux Foundation 治理，150+ 组织支持），MCP 2026-07-28 规范把 Host 无状态化并落地 OAuth 2.1 授权，Agent OS 是协议落地的基础设施。
6. **宿主层机制收敛**：Claude Code、Codex CLI、Gemini CLI、Qwen Code 等 CLI Runtime 在 2025–2026 年独立演化出同一套"准 OS"机制（权限、工作区、上下文压缩、sub-agent），Cowork 类产品把同一套原语带给非开发者——功能收敛意味着抽象已被验证，缺的只是跨宿主、跨租户的统一治理层。

## 本章小结

- 单 Agent 脚本无法解决多实例、多租户、长程任务、资源隔离、审计治理等问题。
- 学术界提出 AIOS、LLM as OS、Agent libOS、Quine 等方向，把 OS 抽象引入 Agent 世界。
- 工业界需要 Agent OS 来管理成百上千个 Agent 的生命周期、权限、成本与可观测性；Microsoft、Salesforce、ServiceNow、阿里云等正在把 Agent 控制面做成平台产品。
- MCP Host（2026-07-28 无状态规范 + OAuth 2.1）与 Governed MCP 代表了 Agent OS 在工具/能力治理方向的关键实践；Firecracker microVM 成为 Agent 沙箱的事实标准。
- CLI Agent Runtime（Claude Code、Codex、Gemini CLI、Qwen Code）在 2025–2026 年收敛出同一套"准 OS"机制，Cowork 类产品将其消费者化；跨宿主、跨租户的统一治理仍缺一层独立的 Agent OS。
- OWASP ASI:2026 给出了 Agentic 系统的十大风险基线，Agent OS 的策略引擎与沙箱是对应控制措施的主要落地载体。

**参考来源**
- [AIOS: LLM Agent Operating System](https://arxiv.org/abs/2403.16971)
- [LLM as OS, Agents as Apps](https://arxiv.org/abs/2312.03815)
- [MemGPT: Towards LLMs as Operating Systems](https://arxiv.org/abs/2310.08560)
- [AgentOS: From Application Silos to a Natural Language-Driven Data Ecosystem](https://arxiv.org/abs/2603.08938)
- [Agent libOS: A Library Operating System for LLM Agents](https://arxiv.org/abs/2606.03895)
- [Quine: LLM agents as native POSIX processes](https://arxiv.org/abs/2603.18030)
- [Governed MCP: From Technical Specifications to Multi-Agent Governance](https://arxiv.org/abs/2604.16870)
- [MCP Specification（2026-07-28）](https://modelcontextprotocol.io/specification/2026-07-28/architecture)
- [OWASP Top 10 for Agentic Applications（ASI:2026）](https://www.promptfoo.dev/docs/red-team/owasp-agentic-ai/)
- [Claude Code 官方文档](https://code.claude.com/docs/en/overview)
- [OpenAI Codex CLI](https://github.com/openai/codex)
- [Gemini CLI](https://github.com/google-gemini/gemini-cli)
- [Qwen Code](https://github.com/QwenLM/qwen-code)
- [Continuum: Multi-Turn LLM Agent Scheduling with KV Cache Time-to-Live](https://arxiv.org/abs/2511.02230)

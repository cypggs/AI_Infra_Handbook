# 源码分析

> 一句话理解：**AIOS、Agent libOS、Quine、AgentRM/HiveMind、MCP Host、OpenAI Agents SDK Runner、AutoGen Runtime、Claude Code、Letta 与开源 AgentOS 项目代表了 Agent OS 的多种实现路径：内核式、库式、进程式、调度式、协议式、宿主式与框架式。**

## 1. AIOS：LLM Agent Operating System

**论文**：AIOS: LLM Agent Operating System（arXiv:2403.16971）

**核心思想**：把 LLM 作为操作系统内核，把 Agent 作为应用进程，围绕 LLM 的上下文窗口与调用特性设计调度器、内存管理器、存储管理器、工具管理器。

**架构图**：

```mermaid
graph TB
    subgraph AIOS
        K[LLM Kernel]
        S[Agent Scheduler]
        CM[Context Manager]
        MM[Memory Manager]
        SM[Storage Manager]
        TM[Tool Manager]
        AM[Access Manager]
    end
    A1[Agent 1] --> S
    A2[Agent 2] --> S
    S --> K
    CM --> K
    MM --> CM
    SM --> MM
    TM --> K
    AM --> TM
```

**关键设计**：

- **Agent Scheduler**：解决多个 Agent 请求对 LLM 的并发访问，支持 FIFO、优先级、时间片等策略。
- **Context Manager**：管理每个 Agent 的上下文窗口，避免超长上下文导致延迟与成本爆炸。
- **Memory Manager**：短期记忆缓存与长期记忆检索。
- **Storage Manager**：持久化 Agent 状态与中间结果。
- **Tool Manager / Access Manager**：工具注册、调用与权限控制。

**代码级思路**（基于 agiresearch/AIOS 开源实现）：

```python
class AIOS:
    def __init__(self, llm, scheduler, memory_manager, tool_manager):
        self.llm = llm
        self.scheduler = scheduler
        self.memory_manager = memory_manager
        self.tool_manager = tool_manager

    def run(self, agent):
        # Agent 进入调度队列
        self.scheduler.add(agent)
        while True:
            # 调度器选择下一个执行的 Agent
            current_agent = self.scheduler.next()
            if current_agent is None:
                break
            # 获取上下文与记忆
            context = self.memory_manager.get_context(current_agent)
            # 调用 LLM 内核
            response = self.llm.chat(context)
            # 解析工具调用
            tool_calls = self.tool_manager.parse(response)
            # 执行并反馈
            results = self.tool_manager.execute(tool_calls, current_agent)
            self.memory_manager.update(current_agent, response, results)
```

**优点**：

- 系统性地把 OS 抽象引入 Agent 世界。
- 调度器、内存管理器、工具管理器职责清晰。

**缺点**：

- 实现相对集中，扩展性受限于 AIOS 内核本身。
- 生产级多租户、强隔离、可观测仍需大量工程补齐。

**适用场景**：研究原型、统一 LLM 调度、上下文敏感型多 Agent 系统。

来源：[AIOS: LLM Agent Operating System](https://arxiv.org/abs/2403.16971)、[agiresearch/AIOS GitHub](https://github.com/agiresearch/AIOS)

## 2. Agent libOS：库操作系统

**论文**：Agent libOS: A Library Operating System for LLM Agents（arXiv:2606.03895）

**核心思想**：把 Agent OS 服务以库的形式链接到 Agent 应用中，而不是作为独立内核运行。

**架构图**：

```mermaid
graph LR
    A[Agent App]
    A --> L[Agent libOS Library]
    L --> S[Scheduler Lib]
    L --> M[Memory Lib]
    L --> T[Tool Lib]
    L --> Sec[Security Lib]
```

**关键设计**：

- Agent 应用与 OS 服务运行在同一地址空间。
- 通过库 API 调用调度、存储、安全服务。
- 适合资源受限或低延迟场景。

**优点**：

- 启动快、延迟低、适合边缘设备。
- 不需要部署独立的 OS 服务。

**缺点**：

- 隔离性弱，一个 Agent 的崩溃可能影响整个进程。
- 多 Agent 之间需要额外机制共享资源。

**适用场景**：边缘计算、移动设备、嵌入式 Agent。

来源：[Agent libOS: A Library Operating System for LLM Agents](https://arxiv.org/abs/2606.03895)

## 3. Quine：LLM Agent 作为 POSIX 进程

**论文**：Quine: LLM agents as native POSIX processes（arXiv:2603.18030）

**核心思想**：让 LLM Agent 成为原生 POSIX 进程，直接使用 fork、exec、信号、文件描述符、管道等机制。

**架构图**：

```mermaid
graph LR
    P1[Agent Process A]
    P2[Agent Process B]
    P3[Agent Process C]
    P1 -->|pipe| P2
    P2 -->|signal| P3
    P1 -->|file| FS[Filesystem]
    P3 -->|syscall| Kernel[Linux Kernel]
```

**关键设计**：

- 每个 Agent 是一个独立的 Unix 进程。
- 使用标准进程间通信机制（pipe、socket、signal）。
- Agent 可以像普通程序一样被 shell 脚本、systemd、Docker 管理。

**优点**：

- 与现有 Unix/Linux 生态完全兼容。
- 隔离性强，可利用容器、VM、cgroups。

**缺点**：

- 对 LLM 特定资源（Token、上下文窗口）的调度不够原生。
- 需要额外封装才能提供 Agent 语义。

**适用场景**：与现有基础设施深度集成、需要强隔离的 Agent 工作负载。

来源：[Quine: LLM agents as native POSIX processes](https://arxiv.org/abs/2603.18030)

## 4. AgentRM：Agent 资源管理框架

**论文**：AgentRM: A Resource Management Framework for LLM Agents（arXiv:2603.13110）

**核心思想**：把 Agent 调度问题建模为资源管理问题，借鉴操作系统中的 MLFQ 与反馈控制理论。

**关键设计**：

- **多级反馈队列（MLFQ）**：根据 Agent 的历史行为调整优先级。
- **失败惩罚**：频繁失败或超预算的 Agent 被降级。
- **依赖感知**：考虑 Agent 之间的依赖关系进行调度。

**调度流程**：

```mermaid
graph TD
    A[Agent 到达] --> Q1[Queue 1 高优先级]
    Q1 -->|时间片用完| Q2[Queue 2]
    Q1 -->|成功完成| Done[完成]
    Q2 -->|失败/超预算| Q3[Queue 3 低优先级]
    Q2 -->|成功| Done
    Q3 -->|持续失败| Suspend[暂停/人工审批]
```

**优点**：

- 调度策略与 Agent 行为反馈结合。
- 适合混合负载与多租户场景。

**缺点**：

- 主要关注调度，对隔离、存储、治理覆盖较少。

**适用场景**：大规模 Agent 集群调度、成本敏感型任务。

来源：[AgentRM: A Resource Management Framework for LLM Agents](https://arxiv.org/abs/2603.13110)

## 5. HiveMind：Token 为中心的调度

**论文**：HiveMind: Token-Centric Scheduling for LLM Agents（arXiv:2604.17111）

**核心思想**：把 Token 作为主要调度资源，围绕 Token 预算进行准入控制、调度与抢占。

**关键设计**：

- **Token Budget**：每个 Agent/任务有 Token 预算。
- **Token-Aware Scheduling**：调度器根据剩余 Token 与任务优先级分配资源。
- **Preemption**：Token 预算耗尽时触发暂停或终止。

**调度公式示意**：

```python
def priority(agent):
    return agent.urgency / (agent.token_used + 1)

# 调度器按 priority 排序，优先执行高紧急度且 Token 消耗低的 Agent
```

**优点**：

- 直接面向 LLM 的核心成本单元（Token）。
- 适合成本敏感与预算约束场景。

**缺点**：

- Token 预测困难，预算可能频繁触发抢占。
- 需要与模型层紧密集成以获取实时 Token 消耗。

**适用场景**：Token 预算严格、需要精细化成本控制的企业环境。

来源：[HiveMind: Token-Centric Scheduling for LLM Agents](https://arxiv.org/abs/2604.17111)

### Continuum：面向推理引擎的 Agent 调度

**论文**：Continuum: Efficient and Robust Multi-Turn LLM Agent Scheduling with KV Cache Time-to-Live（arXiv:2511.02230，ICLR 2026）

**核心思想**：与 AgentRM/HiveMind 在"任务级"调度 Agent 不同，Continuum 下沉到**推理引擎层**：多轮 Agent 的工具调用间隙，KV Cache 常被立即驱逐导致 re-prefill 与重新排队。Continuum 为缓存设置 TTL——工具按时返回则续算，超时则驱逐兜底。

**关键设计**：

- **KV Cache TTL**：按预测时长钉住 GPU 缓存，兼顾延迟与显存安全。
- **Program 级 FCFS**：保持同一 Agent 多轮的执行顺序，减少调度气泡。
- 基于 vLLM 实现，SWE-Bench / BFCL 类负载延迟下降约 1.12×–3.66×，吞吐提升约 1.10×–3.22×。

**与 Agent OS 的关系**：Scheduler 模块需要向下暴露"暂停/恢复"语义给推理层，Token 预算之外还要感知 KV Cache 占用——这是 2026 年 Agent 调度器与传统任务调度器的本质差异。

来源：[Continuum](https://arxiv.org/abs/2511.02230)、[vllm-continuum](https://github.com/Hanchenli/vllm-continuum)

## 6. MCP Host：协议式 Agent OS 入口

**来源**：Model Context Protocol Specification（2026-07-28 修订版）

**核心思想**：MCP 定义了 Host、Client、Server 三方模型，Host 负责管理 Client 与 Server 的生命周期、能力协商、权限边界。Host 本质上是 Agent OS 的”系统调用门面”。

**架构图**：

```mermaid
graph TB
    H[MCP Host]
    C1[MCP Client 1]
    C2[MCP Client 2]
    S1[MCP Server A]
    S2[MCP Server B]
    H --> C1
    H --> C2
    C1 --> S1
    C2 --> S2
```

**关键设计**：

- **无状态核心（2026-07-28）**：取消 initialize/initialized 握手与 `Mcp-Session-Id`，每个请求自带协议版本、Client 身份与能力声明，Host 可无状态水平扩展、部署在标准网关之后。
- **能力协商与发现**：`server/discover` 取代初始化期发现；`tools/list` 结果可缓存（`ttlMs`）；正式扩展框架（Tasks、MCP Apps、EMA 等）按需启用。
- **授权**：HTTP 传输落地 OAuth 2.1 精选子集——强制 RFC 9728 Protected Resource Metadata、RFC 8707 resource 参数、RFC 9207 iss 校验；Bearer 只允许走 Header。
- **Lifecycle Management**：Host 创建/销毁 Client，维护 Server 连接（stdio、Streamable HTTP）。
- **Sampling**：Host 可以代表 Server 向 LLM 请求采样；MRTR（Multi Round-Trip Requests）支持工具执行中反向请求用户补充信息。
- **Security Boundary**：Host 是可信边界，Client 与 Server 之间的通信由 Host 控制。

**与 Agent OS 的关系**：

- MCP Host 是 Agent OS 中 Capability Manager 与 Policy Engine 的协议化身。
- Agent OS 负责 Host 的多实例管理、调度、审计、多租户隔离。
- 无状态化意味着"会话状态"这一传统 Host 职责上移到 Agent OS 的 Workspace 模块。

来源：[MCP Specification（2026-07-28）](https://modelcontextprotocol.io/specification/2026-07-28/architecture)

## 7. OpenAI Agents SDK Runner

**来源**：OpenAI Agents SDK

**核心思想**：提供 `Runner.run()` 作为 Agent 执行入口，封装了循环、工具调用、handoff、guardrails 与 tracing。

**代码示例**：

```python
from agents import Agent, Runner

agent = Agent(
    name="Math Tutor",
    instructions="You are a helpful math tutor.",
    tools=[calculator],
)

result = Runner.run_sync(agent, "What is 2 + 2?")
print(result.final_output)
```

**关键设计**：

- **Runner**：单 Agent 执行容器，管理 ReAct 循环与工具调用。
- **Handoff**：支持 Agent 之间转交任务。
- **Guardrails**：输入/输出护栏。
- **Tracing**：内置可观测能力。

**与 Agent OS 的关系**：

- OpenAI Agents SDK Runner 是 Agent Runtime 层的优秀实现。
- Agent OS 在其之上管理多个 Runner 实例的调度、隔离与治理。

来源：[OpenAI Agents SDK](https://openai.github.io/openai-agents-python/)

## 8. AutoGen Runtime

**来源**：Microsoft AutoGen

**核心思想**：多 Conversable Agent 通过消息传递协作，Runtime 负责消息路由、事件循环与团队执行。

**架构图**：

```mermaid
graph TB
    R[AutoGen Runtime]
    A1[Agent 1]
    A2[Agent 2]
    A3[Agent 3]
    R -->|message| A1
    A1 -->|message| R
    R -->|message| A2
    A2 -->|message| A3
```

**关键设计**：

- **Message-Driven**：Agent 通过发送消息协作，Runtime 负责路由。
- **Group Chat**：支持多 Agent 讨论模式。
- **Human-in-the-Loop**：支持用户代理 Agent 参与协作。

**与 Agent OS 的关系**：

- AutoGen Runtime 是 Multi-Agent 协作的运行时。
- Agent OS 为其提供进程隔离、命名空间、消息持久化与治理。

来源：[AutoGen Documentation](https://microsoft.github.io/autogen/stable/)

## 9. Amazon Bedrock AgentCore：托管式 Agent OS 参照实现

**来源**：Amazon Bedrock AgentCore（2025 年底 GA）

如果说 AIOS 是学术蓝图，Bedrock AgentCore 是 2026 年工业界"模块对齐全套 Agent OS 原语"的代表：它把本主题的核心模块做成一组可独立使用的托管服务。

```mermaid
graph TB
    subgraph AgentCore
        RT[Runtime<br/>会话级 microVM 隔离]
        MEM[Memory<br/>短/长期记忆]
        GW[Gateway<br/>API/Lambda → MCP 工具]
        ID[Identity<br/>对接企业 IdP]
        POL[Policy<br/>Dogwood/Cedar 拦截每次工具调用]
        REG[Registry<br/>Agent/工具目录]
        OBS[Observability<br/>OTel 标准]
        EVAL[Evaluations / Optimization]
        CI[Code Interpreter<br/>隔离代码沙箱]
    end
    A[Agent] --> RT
    RT --> MEM
    RT --> GW
    GW --> POL
    GW --> REG
    RT --> OBS
    EVAL --> OBS
```

**与本主题模块的映射**：

| AgentCore 服务 | 对应 Agent OS 模块 | 要点 |
|---|---|---|
| Runtime | Process Manager + Sandbox | 每个会话运行在隔离 microVM，支持 8 小时长会话与异步 Agent |
| Identity | Capability Manager（身份侧） | Agent 作为身份主体接入企业 IdP（Cognito、Okta、Entra ID） |
| Policy | Policy Engine | Dogwood（兼容 Cedar）声明式策略，在 Gateway 拦截**每一次**工具调用 |
| Registry | Registry | Agent/MCP Server/工具的统一目录与审批发布流 |
| Memory | Workspace | 短期多轮 + 跨会话长期记忆，可跨 Agent 共享 |
| Gateway | MCP Host | 把既有 API/Lambda 包装为 MCP 工具 |
| Observability + Evaluations + Optimization | Observer | OTel 标准 trace + 评测 + A/B 优化闭环 |

**启示**：生产级 Agent OS 的竞争焦点已从"能不能跑"转向"治理闭环"——注册、策略、观测、评测、优化形成飞轮；策略语言（Cedar 系）成为 Policy Engine 的事实选择之一。

来源：[Amazon Bedrock AgentCore 官方文档](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html)

## 10. 开源 AgentOS 项目

### Rivet agentOS

Rivet 是一款可视化 Agent 构建工具，其 agentOS 提供 Agent 部署、监控与生命周期管理。

- 强调低代码/无代码的 Agent 编排。
- 提供运行时的状态监控与版本管理。

### Framers AgentOS

Framers AgentOS 面向企业级 Agent 管理，强调：

- Agent 注册与目录。
- 权限与治理。
- 多环境部署（dev/staging/prod）。

### Microsoft Agent Governance Toolkit

微软的 Agent 治理工具包提供：

- Agent 注册与发现。
- 策略定义与执行。
- 审计与合规报告。

2026-04 的更新版把 OWASP ASI:2026 十大风险映射到具体控制：能力沙箱、MCP 安全网关、身份策略，代表”治理框架 + 风险基线”的整合方向。

### Letta（MemGPT 后继）：状态化 Agent 服务器

MemGPT（arXiv:2310.08560）提出把 LLM 上下文当作"虚拟内存"做分页管理，是上下文工程的思想源头之一。其后继项目 **Letta**（Apache-2.0，活跃开发已迁至 [letta-ai/letta-code](https://github.com/letta-ai/letta-code)）把这一思想产品化为**状态化 Agent 服务器**：

- Agent 状态（含长期记忆）由服务端持有，客户端可随时断线重连——本质上是把"进程持久化 + 上下文分页"做成了托管服务。
- 提供终端 UI、桌面/Web、Slack/Telegram 等 channel 与多语言 SDK；Letta Cloud 负责跨设备同步记忆与身份。

与本主题的对照：Letta 相当于"Memory Manager + Storage Manager"的独立商用实现，而完整 Agent OS 还需要调度、沙箱、策略、消息总线等其余原语。

这些项目代表了 Agent OS 从”调度运行时”向”治理平台”演进的工业实践。

## 11. Claude Code：装机量最大的"准 Agent OS"参照

**来源**：[Claude Code 官方文档](https://code.claude.com/docs/en/overview)

Claude Code 从未自称 Agent OS，但它 2025–2026 年在终端、IDE、桌面、Web、移动五个 surface 上沉淀的机制，与本主题的核心模块几乎一一对应，是目前装机量最大的"准 Agent OS"参照实现：

| Claude Code 机制 | 对应 Agent OS 模块 |
|---|---|
| 权限确认模式（允许列表/询问/plan 模式） | Capability Manager + Policy Engine |
| `CLAUDE.md` / auto memory | per-process 配置 + Workspace |
| Skills / Plugins | Registry + 包管理（技能、命令、MCP Server 的分发与版本） |
| Hooks（编辑/提交等事件前后执行 shell 命令） | 系统调用拦截器（Security Monitor） |
| sub-agents（Task 工具）+ Agent View 并行会话 | Process Manager（进程树 + 独立上下文地址空间） |
| Agent SDK + `claude -p` headless | 系统调用门面（把引擎开放给外部编排） |
| Routines / 云端 session / teleport | Scheduler + checkpoint/resume（跨设备状态迁移） |

**设计启示**：

- **上下文隔离先于能力隔离**：sub-agent 的首要价值是独立上下文窗口（进程地址空间），其次才是并行加速——这印证了第 11 节"上下文工程"的进程级抽象。
- **Hooks 是治理的最低成本落点**：不改 Agent 行为，只在事件边界插入校验，与 Intent Gate"执行前拦截"的思路一致。
- **同引擎多 surface**：同一 Claude Code 引擎跑在终端/桌面/Web/移动，验证了"控制面-数据面分离 + 状态可迁移"的架构；2026-09 Cowork 并入统一 Claude 体验后，Chat 与 Code 双模式共享同一套底层原语。

来源：[Claude Code Skills](https://code.claude.com/docs/en/skills)、[Claude Code Hooks](https://code.claude.com/docs/en/hooks)、[Claude Code Sub-agents](https://code.claude.com/docs/en/sub-agents)、[Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk/overview)

## 设计取舍对比表

| 项目/论文 | 核心抽象 | 调度 | 隔离 | 存储 | 治理 | 适用场景 |
|---|---|---|---|---|---|---|
| AIOS | LLM 内核 + Agent 进程 | 有（Scheduler） | 中 | 有 | 基础 | 研究原型、统一调度 |
| Agent libOS | 库式 OS 服务 | 有 | 低 | 有 | 基础 | 边缘、嵌入式 |
| Quine | POSIX 进程 | 依赖外部 OS | 高 | 文件系统 | 依赖外部 | Unix/Linux 集成 |
| AgentRM | 资源管理 | MLFQ | 弱 | 无 | 无 | 大规模调度 |
| HiveMind | Token 预算 | Token-aware | 弱 | 无 | 无 | 成本敏感 |
| Continuum | KV Cache TTL | 推理引擎级 | 无 | KV Cache | 无 | 多轮 Agent 延迟优化 |
| MCP Host | Host/Client/Server | 无 | 协议边界 | 无 | Host 层策略 | 工具标准化 |
| OpenAI Agents SDK Runner | Runner | 单 Agent | 低 | 无 | Guardrails | 单 Agent 应用 |
| AutoGen Runtime | 消息驱动 | 消息路由 | 低 | 无 | 基础 | Multi-Agent 协作 |
| Bedrock AgentCore | 模块化托管服务 | 有 | 会话级 microVM | 有 | 强（Policy/Registry） | 企业级托管治理 |
| Claude Code | CLI/桌面宿主 | Routines/云端 session | 工作目录约束 | CLAUDE.md/auto memory | 权限模式+Hooks | 个人与团队编码宿主 |
| Letta（letta-code） | 状态化 Agent 服务器 | 服务端调度 | 进程级 | 强（分页记忆） | 基础 | 长记忆对话型 Agent |
| 开源 AgentOS | 治理平台 | 有 | 中/高 | 有 | 强 | 企业治理 |

## 选型建议

| 场景 | 推荐方向 |
|---|---|
| 研究 Agent OS 抽象 | AIOS、Agent libOS |
| 与现有 Linux 生态集成 | Quine |
| 大规模 Agent 调度优化 | AgentRM、HiveMind |
| 多轮 Agent 推理延迟优化 | Continuum（结合 vLLM） |
| 标准化工具接入 | MCP Host（2026-07-28 无状态规范） |
| 单 Agent 应用快速开发 | OpenAI Agents SDK Runner |
| 多 Agent 协作原型 | AutoGen Runtime |
| 学习"准 OS"机制的最佳样本 | Claude Code（Skills/Hooks/sub-agents 对照十大原语） |
| 长记忆、可断线重连的对话 Agent | Letta（letta-code） |
| 企业级托管 Agent OS | Amazon Bedrock AgentCore |
| 企业级 Agent 治理 | Microsoft Agent Governance Toolkit、Framers AgentOS、ServiceNow AI Control Tower |

## 本章小结

- AIOS 是系统化的 Agent OS 学术原型；Agent libOS 与 Quine 分别代表库式与 POSIX 进程式实现。
- AgentRM 与 HiveMind 专注于任务级调度（MLFQ 与 Token 预算）；Continuum 下沉到推理引擎层，用 KV Cache TTL 优化多轮 Agent 延迟——两者组合才是完整的调度栈。
- MCP Host 是 Agent OS 在协议层的关键入口；2026-07-28 规范无状态化后，会话状态上移到 OS 层，Host 可以更纯粹地做策略执行点。
- OpenAI Agents SDK Runner 与 AutoGen Runtime 是 Runtime/Multi-Agent 层的优秀实现，Agent OS 在其之上提供调度、隔离与治理。
- Amazon Bedrock AgentCore 代表了”模块对齐十大原语 + 治理闭环”的托管式工业实现；开源项目正从”运行时”向”治理平台”演进。
- Claude Code 是装机量最大的"准 Agent OS"参照：权限模式、Hooks、Skills/Plugins、sub-agent 与本主题模块一一对应；Letta 则代表"Memory Manager + Storage Manager"独立商用化的路线。

**参考来源**
- [AIOS: LLM Agent Operating System](https://arxiv.org/abs/2403.16971)
- [Agent libOS: A Library Operating System for LLM Agents](https://arxiv.org/abs/2606.03895)
- [Quine: LLM agents as native POSIX processes](https://arxiv.org/abs/2603.18030)
- [AgentRM: A Resource Management Framework for LLM Agents](https://arxiv.org/abs/2603.13110)
- [HiveMind: Token-Centric Scheduling for LLM Agents](https://arxiv.org/abs/2604.17111)
- [Continuum: Multi-Turn LLM Agent Scheduling with KV Cache Time-to-Live](https://arxiv.org/abs/2511.02230)
- [MCP Specification（2026-07-28）](https://modelcontextprotocol.io/specification/2026-07-28/architecture)
- [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/)
- [AutoGen Documentation](https://microsoft.github.io/autogen/stable/)
- [Amazon Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html)
- [Rivet](https://rivet.gg/)
- [Framers AgentOS](https://www.framers.ai/)
- [Microsoft Agent Governance Toolkit](https://www.microsoft.com/en-us/security/blog/2025/05/06/introducing-the-microsoft-agent-governance-toolkit/)
- [agiresearch/AIOS GitHub](https://github.com/agiresearch/AIOS)
- [Claude Code 官方文档](https://code.claude.com/docs/en/overview)
- [Claude Code Sub-agents](https://code.claude.com/docs/en/sub-agents)
- [Letta（letta-ai/letta）](https://github.com/letta-ai/letta)
- [Letta Code（letta-ai/letta-code）](https://github.com/letta-ai/letta-code)
- [MemGPT: Towards LLMs as Operating Systems](https://arxiv.org/abs/2310.08560)

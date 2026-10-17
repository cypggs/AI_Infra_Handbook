# 4. Runtime 工作流程

> 一句话理解：**一个任务进入 Agent Runtime 后，会经过输入校验、规划、ReAct 循环、工具执行、状态更新、输出检查，最终返回结果并落盘 trace**。

## 完整生命周期

```mermaid
sequenceDiagram
    participant U as User
    participant RT as Runtime
    participant P as Planner
    participant G as Guardrails
    participant M as Memory
    participant L as LLM
    participant E as Executor
    participant R as Tool Registry
    participant O as Observer

    U->>RT: submit(task)
    RT->>O: task_received
    RT->>G: check_input(task)
    alt 输入被拦截
        RT-->>U: 403 / blocked reason
    end
    RT->>P: decompose(task)
    P-->>RT: subgoals
    RT->>M: init messages
    RT->>O: planning_done

    loop ReAct (max N)
        RT->>M: build_prompt
        RT->>L: chat.completions(messages, tools)
        L-->>RT: response
        RT->>O: llm_response

        alt finish_reason == tool_calls
            RT->>G: pre_tool_check
            RT->>E: execute(tool_call)
            E->>R: lookup(tool)
            R-->>E: result
            E-->>RT: observation
            RT->>M: append(observation)
            RT->>O: tool_executed
        else finish_reason == stop
            RT->>G: check_output(answer)
            RT->>O: task_completed
            RT-->>U: final answer
        else error / timeout
            RT->>Recovery: handle_error
            Recovery-->>RT: retry / fallback / fail
        end
    end
```

## 阶段详解

### 1. 任务接收

用户提交任务：

```json
{
  "session_id": "sess-123",
  "task": "查询 2026 年 Q1 销售额，并生成同比增长图表",
  "user_id": "u456"
}
```

Runtime 首先：

- 校验身份与权限。
- 生成或恢复 `session_id`。
- 初始化 Observer trace。

### 2. 输入护栏

Guardrails 检查输入：

- 是否包含敏感指令（越狱、提示注入）。
- 是否超出用户权限（例如普通用户查老板数据）。
- 是否符合内容安全策略。

被拦截的任务直接返回错误，不进入 LLM 调用。

### 3. 规划

Planner 把任务拆成子目标：

```text
1. 查询数据库获取 2026 Q1 销售额
2. 查询数据库获取 2025 Q1 销售额
3. 计算同比增长率
4. 调用图表工具生成柱状图
5. 返回图表与摘要
```

对于简单任务，Planner 可能直接返回单个目标，由 ReAct 循环自行决定每一步 action。

### 4. 构建上下文

Memory 组装发送给 LLM 的消息：

```text
system: 你是数据助手，可使用 calculator、query_db、chart 工具。
user: 查询 2026 年 Q1 销售额，并生成同比增长图表。
assistant: thought: 我需要先查询数据库...
```

同时附加可用工具的 JSON Schema 列表。

### 5. LLM 调用

Runtime 通过 LLM Client 调用模型：

```python
response = llm.chat.completions(
    messages=messages,
    tools=tool_schemas,
)
```

模型返回两种结果之一：

- `tool_calls`：需要调用工具。
- `content`：直接给出最终答案。

### 6. 工具执行

如果模型返回 tool_calls：

1. Runtime 解析每个 tool call 的 name 和 arguments。
2. Guardrails 做前置检查（调用次数、参数合法性、权限）。
3. Executor 通过 Tool Registry 找到对应函数并调用。
4. 捕获结果或异常，作为 observation。
5. 把 observation 加入 Memory。

示例：

```json
{
  "role": "tool",
  "tool_call_id": "call_xxx",
  "name": "query_db",
  "content": "{\"q1_2026\": 1200000, \"q1_2025\": 1000000}"
}
```

### 7. 状态更新

每轮循环结束，State Manager 更新状态：

```text
idle → planning → acting → observing → acting → observing → done
```

状态会 checkpoint 到持久化存储，支持中断恢复。

### 8. 输出检查

当模型输出最终答案时：

- Guardrails 检查输出是否合规。
- Observer 记录 task_completed 事件。
- Runtime 返回结果给用户。

### 9. Trace 落盘

无论成功失败，Runtime 都会把完整 trace 写入可观测后端：

- task_id、session_id、user_id。
- 每轮 thought、action、observation。
- 工具调用耗时、token 消耗、guardrail 事件。
- 最终状态与错误信息。

## 异常与恢复路径

| 异常 | 处理策略 |
|---|---|
| LLM 调用失败 | 按策略重试；fallback 到备用模型 |
| 工具参数错误 | 让模型重新生成；超过次数则报错 |
| 工具执行超时 | 返回 timeout observation；可重试或 fallback |
| 工具执行异常 | 捕获异常信息作为 observation |
| 迭代次数超限 | 强制终止，返回当前最佳结果 |
| 护栏触发 | 根据策略阻断、告警或请求 HITL |
| 状态丢失 | 从最近一次 checkpoint 恢复；若运行在 durable execution 引擎上，则通过 journal 重放自动恢复，已完成的 LLM 调用与外部副作用不会重复 |

## Subagents 与 Handoffs：循环的嵌套

2026 年的主流 SDK 把单 Agent 循环扩展成“循环套循环”：

- **Handoffs**：当前 Agent 把任务整体移交给另一个 Agent（OpenAI Agents SDK 的 handoff、ADK 的 agent transfer），移交本身是主循环里的一个特殊 tool call。
- **Subagents**：父 Agent 派生若干子 Agent 并行执行，子 Agent 拥有**隔离的上下文窗口**，完成后把摘要回注给父 Agent（OpenAI Agents SDK 2026-04 加入 subagents；Claude Agent SDK 的 subagent 不允许再嵌套委派）。

2026-07→10 的增量让这一层快速成熟：

- **并行 subagents 成为托管原语**：OpenAI Agents API（2026-09-10 public beta）把“tool search + 并行 subagents”作为服务端能力——工具太多时不再全量塞进上下文，而是按需检索相关工具定义再派生子 Agent。
- **Subagent 回注的注入防御**：Claude Code v2.1.278（2026-09-18）起，subagent 结果以带标记的 header 回注主 Agent，避免子任务输出被当作会话指令执行；同时移除了旧的 TaskOutput 工具。
- **fork subagents 默认化**：Claude Code 在 2026-09/10 把 `subagent_type: "fork"` 设为 `claude -p`、SDK、桌面端与 VS Code 的默认，并为 subagent frontmatter 增加 `autoCompactWindow`，让长时子任务自己管理压缩窗口；subagent 发起的后台命令不再有一小时时限。
- **Multi-phase workflows**：Claude Managed Agents 的 dynamic workflows beta（2026-10-09）让 Agent 自主决定发起多阶段 workflow run（`workflow_run.created/phase_started/status_ended` 事件流），单 run 上限 64 并发线程、1,000 agents、24 小时。
- **开源参照**：xAI 于 2026-07 开源 Grok Build harness（约 132 万行 Rust，走 ACP 协议），其 leader-follower subagents + 自动压缩的实现成为自研 Runtime 的重要参照。

对 Runtime 而言，两者都只是“一个可暂停、可观测、可恢复的子任务”，状态机与 trace 模型不变。

## 上下文压缩（Compaction）：循环的内生阶段

2026 年的共识是：compaction 不是“跑不下去了再补救”，而是主循环里与 planning/acting 平权的一个阶段：

```text
... → acting → observing → [接近上下文上限?] → compact（摘要早期消息）→ acting → ...
```

落地要点：

- **触发时机**：按 token 阈值自动触发（Agents SDK 的 session compaction、Claude Code 的空闲会话压缩），或在阶段边界主动触发。
- **安全护栏**：有待审批的 HITL 请求时推迟压缩（Agents SDK v0.24.0，2026-10-15）；PreCompact hook 可阻断压缩并要求追加保留内容（Claude Code v2.1.x）。
- **可观测**：压缩本身产生 trace event（压缩掉了多少消息、摘要内容、触发原因），否则恢复与调试时上下文对不上。
- **子任务自治**：长时 subagent 应有自己的压缩窗口（`autoCompactWindow`），父 Agent 与子 Agent 的生命周期要分开管理，避免压缩打断父子通信。

## 人机协同（HITL）

高风险工具（如写文件、转账、删除数据）在执行前可以暂停并请求人类确认：

```mermaid
sequenceDiagram
    RT->>G: pre_tool_check(write_file)
    G->>RT: requires_human_approval
    RT->>U: 请求确认
    U-->>RT: 确认 / 拒绝
    alt 确认
        RT->>E: execute(write_file)
    else 拒绝
        RT->>M: append(rejection)
    end
```

HITL 是 Runtime 从 Demo 走向生产的关键能力。

## 本章小结

Agent Runtime 的工作流程是“输入校验 → 规划 → 循环推理 → 工具执行 → 状态更新 → 输出检查 → trace 落盘”。每一环都有明确的异常处理与恢复策略。人机协同则让 Runtime 在高风险场景下安全可控。

**参考来源**

- [ReAct Paper](https://arxiv.org/abs/2210.03629)
- [OpenAI Agents SDK — Tracing](https://platform.openai.com/docs/guides/agents#tracing)
- [OpenAI Agents SDK 2026: Sandbox Agents, Harness Architecture, Any LLM](https://abhs.in/blog/openai-agents-sdk-evolution-sandbox-harness-april-2026)
- [LangGraph Human-in-the-loop](https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/)
- [OpenAI Agents SDK Changelog（v0.19–v0.24）](https://www.gradually.ai/en/changelogs/openai-agents-sdk/)
- [Claude Code Releases（v2.1.278 subagent 回注防御等）](https://github.com/anthropics/claude-code/releases)
- [Claude Managed Agents dynamic workflows (beta), 2026-10-09](https://claude-for.com/guides/claude-managed-agents-dynamic-workflows-2026-10-09)
- [Grok Build Open Source: xAI Agent Harness Architecture](https://dailyaiworld.com/workflow/grok-build-open-source-harness-workflow-2026)

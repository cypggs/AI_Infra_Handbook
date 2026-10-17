# 核心概念

AI SRE 建立在传统可观测性与可靠性工程之上，同时扩展出适用于模型、Agent 与 RAG 的概念。

## 可观测性三大支柱

| 信号 | 用途 | AI 系统关注点 |
|---|---|---|
| **Traces** | 描述请求在系统中的完整路径 | Agent 步骤、模型调用、工具调用、RAG 检索的因果关系 |
| **Metrics** | 聚合数值，用于告警与趋势 | TTFT、ITL、token 用量、成本、质量分数、错误率 |
| **Logs** | 记录离散事件与详细上下文 | prompt、completion、retrieved chunks、异常堆栈 |

OpenTelemetry 把这三种信号统一为一套 instrumentation 标准；2026 年起 profiling（持续剖析，回答“到底是哪个函数在吃 CPU”）作为第四信号进入 Alpha，Elastic 捐献的 eBPF 剖析器已并入 Collector 生态。

## OpenTelemetry 与 GenAI Semantic Conventions

OpenTelemetry 在 2026 年 5 月从 CNCF 毕业，成为云原生可观测性的事实标准；其 profiling signal（持续性能剖析，被称为“第四支柱”）也于 2026 年进入 Alpha。对 AI SRE 最关键的是 **GenAI 语义约定（Semantic Conventions）**，它统一了 LLM、Agent、向量检索与 MCP 工具调用的埋点词汇：

- **LLM span 核心属性**：`gen_ai.operation.name`、`gen_ai.provider.name`（旧名 `gen_ai.system` 已更名）、`gen_ai.request.model`、`gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens`（旧名 `prompt_tokens` / `completion_tokens` 已更名）、`gen_ai.response.finish_reasons`、`error.type`。
- **内容捕获为 opt-in**：`gen_ai.system_instructions`、`gen_ai.input.messages`、`gen_ai.output.messages`，默认关闭以防止 PII 泄露（早期每消息一个 event 的设计在 v1.37 被聚合属性取代，`gen_ai.prompt` / `gen_ai.completion` 已被移除）。
- **Agent span 树**：一次 Agent 运行建模为 `invoke_agent` span，内嵌 `chat`（模型调用）、`execute_tool`（工具调用）、`retrieval`（RAG 检索）、`plan`、`invoke_workflow` 等子 span——这正源自 Google《AI Agents》白皮书对 Agent 生命周期的划分。
- **MCP 约定**：MCP 客户端/服务端调用有独立 span（`mcp.method.name`、`mcp.session.id`），并通过 JSON-RPC `_meta` 字段携带 W3C Trace Context（`traceparent`），把 Agent 侧与 MCP Server 侧的 trace 拼成同一条分布式链路。

**成熟度现状（2026-10）**：所有 `gen_ai.*` 约定仍标记为 Development（未 Stable）。2026-06 发布的 semantic-conventions v1.42.0 把 GenAI/MCP 约定整体迁出主仓库，移入独立的 `open-telemetry/semantic-conventions-genai` 仓库以加快迭代。实践建议是**现在就用、但锁定版本**：埋点对准 `gen_ai.*`、OTLP 导出、告警与看板中的属性名做好更名预案（来源：OpenTelemetry 官方 registry 与 2026 年状态综述，见延伸阅读）。

统一语义约定后，不同框架（LangChain、LlamaIndex、OpenAI SDK、MCP）产生的 telemetry 可以在同一后端对比——“约定即契约，而不是厂商”。

## SLI / SLO / Error Budget

- **SLI（Service Level Indicator）**：可量化的指标，如可用性、TTFT、幻觉率、每次对话成本。
- **SLO（Service Level Objective）**：SLI 的目标值，如 99.9% 可用、P95 TTFT < 300ms、幻觉率 < 5%。
- **Error Budget**：`1 - SLO`，表示一段时间内允许的“坏”事件总量。

### AI 系统典型 SLI

| 类别 | 示例 SLI |
|---|---|
| 可用性 | 成功响应率 |
| 延迟 | TTFT P95、ITL P95、端到端 P99 |
| 质量 | 相关性评分、幻觉率、用户满意度 |
| 成本 | 每会话 token 数、每千次调用成本 |
| 安全 | 有害输出率、PII 泄露次数 |

## Burn-Rate 告警

Google SRE 推荐用 burn rate 把 SLO 转化为告警：

```text
burn rate = 实际错误率 / SLO 错误预算
```

- 14.4x burn rate：1 小时内消耗 2% 月度预算，需要 page。
- 6x burn rate：6 小时内消耗 5% 月度预算，需要 ticket。
- 多窗口：同时看短窗口（敏感）和长窗口（持续），减少误报。

## AIOps 与 AI SRE Agent

AIOps 把机器学习用于运维数据：

1. **异常检测**：从 metrics/logs/traces 中发现偏离基线的模式。
2. **事件关联**：把分散的告警聚合成 incident。
3. **根因分析**：RAG over 历史 incident、runbook、代码变更。
4. **辅助修复**：推荐 runbook、自动回滚、生成 postmortem 草稿。

**LLM 时代的范式转移（2025–2026）**：从“单模型问答”走向**多智能体协作 + 工具调用 + 拓扑感知**的工程化系统。典型架构是一个“运维专家 Agent”按 ReAct 循环制定排查计划，调度指标、日志、调用链等专业子 Agent，通过 MCP 工具接口查询 Prometheus/Grafana/Loki/kubectl/CMDB，迭代收敛后输出结构化根因报告。快手的 KRCA 多智能体系统在其 483 起真实事故复盘中报告根因识别正确率 82%，而单 ReAct Agent 仅 42%（厂商报告数据）。

**AI SRE Agent** 是 2026 年的标志性新角色：一个以只读方式 7×24 值守的虚拟 on-call，能读告警、查 telemetry、形成假设并给出处置建议。主流产品都提供**可调自治级别**：只读调查 → 给出建议 → 人工批准后执行 → 限定护栏内自动执行（如 Azure SRE Agent、PagerDuty Virtual Responder）。落地纪律：先 shadow mode 运行两周以上积累信任，高风险动作必须人工 gate，所有工具调用留审计链。

**边界同样清晰**：多个独立基准（ITBench-AA、OpenRCA 2.0、SREGym）显示，Agent 在真实事故上的严格指标仍只有 40–60% 量级，且存在“过度调查”带来的误报与幻觉性诊断。基准分数只能用于选型初筛，**生产价值要用自己的事故回放集和 shadow 命中率来验证**。

## 质量评估：LLM-as-Judge 与其漂移

AI SRE 把“质量”变成 SLI 的关键工具是 **LLM-as-judge**：用模型对线上抽样的输出做相关性/忠实度/幻觉打分。2026 年的共识是把它当作一个**需要持续校准的生产组件**，而不是一次性评测脚本：

- **同步护栏 + 异步评审**：确定性检查（PII、注入、正则策略）在请求路径内同步执行（预算 50–200ms）；judge 打分异步跑在采样 trace 上，不阻塞用户。
- **judge 自身也要被监控**：用哨兵样本（sentinel cases）检测评分漂移，偏差超过约 5% 告警；人工否决率超过约 15% 触发 judge 复校准——judge 漂移会直接污染质量 SLO。
- **免费先行指标**：点踩率、重试率、会话放弃率往往比 judge 更早暴露质量劣化。

## 事故响应生命周期

```text
检测（Detect） → 分类（Triage） → 响应（Respond） → 缓解（Mitigate）
     → 恢复（Recover） → 复盘（Postmortem） → 改进（Improve）
```

每个阶段都需要明确的负责人、工具、runbook 与退出标准。

## 小结

AI SRE 的核心概念可以概括为：**统一 telemetry（含 GenAI 语义约定）、定义多维 SLO、用 burn rate 告警、用 AIOps 与 AI SRE Agent 增强响应（但保留人工 gate）、用闭环复盘持续改进**。下一章把这些概念组织成可落地的平台架构。

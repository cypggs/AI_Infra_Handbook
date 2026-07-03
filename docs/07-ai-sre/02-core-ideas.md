# 核心概念

AI SRE 建立在传统可观测性与可靠性工程之上，同时扩展出适用于模型、Agent 与 RAG 的概念。

## 可观测性三大支柱

| 信号 | 用途 | AI 系统关注点 |
|---|---|---|
| **Traces** | 描述请求在系统中的完整路径 | Agent 步骤、模型调用、工具调用、RAG 检索的因果关系 |
| **Metrics** | 聚合数值，用于告警与趋势 | TTFT、ITL、token 用量、成本、质量分数、错误率 |
| **Logs** | 记录离散事件与详细上下文 | prompt、completion、retrieved chunks、异常堆栈 |

OpenTelemetry 把这三种信号统一为一套 instrumentation 标准。

## OpenTelemetry 与 GenAI Semantic Conventions

OpenTelemetry 的 GenAI Special Interest Group 正在定义 LLM、VectorDB 与 AI Agent 的语义约定：

- **LLM span**：`gen_ai.system`、`gen_ai.request.model`、`gen_ai.usage.input_tokens`、`gen_ai.usage.output_tokens`、`gen_ai.response.finish_reason`。
- **可选内容捕获**：`gen_ai.content.prompt` 与 `gen_ai.content.completion`，默认关闭以防止 PII 泄露。
- **Agent span**：基于 Google AI Agent 白皮书，定义 planner、tool use、memory access 等 span。
- **VectorDB span**：记录检索操作、返回 chunk 数、延迟。

统一语义约定后，不同框架（LangChain、LlamaIndex、OpenAI SDK）产生的 telemetry 可以在同一后端对比。

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

## AIOps

AIOps 把机器学习用于运维数据：

1. **异常检测**：从 metrics/logs/traces 中发现偏离基线的模式。
2. **事件关联**：把分散的告警聚合成 incident。
3. **根因分析**：RAG over 历史 incident、runbook、代码变更。
4. **辅助修复**：推荐 runbook、自动回滚、生成 postmortem 草稿。

LLM 时代的 AIOps 新方向：用 LLM 理解非结构化日志、生成 RCA、辅助编写 runbook。

## 事故响应生命周期

```text
检测（Detect） → 分类（Triage） → 响应（Respond） → 缓解（Mitigate）
     → 恢复（Recover） → 复盘（Postmortem） → 改进（Improve）
```

每个阶段都需要明确的负责人、工具、runbook 与退出标准。

## 小结

AI SRE 的核心概念可以概括为：**统一 telemetry、定义多维 SLO、用 burn rate 告警、用 AIOps 增强响应、用闭环复盘持续改进**。下一章把这些概念组织成可落地的平台架构。

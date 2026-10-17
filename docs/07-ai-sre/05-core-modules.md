# 核心模块

把 AI SRE 平台拆成独立模块后，每个模块的职责、接口和选型会更加清晰。

## 1. Instrumentation SDK

**职责**：在应用代码中生成 trace、metrics、logs。

- OpenTelemetry SDK（多语言）；OTel 已于 2026 年从 CNCF 毕业。
- GenAI 语义约定（仍为 Development 状态，见 02 章）：`gen_ai.provider.name`、`gen_ai.request.model`、`gen_ai.usage.input_tokens` / `output_tokens`、`gen_ai.response.finish_reasons`。
- Agent span 树：`invoke_agent` 内嵌 `chat`、`execute_tool`、`retrieval`、`plan`；MCP 调用用 `mcp.method.name` 等属性，并经 `_meta.traceparent` 拼接链路。
- 内容捕获为 opt-in（`gen_ai.input.messages` 等），PII 开关：`OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`。

## 2. Auto-Instrumentation

**职责**：不修改业务代码即可埋点。

- OpenTelemetry Python zero-code：`opentelemetry-instrument`。
- FastAPI/Flask/Requests/SQLAlchemy 自动 instrumentor。
- 注意：自动埋点覆盖不到 LLM 语义属性，需要补充手动埋点。

## 3. OpenTelemetry Collector

**职责**：接收、处理、路由 telemetry 数据。

- Receivers：OTLP、Prometheus、filelog。
- Processors：batch、memory_limiter、attributes、probabilistic_sampler、tail_sampling。
- Exporters：OTLP、Prometheus remote_write、Loki、Elasticsearch、S3。

## 4. Metrics Storage & Query

**职责**：存储和查询时序指标。

- Prometheus + Alertmanager + Grafana。
- Thanos / VictoriaMetrics / Mimir 用于长期存储与高可用。
- 关键指标：availability、latency (TTFT/ITL)、token usage、cost、quality score、cache hit。

## 5. Trace Storage & Query

**职责**：存储和查询分布式 trace。

- Jaeger、Tempo、ClickHouse、AWS X-Ray、Grafana Tempo。
- 要求：支持按 trace_id、service、model、error 快速检索。

## 6. Log Storage & Query

**职责**：存储和查询日志。

- Loki、Elasticsearch、OpenSearch、Splunk。
- 建议：日志与 trace_id 关联，便于从 trace 跳到日志。

## 7. SLO Engine

**职责**：计算 SLI、SLO、Error Budget 和 Burn Rate。

- 输入：时序查询（PromQL）。
- 输出：预算剩余量、burn rate、告警状态。
- 工具：Prometheus recording rules、Sloth、Pyrra、OpenSLO。

## 8. Alerting Engine

**职责**：把 SLO  breach 转化为通知。

- Prometheus Alertmanager、Grafana Alerting、PagerDuty、Opsgenie。
- 策略：多窗口 multi-burn-rate、抑制、升级、值班表。

## 9. Dashboards

**职责**：可视化 SLI/SLO、trace、log、incident。

- Grafana 为主流。
- 必备视图：SLO 仪表板、Latency 分解、Token 成本、模型质量、Agent step 漏斗。

## 10. AIOps Engine

**职责**：从海量 telemetry 中提取洞察。

- 异常检测：动态基线、孤立森林、VAE；日志侧的新范式是用 LLM 做结构化抽取与规则合成（如 KRONE 的分层日志抽象、用 LLM 生成可执行检测规则），兼顾可解释与低开销。
- 事件关联：把相似告警聚类为 incident。
- 根因分析：2026 主流是**多智能体 ReAct + 工具调用（MCP）+ CMDB 拓扑 + RAG over 历史事故/变更**；输出必须带置信度与证据链，低置信度转人工。
- 防幻觉：规则约束、根因白名单、推理链验证，避免“看似合理的错误根因”。
- 辅助决策：推荐 runbook、生成 timeline 草稿。

## 11. Incident Manager

**职责**：管理事故全生命周期。

- 记录 incident、severity、timeline、沟通、action items。
- 与 Slack/钉钉/飞书集成，自动创建 war room。
- 代表工具：PagerDuty Incident Response、Opsgenie、incident.io、FireHydrant。

## 12. Runbook & Postmortem

**职责**：把经验固化为可执行文档。

- Runbook：分步骤操作，绑定到告警。
- Postmortem：blameless，包含 timeline、root cause、action items。
- LLM 辅助：用历史 incident 生成 runbook 改进建议；事故关闭后自动缝合 timeline 草稿（来源可溯源），人工校对后归档。

## 13. AI SRE Agent

**职责**：7×24 自动调查与有限处置。

- 只读默认：查询类工具（Prometheus/Grafana/Loki/kubectl get）放开，写操作走批准流。
- 安全件不可省：工具 token 可单独撤销（agent 失陷时止血）、OPA 策略门禁、全量审计链、MCP Server 按信任分级。
- 评估：用自有事故回放集 + shadow mode 命中率衡量，而非厂商基准分（见 08 章）。

## 14. LLM-as-Judge 与 Guardrails

**职责**：把质量变成可告警的 SLI。

- 同步护栏：确定性检查（PII、注入、策略）在请求路径内执行，预算 50–200ms。
- 异步 judge：对采样 trace 打质量/幻觉/相关性分数，驱动质量 SLO。
- Judge 健康度：哨兵样本漂移告警（约 5% 阈值）、人工否决率监控（约 15% 触发复校准）。

## 15. GPU 健康度监控

**职责**：把硬件遥测纳入 SRE 信号。

- DCGM exporter → Prometheus → Grafana 是 2026 事实标准（开销约 1–5%）。
- 关键信号：ECC 单比特错误计数（先行指标）、XID 错误（XID 48 = 不可纠正双比特 ECC，换卡）、throttle reason（利用率 100% 不代表没降频）、温度/功耗、NVLink 错误、动态显存页退役。
- 训练侧 straggler 定位：逐 rank 迭代时间对比（慢于集群均值 15% 标疑）、AllReduce 二维延迟矩阵区分网络慢与节点慢。
- 推理侧：DCGM 硬件指标 + vLLM/SGLang 应用指标（TTFT/ITL/KV cache）+ 网络 RTT 联合做健康评分与路由（见 08 章）。

## 16. 故障注入与混沌工程

**职责**：用受控实验验证系统与 Agent 的韧性。

- 基础设施层：Chaos Mesh（K8s 原生）、LitmusChaos（CNCF 毕业）、Gremlin、AWS FIS；生产实验必须设爆炸半径与自动中止条件。
- AI 应用特有故障：超时、rate limit、部分响应、schema 漂移、检索空召回、模型行为漂移；学术原型如 ReliabilityBench（1,280 个生产化 episode 注入）显示限流类故障杀伤最大。
- Agent 韧性：对推理循环加熔断与 checkpoint，监控任务完成率与“重试放大系数”。

## 小结

这些模块可以根据团队规模组合使用。初创团队可以用 Prometheus + Grafana + OpenTelemetry Collector + PagerDuty 起步；大型企业会引入 Thanos、Tempo、Sloth、AIOps 平台、AI SRE Agent 与专门的 Incident Manager。评估框架与 benchmark 的选型见子主题 [Benchmark + Evaluation](./benchmark-evaluation/)。下一章看这些模块在主流开源/商业生态中是如何实现的。

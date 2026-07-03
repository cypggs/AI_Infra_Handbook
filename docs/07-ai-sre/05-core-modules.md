# 核心模块

把 AI SRE 平台拆成独立模块后，每个模块的职责、接口和选型会更加清晰。

## 1. Instrumentation SDK

**职责**：在应用代码中生成 trace、metrics、logs。

- OpenTelemetry SDK（多语言）。
- GenAI 语义约定：`gen_ai.system`、`gen_ai.request.model`、token counts。
- 手动 span：LLM 调用、Agent step、RAG retrieve/rerank/generate。
- PII 开关：`OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`。

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

- 异常检测：动态基线、孤立森林、VAE。
- 事件关联：把相似告警聚类为 incident。
- 根因分析：RAG over 历史 incident、变更记录。
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
- LLM 辅助：用历史 incident 生成 runbook 改进建议。

## 小结

这些模块可以根据团队规模组合使用。初创团队可以用 Prometheus + Grafana + OpenTelemetry Collector + PagerDuty 起步；大型企业会引入 Thanos、Tempo、Sloth、AIOps 平台与专门的 Incident Manager。下一章看这些模块在主流开源/商业生态中是如何实现的。

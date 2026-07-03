# 架构设计

AI SRE 平台需要同时处理高频低价值的指标数据、低频高价值的 trace 与日志，并把三者关联到业务 SLO。其架构通常分为五层。

## 分层架构

```text
┌─────────────────────────────────────────────────────────────┐
│                    Action / Response Layer                  │
│  Alerting → Runbook → Auto-remediation → Incident Manager   │
└─────────────────────────────────────────────────────────────┘
                              ▲
┌─────────────────────────────┼───────────────────────────────┐
│              Analysis / AI Layer                            │
│  Dashboards → SLO Engine → AIOps Engine → LLM-as-Judge      │
└─────────────────────────────────────────────────────────────┘
                              ▲
┌─────────────────────────────┼───────────────────────────────┐
│                    Storage Layer                            │
│  Time-Series DB (Prometheus/Thanos)                         │
│  Trace Store (Jaeger/Tempo/ClickHouse)                      │
│  Log Store (Loki/Elasticsearch)                             │
│  Event / Incident Store                                     │
└─────────────────────────────────────────────────────────────┘
                              ▲
┌─────────────────────────────┼───────────────────────────────┐
│                  Collection / Routing Layer                 │
│  OpenTelemetry Collector → sampling → routing → enrichment  │
└─────────────────────────────────────────────────────────────┘
                              ▲
┌─────────────────────────────┼───────────────────────────────┐
│                Instrumentation Layer                        │
│  Application SDK / Auto-instrumentation / Agent Sidecar     │
└─────────────────────────────────────────────────────────────┘
```

## 1. Instrumentation Layer

- **SDK**：OpenTelemetry SDK 在应用代码中生成 trace、metrics、logs。
- **Auto-instrumentation**：对 FastAPI/Flask、HTTP 客户端、数据库、消息队列自动埋点。
- **GenAI 扩展**：在 LLM 调用处手动创建 span，记录 model、token、temperature、tool name、cache hit。
- **PII 控制**：通过环境变量或 collector 配置关闭 prompt/completion 内容捕获，必要时做脱敏。

## 2. Collection / Routing Layer

OpenTelemetry Collector 负责：

- **接收**：OTLP/gRPC/HTTP、Prometheus remote write、filelog。
- **处理**：batch、采样、属性增强（tenant、环境、版本）、PII 脱敏。
- **导出**：按数据类型路由到不同后端；同时支持测试/灰度/生产多目的地。

采样策略：

- **Head-based sampling**：在请求入口处决定，实现简单但可能丢弃关键错误。
- **Tail-based sampling**：等 trace 完成后再根据错误/延迟/高成本决定是否保留，更适合 AI 场景。

## 3. Storage Layer

| 数据类型 | 典型存储 |  retention 策略 |
|---|---|---|
| Metrics | Prometheus / Thanos / VictoriaMetrics | 15s–1h 粒度，长期降采样 |
| Traces | Jaeger / Tempo / ClickHouse / AWS X-Ray | 7–30 天热，90 天温，1–7 年冷 |
| Logs | Loki / Elasticsearch / OpenSearch | 与 traces 对齐 |
| Incidents | PagerDuty / Opsgenie / 内部 DB | 永久 |

## 4. Analysis / AI Layer

- **Dashboards**：Grafana 展示 SLI、SLO、Error Budget、Burn Rate。
- **SLO Engine**：周期性计算 SLI，判断是否消耗预算。
- **AIOps Engine**：动态基线、异常检测、事件聚类、根因推荐。
- **LLM-as-Judge**：对输出质量、幻觉、相关性打分，作为质量 SLI。

## 5. Action / Response Layer

- **Alerting**：Prometheus Alertmanager、Grafana Alerting、PagerDuty。
- **Runbook**：把告警与 runbook 绑定，提供下一步操作。
- **Auto-remediation**：自动扩容、模型降级、缓存切换、流量摘除。
- **Incident Manager**：记录 incident 时间线、沟通、action item。

## 与 LLM Gateway / Agent Runtime / RAG 的集成

- **LLM Gateway**：天然是 metrics 与 trace 的汇聚点，提供统一的 provider、模型、成本维度。
- **Agent Runtime**：每个 Agent step 生成 span，工具调用作为子 span。
- **RAG**：retriever、reranker、generator 各自生成 span 与 metrics。

## 小结

AI SRE 平台不是单一工具，而是一个能把**应用埋点、数据路由、存储、分析、响应**串起来的体系。下一章将按事故生命周期梳理这套体系的实际工作流程。

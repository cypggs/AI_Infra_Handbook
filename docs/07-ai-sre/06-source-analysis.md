# 源码与生态分析

AI SRE 生态涵盖开源可观测性栈、商业 APM、LLM 专用可观测性平台与 AIOps 工具。本章对比它们的设计取舍。

## OpenTelemetry

- **定位**：云原生可观测性的统一标准与 SDK/Collector。
- **核心能力**：trace、metrics、logs 三信号；多语言 SDK；Collector 处理/路由。
- **GenAI SIG**：正在制定 LLM、VectorDB、Agent 的语义约定。
- **优点**：厂商中立、生态最广、与 Prometheus/Grafana/Jaeger 无缝集成。
- **缺点**：概念多、配置复杂；GenAI 语义约定仍在演进。

## Prometheus + Grafana

- **Prometheus**：时序数据库与告警引擎，Pull 模式，PromQL 强大。
- **Alertmanager**：告警路由、抑制、静默、分组。
- **Grafana**：可视化与告警配置中心。
- **适用**：metrics 监控、SLO burn rate、latency/token 成本仪表板。
- **扩展**：Thanos、Mimir、VictoriaMetrics 解决长期存储与高可用。

## Jaeger / Tempo / ClickHouse

| 产品 | 定位 | 特点 |
|---|---|---|
| **Jaeger** | 开源分布式追踪 | 支持 OTLP、Adaptive Sampling、Service Dependency Graph |
| **Tempo** | Grafana Labs 的 trace 后端 | 低成本、与 Loki/Prometheus 标签对齐 |
| **ClickHouse** | 列式 OLAP | 高性能 trace/log 存储，适合大规模 |

## Loki / Elasticsearch

- **Loki**：Grafana Labs 的日志聚合，只索引标签，成本低。
- **Elasticsearch/OpenSearch**：全文索引，查询灵活，成本高。
- 选择：结构化日志多、预算有限选 Loki；需要复杂全文检索选 ES。

## 商业 APM / Observability

| 产品 | 特点 |
|---|---|
| **Datadog** | 一体化 APM、基础设施监控、日志、SLO、AI 助手 Bits AI |
| **New Relic** | 全栈可观测、OpenTelemetry 原生支持 |
| **Dynatrace** | Davis AI 引擎、自动根因分析 |
| **Splunk** | 日志起家，AIOps 与事件关联强 |

## LLM 专用可观测性平台

| 产品 | 定位 |
|---|---|
| **LangSmith** | LangChain 生态，trace、eval、prompt 管理 |
| **Langfuse** | 开源 LLM 可观测性，OpenTelemetry 支持 |
| **Arize Phoenix** | LLM 可观测与评估，偏向模型质量 |
| **TruLens** | RAG/LLM 评估与反馈 |
| **DeepEval** | LLM 单元测试与评估框架 |
| **OpenLLMetry** | 基于 OpenTelemetry 的 LLM 可观测 SDK |
| **Braintrust** | 评估与实验平台 |

## AIOps / Incident Management

| 产品 | 定位 |
|---|---|
| **PagerDuty** | On-call、告警升级、incident response |
| **Opsgenie** | Atlassian 的事件响应 |
| **incident.io** | 现代 incident 管理，runbook、postmortem |
| **FireHydrant** | SRE 平台，自动化 runbook、状态页 |
| **BigPanda / Moogsoft** | 传统 AIOps 事件关联 |

## 选型对比

| 维度 | 开源栈 (OTel + Prometheus + Grafana) | 商业 APM | LLM 专用平台 |
|---|---|---|---|
| 成本 | 低（自运维） | 高（按量付费） | 中高 |
| 可控性 | 高 | 中 | 中 |
| AI 语义支持 | 需自建 | 部分支持 | 强 |
| 易用性 | 中 | 高 | 高 |
| 适合场景 | 有 SRE 团队、强定制 | 快速上线、一体化 | LLM 应用深度评估 |

## 小结

大多数团队的最佳路径是：**用 OpenTelemetry 统一埋点，Prometheus/Grafana 做 metrics 与 SLO，Jaeger/Tempo 做 trace，再用 Langfuse/Arize 补充 LLM 质量评估**。商业 APM 适合缺少自运维能力或需要快速落地的场景。

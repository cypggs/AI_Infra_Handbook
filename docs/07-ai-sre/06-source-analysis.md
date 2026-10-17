# 源码与生态分析

AI SRE 生态涵盖开源可观测性栈、商业 APM、LLM 专用可观测性平台与 AIOps 工具。本章对比它们的设计取舍。

## OpenTelemetry

- **定位**：云原生可观测性的统一标准与 SDK/Collector；2026 年 5 月从 CNCF 毕业。
- **核心能力**：trace、metrics、logs 三信号 + profiling（2026 Alpha，Elastic 捐献 eBPF 剖析器）；多语言 SDK；Collector 处理/路由；声明式配置已 Stable。
- **GenAI 约定**：2026-06 的 semconv v1.42.0 把 GenAI/MCP 约定迁入独立的 `semantic-conventions-genai` 仓库；至今仍是 Development 状态，但 Datadog、New Relic、Langfuse 等已原生支持，`gen_ai.*` 成为事实契约。
- **优点**：厂商中立、生态最广、与 Prometheus/Grafana/Jaeger 无缝集成。
- **缺点**：概念多、配置复杂；GenAI 属性仍在更名期（如 `gen_ai.system` → `gen_ai.provider.name`），需锁定版本。

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
| **Datadog** | 一体化 APM + LLM Observability，Bits AI 助手原生支持 OTel GenAI 约定 |
| **New Relic** | 全栈可观测、OTel 原生；2026-07 发布 Autopilot（AI 故障调查 GA） |
| **Dynatrace** | Davis AI 引擎、自动根因分析 |
| **Splunk** | 日志起家，AIOps 与事件关联强；2026 年推出 AI SRE Troubleshooting Agent |
| **Azure Monitor / Azure SRE Agent** | 2026-03 GA；微软内部运行 1,300+ 实例，官方宣称缓解 35,000+ 事故；自治级别可调，按 Agent 计费 |

## AI SRE Agent 生态（2026）

2026 年被普遍视为 “agentic ops” 落地元年：Gartner 发布首份 AI SRE 工具市场指南，一次横评覆盖 60+ 工具。生态分三类：

| 类别 | 代表 | 特点 |
|---|---|---|
| 独立 AI SRE 创业公司 | Resolve.ai、Traversal、Cleric、NeuBird Hawkeye | 深度调查 Agent，主打端到端 MTTR 下降（厂商报告 DigitalOcean 用 Traversal 降 38%） |
| 可观测性厂商内置 | Datadog Bits AI、New Relic Autopilot、Splunk AI SRE Agent | telemetry 就在手边，调查链路最短 |
| Incident 平台内置 | PagerDuty SRE Agent / Virtual Responder（2026-03 春季发布）、incident.io、Rootly AI | 作为“虚拟值班员”嵌入 escalation policy，主打 agent 间 MCP 互操作 |

开源阵营同样活跃（均为 Apache 2.0、CNCF Sandbox）：**HolmesGPT**（Robusta，2025-10 进入 Sandbox；多步 ReAct 调查，30+ 数据源集成，Operator 模式 7×24 值守，默认只读、修复走人工 gate）、**K8sGPT**（50+ 内置分析器扫描 K8s 故障并用人话解释，只读不修复）、**Aurora**（多云，生成修复 PR）、NudgeBee、Keep。

**AI SRE 与 AIOps 的关系**：AIOps 回答“怎么把告警变少、变准”（降噪、聚类、动态基线）；AI SRE Agent 回答“这个告警为什么会发生、该怎么办”（调查、假设、处置）。两者互补：前者是输入层，后者是行动层。

## AI SRE 评测基准（2025–2026）

给 AI SRE Agent 打分成为独立赛道，但分数要批判性地看（厂商自报分数普遍偏高，独立榜单更严格）：

| 基准 | 出品方 | 形态 | 2026 分数现状 |
|---|---|---|---|
| **AIOpsLab** | 微软（SoCC'24） | DeathStarBench + Chaos Mesh 注入，拆分为检测/定位/根因/缓解四任务 | 独立实现报告 60–91%，口径差异大 |
| **ITBench / ITBench-AA** | IBM（ICML'25）+ Artificial Analysis | 真实 K8s 事故快照（告警/事件/trace/指标/日志），RCA 按“全召回下的平均精度”计分 | 2026-05 发布时所有前沿模型低于 50%；2026-10 最佳 56.2% |
| **OpenRCA / OpenRCA 2.0** | 微软（ICLR'25） | 3 个企业系统 335 起真实故障，输出时间/组件/原因三元组 | 命中根因服务 76%，因果链完整落地仅 61.5%，精确恢复根因集 20.7% |
| **SREGym** | 学术（2026-05） | MCP 接入 metrics/logs/traces/kubectl 的端到端实战基准 | Agent 对硬件故障与 metastable failure 表现最差 |
| **CCF AIOps 挑战赛（天池）** | CCF + 清华等 | 云环境真实注入故障，多模态数据（Log/Trace/Metric/Entity/Event），F1 计分 | 2026 届聚焦大模型故障定位 |

一句话：**严格口径下 Agent 真实事故处置能力仍在 40–60% 量级**，benchmark 用于选型初筛，生产价值用自有回放集验证。

## LLM 专用可观测性平台

| 产品 | 定位 |
|---|---|
| **LangSmith** | LangChain 生态，trace、eval、prompt 管理 |
| **Langfuse** | 开源 LLM 可观测性，OTLP 端点原生映射 `gen_ai.*` |
| **Arize Phoenix** | LLM 可观测与评估，OpenInference `llm.*` 语义 + OTel 互操作层 |
| **TruLens / DeepEval / Braintrust** | RAG 评估 / LLM 单测 / 评估实验平台 |
| **OpenLLMetry** | 基于 OpenTelemetry 的 LLM 可观测 SDK（部分属性仍在迁移期） |

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

大多数团队的最佳路径是：**用 OpenTelemetry 统一埋点，Prometheus/Grafana 做 metrics 与 SLO，Tempo/ClickHouse 做 trace，再用 Langfuse/Arize 补充 LLM 质量评估**；事故管理从 PagerDuty/incident.io 起步，待告警噪音与重复调查成为明显负担后再引入 AI SRE Agent，并以只读模式先行。商业 APM 适合缺少自运维能力或需要快速落地的场景。

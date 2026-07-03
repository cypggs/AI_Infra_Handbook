# 延伸阅读

## 官方文档与规范

- **OpenTelemetry**
  - https://opentelemetry.io/
  - GenAI 语义约定与 Agent 可观测性最新标准。

- **OpenTelemetry GenAI Semantic Conventions**
  - https://opentelemetry.io/docs/specs/semconv/gen-ai/

- **Prometheus**
  - https://prometheus.io/

- **Grafana**
  - https://grafana.com/

- **Google SRE Book**
  - https://sre.google/sre-book/table-of-contents/

- **Google SRE Workbook — Alerting on SLOs**
  - https://sre.google/workbook/alerting-on-slos/

## 学术论文

- **A Survey of AIOps in the Era of Large Language Models**
  - https://dl.acm.org/doi/full/10.1145/3746635

- **Site Reliability Engineering: How Google Runs Production Systems**
  - https://sre.google/sre-book/table-of-contents/

## 工程博客

- **Maxim AI — LLM Observability Best Practices for 2025**
  - https://www.getmaxim.ai/articles/llm-observability-best-practices-for-2025/

- **Zylos Research — AI Observability and Agent Monitoring 2026**
  - https://zylos.ai/research/2026-01-16-ai-observability-agent-monitoring

- **OpenTelemetry Blog — AI Agent Observability**
  - https://opentelemetry.io/blog/2025/ai-agent-observability/

- **Grafana — Multi-window, multi-burn-rate alerts**
  - https://grafana.com/blog/how-to-implement-multi-window-multi-burn-rate-alerts-with-grafana-cloud/

- **incident.io — SRE Incident Post-Mortem Best Practices**
  - https://incident.io/blog/sre-incident-postmortem-best-practices

## 相邻主题交叉引用

| 主题 | 链接 | 与本主题关系 |
|---|---|---|
| LLM Gateway | /04-llmops/llm-gateway/ | Gateway 是 AI 服务的流量入口与核心 SLI 来源。 |
| vLLM | /04-llmops/vllm/ | 推理引擎 metrics（TTFT、ITL、KV cache）是监控重点。 |
| Agent Runtime | /05-agent/agent-runtime/ | Agent 步骤需要 trace 与 SLO。 |
| RAG | /06-rag/ | RAG 流水线需要专门的可观测性与评估指标。 |
| Agent OS | /05-agent/agent-os/ | 进程隔离与资源治理是故障缓解的底座。 |

## 推荐学习路径

1. **入门**：读完 Google SRE Book 与 Workbook，用 Prometheus + Grafana 搭建一个服务的 SLO 仪表板。
2. **进阶**：接入 OpenTelemetry，为 FastAPI/Flask 服务生成 trace 与 metrics。
3. **深入**：学习 tail-based sampling、SLO-as-code（Sloth/OpenSLO）、AIOps 异常检测。
4. **生产**：为 LLM/Agent/RAG 服务定义多维 SLO，建立 on-call、runbook、postmortem 闭环。

## 一句话收尾

AI SRE 的终极目标不是“零故障”，而是让每一次故障都可观测、可度量、可恢复、可改进。

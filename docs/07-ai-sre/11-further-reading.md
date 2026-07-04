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
| KServe | /03-ai-platform/kserve/ | 模型服务平台暴露 /metrics 与 status conditions，是 AI SRE 的核心监控对象。 |
| LLM Gateway | /04-llmops/llm-gateway/ | Gateway 是 AI 服务的流量入口与核心 SLI 来源。 |
| vLLM | /04-llmops/vllm/ | 推理引擎 metrics（TTFT、ITL、KV cache）是监控重点。 |
| Agent Runtime | /05-agent/agent-runtime/ | Agent 步骤需要 trace 与 SLO。 |
| RAG | /06-rag/ | RAG 流水线需要专门的可观测性与评估指标。 |
| Agent OS | /05-agent/agent-os/ | 进程隔离与资源治理是故障缓解的底座。 |
| OpenAI 案例研究 | /09-case-study/openai/ | 大规模 LLM 服务的可观测性、SLO 与事件响应经验。 |
| Anthropic 案例研究 | /09-case-study/anthropic/ | run-rate $30B 增长冲击可靠性的容量治理；prompt cache 命中率作为 SLO。 |
| Meta 案例研究 | /09-case-study/meta/ | 同步训练可靠性工程标杆：SDC 三件套检测、~50x 中断下降、>95% 有效训练时间、故障→checkpoint→auto-restart 闭环。 |
| Linux 系统与性能调优 | /01-foundation/linux-systems/ | CPU、memory、I/O、network 指标都来自 Linux 内核；Linux 调优是 AI SRE 根因分析的基础。 |
| Google 案例研究 | /09-case-study/google/ | 超大规模同步训练可用率标杆：NSDI'24 healthd + preflight 四层检测、reconfigure/reroute 双路径恢复、99.98% 可用率、OCS 把主机可用率要求从 99.9% 降到 99%。 |

## 推荐学习路径

1. **入门**：读完 Google SRE Book 与 Workbook，用 Prometheus + Grafana 搭建一个服务的 SLO 仪表板。
2. **进阶**：接入 OpenTelemetry，为 FastAPI/Flask 服务生成 trace 与 metrics。
3. **深入**：学习 tail-based sampling、SLO-as-code（Sloth/OpenSLO）、AIOps 异常检测。
4. **生产**：为 LLM/Agent/RAG 服务定义多维 SLO，建立 on-call、runbook、postmortem 闭环。

## 一句话收尾

AI SRE 的终极目标不是“零故障”，而是让每一次故障都可观测、可度量、可恢复、可改进。

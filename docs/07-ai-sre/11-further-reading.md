# 延伸阅读

## 官方文档与规范

- **OpenTelemetry**
  - https://opentelemetry.io/
  - 2026-05 从 CNCF 毕业；profiling signal 进入 Alpha。

- **OpenTelemetry GenAI Semantic Conventions**
  - https://opentelemetry.io/docs/specs/semconv/gen-ai/
  - 注意：v1.42.0（2026-06）起 GenAI/MCP 约定迁入独立仓库 `open-telemetry/semantic-conventions-genai`，状态仍为 Development。

- **OpenTelemetry GenAI 约定 2026 状态综述（属性更名与落地建议）**
  - https://dev.to/azena-ai/opentelemetrys-genai-semantic-conventions-are-not-stable-yet-heres-what-actually-shipped-in-2026-3mke
  - https://john-hodge.com/blog/opentelemetry-genai-semantic-conventions/

- **Prometheus**
  - https://prometheus.io/

- **Grafana**
  - https://grafana.com/

- **NVIDIA DCGM**
  - https://developer.nvidia.com/dcgm
  - GPU 健康度监控（ECC/XID/throttle）的事实标准。

- **Google SRE Book**
  - https://sre.google/sre-book/table-of-contents/

- **Google SRE Workbook — Alerting on SLOs**
  - https://sre.google/workbook/alerting-on-slos/

## 学术论文与评测基准

- **A Survey of AIOps in the Era of Large Language Models（ACM Computing Surveys, 2025）**
  - https://dl.acm.org/doi/full/10.1145/3746635
  - LLM 时代 AIOps 的权威综述：故障感知、根因分析、辅助修复三阶段分类。

- **AIOpsLab：评估自治云 AI Agent 的整体框架（微软, SoCC'24）**
  - https://arxiv.org/pdf/2501.06706

- **ITBench / ITBench-AA（IBM + Artificial Analysis, 2026）**
  - https://www.linkedin.com/posts/bhavya24_itbench-labaaai-2026-activity-7417937993203687424-CyOt
  - 2026 年最严格的独立 AI SRE 基准之一；发布时所有前沿模型低于 50%。

- **OpenRCA / OpenRCA 2.0（微软, ICLR'25）**
  - https://llm-stats.com/benchmarks/openrca
  - 335 起企业真实故障的 RCA 基准。

- **SREGym：高保真实战环境下 AI SRE Agent 的活基准（2026-05）**
  - https://arxiv.org/html/2605.07161v2
  - MCP 接入 metrics/logs/traces/kubectl 的端到端评测，Agent 对硬件故障与 metastable failure 表现最差。

- **ORCA-bench：LLM Agent 的 on-call 就绪度评测（2026）**
  - https://arxiv.org/html/2607.28545v3

- **ReliabilityBench：LLM Agent 的混沌工程式故障注入评测（2026-01）**
  - https://arxiv.org/abs/2601.06112
  - 1,280 个生产化 episode；限流类故障杀伤最大。

- **KRONE：面向 LLM 的结构感知日志异常检测新范式（2026）**
  - https://arxiv.org/pdf/2602.07303

- **LogICL：蒸馏 LLM 推理的跨域日志异常检测（2025-12）**
  - https://arxiv.org/html/2512.09627v1

- **Site Reliability Engineering: How Google Runs Production Systems**
  - https://sre.google/sre-book/table-of-contents/

## 工程博客与产业报告

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

- **Microsoft — Announcing general availability for the Azure SRE Agent（2026-03）**
  - https://techcommunity.microsoft.com/blog/appsonazureblog/announcing-general-availability-for-the-azure-sre-agent/4500682

- **PagerDuty — Spring 2026 发布：SRE Agent 与 Virtual Responder**
  - https://markets.ft.com/data/announce/detail?dockey=600-202603120800BIZWIRE_USPRX____20260312_BW121276-1

- **PagerDuty — SRE Agent 基准测试报告（2026-10，定位/诊断/缓解/证据/抗误导五维评分）**
  - https://www.pagerduty.com/resources/ai/learn/sre-agent-benchmark-report/

- **HolmesGPT vs K8sGPT vs Aurora：开源 AI SRE 对比（2026）**
  - https://www.aurorasre.ai/blog/open-source-ai-sre-aurora-vs-holmesgpt-vs-k8sgpt
  - https://dev.to/siddharth_singh_409bd5267/open-source-ai-sre-aurora-vs-holmesgpt-vs-k8sgpt-2026-5g26

- **AIOps in 2026：独立视角的产业盘点（ITBench 47%、调查成本与“自动化即事故”案例）**
  - https://www.ajayk.sh/blog/aiops-2026-incident-response-agents-mttr/

- **AuroraSRE — AI SRE Accuracy: What the Benchmarks Show (2026)**
  - https://www.aurorasre.ai/blog/ai-sre-accuracy-benchmarks
  - 对厂商自报基准分数的批判性审计。

- **腾讯云 — 大模型驱动的 AIOps：让故障自动消失的底层逻辑**
  - https://cloud.tencent.com/developer/article/2623515

- **阿里云 — AI 大模型让故障诊断告别“摸黑时代”**
  - https://developer.aliyun.com/article/1669435

- **CCF AIOps 挑战赛（天池，2026 届：大模型故障定位）**
  - https://tianchi.aliyun.com/competition/entrance/532387/information

- **Lablup — 504 卡 LLM 预训练运营分析（DCGM + 训练可观测实战）**
  - https://arxiv.org/html/2605.09370v4

## 相邻主题交叉引用

| 主题 | 链接 | 与本主题关系 |
|---|---|---|
| KServe | /03-ai-platform/kserve/ | 模型服务平台暴露 /metrics 与 status conditions，是 AI SRE 的核心监控对象。 |
| LLM Gateway | /04-llmops/llm-gateway/ | Gateway 是 AI 服务的流量入口与核心 SLI 来源。 |
| vLLM | /04-llmops/vllm/ | 推理引擎 metrics（TTFT、ITL、KV cache）是监控重点。 |
| Agent Runtime | /05-agent/agent-runtime/ | Agent 步骤需要 trace 与 SLO。 |
| RAG | /06-rag/ | RAG 流水线需要专门的可观测性与评估指标。 |
| Benchmark + Evaluation | /07-ai-sre/benchmark-evaluation/ | AI SRE 的评测子主题：trace-based eval、benchmark 数据集、CI 评估门、生产回归检测。 |
| Agent OS | /05-agent/agent-os/ | 进程隔离与资源治理是故障缓解的底座。 |
| OpenAI 案例研究 | /09-case-study/openai/ | 大规模 LLM 服务的可观测性、SLO 与事件响应经验。 |
| Anthropic 案例研究 | /09-case-study/anthropic/ | run-rate $30B 增长冲击可靠性的容量治理；prompt cache 命中率作为 SLO。 |
| Meta 案例研究 | /09-case-study/meta/ | 同步训练可靠性工程标杆：SDC 三件套检测、~50x 中断下降、>95% 有效训练时间、故障→checkpoint→auto-restart 闭环。 |
| Linux 系统与性能调优 | /01-foundation/linux-systems/ | CPU、memory、I/O、network 指标都来自 Linux 内核；Linux 调优是 AI SRE 根因分析的基础。 |
| Google 案例研究 | /09-case-study/google/ | 超大规模同步训练可用率标杆：NSDI'24 healthd + preflight 四层检测、reconfigure/reroute 双路径恢复、99.98% 可用率、OCS 把主机可用率要求从 99.9% 降到 99%。 |
| DeepSeek 案例研究 | /09-case-study/deepseek/ | 开源 LLM 服务的生产可观测与故障恢复实践参照：推理集群 HAI-LLM 可观测、V3.1 灰度降级与 Fire-Flyer 文件系统容错。 |
| xAI 案例研究 | /09-case-study/xai/ | Colossus 超算集群（20 万卡）的故障注入演练、训练中断自愈与 RDMA 网络治理是 AI SRE 容量与韧性治理的参照。 |

## 推荐学习路径

1. **入门**：读完 Google SRE Book 与 Workbook，用 Prometheus + Grafana 搭建一个服务的 SLO 仪表板。
2. **进阶**：接入 OpenTelemetry，为 FastAPI/Flask 服务生成 trace 与 metrics；按 GenAI 语义约定埋点 LLM/Agent 调用。
3. **深入**：学习 tail-based sampling、SLO-as-code（Sloth/OpenSLO）、AIOps 异常检测；用 HolmesGPT/K8sGPT 在测试集群跑只读 Agent。
4. **生产**：为 LLM/Agent/RAG 服务定义多维 SLO，建立 on-call、runbook、postmortem 闭环；再评估 AI SRE Agent（shadow mode 起步）与 GPU 健康度监控。

## 一句话收尾

AI SRE 的终极目标不是“零故障”，而是让每一次故障都可观测、可度量、可恢复、可改进。

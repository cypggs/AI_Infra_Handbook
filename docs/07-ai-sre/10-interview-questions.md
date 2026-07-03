# 面试题

## 初级

### 1. 什么是 SLI、SLO、Error Budget？它们之间关系是什么？

**要点**：SLI 是指标，SLO 是目标，Error Budget = 1 - SLO，是允许的“坏”事件总量。

### 2. AI 系统与传统服务在监控上有什么不同？

**要点**：AI 可能返回 200 但内容错误；需要监控质量、幻觉、成本、模型漂移，而不仅是可用性。

### 3. 什么是 TTFT 和 ITL？为什么对 LLM 很重要？

**要点**：TTFT = Time to First Token，反映用户感知的首字延迟；ITL = Inter-Token Latency，反映生成流畅度。

### 4. OpenTelemetry 的三大信号是什么？

**要点**：traces、metrics、logs。

### 5. 什么是 burn rate？

**要点**：实际错误率除以 SLO 错误预算，用于把 SLO  breach 转化为告警。

## 中级

### 6. 如何为 LLM 服务设计 SLO？

**要点**：覆盖可用性、TTFT/ITL、质量分数、幻觉率、每次请求成本；按功能/模型分层。

### 7. Head-based sampling 和 Tail-based sampling 有什么区别？

**要点**：Head 在请求入口决定；Tail 等 trace 完成后按错误/延迟等条件决定是否保留。Tail 更适合保留异常 trace。

### 8. 如何检测模型幻觉或输出质量下降？

**要点**：LLM-as-judge、用户反馈、RAG 引用校验、NLI 模型、对比历史质量分布。

### 9. 多窗口 burn rate 告警怎么减少误报？

**要点**：短窗口发现突发问题，长窗口确认持续性；两者同时满足才告警。

### 10. AI SRE 中如何处理 PII？

**要点**：关闭 prompt/completion 内容捕获；Collector 层脱敏；敏感事件单独保留并加密。

## 高级

### 11. 设计一个可扩展的 AI 可观测性平台。

**要点**：OpenTelemetry 统一埋点 → Collector 采样/脱敏 → Prometheus/Thanos + Tempo/ClickHouse + Loki → Grafana SLO + AIOps → PagerDuty/Incident Manager。

### 12. 如何在多模型、多 provider 环境中做 SLO 与成本治理？

**要点**：统一 Gateway 收集按 model/provider 的 metrics；设定 tiered SLO；路由简单请求到便宜模型；按 user/feature 限额。

### 13. AIOps 在 AI SRE 中能做什么？边界在哪？

**要点**：告警降噪、动态基线、事件关联、根因推荐、生成 postmortem；边界在于低置信度时必须人工确认，不能自动执行高风险修复。

### 14. 如何设计一次 AI 生产事故的 postmortem？

**要点**：Timeline、影响范围、根因、缓解措施、action items；blameless；把改进项加入 backlog。

### 15. 如果模型版本更新后质量 SLO 下降，你会怎么做？

**要点**：快速回滚或灰度切换；分析 bad cases；更新评估集；复盘模型评估流程；必要时加入 shadow test。

## 小结

面试题覆盖了概念、实现与生产。准备时建议结合自己项目：你监控了哪些 AI 指标？SLO 是什么？遇到过哪些事故？如何改进？

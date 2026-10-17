# 最佳实践

本章整理 AI SRE 的检查清单与常见反模式。

## Instrumentation 检查清单

- [ ] 所有 AI 服务接入 OpenTelemetry SDK。
- [ ] LLM 调用记录 model、token、temperature、finish_reason、cache hit。
- [ ] Agent 每一步生成 span，工具调用作为子 span。
- [ ] RAG 检索记录 query、返回 chunk 数、rerank 分数。
- [ ] trace_id 在 Gateway、Agent、RAG、工具之间传递。
- [ ] 默认关闭 prompt/completion 内容捕获，按需开启并脱敏。

## Metrics 检查清单

- [ ] 监控 HTTP 可用性与端到端延迟。
- [ ] 单独监控 TTFT 与 ITL。
- [ ] 监控 token 用量与成本 per user / per feature / per model。
- [ ] 监控缓存命中率与降级次数。
- [ ] 监控 LLM-as-judge 质量分数、幻觉率、安全合规率。

## SLO / Alerting 检查清单

- [ ] 每个关键服务都有明确的 SLI 与 SLO。
- [ ] 告警基于 burn rate，而非固定阈值。
- [ ] 使用多窗口减少误报。
- [ ] 告警信息包含 trace 链接、影响范围、最近变更。
- [ ] 告警与 runbook 绑定。

## Incident Response 检查清单

- [ ] 有清晰的 severity 定义与升级路径。
- [ ] 已知故障模式有自动化 runbook。
- [ ] War room 自动创建，附带关键上下文。
- [ ] Postmortem blameless，action items 有 owner 与 deadline。
- [ ] 定期演练 runbook 与灾难恢复。

## AIOps 检查清单

- [ ] 先解决告警噪音，再做根因分析。
- [ ] 动态基线需要足够历史数据。
- [ ] AIOps 推荐必须附带置信度与证据。
- [ ] 保留人工否决与接管机制。

## AI SRE Agent 检查清单

- [ ] 以只读权限起步，写操作走人工批准流。
- [ ] 工具 token 与人员账号分离，支持单独撤销。
- [ ] 所有工具调用有审计链，可回放完整调查过程。
- [ ] 策略门禁（OPA/配额/熔断）覆盖 Agent 全部写操作。
- [ ] shadow mode 运行至少两周，用自有事故回放集验证后再放权。
- [ ] 监控 Agent 自身：任务完成率、重试放大系数、单次调查成本。
- [ ] Agent 引发的事故也按 blameless 流程复盘。

## GPU 健康检查清单

- [ ] DCGM exporter 全覆盖，监控 ECC/XID/throttle reason，而非只看利用率。
- [ ] ECC 单比特错误增长触发预防性换卡流程。
- [ ] 训练任务监控逐 rank 迭代时间与 AllReduce 延迟矩阵。
- [ ] 推理路由的健康评分同时考虑硬件、引擎、网络三层信号。

## 质量评估检查清单

- [ ] 同步护栏（确定性检查）与异步 judge 分离。
- [ ] judge 有哨兵样本与人工否决率监控，漂移即复校准。
- [ ] 点踩率/重试率/会话放弃率作为先行指标入库。

## 常见反模式

| 反模式 | 后果 | 修正 |
|---|---|---|
| 只看 HTTP 200 | 幻觉与质量漂移被掩盖 | 增加质量/幻觉指标 |
| 平均延迟当 SLO | 长尾体验差 | 用 TTFT/ITL P95/P99 |
| 全量采集 | 成本爆炸 | tail-based sampling |
| 固定阈值告警 | 大量误报漏报 | burn rate + 动态基线 |
| 无 Error Budget 政策 | 团队对可靠性没有共识 | 定义预算耗尽后的行动 |
| 忽略 PII | 数据泄露风险 | 关闭内容捕获或脱敏 |
| 没有 runbook | 每次事故重新摸索 | 把经验固化为文档与自动化 |
| Agent 直接拿写权限上生产 | 误操作扩大事故，且难以定责 | 只读起步、白名单 + 门禁 + 审计链 |
| 盲信厂商基准分 | 选型误判（自报分数普遍偏高） | 用独立榜单初筛 + 自有回放集终验 |
| judge 不校准 | 质量 SLO 被评分漂移污染 | 哨兵样本 + 否决率监控 |
| 只看 GPU 利用率 | 降频、显存错误被漏掉 | ECC/XID/throttle reason + 引擎指标 |

## 一句话总结

AI SRE 的最佳实践：**统一埋点、多维 SLO、burn-rate 告警、tail sampling、自动化响应（Agent 只读起步、渐进放权）、blameless 复盘**。

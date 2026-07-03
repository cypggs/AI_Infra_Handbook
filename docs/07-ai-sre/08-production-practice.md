# 企业生产实践

把 AI SRE 从 Demo 搬到生产，需要处理规模、成本、安全、多租户和组织协同。本章按主题给出落地经验。

## 1. 大规模 Instrumentation

| 问题 | 实践 |
|---|---|
| 数据量爆炸 | tail-based sampling + adaptive sampling，只保留高价值 trace |
| 全量日志成本过高 | 结构化日志 + 分级 retention，错误/慢请求全保留 |
| 多语言栈 | 统一 OpenTelemetry SDK 与 Collector，避免各团队重复造轮子 |
| 性能开销 | 异步 batch export、metrics 聚合后再上报 |

## 2. 采样策略

| 策略 | 适用 |
|---|---|
| 100% sampling | 开发/测试、低流量核心接口 |
| Head-based probabilistic | 通用在线服务，实现简单 |
| Tail-based | AI 服务推荐，按错误/高延迟/高成本保留 |
| Adaptive | 根据流量自动调整采样率，保持成本可控 |

## 3. SLO 治理

- **分层 SLO**：平台层（Gateway）、服务层（Agent Runtime）、能力层（RAG/LLM）。
- **质量 SLO**：用 LLM-as-judge 或用户反馈打分，设定 hallucination rate、relevance。
- **成本 SLO**：每会话/每用户 token 上限，防止成本失控。
- **Error Budget 政策**：预算耗尽时 freeze 非关键发布、启动 review。

## 4. 多租户与权限

- 每个 tenant 的 telemetry 通过 resource attribute 区分。
- 在 Collector 或后端按 tenant 做访问控制。
- 日志中避免泄露 prompt/PII；必要时做 token 化或哈希。

## 5. PII 与安全

- 关闭 `gen_ai.content.*` 默认捕获。
- Collector 层做 PII 检测与脱敏（regex、NER）。
- 敏感操作（安全事件、越狱尝试）100% trace 并长期保留。
- TLS 1.2+、加密存储、RBAC。

## 6. 成本与 Retention

- **三档 retention**：热（7–15 天）、温（90 天）、冷（1–7 年）。
- 高频 metrics 做降采样：15s → 1m → 5m → 1h。
- 对非生产环境降低采样率与 retention。

## 7. On-Call 与 Incident Response

- 告警分层：page（立即）、ticket（工作时间）、info（次日 review）。
- Runbook 与告警绑定，要求每一步可执行、可验证。
- War room 自动化：告警触发时自动拉群、创建 incident、附上 trace 链接。
- Postmortem 在 24–48 小时内完成，action items 进入 sprint。

## 8. AIOps 落地

- 从**告警降噪**开始：把相似告警聚类，减少 50% 以上噪音。
- 再引入**动态基线**：对 latency、token 用量、质量分数做异常检测。
- 最后做**根因推荐**：RAG over 历史 incident + 近期变更 + 依赖指标。
- 关键：AIOps 输出必须有置信度，低置信度时转人工。

## 9. 故障模式与应对

| 故障 | 应对 |
|---|---|
| 模型幻觉率上升 | 切换模型、启用 RAG、增加拒绝回答、回滚 prompt |
| 延迟 P99 飙升 | 限流、降级、缓存、扩容、模型切换 |
| 单用户成本异常 | 限流、告警、人工复核 |
| 工具调用失败 | 禁用 tool、fallback、告警 |
| 安全事件 | 人工接管、隔离、审计、升级 |
| 依赖 API 限流 | 多 provider 路由、指数退避、缓存 |

## 10. 持续改进

- 每周 SLO review：哪些 SLO 接近预算？为什么？
- 每月质量 audit：抽样评估模型输出质量。
- 每季度回顾 runbook 有效性、更新阈值与采样。

## 小结

生产级 AI SRE 的关键不是堆工具，而是建立**统一的 telemetry 标准、清晰的 SLO 政策、自动化的事件响应与持续复盘机制**。

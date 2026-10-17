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
- **质量 SLO**：用 LLM-as-judge 或用户反馈打分，设定 hallucination rate、relevance；同时监控 judge 自身健康度（哨兵样本漂移约 5% 告警、人工否决率超约 15% 复校准）。
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
- War room 自动化：告警触发时自动拉群、创建 incident、附上 trace 链接与 AI SRE Agent 的初步调查报告。
- Postmortem 在 24–48 小时内完成，timeline 可由 Agent 自动缝合草稿（来源可溯源），action items 进入 sprint。

## 8. AIOps 落地

- 从**告警降噪**开始：把相似告警聚类，减少 50% 以上噪音。
- 再引入**动态基线**：对 latency、token 用量、质量分数做异常检测。
- 然后做**根因推荐**：多智能体 ReAct + RAG over 历史 incident + 近期变更 + CMDB 拓扑；输出必须带置信度与证据，低置信度转人工。
- 成熟度量级参考（2026 行业报告）：Level 3（ML 辅助 RCA）可带来 40–50% MTTR 下降；Level 4（自愈）号称 18 个月 300% ROI，但约三分之一团队 rollout 失败——失败主因是 runbook 配置错误而非模型能力。
- 生产验证案例（厂商报告）：快手 KRCA 多智能体在 483 起真实事故复盘上根因正确率 82%（单 ReAct Agent 为 42%）；某混沌工程研究中人肉 RCA 约 62% 正确，GPT-4 约 52%——LLM 是优秀的副驾驶，尚不是主驾驶。

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
- 每月质量 audit：抽样评估模型输出质量，校准 judge。
- 每季度回顾 runbook 有效性、更新阈值与采样。

## 11. 推理集群与 GPU 健康度

LLM 服务自身就是一套需要 SRE 的基础设施，监控要同时覆盖硬件、引擎、网络三层：

| 层 | 关键信号 | 工具 |
|---|---|---|
| 硬件 | ECC 单/双比特错误、XID（48 = 换卡）、throttle reason、温度、功耗、NVLink 错误 | DCGM exporter（开销约 1–5%）→ Prometheus → Grafana |
| 推理引擎 | TTFT、ITL、queue time、KV cache 占用/命中率、batch 大小 | vLLM / SGLang / TRT-LLM 内置 metrics |
| 网络 | RTT、抖动、丢包、重传 | 节点 exporter + IB/RoCE 计数器 |

- **利用率 ≠ 速度**：GPU 可能 100% SM 占用但因功耗/温度降频而变慢，必须看带标签的 throttle reason 指标。
- **ECC 是先行指标**：单比特错误持续增长预示卡将故障，应触发 drain + checkpoint + 换卡流程，而不是等 XID 48 硬失败。
- **训练 straggler 定位**：逐 rank 迭代时间对比（慢于均值 15% 标疑）+ AllReduce 二维延迟矩阵（单格高 = 链路瓶颈，整行/列高 = 节点问题）；有生产系统报告靠这两招把故障定位从 30 分钟降到秒级。
- **推理路由健康评分**：2026 年的新做法是把 DCGM 硬件分 + vLLM 应用分 + 网络分加权成压力分，驱动请求放置与故障转移（研究报告：P99 尾延迟降 27.9%，failover P99 约 1.2s vs Round-Robin 4.2s）。

## 12. AI SRE Agent 落地

- **预期管理**：独立基准的严格口径下，Agent 端到端事故处置正确率约 40–60%（ITBench-AA 最佳 56.2%，OpenRCA 2.0 因果链完整落地 61.5%）。先把它定位成“永远在线的一级调查员”，不是“自动消防员”。
- **渐进放权**：shadow mode（只记录建议、不影响生产）至少两周 → 建议模式 → 批准执行 → 限定护栏自治；每级都用自有事故回放集验证命中率。
- **安全件是硬性要求**：只读默认；写操作白名单 + OPA 门禁；工具 token 与人员账号分离、可单独撤销；全量审计链；MCP Server 按信任分级隔离。
- **成本要单独预算**：Agent 调查每次调用多个工具与模型，按“每次调查成本”单独核算（2026 年行业观察：单次调查约数美元量级），防止巡检 Agent 本身成为成本漏洞。
- **给 Agent 做 SRE**：Agent 自身也是生产系统——监控其任务完成率、重试放大系数、工具错误率，并对它的推理循环加熔断与超时；若 Agent 引发事故，按 04 章流程对它做 postmortem。

## 小结

生产级 AI SRE 的关键不是堆工具，而是建立**统一的 telemetry 标准、清晰的 SLO 政策、自动化的事件响应与持续复盘机制**。

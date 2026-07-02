# 9. 最佳实践

> 一句话理解：LLM Gateway 的最佳实践不是追求功能最全，而是**在稳定性、成本、延迟、安全之间找到当前业务阶段的最优解**。

## 1. 供应商与模型选择

- **不要只绑定一家供应商**。至少准备一家备用，防止区域性故障或额度耗尽。
- **把昂贵模型当“精品”用**。简单任务用便宜模型或自研 vLLM，复杂任务才用 GPT-4o / Claude 3.5。
- **为不同任务定义 model alias**。例如：
  - `smart` → GPT-4o / Claude 3.5
  - `fast` → GPT-4o-mini / Llama-3.1-8B
  - `cheap` → 自研小模型
- **定期评估替代模型**。LLM 能力迭代快，上个月昂贵的模型可能本月已有性价比更高的替代。

## 2. 路由策略

- **默认用 weighted + priority**。权重控制成本比例，优先级保证主备切换。
- **延迟敏感场景用 least-latency**。但要加窗口平滑，避免某次抖动导致频繁切换。
- **长上下文单独路由**。长 prompt 走支持长上下文且价格合理的 provider。
- **按地域路由**。用户在欧洲，优先走欧洲 endpoint，降低延迟并满足数据驻留。

## 3. 限流与配额

- **多层限流**：全局 > tenant > user > model。
- **按 token 限流比按请求数更精准**。100 个短请求和 100 个长文请求对上游压力完全不同。
- **预算告警要前置**。不要等月底账单爆炸才发现问题。
- **给 burst 留缓冲**。Token bucket 的 capacity 要大于 refill_rate，允许合理突发。

## 4. 超时与退避

- **连接超时短，读取超时按场景设**。简单请求 10s，复杂长文 60s~120s。
- **指数退避必须加 jitter**。避免所有失败请求在同一时刻重试。
- **尊重 Retry-After**。如果上游明确返回，优先使用其值。
- **设置最大重试次数**。通常 2~3 次，过多会拖垮备用 provider。

## 5. 降级与熔断

- **降级链要清晰**。`primary → backup → cheapest → static error`。
- **fallback 模型要预先告知业务方**。避免输出质量突然下降引发客诉。
- **熔断阈值不要太敏感**。建议基于失败率 + 连续失败数双重判断。
- **半开探测流量要小**。防止一恢复就被打爆。

## 6. 可观测

- **把 Gateway 当统一观测点**。所有请求都经过它，指标最完整。
- **关注 TTFT 和 TPOT**。TTFT（Time To First Token）影响用户感知，TPOT（Time Per Output Token）影响总延迟。
- **按 tenant / model / provider 拆分大盘**。方便快速定位问题。
- **成本指标与业务指标一起展示**。例如：每千次对话成本、每个用户月均成本。

## 7. Secret 管理

- **不要在配置文件里写明文 API key**。即使是示例配置也要明确标记为“教学用途”。
- **使用 Vault / KMS / 云 Secret Manager**。
- **定期 rotate key**。Gateway 层支持 key 热切换，业务无感知。
- **区分 upstream key 和 gateway key**。上游 key 不暴露给客户端，客户端只用 gateway 颁发的 virtual key。

## 8. 缓存策略

- **Prompt 缓存**：对 FAQ、固定模板、重复查询效果显著。
- **语义缓存**：用 embedding 缓存相似 prompt 的结果，命中更高。
- **注意缓存失效**。模型版本更新、上下文变化时要失效或版本化缓存。
- **敏感数据不缓存**。涉及 PII 或商业机密的 prompt 应跳过缓存。

## 9. 安全与合规

- **输入侧**：PII 检测、敏感词过滤、越狱提示识别。
- **输出侧**：内容审核、敏感信息脱敏、引用来源校验。
- **审计**：记录完整请求日志（脱敏后），保留期限满足合规要求。
- **数据驻留**：按 tenant/region 路由，确保数据不跨境。

## 10. 金丝雀与 A/B 测试

- **新 provider 上线先给 1% 流量**。观察成功率、延迟、成本、输出质量。
- **按 header 切流量**。例如 `X-Canary: new-provider`。
- **回滚要快**。发现问题后能在秒级把流量切回旧 provider。
- **用 shadow traffic 做容量测试**。把部分流量镜像到新 provider，不影响真实用户。

## 11. 配置管理

- **配置即代码**。把 gateway 配置纳入 Git，走 code review。
- **分环境管理**。dev/staging/prod 用不同配置，但结构一致。
- **热更新但可回滚**。保留上一个版本的配置，便于快速回滚。
- **敏感配置与业务配置分离**。密钥用 Secret Manager，路由规则用 ConfigMap/Git。

## 12. 测试

- **单元测试**：路由、限流、转换、重试逻辑。
- **集成测试**：mock provider 端到端。
- **混沌测试**：模拟上游 429/500/超时，验证 fallback 与熔断。
- **负载测试**：验证限流与横向扩展能力。

## 最佳实践速查表

| 维度 | 推荐做法 |
|---|---|
| 供应商 | 多供应商 + 主备 + 按任务选模型 |
| 路由 | weighted + priority 默认；least-latency 针对延迟 |
| 限流 | 多层 + token-based + 预算告警 |
| 重试 | 指数退避 + jitter + 尊重 Retry-After |
| 熔断 | 失败率 + 连续失败 + 半开探测 |
| Secret | Vault/KMS + virtual key + 定期 rotate |
| 可观测 | Prometheus + Grafana + OpenTelemetry |
| 安全 | PII 过滤 + 审计 + 数据驻留 |
| 发布 | 金丝雀 + shadow traffic + 快速回滚 |
| 配置 | Git 管理 + 热更新 + 分环境 |

## 本章小结

LLM Gateway 的最佳实践覆盖了供应商管理、路由、限流、重试、熔断、可观测、安全、缓存、发布与配置管理十个方面。核心原则是：**用 Gateway 把复杂性与风险集中收敛，让业务方只关心“调用哪个 model alias”**。

**参考来源**

- [LiteLLM Best Practices](https://docs.litellm.ai/docs/proxy/enterprise)
- [OpenAI API — Rate Limits](https://platform.openai.com/docs/guides/rate-limits)
- [Google SRE Book — Reliability](https://sre.google/sre-book/table-of-contents/)

# 10. 面试题

## 初级

### Q1：LLM Gateway 与传统 API Gateway 有什么区别？

**参考答案**：

传统 API Gateway 主要处理通用七层能力：路由、负载均衡、认证、限流、日志。LLM Gateway 在此基础上增加了对 LLM 语义的理解：

- 按 `model` 路由，而不是只按 path/host。
- 按 token 用量限流与计费。
- 重试/降级需要考虑 429、内容审查、长超时等 LLM 特有失败模式。
- 需要统一 OpenAI-compatible API，屏蔽不同 provider 的协议差异。
- 需要成本追踪与输出质量相关指标（TTFT、TPOT）。

### Q2：为什么企业需要 LLM Gateway，而不是直接用 OpenAI SDK？

**参考答案**：

直接用 SDK 的问题：

- 每个业务都要处理多供应商差异、鉴权、重试、限流。
- 切换供应商需要改代码。
- 无法统一监控成本与用量。
- 无法做 fallback 与多区域路由。

Gateway 把这些问题收敛到一层，业务方只调一个统一入口。

### Q3：什么是 Provider 抽象？

**参考答案**：

Provider 抽象是指 Gateway 把 OpenAI、Azure、vLLM、Triton 等上游统一抽象成相同的接口。业务方请求的是 `model=gpt-4o`，Gateway 决定它对应哪个真实 endpoint、用什么协议、做什么转换。

## 中级

### Q4：常见的路由策略有哪些？各适合什么场景？

**参考答案**：

| 策略 | 特点 | 场景 |
|---|---|---|
| Round-robin | 轮流 | 上游同质 |
| Weighted | 按权重 | 控制成本比例 |
| Least-latency | 选延迟低的 | 延迟敏感 |
| Priority | 主备 | 成本优先，备用更贵 |
| Cost-based | 选 cheapest | 成本优先 |
| Content-based | 按 prompt 特征 | 长文/敏感内容分流 |

### Q5：限流用 Token Bucket 还是 Fixed Window？为什么？

**参考答案**：

Token Bucket 更适合 LLM Gateway，因为：

- 允许合理突发（burst），符合真实业务请求模式。
- 平滑限流，不会在窗口边界出现流量尖刺。
- 实现简单，内存开销低。

Fixed Window 在窗口边界容易突刺；Sliding Window 精确但内存开销大。

### Q6：重试时需要注意哪些问题？

**参考答案**：

- 只重试可重试错误：5xx、429、网络超时；不重试 4xx（除 429）。
- 使用指数退避 + jitter，避免惊群。
- 设置最大重试次数，防止拖垮备用 provider。
- 流式响应一旦开始发送，无法重试。
- 尊重上游 `Retry-After`。

### Q7：熔断器的状态机是怎样的？

**参考答案**：

```text
CLOSED（正常） → 失败率/连续失败超限 → OPEN（快速失败）
OPEN → 冷却时间到 → HALF-OPEN（放行少量探测请求）
HALF-OPEN → 探测成功 → CLOSED
HALF-OPEN → 探测失败 → OPEN
```

熔断状态通常需要跨 Gateway 实例共享（Redis），否则多实例会重复触发。

### Q8：如何实现多租户配额？

**参考答案**：

- API Key → tenant 映射。
- 限流键组合 tenant / user / model / app。
- Token bucket 容量与 refill rate 按 tenant 配置。
- 配额数据存在 Redis，保证多实例一致。
- 超出配额返回 429，并提示剩余配额。

## 高级

### Q9：设计一个支持 10k QPS 的 LLM Gateway，你会怎么设计？

**参考答案**：

- **数据面无状态**：使用 FastAPI/Go/Rust 异步处理，水平扩展。
- **状态外置**：限流、熔断、session 放 Redis。
- **接入层**：Nginx/Envoy 做 TLS 终止、连接复用、WAF。
- **路由**：加权 + latency-aware，动态剔除慢实例。
- **上游连接池**：与每个 provider 保持长连接，避免重复建连。
- **流式优化**：首包前完成路由与重试；使用 chunked transfer。
- **可观测**：Prometheus + OpenTelemetry + 按 tenant 分大盘。
- **容量规划**：按 token/s 而不是 req/s 做容量评估。

### Q10：流式响应失败时，Gateway 如何优雅处理？

**参考答案**：

- 路由和 provider 选择在发送第一个 chunk 前完成。
- 一旦开始流式，不再做整体重试；若上游断开，向客户端发送 `data: [DONE]` 或特定错误 event。
- 可以记录“流式中断”指标，用于定位上游稳定性。
- 对非流式请求保留完整重试/降级能力。

### Q11：Gateway 如何统一不同 provider 的错误码？

**参考答案**：

- 维护 provider 错误码到 OpenAI 标准错误码的映射表。
- 429 → 429 Too Many Requests。
- 5xx → 502/503 Bad Gateway / Service Unavailable。
- 内容审查 → 400 并附带 `content_filter` 原因。
- 在响应体里保留原始错误信息，方便排查。

### Q12：成本追踪在 Gateway 层怎么做？

**参考答案**：

- 解析上游响应的 `usage` 字段，得到 input/output token 数。
- 用内置价格表计算：`cost = input_tokens * input_price + output_tokens * output_price`。
- 按 tenant / user / model / provider 聚合。
- 暴露 Prometheus 指标，并写入成本数据库做月结。
- 对没有 `usage` 的 provider，用本地 tokenizer 估算。

## 本章小结

面试中关于 LLM Gateway 的问题通常集中在：**与传统网关的区别**、**路由/限流/重试/熔断**、**多租户配额**、**流式与错误处理**、**成本与可观测**。掌握本章问题，基本可以覆盖中级到高级面试场景。

**参考来源**

- [LiteLLM Proxy Reliability](https://docs.litellm.ai/docs/proxy/reliability)
- [OpenAI API Errors](https://platform.openai.com/docs/guides/error-codes)
- [Envoy AI Gateway Routing](https://aigateway.envoyproxy.io/docs/)

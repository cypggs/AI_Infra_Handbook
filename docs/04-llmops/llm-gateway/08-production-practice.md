# 8. 企业生产实践

> 一句话理解：生产环境的 LLM Gateway 要解决的不是“能不能跑”，而是“能不能在高并发、多租户、多区域、多供应商的情况下稳定、低成本、可审计地跑”。

## 部署形态选择

### 独立服务（推荐大多数团队）

```text
Client -> DNS / Global Load Balancer -> LLM Gateway Cluster -> Providers
```

适用：

- 多个业务方共享模型资源。
- 需要统一成本核算、审计、配额。
- 团队有运维网关的经验。

高可用要点：

- 至少 2 个副本，跨可用区部署。
- 使用 Redis 共享限流、熔断、会话状态。
- 配置中心支持热更新。
- 日志、指标、tracing 集中收集。

### Sidecar

```text
App Pod [App Container + Gateway Sidecar]
```

适用：

- 低延迟要求极高。
- 每个应用需要独立的配额与策略。
- 已有 Service Mesh 基础设施。

注意：

- 配置碎片化，需要统一的配置分发机制。
- 资源占用随 Pod 数线性增长。
- 成本聚合需要把 sidecar 指标统一汇总。

### 边缘网关

Cloudflare AI Gateway、AWS API Gateway 等属于此类。

适用：

- 希望零运维、全球加速。
- 需要边缘缓存与边缘安全。
- 不担心供应商锁定。

## Kubernetes 部署示例

以 LiteLLM Proxy 为例，最小部署：

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: llm-gateway
spec:
  replicas: 3
  selector:
    matchLabels:
      app: llm-gateway
  template:
    metadata:
      labels:
        app: llm-gateway
    spec:
      containers:
        - name: gateway
          image: ghcr.io/berriai/litellm:main-latest
          args: ["--config", "/etc/litellm/config.yaml"]
          ports:
            - containerPort: 4000
          volumeMounts:
            - name: config
              mountPath: /etc/litellm
          envFrom:
            - secretRef:
                name: llm-gateway-secrets
      volumes:
        - name: config
          configMap:
            name: litellm-config
---
apiVersion: v1
kind: Service
metadata:
  name: llm-gateway
spec:
  selector:
    app: llm-gateway
  ports:
    - port: 80
      targetPort: 4000
```

Secret 管理：

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: llm-gateway-secrets
type: Opaque
stringData:
  OPENAI_API_KEY: "sk-..."
  AZURE_API_KEY: "..."
```

> 生产上更推荐使用 External Secrets Operator 从 Vault/AWS Secrets Manager 同步。

## 多租户与配额

多租户是 LLM Gateway 的核心生产场景。常见隔离维度：

| 维度 | 说明 | 限流键示例 |
|---|---|---|
| Tenant | 团队/部门级别 | `tenant:team-a` |
| Application | 应用级别 | `tenant:team-a:app:chatbot` |
| User | 用户级别 | `tenant:team-a:user:u123` |
| Model | 模型级别 | `tenant:team-a:model:gpt-4o` |

配额策略：

- **硬配额**：超过即拒绝，保护上游。
- **软配额**：超过后允许但告警/降速。
- **预算上限**：按美元设置月度预算，超支后禁止调用昂贵模型。

## 与 vLLM / Triton 集成

### vLLM 作为上游

vLLM 自带 OpenAI-compatible server：

```bash
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-3.1-8B-Instruct \
  --tensor-parallel-size 1 \
  --port 8000
```

Gateway 配置：

```yaml
providers:
  vllm-llama:
    kind: openai
    base_url: http://vllm-service:8000/v1
    models: [llama-3.1-8b]
```

### Triton 作为上游

Triton 提供 OpenAI-compatible frontend（2025 年底进入 stable）。Gateway 可直接把它当作 OpenAI provider：

```yaml
providers:
  triton-llm:
    kind: openai
    base_url: http://triton-service:8000/v2/models/ensemble/generate
    models: [triton-llama-3.1-8b]
```

如果 Triton 暴露的是 gRPC，则 Gateway 需要额外做 gRPC ↔ HTTP 转换。

## 多区域与多供应商降级

生产推荐设计 fallback 链：

```text
Primary   : Azure OpenAI (us-east)
Backup 1  : OpenAI (global)
Backup 2  : Anthropic Claude (us-west)
Backup 3  : 自研 vLLM (on-prem)
```

触发条件：

- HTTP 5xx 或 429。
- 延迟超过 SLO（例如 TTFT > 2s）。
- 内容审查拒绝（不可重试，直接返回）。

实现方式：

- Gateway 维护每个 region/provider 的健康状态。
- 跨 region 路由时优先选择地理最近的 healthy provider。
- 主 region 故障时，DNS 或 Gateway 自动切到备用 region。

## 成本优化实践

1. **模型降级**：默认用便宜模型处理简单任务，复杂任务才用贵模型。
2. **缓存**：重复 prompt 直接返回缓存结果，减少调用。
3. **批量调用**：把多个小请求合并成 batch，降低 per-request 开销。
4. **智能路由**：按 prompt 长度/复杂度选择 cheapest provider。
5. **监控成本异常**：按应用/用户设置预算告警，防止某处 burst。

## 可观测体系

生产需要三类可观测数据：

| 类型 | 工具 | 关注点 |
|---|---|---|
| Metrics | Prometheus + Grafana | QPS、延迟、token、成功率、成本 |
| Logs | Loki / ELK | 请求详情、错误堆栈、审计 |
| Traces | OpenTelemetry + Jaeger | 请求在网关与上游的完整链路 |

关键告警：

- 5xx 率 > 1% 持续 5 分钟。
- P99 延迟 > 阈值。
- 某 provider 失败率突增。
- 租户配额使用接近上限。

## 安全与合规

1. **Secret 管理**：API key 不存代码、不存镜像，使用 Vault / KMS。
2. **传输安全**：TLS 1.2+，内部服务间 mTLS。
3. **内容安全**：PII 过滤、敏感词检测、越狱提示识别。
4. **审计日志**：记录 who/when/what model/how many tokens。
5. **数据驻留**：某些合规场景要求数据不出境，Gateway 需要按 tenant 路由到特定 region。

## 常见踩坑

| 踩坑 | 原因 | 解法 |
|---|---|---|
| 流式响应中断无法重试 | chunk 已发送给客户端 | 重试窗口只放在首包前；建立连接超时设置合理 |
| 限流键太粗 | 一个租户打满全局 bucket | 多维度限流：tenant + model + user |
| fallback 模型能力不匹配 | 备用模型输出质量差 | 明确 fallback 模型能力边界，必要时返回错误 |
| 上游 429 导致重试风暴 | 没有 jitter / backoff | 指数退避 + jitter + 按 Retry-After 等待 |
| 配置热更新导致状态不一致 | 部分实例先加载新配置 | 使用配置版本号 + 原子切换 |
| 日志泄露敏感信息 | prompt 含 PII | 日志脱敏，只记录 token 长度与 hash |

## 本章小结

生产级 LLM Gateway 需要在部署形态、多租户配额、上游集成、多区域降级、成本控制、可观测、安全合规等方面做系统设计。网关本身不生产模型能力，但它是模型能力能否稳定、经济、合规地交付给业务的关键层。

**参考来源**

- [LiteLLM Proxy — Deploy](https://docs.litellm.ai/docs/proxy/deploy)
- [LiteLLM Production Guide](https://docs.litellm.ai/docs/proxy/production)
- [Envoy AI Gateway — Backend](https://aigateway.envoyproxy.io/docs/)
- [Cloudflare AI Gateway](https://developers.cloudflare.com/ai-gateway/)

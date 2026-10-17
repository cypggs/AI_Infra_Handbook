# 3. 架构设计

> 一句话理解：LLM Gateway 的架构可以概括为“**南北向收敛、东西向解耦、控制面与数据面分离**”——所有客户端走一个统一入口，后端可以任意扩展，策略由控制面集中管理。

## 整体架构

```mermaid
flowchart TB
    Client[Client / SDK / Agent]
    GW[LLM Gateway 数据面]
    CP[控制面 / Admin API]
    Obs[可观测 stack<br/>Prometheus / Grafana / Jaeger]

    Client -->|HTTPS / HTTP2| GW
    GW -->|配置拉取| CP
    GW -->|指标上报| Obs

    GW --> P1[Provider A<br/>OpenAI]
    GW --> P2[Provider B<br/>Azure OpenAI]
    GW --> P3[Provider C<br/>vLLM Cluster]
    GW --> P4[Provider D<br/>Triton / TRT-LLM]
    GW --> P5[Provider E<br/>SGLang]
```

## 分层职责

| 层级 | 职责 | 典型组件/能力 |
|---|---|---|
| **接入层（Ingress）** | TLS 终止、HTTP/2、负载均衡、WAF | Nginx、Envoy、Cloudflare、AWS ALB |
| **网关数据面** | 认证、限流、路由、转换、重试、指标 | LiteLLM Proxy、Envoy AI Gateway、Kong AI Gateway、自研 |
| **网关控制面** | 配置、provider 注册、配额、审计 | Postgres/Redis、Admin API、Vault |
| **上游 Provider** | 实际模型推理 | OpenAI、Azure、vLLM、Triton、SGLang |
| **可观测层** | 日志、指标、追踪、成本分析 | Prometheus、Grafana、OpenTelemetry、Langfuse |

## 数据面内部模块

```mermaid
flowchart LR
    Req[HTTP Request]
    Auth[Auth Middleware]
    RL[Rate Limiter]
    Router[Router]
    LB[Load Balancer]
    Transform[Transformer]
    Retry[Retry / Fallback / CB]
    Provider[Provider Client]
    Metrics[Metrics]

    Req --> Auth --> RL --> Router --> LB --> Transform --> Retry --> Provider
    Provider --> Transform2[响应转换] --> Metrics --> Resp[HTTP Response]
```

### 接入顺序的考量

1. **Auth 放在第一位**：没权限的请求尽早拒绝，避免后续资源浪费。
2. **Rate Limiter 放在 Auth 之后**：只有知道是谁，才能按租户限流。
3. **Router 在限流之后**：确定能放行，再决定去哪。
4. **Transformer 在路由之后**：不同 provider 可能需要不同的请求体格式。
5. **Retry / Fallback 紧贴上游调用**：把失败封装在 provider client 内部。
6. **Metrics 贯穿全程**：记录每个阶段的延迟与结果。

## 控制面设计

控制面通常包含：

### 配置中心

- Provider 定义：endpoint、model alias、权重、优先级、超时、重试次数。
- 路由规则：按 model / tenant / prompt 特征匹配。
- 限流策略：token bucket 容量、 refill rate。
- 密钥映射：api_key → tenant / quota / allowed_models。

### Provider Registry

- 动态注册/下线 provider。
- 健康检查与权重调整。
- 支持 canary 发布：新 provider 先给少量流量。

### 配额与审计

- 实时用量：按 api_key、tenant、model、user 聚合。
- 审计日志：记录谁、何时、调用了什么模型、消耗多少 token。
- 成本分摊：把账单拆分到应用/团队。

### Secret 管理

- 上游 provider 的 API key 应存储在 Vault / KMS / 云 Secret Manager。
- Gateway 只保存引用或短期 token，不持久化明文。

## 部署形态

### 形态 1：独立服务

```text
Client -> DNS/ALB -> LLM Gateway (容器/VM) -> Providers
```

优点：集中管理、易于扩展、适合多业务方。
缺点：多一跳网络延迟，需要保证自身高可用。

### 形态 2：Sidecar

```text
App Pod [App Container + Gateway Sidecar] -> Providers
```

优点：低延迟、按应用隔离、无共享网关瓶颈。
缺点：配置分散、运维复杂、资源碎片。

### 形态 3：边缘网关

```text
Client -> CDN/Edge -> LLM Gateway -> Origin Providers
```

Cloudflare AI Gateway 是典型代表，适合缓存、全球加速、边缘安全。

### 形态 4：Service Mesh 扩展

Envoy AI Gateway 通过 Envoy filter + Gateway API 实现，适合已经使用 Istio/Envoy 的团队。

### 形态 5：MCP / Agent 网关（2025-2026 新形态）

随着 Agent 应用爆发，网关的北向接口不再只有 `/v1/chat/completions`，还需要托管 MCP（Model Context Protocol）端点：向上为 Agent 提供统一的工具入口，向下聚合/转换多个 MCP Server 与存量 REST API。

```text
Agent --MCP (tools/list, tools/call)--> MCP Gateway --HTTP/REST--> 存量业务 API
                                     \--MCP--> 上游 MCP Server
```

典型实现：LiteLLM MCP Gateway（聚合 + 工具白名单 + 虚拟 key 隔离）、Higress（REST API 零代码转 MCP Server + MCP Marketplace）、Envoy AI Gateway（MCPRoute / MCPRouteSecurityPolicy CRD + CEL 工具级鉴权）。

## 网关 × 推理引擎集成的新范式：KV-Cache 感知路由

传统架构里网关只按“哪台健康”做负载均衡。2025 年起，自托管 vLLM/SGLang 集群普遍采用 **Kubernetes Gateway API Inference Extension（GIE）**：数据面网关把“选哪个副本”的决策委托给一个独立的 Endpoint Picker（EPP）组件。

```mermaid
flowchart LR
    Client --> GW[Envoy / Gateway]
    GW -->|ext_proc 询问| EPP[Endpoint Picker<br/>llm-d / Dynamo EPP]
    subgraph Fleet[vLLM 集群]
        V1[副本 1<br/>KV 前缀: ABC, 队列 3]
        V2[副本 2<br/>KV 前缀: ABX, 队列 0]
        V3[副本 3<br/>KV 前缀: 空, 队列 1]
    end
    EPP -->|"前缀命中多 + 最空闲"| V2
    EPP -.上报指标.-> Prom[(Prometheus<br/>vllm:kv_cache_usage 等)]
```

关键机制：

- EPP 通过 vLLM 暴露的指标（如 `vllm:kv_cache_usage_perc`、队列深度，vLLM v0.10+ 支持 KV cache 事件流）维护每个副本的状态视图。
- 路由目标从“最空闲”升级为“KV cache 前缀命中最多 + 最空闲”，相同前缀的连续请求落到同一副本，prefix caching 直接转化为 TTFT 收益（llm-d 报告热命中 TTFT 降低约 88%）。
- 决策开销控制在毫秒级（GKE 实测约 1~2ms），Google 已在 1.7 万节点规模验证多集群 GIE 开销小于 1%。

对应地，商业与半托管方案也在跟进：阿里云推理扩展网关提供估计模式（不依赖引擎改造）与精确模式（vLLM v0.10+ KV 事件）；NVIDIA Dynamo 提供兼容 GIE 的 EPP，并支持 prefill/decode 分离调度。

> eBPF 的角色：2026 年 eBPF（以 Cilium 为代表）已承担网关数据面的 L3/L4 快速路径、负载均衡与可观测，LLM 语义决策（EPP、工具鉴权）仍跑在用户态。两者是“内核转发 + 用户态决策”的叠加关系，而非替代关系。

## 与 Service Mesh 的关系

| 维度 | Service Mesh | LLM Gateway |
|---|---|---|
| 关注点 | 服务间通信安全、流量、可观测 | 客户端到 LLM provider 的统一接入与治理 |
| 路由粒度 | 服务 / 版本 / header | model / tenant / cost / latency / content |
| 失败处理 | 通用重试、超时、熔断 | LLM 语义重试、fallback、内容审查 |
| 位置 | 通常作为 sidecar 或 shared proxy | 独立服务或边缘节点 |

两者不冲突：Service Mesh 管东西向，LLM Gateway 管南北向；也可以让 LLM Gateway 本身作为 Mesh 的一个 workload。

## 数据面状态设计

理想的数据面是**无状态**的，这样可以直接水平扩展：

```text
                 ┌─ Gateway Pod 1
Client -> LB ────┼─ Gateway Pod 2
                 └─ Gateway Pod 3
```

但限流、熔断、会话上下文会引入状态：

- **限流**：Token bucket 状态可放在 Redis，保证跨实例一致。
- **熔断**：Circuit breaker 状态可放在 Redis 或 gossip 同步。
- **会话**：多轮对话的 session affinity 可通过 sticky header 或外部 cache 解决。

## 本章小结

LLM Gateway 架构的核心是“统一入口 + 数据面快速决策 + 控制面集中治理”。无论是独立服务、Sidecar、边缘部署还是 2025 年后兴起的 MCP/Agent 网关形态，都需要把认证、限流、路由、转换、重试、指标这些能力模块化、可配置化；而自托管推理集群则应通过 Gateway API Inference Extension 把 KV-cache 感知的路由决策下沉到独立的 Endpoint Picker。

**参考来源**

- [LiteLLM Architecture](https://docs.litellm.ai/docs/proxy/architecture)
- [Envoy AI Gateway Architecture](https://aigateway.envoyproxy.io/docs/)
- [Kubernetes Gateway API Inference Extension](https://github.com/kubernetes-sigs/gateway-api-inference-extension)
- [llm-d 官网](https://www.llm-d.ai/)
- [GKE Inference Gateway：KV-Cache-Aware 路由](https://www.spheron.network/blog/gke-inference-gateway-kv-cache-aware-llm-routing/)
- [Higress v2.2.4：新版 MCP 与 Gateway API 推理扩展](https://higress.ai/blog/higress-mmse_awbbpb_qwo0xq9sf9bc9i21/)
- [Kong AI Gateway Plugin](https://docs.konghq.com/hub/kong-inc/ai-proxy/)

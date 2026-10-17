# 1. 背景

## 为什么需要 LLM Gateway？

在 [vLLM](/04-llmops/vllm/)、[SGLang](/04-llmops/sglang/)、[TensorRT-LLM](/04-llmops/tensorrt-llm/)、[Triton Inference Server](/04-llmops/triton/) 解决完“单个模型如何跑得快”之后，生产环境真正要面对的是：

> **企业里同时存在多家供应商、多个自研引擎、多种协议，业务方却只想用一个统一入口调用模型。**

典型场景包括：

1. **多云/多供应商**：OpenAI GPT-4o、Azure OpenAI、Anthropic Claude、Google Gemini、AWS Bedrock、阿里云百炼、百度千帆等混用。
2. **多自研引擎**：vLLM 跑开源模型、TensorRT-LLM 跑 NVIDIA 优化模型、Triton 跑多框架模型、SGLang 跑结构化生成。
3. **多业务方/多租户**：不同团队、不同应用共享同一套模型资源，需要按租户隔离配额与成本。
4. **横切能力重复建设**：认证、限流、重试、降级、日志、成本追踪每家业务都自己写一遍。

如果没有网关，架构会变成这样：

```mermaid
flowchart LR
    A[业务 A] -->|OpenAI SDK| OAI[OpenAI]
    B[业务 B] -->|Azure SDK| AZ[Azure OpenAI]
    C[业务 C] -->|HTTP| vLLM[vLLM 集群]
    D[业务 D] -->|gRPC| Triton[Triton]
    E[业务 E] -->|自定义协议| TRT[TensorRT-LLM]
```

每个业务都要处理：不同 SDK、不同鉴权、不同重试策略、不同错误码、不同成本核算口径。运维也痛苦：无法统一限流，无法快速切换供应商，无法统一监控。

引入 LLM Gateway 后，架构收敛为：

```mermaid
flowchart LR
    A[业务 A] --> GW
    B[业务 B] --> GW
    C[业务 C] --> GW[LLM Gateway]
    GW --> OAI[OpenAI]
    GW --> AZ[Azure]
    GW --> vLLM[vLLM]
    GW --> Triton[Triton]
    GW --> TRT[TRT-LLM]
```

## LLM Gateway 从 API 代理演进到 AI 控制面

早期的 API 代理只解决两个问题：

- 把请求转发到后端。
- 加一层鉴权或缓存。

但在 LLM 场景下，仅做转发远远不够，因为：

- **模型选择是动态的**：同一个 `gpt-4o` 可能对应 OpenAI、Azure、自研 vLLM 三个上游，需要根据成本、延迟、可用性实时选择。
- **失败模式复杂**：LLM 调用可能因内容审查、速率限制、模型过载、长上下文导致超时，需要重试、降级、熔断。
- **成本敏感**：输入/输出 token 价格差异大，需要按用户/应用追踪用量与费用。
- **安全与合规**：需要过滤 PII、敏感词、越狱提示，需要审计日志。

因此，现代 LLM Gateway 已经从“代理”演进到“AI 控制面”：

```text
API Proxy -> API Gateway -> AI Gateway -> LLM Control Plane
```

它不仅要转发，还要做**智能决策**。

## 没有 LLM Gateway 会怎样？

| 问题 | 没有 Gateway 的表现 | 有 Gateway 的解法 |
|---|---|---|
| 供应商切换 | 业务代码里硬编码 OpenAI SDK，切换要改代码 | Gateway 层改 model alias 映射，业务无感知 |
| 限流 | 单点限流靠业务自己，容易击穿 | 按 api_key / model / tenant 统一 Token Bucket |
| 失败降级 | 主供应商 429 时业务直接报错 | Gateway 自动重试并切换到备用 provider |
| 成本控制 | 月底看账单才发现某应用烧钱 | 实时记录 token 用量，按应用/用户/模型聚合 |
| 可观测 | 各 SDK 日志格式不同，难以统一 | Gateway 统一输出请求数、延迟、状态码、token 数 |
| 安全合规 | 每个业务自己实现内容过滤 | Gateway 统一做 PII/敏感词/越狱检测 |

## LLM Gateway 与相关方案的对比

| 方案 | 定位 | 优点 | 缺点 |
|---|---|---|---|
| **裸 SDK 直连** | 业务直接调用 OpenAI/Azure SDK | 简单、延迟最低 | 无统一治理、重复建设 |
| **传统 API Gateway（Kong/NGINX）** | 通用七层网关 | 成熟、插件丰富 | 对 LLM 语义（model、token、retry、fallback）理解不足 |
| **Service Mesh（Istio/Linkerd）** | 服务间流量治理 | 透明、可观测强 | 通常作用于微服务间，对 LLM 语义路由需额外扩展 |
| **Triton Inference Server** | 多框架推理服务入口 | 强 GPU 调度、backend 抽象 | 主要面向自托管模型，多云供应商接入需额外封装 |
| **KServe** | Kubernetes 上的模型服务框架 | 自动扩缩、蓝绿发布 | 以 Kubernetes 为中心，对供应商 API 的抽象较弱 |
| **LiteLLM Proxy** | 专门面向 LLM 的统一网关 | 100+ provider 抽象、OpenAI-compatible、内置 MCP Gateway 与 Guardrails，成本低 | 开源版高可用/多集群需要自行设计；需及时跟进安全补丁 |
| **Envoy AI Gateway** | 基于 Envoy 的 AI 网关 | 2026 年 6 月发布 v1.0 GA，与 Kubernetes Gateway API 深度集成、BackendSecurityPolicy 统一管密钥、原生 MCP 路由与鉴权 | 语义缓存等高级能力需外部 ext_proc 扩展；部署相对复杂 |
| **Higress** | 云原生 AI 网关（CNCF Sandbox） | 基于 Envoy + Wasm 插件，率先支持 MCP 网关（REST API 零代码转 MCP Server、MCP Marketplace）、Gateway API 推理扩展（AdaptiveScore 负载均衡） | 社区生态以中文为主 |
| **Apache APISIX** | 通用 API 网关的 AI 插件集 | ai-proxy / ai-proxy-multi / ai-prompt-guard / ai-cache（支持语义缓存）全开源，etcd 驱动的热更新 | 通用网关基因，LLM 语义能力以插件形式提供 |
| **Kong AI Gateway** | 企业级 AI 网关 | 2025 年发布 ai-semantic-cache（语义缓存）、6 种 LLM 负载均衡算法；2026 年拆分为独立 AI Gateway 2.x 产品 | 语义缓存、Guardrails、MCP 代理等高级插件多为 Enterprise 档位 |
| **Portkey** | 开源 AI Gateway（MIT）+ 商业平台 | TypeScript 实现、轻量易嵌入，内置简单/语义双模缓存与 50+ Guardrails | 深度治理能力依赖商业平台；2026 年被 Palo Alto Networks 收购 |
| **OpenRouter** | 托管多模型聚合 API | 一个 OpenAI-compatible 端点接入 400+ 模型、按 provider 透传计价，代表“模型市场型网关” | 公有云托管，无私有部署；加价随规模累积，无内置语义缓存 |
| **Cloudflare AI Gateway** | 边缘 AI 网关 | 零部署、缓存、分析 | 供应商锁定、自定义能力有限 |

> 选型速记：快速落地选 LiteLLM；已有 Envoy/Kubernetes Gateway API 体系选 Envoy AI Gateway；国内 MCP 场景选 Higress；已有 Kong 基础设施选 Kong；轻量嵌入应用选 Portkey；不想运维选 Cloudflare / OpenRouter。

> 一句话：如果你需要把“多家供应商 + 多个自研引擎 + 多个业务方”统一管起来，LLM Gateway 是最合适的抽象层。

## 2025-2026：从 LLM Gateway 演进到 MCP / Agent Gateway

2025 年下半年以来，网关的治理对象从“chat completions 请求”扩展到了“Agent 的工具调用”，行业出现了三条清晰的新脉络：

### 1. 语义缓存（Semantic Caching）成为标配能力

精确缓存（prompt 哈希完全一致才命中）之外，主流网关陆续内置**语义缓存**：把 prompt 用 embedding 模型向量化，存入向量库，新请求按余弦相似度命中相似 prompt 的缓存结果。典型落地：

- **Kong Gateway 3.8**（2025 年）发布 `ai-semantic-cache` 插件，embedding + 向量存储 + 相似度阈值，命中时官方称延迟可降低 3~10 倍。
- **Apache APISIX** 的 `ai-cache` 插件支持精确、语义、流式三种缓存模式，全部开源。
- **Portkey** 提供 simple（精确）+ semantic（语义）双模级联缓存，RAG 场景命中率可达 18~60%。
- **LiteLLM** 内置 Redis 精确缓存，并在 2026 年版本中加入语义级缓存与语义 MCP 工具检索。

> 注意：Envoy AI Gateway 截至 v1.0 仍未内置语义缓存，需要通过 `ext_proc` 外接处理器 + 向量库实现。

### 2. MCP Gateway：治理对象从“模型”变成“工具”

MCP（Model Context Protocol）成为 Agent 访问工具的事实标准后，网关需要理解 MCP 的 `tools/list`、`tools/call` 语义，在工具粒度上做鉴权、限流、审计：

- **LiteLLM**：内置 MCP Gateway，支持把多个上游 MCP Server 聚合为一个端点，提供按 deny-by-default 的工具白名单、按虚拟 key 的工具级访问控制、MCP spec 版本固定等治理能力。
- **Higress**：国内率先提供 MCP 网关能力，支持存量 REST API “零代码”转化为 MCP Server、MCP Marketplace，并在 2026 年 7 月 MCP 新协议修订（无状态 HTTP Tools 基线）发布不到三周内首个支持，可把 MCP 方法与工具名放入 HTTP Header 做路由、鉴权、限流与计量。
- **Envoy AI Gateway v1.0**（2026 年 6 月 GA）把 `MCPRoute` / `MCPRouteSecurityPolicy` 做成稳定 CRD，支持基于 CEL 表达式的工具级细粒度鉴权（按 JWT claims 过滤工具）。
- **Kong AI Gateway 2.2**（2026 年 9 月）加入 MCP 工具治理与身份感知的 AI 策略。

### 3. 与推理引擎深度集成：KV-Cache 感知路由

自托管 vLLM/SGLang 集群的网关不再满足于 round-robin。通过 Kubernetes **Gateway API Inference Extension**（GIE），网关侧的 Endpoint Picker（EPP）读取各副本的 KV cache 前缀命中情况与队列深度，把请求路由到“缓存命中最多 + 最空闲”的副本：

- GKE Inference Gateway（2025 年 Cloud Next 发布）与 **llm-d**（Red Hat 主导，Apache 2.0）是代表实现，llm-d 报告 KV 命中率约 87%、热命中 TTFT 降低约 88%。
- **NVIDIA Dynamo** 提供兼容 GIE 的 EPP，支持 prefill/decode 分离调度；阿里云“推理扩展网关”提供估计模式与精确模式两档前缀缓存感知路由。

```mermaid
flowchart LR
    Client -->|chat/completions| GW[AI Gateway<br/>含 EPP]
    GW -->|"KV-cache 感知"| V1[vLLM 副本 1<br/>持有前缀 ABC]
    GW --> V2[vLLM 副本 2<br/>队列空闲]
    GW --> V3[vLLM 副本 3]
    MCP[Agent / MCP Client] -->|"tools/call"| GW
    Cache[(语义缓存<br/>embedding + 向量库)] -.命中.-> GW
```

此外，eBPF 开始在网关数据面底层承担 L3/L4 快速路径与可观测（Cilium + per-node Envoy 的无 sidecar 模式在 2026 年成为主流），但 LLM 语义决策（路由、限流、工具鉴权）仍运行在用户态——“eBPF 做转发、用户态做决策”是当前务实形态。

## 本章小结

LLM Gateway 的产生不是技术炫技，而是生产环境多供应商、多引擎、多租户治理的必然结果。它把认证、路由、限流、重试、降级、成本、可观测这些横切问题从业务代码中抽离，形成一个可演进、可审计、可治理的 AI 控制面。2025-2026 年，这一层又长出三个新枝干：**语义缓存降本、MCP/Agent 工具治理、与推理引擎的 KV-cache 感知协同**。

**参考来源**

- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [LiteLLM Documentation](https://docs.litellm.ai)
- [LiteLLM Release Notes](https://docs.litellm.ai/release_notes/)
- [Envoy AI Gateway v1.0 GA（Tetrate）](https://tetrate.io/press/envoy-ai-gateway-reaches-v1-0-establishing-the-open-source-standard-for-enterprise-ai-traffic)
- [Kong AI Gateway 3.8：Semantic Caching](https://konghq.com/blog/product-releases/ai-gateway-3-8)
- [Higress 官网](https://higress.ai/)
- [Higress v2.2.4 支持新版 MCP 基线](https://higress.ai/blog/higress-mmse_awbbpb_qwo0xq9sf9bc9i21/)
- [Portkey Semantic Cache 文档](https://docs.portkey.ai/docs/product/ai-gateway/cache-simple-and-semantic)
- [OpenRouter Models 文档](https://openrouter.ai/docs/guides/overview/models)
- [Kong AI Gateway with Redis（语义缓存）](https://redis.io/blog/kong-ai-gateway-and-redis/)
- [NGINX AI Gateway](https://www.nginx.com/solutions/ai-gateway/)

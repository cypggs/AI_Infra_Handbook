# 6. 源码分析

> 一句话理解：现代 LLM Gateway 的源码核心可以概括为“**配置驱动 + 插件化流水线 + 统一 OpenAI 协议适配**”；本节以 LiteLLM 为主轴，结合 Envoy/Kong AI Gateway 的过滤器链设计，说明关键代码组织与扩展点。

## 分析对象选择

| 项目 | 仓库 | 定位 | 分析重点 |
|---|---|---|---|
| **LiteLLM** | [BerriAI/litellm](https://github.com/BerriAI/litellm) | 开源 LLM 统一调用库 + Proxy | Provider 抽象、Router、Rate Limit、Fallback |
| **Envoy AI Gateway** | [envoyproxy/ai-gateway](https://github.com/envoyproxy/ai-gateway) | 基于 Envoy 的 AI 网关 | Gateway API 集成、Filter 链、backend 协议转换 |
| **Kong AI Gateway** | [Kong/kong](https://github.com/Kong/kong) | API Gateway 的 AI 插件集 | Plugin 体系、上游选择、token 计数 |

> 注：开源项目迭代较快，本节基于 2026 年 7 月前后主流分支的结构进行分析，具体文件名可能随版本微调。

## LiteLLM 架构概览

LiteLLM 由两部分组成：

1. **`litellm` Python SDK**：统一的 `completion()` / `embedding()` 接口，屏蔽 100+ provider 差异。
2. **`litellm-proxy`（LiteLLM Proxy Server）**：基于 FastAPI 的网关，把 SDK 能力暴露为 OpenAI-compatible HTTP 服务。

Gateway 形态主要使用后者，其源码组织大致如下：

```text
litellm/
├── proxy/
│   ├── proxy_server.py      # FastAPI 入口、startup、路由注册
│   ├── proxy_cli.py         # 命令行入口
│   ├── proxy_config.yaml    # 配置示例
│   ├── auth/
│   │   └── auth_utils.py    # API Key / JWT 校验
│   ├── hooks/
│   │   └── proxy_logging.py # 日志、指标、成本追踪
│   └── route_llm.py         # 请求路由相关
├── router.py                # Router 核心：load balance、fallback、retry
├── main.py                  # SDK 入口
├── integrations/            # 与 Langfuse、Langsmith、OpenTelemetry 集成
└── litellm_core_utils/      # token 计数、异常处理、规则校验
```

## LiteLLM Proxy Server 启动流程

`proxy_server.py` 的核心启动逻辑：

1. **解析配置**：从 `config.yaml` 或环境变量读取 `model_list`、`router_settings`、`litellm_settings`。
2. **初始化 Router**：把 `model_list` 中的每个模型条目传给 `litellm.Router`。
3. **注册鉴权**：根据配置启用 API Key、JWT 或 OAuth。
4. **挂载 OpenAI 路由**：`/v1/models`、`/v1/chat/completions`、`/v1/embeddings` 等。
5. **启动 FastAPI**：监听 HTTP/HTTPS，暴露 `/metrics` 等管理端点。

关键配置示例：

```yaml
model_list:
  - model_name: gpt-4o
    litellm_params:
      model: openai/gpt-4o
      api_key: os.environ/OPENAI_API_KEY
      weight: 0.7
  - model_name: gpt-4o
    litellm_params:
      model: azure/gpt-4o
      api_base: os.environ/AZURE_API_BASE
      api_key: os.environ/AZURE_API_KEY
      weight: 0.3

router_settings:
  routing_strategy: weighted-priority
  num_retries: 3
  retry_after: 1
  fallback: [{"gpt-4o": "gpt-4o-mini"}]

litellm_settings:
  success_callback: ["langfuse"]
  failure_callback: ["langfuse"]
```

## Router 核心实现

`litellm/router.py` 是网关最复杂的部分之一，职责包括：

### Provider 选择

Router 维护一个 `model_list`，并为每个 `model_name` 维护候选 provider。选择时：

- 过滤掉被标记为 unhealthy 的 provider（通过内部健康检查或失败计数）。
- 根据 `routing_strategy` 决定选哪一个：
  - `simple-shuffle`：random。
  - `least-busy`：选当前未完成请求数最少的。
  - `weighted-priority`：按权重，权重相同按优先级。
  - `latency-based-routing`：根据历史延迟 EMA 选择。

### Retry 与 Fallback

当某个 provider 失败时：

1. 判断是否可重试（5xx、429、timeout）。
2. 按指数退避重试 `num_retries` 次。
3. 若仍失败，查找 `fallback` 映射，把请求发给备用模型。
4. 记录失败到内部失败计数器，供健康检查使用。

### 健康检查

LiteLLM Router 没有重量级独立 health check，而是通过请求结果动态维护：

- 连续失败超过阈值 → 标记 cooldown。
- cooldown 期间减少流量或完全跳过。
- 一段时间后重新尝试（类似半开熔断）。

## Rate Limiter 实现

LiteLLM Proxy 的限流主要在 `proxy_server.py` 的请求入口实现：

- 按 `api_key`、`model`、`team`、`user` 组合生成限流键。
- 使用 Redis 作为后端存储时，基于 `Redis` 的滑动窗口或 token bucket。
- 限流返回 OpenAI 风格的 `429` 错误，并附带 `Retry-After`。

配置示例：

```yaml
general_settings:
  master_key: sk-xxx
  proxy_batch_write_at: 1
  
router_settings:
  redis_host: localhost
  redis_port: 6379
```

## Auth 与 Key 管理

LiteLLM Proxy 支持两种模式：

1. **Master Key**：单一 `Authorization: Bearer sk-master` 管理一切。
2. **Virtual Keys**：通过 Admin API 创建虚拟 key，映射到 tenant / budget / allowed_models。

虚拟 key 信息通常保存在 Postgres，支持：

- 按 key 设置 budget（美元上限）。
- 按 key 设置 rate limit。
- 按 key 设置 allowed model list。

## 日志、指标与成本

`proxy/hooks/proxy_logging.py` 在请求前后执行回调：

- **成功回调**：把 `model`、`usage`、`response_cost` 发送给 Langfuse / Langsmith / OpenTelemetry。
- **失败回调**：记录异常类型与重试次数。
- **Prometheus**：暴露 `litellm_requests_total`、`litellm_latency` 等指标。

成本计算依赖 `litellm.get_model_cost_map()`，其中维护了各 provider/model 的 input/output token 单价。

## Envoy AI Gateway 的过滤器链

Envoy AI Gateway 不是独立网关，而是基于 Envoy 的扩展：

```text
Client -> Envoy Listener -> HTTP Connection Manager -> AI Gateway Filters -> Upstream Cluster
```

关键扩展点：

1. **Filter 链**：
   - **AI Input Filter**：解析 OpenAI 请求，提取 model、messages、stream。
   - **AI Routing Filter**：根据 model / backend 选择 upstream cluster。
   - **AI Output Filter**：转换响应格式，统计 token。
2. **Gateway API**：通过 Kubernetes Gateway API 定义 LLM 路由规则，与 Ingress 统一管理。
3. **Backend Policy**：把 provider（OpenAI、vLLM 等）声明为 Backend，配置 credential、timeout、retry。

Envoy 的优势在于：

- 与现有 Service Mesh / Kubernetes Gateway API 生态无缝集成。
- C++ 数据面性能高。
- 可插拔 filter，适合需要深度定制的团队。

## Kong AI Gateway 的插件体系

Kong 通过一系列 AI 插件实现 LLM 网关能力：

- **`ai-proxy`**：把请求代理到 LLM provider，支持 OpenAI、Azure、Anthropic、Cohere 等。
- **`ai-request-transformer`**：修改请求体，例如添加 system prompt。
- **`ai-response-transformer`**：格式化响应。
- **`ai-prompt-guard`**：敏感词/越狱检测。
- **`ai-prompt-template`**：预定义 prompt 模板。
- **`ai-token-rate-limiting`**：按 token 限流。

Kong 的插件链与 NGINX/OpenResty 的 access/content/log 阶段对应，适合已有 Kong 基础设施的团队。

## 源码层面的共同模式

| 能力 | LiteLLM | Envoy AI Gateway | Kong AI Gateway |
|---|---|---|---|
| Provider 抽象 | `model_list` + `litellm_params` | Backend + Extension | `ai-proxy` upstream |
| 路由 | `router.py` | AI Routing Filter | Route + Plugin |
| 限流 | Redis / in-memory | Rate Limit Filter | `ai-token-rate-limiting` |
| 重试降级 | `router.py` retry/fallback | Retry Policy | NGINX retry / plugin |
| 认证 | Virtual Keys / JWT | External Auth Filter | Key Auth / OAuth2 |
| 可观测 | Langfuse / Prometheus | Envoy stats / OTLP | Kong Analytics |

## 本章小结

LiteLLM、Envoy AI Gateway、Kong AI Gateway 虽然实现不同，但都遵循“配置驱动 + 插件/过滤器链 + 统一协议适配”的模式。LiteLLM 适合快速落地和多样化 provider；Envoy 适合与 Kubernetes Gateway API / Service Mesh 深度集成；Kong 适合已有 API 网关基础设施的团队。

**参考来源**

- [LiteLLM GitHub](https://github.com/BerriAI/litellm)
- [LiteLLM Proxy Docs](https://docs.litellm.ai/docs/proxy/)
- [Envoy AI Gateway Docs](https://aigateway.envoyproxy.io/docs/)
- [Kong AI Gateway Plugins](https://docs.konghq.com/hub/?q=ai)

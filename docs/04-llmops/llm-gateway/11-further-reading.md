# 11. 延伸阅读

## 官方文档（必读）

- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
  - 现代 LLM Gateway 的事实标准协议。
- [vLLM OpenAI-compatible Server](https://docs.vllm.ai/en/stable/serving/openai_compatible_server.html)
  - 如何把 vLLM 作为 Gateway 的上游 Provider。
- [Triton OpenAI-compatible Frontend](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/protocol/extension_generate.html)
  - Triton 的 OpenAI 兼容端点说明。
- [LiteLLM Documentation](https://docs.litellm.ai)
  - 最流行的开源 LLM 统一调用库与 Proxy Server。
- [LiteLLM Proxy Server](https://docs.litellm.ai/docs/proxy/)
  - Gateway 模式的核心文档。

## 开源项目

- [BerriAI/litellm](https://github.com/BerriAI/litellm)
  - 100+ provider 抽象、Proxy Server、虚拟 key、预算管理，2025 年后内置 MCP Gateway 与 Guardrails hook；2026 年下半年新增 Auto Router、Decisions API 与 `litellm.agent()`（2026 年 10 月稳定版 v1.105）。
- [envoyproxy/ai-gateway（Agent Router）](https://github.com/envoyproxy/ai-gateway)
  - 基于 Envoy 的 AI 网关，v1.0（2026 年 6 月）提供稳定 CRD 与 MCP 工具级鉴权，与 Kubernetes Gateway API 集成；v1.2（2026 年 10 月）起更名 Agent Router，CRD 与 API group 保持不变。
- [Kong/kong](https://github.com/Kong/kong)
  - Kong AI Gateway 插件体系，3.8 起含 ai-semantic-cache、ai-prompt-decorator；AI Gateway 2.2（2026 年 9 月 GA）加入 MCP Server Bundling 与 MCP ACL。
- [alibaba/higress](https://github.com/alibaba/higress)
  - 云原生 AI 网关（CNCF Sandbox），Wasm 插件体系、MCP 网关与 Marketplace、推理扩展负载均衡。
- [apache/apisix](https://github.com/apache/apisix)
  - 云原生 API 网关，ai-proxy / ai-prompt-guard / ai-cache 插件全开源。
- [Portkey AI Gateway](https://github.com/Portkey-AI/gateway)
  - MIT 协议的开源 AI 网关（TypeScript），内置简单/语义双模缓存与 Guardrails。
- [kubernetes-sigs/gateway-api-inference-extension](https://github.com/kubernetes-sigs/gateway-api-inference-extension)
  - Gateway API 推理扩展：KV-cache 感知路由的标准 CRD 与 Endpoint Picker 参考实现。
- [llm-d](https://github.com/llm-d/llm-d)
  - Red Hat 主导的 Kubernetes 原生推理网关，prefix-cache 感知调度。
- [mlflow/mlflow — AI Gateway](https://mlflow.org/docs/latest/llms/gateway/index.html)
  - MLflow 生态中的 LLM Gateway。

## 协议与标准

- [Model Context Protocol 规范](https://modelcontextprotocol.io/specification)
  - Agent 访问工具的事实标准，2026 年演进为无状态 HTTP Tools 基线。
- [OpenTelemetry GenAI 语义约定](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
  - 网关 GenAI 指标与追踪的标准命名。

## 商业/托管方案

- [Cloudflare AI Gateway](https://developers.cloudflare.com/ai-gateway/)
  - 边缘 AI 网关，提供缓存、分析、日志。
- [NGINX AI Gateway](https://www.nginx.com/solutions/ai-gateway/)
  - NGINX 的 AI 网关解决方案。
- [Kong AI Gateway](https://docs.konghq.com/gateway/latest/ai-gateway/)
  - Kong 的企业级 AI 网关（2026 年拆分为独立 2.x 产品）。
- [OpenRouter](https://openrouter.ai/docs/guides/overview/models)
  - 模型市场型网关：一个 OpenAI-compatible 端点接入 400+ 模型。
- [Portkey 文档](https://docs.portkey.ai/docs/product/ai-gateway)
  - 开源网关 + 商业治理平台（2026 年被 Palo Alto Networks 收购）。
- [AWS Bedrock AgentCore Gateway](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html)
  - 全托管 Agentic 网关：API/Lambda/OpenAPI/Smithy 自动转 MCP 工具，Cedar 默认拒绝策略，网关侧 Guardrails，按调用量计费。

## 相关主题

- [Agent Runtime 详解](/05-agent/agent-runtime/) — Agent 的执行容器，常与 LLM Gateway 组合使用以统一接入多模型。
- [vLLM 详解](/04-llmops/vllm/) — LLM 推理引擎，可作为 Gateway 上游。
- [SGLang 详解](/04-llmops/sglang/) — LLM Program 执行引擎，可作为 Gateway 上游。
- [TensorRT-LLM 详解](/04-llmops/tensorrt-llm/) — NVIDIA 编译型推理引擎，可作为 Gateway 上游。
- [Triton Inference Server 详解](/04-llmops/triton/) — 多框架推理服务入口，常与 Gateway 配合使用。
- [KServe 详解](/03-ai-platform/kserve/) — Kubernetes 模型服务平台，可为 Gateway 提供集群内模型端点、扩缩与金丝雀能力。
- [Ray 详解](/03-ai-platform/ray/) — Ray Serve 可作为 Gateway 上游的分布式推理引擎，Ray Serve LLM 提供 OpenAI-compatible 端点。
- [LLM 推理缓存与 KV Cache 管理详解](/04-llmops/kv-cache/) — 网关层 prefix 路由与缓存亲和（KV-cache 感知调度）的基础设施视角，与 Gateway API Inference Extension / llm-d 呼应。
- [Perplexity 案例研究](/09-case-study/perplexity/) — 推理经济学典型案例：网关/路由层如何在高吞吐搜索场景下管理推理成本与延迟。

## 推荐学习路径

1. 先通读 OpenAI API Reference，理解请求/响应格式。
2. 本地用 LiteLLM Proxy 接入 OpenAI 与 vLLM，跑通 `/chat/completions`。
3. 阅读 LiteLLM `router.py` 与 `proxy_server.py`，理解路由与限流实现。
4. 学习 Agent Router 的 CRD（AIGatewayRoute / BackendSecurityPolicy / MCPRoute）与 filter 链。
5. 用 Higress 把一个存量 REST API 转成 MCP Server，体验 Agent 网关的治理粒度。
6. 在 vLLM 集群上试验 Gateway API Inference Extension / llm-d，观察 prefix-cache 命中对 TTFT 的影响。
7. 用本主题的 [Mini Demo](./07-mini-demo) 手动扩展一个自定义 provider 或路由策略。
8. 在生产环境中从独立 LiteLLM Proxy 开始，逐步引入 Redis、Vault、Prometheus 与 Guardrails。

## 本章小结

LLM Gateway 的生态系统正在快速演进。OpenAI API 已成为事实标准，LiteLLM 是最易落地的开源方案并以 Auto Router / Decisions API 向 Agent 层延伸，Agent Router（原 Envoy AI Gateway）以 v1.0 GA 成为 Kubernetes 体系的标准答案，Higress 在 MCP 网关场景领先，Kong AI Gateway 2.2 把 MCP 治理推进到工具发现阶段，AWS Bedrock AgentCore Gateway 提供了全托管的企业级替代，Cloudflare / OpenRouter 等托管方案则适合希望零运维的团队；语义缓存、MCP 工具治理、KV-cache 感知路由与成本分档计量是 2025-2026 年的四条主线。结合本主题的 [Mini Demo](./07-mini-demo)、[生产实践](./08-production-practice) 与 [最佳实践](./09-best-practices)，可以从理论到工程全面掌握 LLM Gateway。

**参考来源**

- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [LiteLLM Docs](https://docs.litellm.ai)
- [Agent Router Docs](https://aigateway.envoyproxy.io/docs/)
- [Agent Router Release Notes](https://theagentrouter.ai/release-notes/)
- [Kong AI Gateway Docs](https://docs.konghq.com/gateway/latest/ai-gateway/)
- [Higress 官网](https://higress.ai/)
- [Cloudflare AI Gateway Docs](https://developers.cloudflare.com/ai-gateway/)
- [AWS Bedrock AgentCore Gateway 文档](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html)
- [MLflow AI Gateway Docs](https://mlflow.org/docs/latest/llms/gateway/index.html)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [LiteLLM Release Notes](https://docs.litellm.ai/release_notes/)

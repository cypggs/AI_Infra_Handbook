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
  - 100+ provider 抽象、Proxy Server、虚拟 key、预算管理。
- [envoyproxy/ai-gateway](https://github.com/envoyproxy/ai-gateway)
  - 基于 Envoy 的 AI 网关，与 Kubernetes Gateway API 集成。
- [Kong/kong](https://github.com/Kong/kong)
  - Kong AI Gateway 插件体系。
- [mlflow/mlflow — AI Gateway](https://mlflow.org/docs/latest/llms/gateway/index.html)
  - MLflow 生态中的 LLM Gateway。

## 商业/托管方案

- [Cloudflare AI Gateway](https://developers.cloudflare.com/ai-gateway/)
  - 边缘 AI 网关，提供缓存、分析、日志。
- [NGINX AI Gateway](https://www.nginx.com/solutions/ai-gateway/)
  - NGINX 的 AI 网关解决方案。
- [Kong AI Gateway](https://docs.konghq.com/gateway/latest/ai-gateway/)
  - Kong 的企业级 AI 网关。

## 相关主题

- [Agent Runtime 详解](/05-agent/agent-runtime/) — Agent 的执行容器，常与 LLM Gateway 组合使用以统一接入多模型。
- [vLLM 详解](/04-llmops/vllm/) — LLM 推理引擎，可作为 Gateway 上游。
- [SGLang 详解](/04-llmops/sglang/) — LLM Program 执行引擎，可作为 Gateway 上游。
- [TensorRT-LLM 详解](/04-llmops/tensorrt-llm/) — NVIDIA 编译型推理引擎，可作为 Gateway 上游。
- [Triton Inference Server 详解](/04-llmops/triton/) — 多框架推理服务入口，常与 Gateway 配合使用。
- [Ray 详解](/03-ai-platform/ray/) — Ray Serve 可作为 Gateway 上游的分布式推理引擎，Ray Serve LLM 提供 OpenAI-compatible 端点。

## 推荐学习路径

1. 先通读 OpenAI API Reference，理解请求/响应格式。
2. 本地用 LiteLLM Proxy 接入 OpenAI 与 vLLM，跑通 `/chat/completions`。
3. 阅读 LiteLLM `router.py` 与 `proxy_server.py`，理解路由与限流实现。
4. 学习 Envoy AI Gateway 的 filter 链与 Gateway API 集成。
5. 用本主题的 [Mini Demo](./07-mini-demo) 手动扩展一个自定义 provider 或路由策略。
6. 在生产环境中从独立 LiteLLM Proxy 开始，逐步引入 Redis、Vault、Prometheus。

## 本章小结

LLM Gateway 的生态系统正在快速演进。OpenAI API 已成为事实标准，LiteLLM 是最易落地的开源方案，Envoy/Kong 适合与现有基础设施深度集成，Cloudflare 等托管方案则适合希望零运维的团队。结合本主题的 [Mini Demo](./07-mini-demo)、[生产实践](./08-production-practice) 与 [最佳实践](./09-best-practices)，可以从理论到工程全面掌握 LLM Gateway。

**参考来源**

- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [LiteLLM Docs](https://docs.litellm.ai)
- [Envoy AI Gateway Docs](https://aigateway.envoyproxy.io/docs/)
- [Kong AI Gateway Docs](https://docs.konghq.com/gateway/latest/ai-gateway/)
- [Cloudflare AI Gateway Docs](https://developers.cloudflare.com/ai-gateway/)
- [MLflow AI Gateway Docs](https://mlflow.org/docs/latest/llms/gateway/index.html)

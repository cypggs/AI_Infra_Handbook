# LLM Gateway 总览

> 一句话理解：**LLM Gateway 是客户端与多种推理后端之间的访问控制与抽象层**，它把“用哪家模型、走哪条链路、限多少流、失败怎么办”这些横切问题从业务代码里抽离出来，集中治理。

## 学习目标

阅读完本主题后，你应该能够：

1. 解释为什么企业在 vLLM / TensorRT-LLM / Triton / OpenAI / Azure 共存时需要 LLM Gateway。
2. 说清楚 LLM Gateway 的 8 大核心能力：Provider 抽象、统一 API、路由、负载均衡、限流、重试降级、认证、可观测。
3. 画出典型 LLM Gateway 架构，并说明控制面与数据面的职责边界。
4. 理解一个请求从进入网关到返回的完整生命周期。
5. 对比 LiteLLM Proxy、Envoy AI Gateway、Kong AI Gateway、NGINX AI Gateway、Cloudflare AI Gateway 的侧重点。
6. 跑通并扩展本主题的 Mini Demo，理解其代码组织。
7. 回答生产部署、多租户、成本追踪、安全相关的面试问题。

## LLM Gateway 与 LLMOps 其他主题的关系

| 主题 | 解决的核心问题 | 与 LLM Gateway 的关系 |
|---|---|---|
| [vLLM](/04-llmops/vllm/) | 单个开源 LLM 如何跑得快 | Gateway 可以把 vLLM OpenAI-compatible Server 作为一个上游 Provider |
| [SGLang](/04-llmops/sglang/) | LLM Program 执行与结构化生成 | Gateway 可路由到 SGLang 后端并做请求/响应格式转换 |
| [TensorRT-LLM](/04-llmops/tensorrt-llm/) | NVIDIA 编译型推理引擎 | Gateway 可以把 TensorRT-LLM Triton backend 作为高性能上游 |
| [Triton Inference Server](/04-llmops/triton/) | 多框架统一推理服务 | Gateway 通常位于 Triton 前面，处理认证、限流、多租户 |
| [计算机网络](/01-foundation/computer-networks/) | 网络协议、LB、DNS、服务网格 | Gateway 的负载均衡、DNS、路由、TLS 终止都建立在计算机网络基础之上 |
| **LLM Gateway** | 多引擎/多云/多租户统一接入 | 承上启下，向下屏蔽 Provider 差异，向上暴露统一 API |
| 安全 | /08-security/ | Gateway 是认证、限流、审计、Provider key 隔离与 Guardrails 的核心策略执行点。 |

## 本章结构

1. [背景](01-background) — 多供应商与多引擎带来的协议碎片化。
2. [核心思想](02-core-ideas) — Gateway 的 8 大横切能力。
3. [架构设计](03-architecture) — 控制面与数据面，以及与 Service Mesh 的关系。
4. [Runtime 工作流程](04-runtime-workflow) — 请求生命周期详解。
5. [核心模块](05-core-modules) — 配置、Provider、路由、限流、重试、认证、转换、指标。
6. [源码分析](06-source-analysis) — 以 LiteLLM 为主，Envoy/Kong 为辅。
7. [工程实践](07-mini-demo) — 纯 Python 可运行的 Mini Demo。
8. [企业生产实践](08-production-practice) — Sidecar、独立服务、Kubernetes 部署、多区域降级。
9. [最佳实践](09-best-practices) — 供应商选择、限流、超时、缓存、PII 过滤。
10. [面试题](10-interview-questions) — 初级/中级/高级面试题。
11. [延伸阅读](11-further-reading) — 官方文档、论文、开源项目。

## 一句话总结

LLM Gateway 不是又一个推理引擎，而是**推理服务的“前门”和“控制面”**；它让业务方像调用一家供应商一样调用多家模型，同时让平台方统一治理路由、成本、质量与安全。

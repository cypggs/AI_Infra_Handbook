# KServe：云原生模型服务平台

> 一句话理解：**KServe 是把 vLLM/Triton/TorchServe/TensorFlow Serving 等单个推理引擎封装成统一、可扩缩、可灰度、可观测的 Kubernetes 服务的控制平面**——用户只写一个 `InferenceService` CR，KServe 自动选好 runtime、拉起 Pod、接入流量、处理扩缩和金丝雀；它是 AI 平台从"能跑一个模型"到"能服务一千个模型"的关键一层。

## 学习目标

读完本主题，你应该能：

1. 解释为什么需要 KServe（裸部署 vLLM/Triton 的痛点）。
2. 说清 KServe 的核心抽象：`InferenceService`、`Predictor`/`Transformer`/`Explainer`、`ServingRuntime`/`ClusterServingRuntime`、`InferenceGraph`。
3. 理解 Serverless 模式（Knative，缩到零）和 RawDeployment 模式（原生 K8s + HPA）的取舍。
4. 理解 V1、V2（Open Inference Protocol）、OpenAI-compatible 三种数据面协议。
5. 追踪一个 `InferenceService` 从 `kubectl apply` 到请求被路由的完整链路。
6. 了解 KServe 源码主结构和关键控制器调用链。
7. 动手跑一个纯 Python mini-demo，模拟 runtime 选择、Pod 渲染、流量路由、canary。
8. 知道生产落地要点：runtime 选择、协议统一、金丝雀、autoscaling、多租户、可观测、成本。

## 与相邻主题的关系

| 主题 | 关系 | 链接 |
|---|---|---|
| **Operator 模式** | KServe 本身是一个 Operator（`kserve-controller-manager`），`InferenceService` 就是 CRD | [Operator 模式](../../02-cloud-native/operator/) |
| **vLLM / Triton / SGLang / TensorRT-LLM** | 它们是 KServe 的 runtime 之一，被 `ServingRuntime` 抽象封装 | [LLMOps 篇](../../04-llmops/) |
| **Kubernetes** | KServe 的底座：Deployment/Service/Ingress/CRD/Scheduler/Leader Election | [Kubernetes](../../02-cloud-native/kubernetes/) |
| **Ray** | 分布式训练/推理平台，可与 KServe 互补（Ray Serve 也是替代方案） | [Ray 主题](../ray/) |
| **LLM Gateway** | 统一多供应商/多模型接入，可与 KServe 的模型端点组合 | [LLM Gateway](../../04-llmops/llm-gateway/) |
| **存储系统** | 模型权重通过对象存储/共享 PVC 加载；storage-initializer 是存储系统的上层应用 | [存储系统](../../01-foundation/storage-systems/) |
| **AI SRE** | KServe 的指标、SLO、扩缩告警是 SRE 核心 | [AI SRE](../../07-ai-sre/) |

## 本章结构

| 章节 | 标题 | 内容 |
|---|---|---|
| 1 | [背景](01-background) | 裸推理服务的痛点、KServe 诞生、与裸 vLLM/Triton/自研网关的对比 |
| 2 | [核心思想](02-core-ideas) | InferenceService、Predictor/Transformer/Explainer、ServingRuntime、InferenceGraph、协议面 |
| 3 | [架构设计](03-architecture) | Control Plane vs Data Plane、Serverless vs RawDeployment、runtime 注册表、网关层 |
| 4 | [Runtime 工作流程](04-runtime-workflow) | 一次 `kubectl apply` 到请求被路由的完整时序 |
| 5 | [核心模块](05-core-modules) | Controller、Webhook、Runtime Manager、Agent/Queue-Proxy、Ingress/Gateway、Autoscaler、Metrics |
| 6 | [源码分析](06-source-analysis) | `kserve` repo 结构、IS controller reconcile 调用链、关键代码 |
| 7 | [Mini Demo](07-mini-demo) | 纯 Python 模拟 KServe 控制面：runtime 选择、Pod 渲染、canary、autoscaling |
| 8 | [企业生产实践](08-production-practice) | 多 runtime 管理、协议统一、金丝雀、缩到零、多租户、可观测、成本 |
| 9 | [最佳实践](09-best-practices) | runtime 选型、协议选择、请求/响应大小、超时、错误处理、安全 |
| 10 | [面试题](10-interview-questions) | 初/中/高级 KServe 高频题 |
| 11 | [延伸阅读](11-further-reading) | 官方文档、论文/博客、生态工具、学习路径 |

## 一句话总结

**KServe = Kubernetes 上的"模型服务操作系统"**：Operator 负责生命周期，ServingRuntime 负责模型格式，InferenceGraph 负责组合，网关负责流量，autoscaler 负责弹性——让你用一份声明式 CRD 服务任意模型。

## 参考来源

- [KServe 官网](https://kserve.github.io/website/)
- [KServe GitHub](https://github.com/kserve/kserve)
- 本手册 [Operator 模式](../../02-cloud-native/operator/)、[vLLM](../../04-llmops/vllm/)、[Triton](../../04-llmops/triton/)、[Ray](../ray/)

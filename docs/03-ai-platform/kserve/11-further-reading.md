# 11. 延伸阅读

## 官方文档

- [KServe 官网](https://kserve.github.io/website/)
- [KServe GitHub](https://github.com/kserve/kserve)
- [KServe Python SDK](https://kserve.github.io/website/sdk_docs/sdk_doc/)
- [Open Inference Protocol](https://github.com/kserve/open-inference-protocol)

## 关键概念文档

- [InferenceService API](https://kserve.github.io/website/docs/get_started/first_isvc/)
- [ServingRuntime / ClusterServingRuntime](https://kserve.github.io/website/docs/concepts/resources/servingruntime/)
- [InferenceGraph](https://kserve.github.io/website/docs/concepts/resources/inference_graph/)
- [Data Plane Protocol](https://kserve.github.io/website/docs/concepts/data_plane/)
- [Architecture](https://kserve.github.io/website/docs/concepts/architecture/)
- [Autoscaling](https://kserve.github.io/website/docs/modelserving/autoscaling/)
- [Canary Rollout](https://kserve.github.io/website/docs/modelserving/v1beta1/rollout/canary/)
- [LLMInferenceService 概览](https://kserve.github.io/website/docs/model-serving/generative-inference/llmisvc/llmisvc-overview) / [架构深入](https://kserve.github.io/website/docs/next/concepts/architecture/control-plane-llmisvc) / [LoRA Adapters](https://kserve.github.io/website/docs/model-serving/generative-inference/llmisvc/lora-adapters)
- [LocalModelCache](https://kserve.github.io/website/docs/0.17/model-serving/generative-inference/modelcache/localmodel)
- [kserve/modelmesh（已归档，仅供历史参考）](https://github.com/kserve/modelmesh)

## 版本发布博客（2025-2026 演进线）

- [Announcing KServe v0.15（2025-06）](https://www.cncf.io/blog/2025/06/18/announcing-kserve-v0-15-advancing-generative-ai-model-serving/) —— LocalModelCache、LMCache、Envoy AI Gateway。
- [KServe 成为 CNCF 孵化项目（2025-11）](https://www.cncf.io/blog/2025/11/11/kserve-becomes-a-cncf-incubating-project/)
- [Announcing KServe v0.17（2026-03）](https://kserve.github.io/website/blog/kserve-0.17-release) —— LLMInferenceService 生产可用、安装拆分。
- [Announcing KServe v0.18（2026-04）](https://kserve.github.io/website/blog/kserve-0.18-release) —— 多节点推理、Responses API、llm-d v0.6。
- [KServe Releases（v0.19-v0.21）](https://github.com/kserve/kserve/releases)
- [Cloud-Native AI Inference at Scale using KServe and llm-d](https://kserve.github.io/website/blog/cloud-native-ai-inference-kserve-llm-d)

## 相关主题（本手册内）

| 主题 | 关系 | 链接 |
|---|---|---|
| Operator 模式 | KServe 本身就是 Operator | [Operator 模式](../../02-cloud-native/operator/) |
| Kubernetes | KServe 的底座与调度层 | [Kubernetes](../../02-cloud-native/kubernetes/) |
| vLLM | KServe 的 LLM runtime 之一 | [vLLM](../../04-llmops/vllm/) |
| Triton | KServe 的多 backend runtime | [Triton](../../04-llmops/triton/) |
| Ray | 可与 KServe 互补的分布式平台 | [Ray](../ray/) |
| Kubeflow | KServe 是 Kubeflow 的服务组件，可组合成完整 ML 平台 | [Kubeflow](../kubeflow/) |
| MLflow | 实验追踪与模型注册，KServe 可加载 MLflow 模型 | [MLflow](../mlflow/) |
| KubeRay | Ray 在 K8s 上的 Operator，可与 KServe 组合 | [KubeRay](../kuberay/) |
| Airflow | 工作流编排；可编排 KServe 部署流水线 | [Airflow](../airflow/) |
| LLM Gateway | 可与 KServe 端点组合 | [LLM Gateway](../../04-llmops/llm-gateway/) |
| AI SRE | KServe 的可观测与 SLO | [AI SRE](../../07-ai-sre/) |

## 论文与博客

- [KFServing becomes KServe](https://blog.kubeflow.org/kfserving-becomes-kserve/) —— KServe 改名与项目拆分历史。
- [Knative Serving: Scale to Zero](https://knative.dev/docs/serving/autoscaling/scale-to-zero/) —— 缩到零机制。
- [Triton Inference Server Architecture](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/architecture.html) —— Triton 作为 KServe runtime 的架构。
- [vLLM: Easy, Fast, and Cheap LLM Serving with PagedAttention](https://arxiv.org/abs/2309.06180) —— vLLM 底层原理。

## 生态工具

| 工具 | 用途 |
|---|---|
| [Kustomize](https://kustomize.io/) / [Helm](https://helm.sh/) | KServe 安装配置管理（v0.17 起为 10 个子 chart） |
| [Istio](https://istio.io/) | KServe 经典服务网格与网关 |
| [Envoy Gateway](https://gateway.envoyproxy.io/) / [Envoy AI Gateway](https://aigateway.envoyproxy.io/) | llmisvc 默认 Gateway 实现与 AI 网关能力（token 级限流） |
| [Kourier](https://github.com/knative-sandbox/net-kourier) | Knative 轻量级入口 |
| [llm-d](https://llm-d.ai/) | KServe LLM 路由/调度的底层框架（EPP、WVA） |
| [KEDA](https://keda.sh/) | 事件驱动扩缩（支持 vLLM 指标） |
| [Prometheus](https://prometheus.io/) + [Grafana](https://grafana.com/) | 指标与可视化 |
| [Locust](https://locust.io/) / [k6](https://k6.io/) | 压力测试 |

## 学习路径建议

1. **先修**：Kubernetes CRD/Operator、Docker、HTTP/gRPC、Prometheus。
2. **本主题**：通读本主题 11 章 + 跑 mini-demo。
3. **动手**：在本地 kind/minikube 部署 KServe（先核心组件，再加 llmisvc/localmodel），发布一个 sklearn 和 vLLM 模型。
4. **进阶**：读 `kserve/kserve` controller 源码（重点 llmisvc 与 localmodel 控制面），尝试自定义 runtime。
5. **生产**：阅读官方 admin 文档与 v0.17+ 升级指南，搭建多租户、LocalModelCache、可观测、金丝雀完整方案。

## 一句话总结

KServe 是连接 K8s 与 AI 推理的桥梁：官方文档是它的使用手册，源码是它的实现地图，相邻主题（Operator/Kubernetes/vLLM/Triton/AI SRE）共同构成完整的 AI 平台知识拼图；而 2025-2026 的 LLMInferenceService + llm-d 演进线，是读懂"下一代推理平台"的最佳入口。

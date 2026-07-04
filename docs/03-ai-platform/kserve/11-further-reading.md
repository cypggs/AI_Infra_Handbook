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
- [ModelMesh](https://kserve.github.io/website/docs/modelserving/model_mesh/)

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
| [Kustomize](https://kustomize.io/) | KServe 安装配置管理 |
| [Istio](https://istio.io/) | KServe 默认服务网格与网关 |
| [Kourier](https://github.com/knative-sandbox/net-kourier) | Knative 轻量级入口 |
| [Prometheus](https://prometheus.io/) + [Grafana](https://grafana.com/) | 指标与可视化 |
| [KEDA](https://keda.sh/) | 事件驱动扩缩 |
| [Locust](https://locust.io/) / [k6](https://k6.io/) | 压力测试 |

## 学习路径建议

1. **先修**：Kubernetes CRD/Operator、Docker、HTTP/gRPC、Prometheus。
2. **本主题**：通读本主题 11 章 + 跑 mini-demo。
3. **动手**：在本地 kind/minikube 部署 KServe，发布一个 sklearn 和 HuggingFace 模型。
4. **进阶**：读 `kserve/kserve` controller 源码，尝试自定义 runtime。
5. **生产**：阅读官方 admin 文档，搭建多租户、可观测、金丝雀完整方案。

## 一句话总结

KServe 是连接 K8s 与 AI 推理的桥梁：官方文档是它的使用手册，源码是它的实现地图，相邻主题（Operator/Kubernetes/vLLM/Triton/AI SRE）共同构成完整的 AI 平台知识拼图。

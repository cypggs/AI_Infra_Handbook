# 11. 延伸阅读

## 官方文档（必读）

- [Triton Inference Server User Guide](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/)
  - 最权威、最全面的 Triton 文档。
- [Triton Architecture](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/architecture.html)
  - 官方架构介绍，含 Dynamic Batching、Sequence Batching、Ensemble 的图示。
- [Triton Model Configuration](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/model_configuration.html)
  - `config.pbtxt` 完整字段说明。
- [Triton Model Repository](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/model_repository.html)
  - 模型仓库结构、远程存储、版本管理。
- [Triton Metrics](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/metrics.html)
  - Prometheus 指标列表与解释。

## GitHub 仓库

- [triton-inference-server/server](https://github.com/triton-inference-server/server)
  - Triton core 源码与 issue 讨论。
- [triton-inference-server/backend](https://github.com/triton-inference-server/backend)
  - Backend API 与公共库。
- [triton-inference-server/core](https://github.com/triton-inference-server/core)
  - Triton server 核心 C++ 库。
- [triton-inference-server/python_backend](https://github.com/triton-inference-server/python_backend)
  - Python backend 源码。
- [triton-inference-server/tensorrtllm_backend](https://github.com/triton-inference-server/tensorrtllm_backend)
  - TensorRT-LLM backend。
- [triton-inference-server/vllm_backend](https://github.com/triton-inference-server/vllm_backend)
  - vLLM backend。
- [triton-inference-server/model_analyzer](https://github.com/triton-inference-server/model_analyzer)
  - 自动配置调优工具。

## NVIDIA 资源

- [NVIDIA Triton Inference Server 主页](https://developer.nvidia.com/triton-inference-server)
- [NGC Triton Container Catalog](https://catalog.ngc.nvidia.com/orgs/nvidia/containers/tritonserver)
  - 官方 Docker 镜像与版本说明。
- [NVIDIA Deep Learning Examples — Triton](https://github.com/NVIDIA/DeepLearningExamples/tree/master/Triton)
  - 官方推理示例。

## Kubernetes / KServe 集成

- [KServe Triton Runtime 文档](https://kserve.github.io/website/latest/modelserving/v1beta1/triton/)
- [KServe 官方文档](https://kserve.github.io/website/)
- [Triton Kubernetes Deploy Guide](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/kubernetes_deploy.html)

## 相关主题

- [vLLM 详解](/04-llmops/vllm/) — LLM 推理引擎，可作为 Triton vLLM backend。
- [SGLang 详解](/04-llmops/sglang/) — LLM Program 执行引擎。
- [TensorRT-LLM 详解](/04-llmops/tensorrt-llm/) — NVIDIA 编译型 LLM 推理引擎，可作为 Triton TensorRT-LLM backend。

## 推荐学习路径

1. 先通读 Triton 官方 Architecture 与 Model Configuration 文档。
2. 用 NGC Docker 跑通一个 classification 示例。
3. 尝试把 vLLM 或 TensorRT-LLM 模型接入 Triton。
4. 阅读 `server` 仓库的 `src/core/dynamic_batch_scheduler.cc` 与 `ensemble_scheduler.cc`。
5. 用 Triton Model Analyzer 自动搜索最优配置。

## 本章小结

Triton 的生态系统非常丰富，官方文档、GitHub 源码、NGC 镜像、Model Analyzer 是最核心的学习资源。结合本主题的 [Mini Demo](./07-mini-demo) 与 [生产实践](./08-production-practice)，可以从理论到工程全面掌握 Triton Inference Server。

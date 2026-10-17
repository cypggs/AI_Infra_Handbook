# 11. 延伸阅读

本章列出 TensorRT-LLM 相关的官方文档、源码、论文、演讲与社区资源，供深入学习参考。

## 官方文档

- [TensorRT-LLM User Guide](https://nvidia.github.io/TensorRT-LLM/) — 最权威的使用与架构文档
- [TensorRT-LLM Architecture Overview](https://nvidia.github.io/TensorRT-LLM/architecture/overview.html) — 架构总览
- [Paged Attention, IFB, and Request Scheduling](https://nvidia.github.io/TensorRT-LLM/features/paged-attention-ifb-scheduler.html) — IFB 与调度器
- [Quantization](https://nvidia.github.io/TensorRT-LLM/features/quantization.html) — 量化方案与硬件支持矩阵
- [Speculative Decoding](https://nvidia.github.io/TensorRT-LLM/features/speculative-decoding.html) — 投机解码
- [Triton TensorRT-LLM Backend](https://github.com/triton-inference-server/tensorrtllm_backend) — 生产部署 backend

## 源码仓库

- [NVIDIA/TensorRT-LLM](https://github.com/NVIDIA/TensorRT-LLM) — 主仓库
- [triton-inference-server/tensorrtllm_backend](https://github.com/triton-inference-server/tensorrtllm_backend) — Triton backend
- [NVIDIA/TensorRT](https://github.com/NVIDIA/TensorRT) — TensorRT 本体
- [NVIDIA/ModelOpt](https://github.com/NVIDIA/ModelOpt) — 量化校准工具

## 关键源码路径

| 路径 | 内容 |
|---|---|
| `tensorrt_llm/llmapi/llm.py` | LLM API 入口 |
| `tensorrt_llm/_torch/pyexecutor/py_executor.py` | PyExecutor 主循环 |
| `tensorrt_llm/_torch/pyexecutor/model_engine.py` | PyTorchModelEngine |
| `tensorrt_llm/_torch/pyexecutor/scheduler.py` | CapacityScheduler / MicroBatchScheduler |
| `tensorrt_llm/_torch/pyexecutor/kv_cache_manager.py` | KVCacheManager（1.3 起 V2 为主，C++ 实现） |
| `tensorrt_llm/_torch/models/` | 各模型 PyTorch 实现 |
| `tensorrt_llm/openengine/` | OpenEngine gRPC server（接入 Dynamo，1.3+） |
| `cpp/tensorrt_llm/executor/` | C++ Executor 实现 |
| `cpp/tensorrt_llm/kernels/` | CUDA kernels |
| `examples/` | 官方示例 |
| `triton_backend/` | Triton backend 源码与模板（进入维护期） |

## Release Notes

- [TensorRT-LLM Release Notes](https://nvidia.github.io/TensorRT-LLM/release-notes.html) — 版本更新、breaking changes、新模型支持

重点关注以下版本的变更：

- **1.0**：PyTorch 后端稳定、LLM API 稳定、`trtllm-serve` 服务入口
- **1.1**：KV Cache Connector、FP4/MXFP4、投机解码增强
- **1.2**：移除 TensorRT 后端、B300/GB300 与 DGX Spark（beta）、投机解码单模型化
- **1.3（RC）**：KVCacheManager V2 默认、TRITON MoE 弃用、NIXL/Ray 分离式传输、早期 Rubin（SM107）kernel、OpenEngine gRPC

## NVIDIA Dynamo 与 OpenEngine（2025-2026 推理编排层）

- [ai-dynamo/dynamo](https://github.com/ai-dynamo/dynamo) — NVIDIA 开源的分布式推理编排框架（GTC 2025 开源，1.0 于 GTC 2026 发布）：KV 感知路由、SLA Planner、KV Block Manager、NIXL
- [ai-dynamo/openengine](https://github.com/ai-dynamo/openengine) — vendor-neutral 的引擎接入 gRPC 契约（aggregated / prefill / decode 角色）
- [NVIDIA Dynamo 官方页](https://developer.nvidia.com/dynamo) 与 [Dynamo 1.0 新闻稿](http://nvidianews.nvidia.com/news/dynamo-1-0)
- [TensorRT-LLM Disaggregated Serving 文档](https://github.com/NVIDIA/TensorRT-LLM/blob/main/docs/source/features/disagg-serving.md) — 原生分离式服务与 `cache_transceiver_config`
- [NVIDIA EOL Notices](https://docs.nvidia.com/ai-enterprise/lifecycle/latest/eol-notices.html) — Triton `*-trtllm-python-py3` 容器弃用信息

## NVIDIA 演讲与博客

- NVIDIA GTC 历年演讲：搜索 "TensorRT-LLM" 在 [NVIDIA On-Demand](https://www.nvidia.com/en-us/on-demand/)
- NVIDIA Developer Blog：[TensorRT-LLM 相关文章](https://developer.nvidia.com/blog)
- NVIDIA Technical Blog：关于 FP8 / FP4、Blackwell 推理优化的专题

## 相关论文

| 论文 | 主题 |
|---|---|
| [Efficient Large Language Models: A Survey](https://arxiv.org/abs/2312.00663) | LLM 推理优化综述 |
| [FlashAttention-2](https://arxiv.org/abs/2307.08691) | 注意力 kernel 优化 |
| [LLM in a Flash](https://arxiv.org/abs/2312.11514) | 低显存推理 |
| [Speculative Decoding 系列](https://arxiv.org/abs/2211.17192) | 投机解码 |

## 对比阅读

- [vLLM 详解](/04-llmops/vllm/) — 理解 PagedAttention 与 Continuous Batching
- [SGLang 详解](/04-llmops/sglang/) — 理解 LLM Program、RadixAttention 与结构化生成
- [GPU 架构与 CUDA 基础](/01-foundation/gpu-cuda/) — 理解 Tensor Core、FP8/FP4、NVLink、HBM 等 TRT-LLM 依赖的底层硬件能力
- [Triton Inference Server 详解](/04-llmops/triton/) — 多框架推理服务入口，可承载 TensorRT-LLM backend
- [GPU 在 Kubernetes 上的调度详解](/02-cloud-native/gpu-scheduling/) — TensorRT-LLM 生产部署依赖 K8s GPU 调度、MIG/MPS、拓扑感知与 Gang 调度，理解集群层面 GPU 资源模型
- [LLM Gateway 详解](/04-llmops/llm-gateway/) — 统一接入层，可把 TensorRT-LLM 作为上游 Provider

## 社区与 benchmark

- [Artificial Analysis](https://artificialanalysis.ai/) — 第三方推理性能对比
- [Anyscale LLMPerf](https://github.com/ray-project/llmperf) — LLM 服务 benchmark 工具
- [LMSYS Chatbot Arena](https://chat.lmsys.org/) — 模型能力评估（非性能）

## 本章小结

TensorRT-LLM 的资料高度集中在 NVIDIA 官方渠道。建议优先阅读 User Guide、Architecture Overview 与 Release Notes，再结合源码路径 `llmapi → pyexecutor → model_engine/scheduler/kv_cache_manager` 进行源码级学习。生产部署时务必跟踪 Release Notes 中的 breaking changes。

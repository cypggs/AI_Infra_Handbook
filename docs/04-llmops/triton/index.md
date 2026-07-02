# Triton Inference Server

[Triton Inference Server](https://github.com/triton-inference-server/server) 是 NVIDIA 开源的**多框架、高性能推理服务软件**。它通过统一的 model repository、`config.pbtxt` 与可插拔 backend，把 TensorRT-LLM、vLLM、ONNX Runtime、PyTorch、Python 等推理引擎整合成可观测、可扩展的生产级在线服务。

## 一句话理解

> Triton 是模型与业务之间的“服务层”：它不关心模型用什么框架训练，只负责把请求路由到正确的 backend、拼成最优的 batch、以最低延迟返回结果。

## 本主题结构

1. [背景](01-background)
2. [核心思想](02-core-ideas)
3. [架构设计](03-architecture)
4. [Runtime 工作流程](04-runtime-workflow)
5. [核心模块](05-core-modules)
6. [源码分析](06-source-analysis)
7. [工程实践：Mini Demo](07-mini-demo)
8. [企业生产实践](08-production-practice)
9. [最佳实践](09-best-practices)
10. [面试题](10-interview-questions)
11. [延伸阅读](11-further-reading)

## 学习目标

阅读完本主题后，你应该能够：

- 解释 Triton 与 vLLM / SGLang / TensorRT-LLM 在 LLMOps 链路中的不同定位
- 设计一个满足生产需求的 model repository 与 `config.pbtxt`
- 比较 Dynamic Batching、Sequence Batching、Ensemble 三种调度策略的适用场景
- 说明 Backend API、Instance Group、模型版本管理、Metrics 的作用
- 在 Kubernetes / KServe 环境中规划 Triton 部署方案
- 判断何时应选 Triton，何时应选自研网关或 KServe

## 与 vLLM / SGLang / TensorRT-LLM 的关系

| 维度 | vLLM | SGLang | TensorRT-LLM | Triton Inference Server |
|---|---|---|---|---|
| 定位 | 通用 LLM 推理引擎 | LLM Program 执行引擎 | NVIDIA 编译型 LLM 推理引擎 | 多框架推理服务入口 |
| 核心能力 | PagedAttention + Continuous Batching | RadixAttention + 结构化生成 | Builder/Engine + In-flight Batching | Model Repository + Backend + Scheduler |
| 与 Triton 的关系 | 可作为 Triton 的 vLLM backend 被调用 | 可作为 Triton 的 Python backend 被调用 | 可作为 Triton 的 TensorRT-LLM backend 被调用 | 统一承载上述引擎并提供服务层能力 |
| 解决的主要问题 | 单模型高吞吐 | LLM Program 高效执行 | NVIDIA 硬件极致性能 | 多模型、多框架、可扩展、可观测服务 |

建议先阅读 [vLLM 详解](/04-llmops/vllm/)、[SGLang 详解](/04-llmops/sglang/) 与 [TensorRT-LLM 详解](/04-llmops/tensorrt-llm/)，再理解 Triton 如何作为“服务层”把这些引擎组织起来。

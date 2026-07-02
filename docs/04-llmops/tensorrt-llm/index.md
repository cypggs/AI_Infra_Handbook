# TensorRT-LLM

[TensorRT-LLM](https://github.com/NVIDIA/TensorRT-LLM) 是 NVIDIA 开源的大语言模型与视觉生成模型推理优化库，核心目标是**把模型一次性编译成硬件专属的极致执行计划，然后在 NVIDIA GPU 上以低延迟、高吞吐持续服务**。 historically它基于 TensorRT 的 Builder → Engine/Plan → Runtime 路径，但从 2026 年中发布的 [1.2](https://github.com/NVIDIA/TensorRT-LLM/releases) 起，TensorRT 后端已被移除，PyTorch 成为唯一执行后端，用户侧的 `LLM` API 保持稳定。

## 一句话理解

> TensorRT-LLM 先把模型“编译”成一张针对当前 GPU 优化的执行图，再用 Executor 持续动态批处理请求，从而在 NVIDIA 硬件上榨取极限推理性能。

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

- 解释 TensorRT-LLM 与 vLLM / SGLang 在设计哲学上的差异
- 说明 Builder / Engine / Runtime / Executor 的职责与协作关系
- 描述 In-flight Batching（IFB）与 Paged KV Cache 在 TRT-LLM 中的实现方式
- 定位 PyTorch 后端源码中的关键模块与调用链
- 理解 TensorRT 后端被移除后，PyTorch 后端如何承担编译与执行职责
- 在生产环境中判断是否使用 TRT-LLM，以及如何调优与量化

## 与 vLLM / SGLang 的关系

三者不是简单的性能排序，而是面向不同约束的解法：

| 维度 | vLLM | SGLang | TensorRT-LLM |
|---|---|---|---|
| 核心命题 | 通用高吞吐 LLM 推理 | LLM 程序的高效执行 | NVIDIA 硬件上的极致性能 |
| 执行模式 | Eager + 动态调度 | Eager + 编译/缓存 | 编译/优化后的执行图 |
| KV Cache | PagedAttention（Block Table） | RadixAttention（Radix Tree） | Paged KV Cache / Contiguous KV Cache |
| 批处理 | Continuous Batching | Continuous Batching | In-flight Batching（IFB） |
| 可移植性 | 跨硬件 | 跨硬件 | 绑定 NVIDIA GPU |
| 灵活性 | 高 | 高 | 中（受支持的模型/算子约束） |
| 适用场景 | 通用在线推理 | Agent / 结构化生成 | 对延迟/吞吐敏感的 NVIDIA 部署 |

建议先阅读 [vLLM 详解](/04-llmops/vllm/) 与 [SGLang 详解](/04-llmops/sglang/)，再来理解 TRT-LLM 在“编译-执行”这一轴上的取舍。

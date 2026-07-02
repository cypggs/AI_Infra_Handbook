# vLLM

[vLLM](https://github.com/vllm-project/vllm) 是当前最主流的开源大语言模型推理引擎之一，以 **PagedAttention** 和 **Continuous Batching** 为核心创新，显著提升了 GPU 显存利用率与推理吞吐。

## 一句话理解

> vLLM 通过把 KV Cache 按 Block 分页管理，并持续动态批处理请求，解决了 LLM 推理中显存浪费和吞吐低下的核心问题。

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

- 解释为什么 LLM 推理需要 PagedAttention
- 画出 vLLM 的核心架构图
- 描述一个请求从进入到返回的完整生命周期
- 定位 vLLM 源码中的关键模块与调用链
- 实现一个简化的 PagedAttention + Continuous Batching Demo
- 在生产环境中评估是否使用 vLLM，以及如何调优

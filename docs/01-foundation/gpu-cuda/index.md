# GPU 架构与 CUDA 基础

> 一句话理解：**GPU 不是“更快的 CPU”，而是一台专精于并行吞吐的“数据工厂”——CUDA 就是调度这座工厂的编程语言，而 AI 大模型正是它最擅长生产的“产品”。**

如果你曾好奇：为什么训练 GPT 需要几万张 GPU？为什么同样的模型在 H100 上比 A100 快那么多？为什么 vLLM、TensorRT-LLM 动不动就谈 PagedAttention、FP8、Tensor Core、NVLink？或者你只是一个想在 Kubernetes 上调度 GPU 的 AI Infra 工程师，却总被同事问“这个 kernel 为什么 OOM”“NCCL 超时怎么查”——那么这一章就是为你写的。

GPU/CUDA 是 AI Infra 的**底层分水岭**。它不像 Kubernetes 那样看得见摸得着，也不像 vLLM 那样直接面向业务，但它决定了：

- 模型能不能训练出来（算力、显存、通信）；
- 推理服务能不能省钱（带宽、Tensor Core、量化）；
- 集群调度有没有意义（MIG、MPS、拓扑、NVLink）。

## 学习目标

读完本章，你将能够：

1. 用一句话向非技术人员解释 GPU 和 CPU 的设计差异；
2. 画出 NVIDIA GPU 的层级结构：GPU → GPC → SM → Warp → Thread；
3. 理解 CUDA 编程模型中的 Grid/Block/Thread、内存层次、合并访问、bank conflict、warp divergence；
4. 知道 H100/H200/B200/GB200 的关键差异，以及 Tensor Core、NVLink、HBM 在 AI 中的作用；
5. 在生产环境中初步判断：CUDA OOM、NCCL 超时、Xid 错误、低 occupancy 问题的根因；
6. 与 Kubernetes GPU 调度、TensorRT-LLM、分布式训练、案例研究主题形成知识闭环。

## 本章与手册其他主题的关系

| 主题 | 关系 | 本章会讲到的交叉点 |
|---|---|---|
| [Kubernetes GPU 调度](/02-cloud-native/kubernetes/) | 上层编排 vs 底层执行 | Kubernetes 决定“把 Pod 放到哪张 GPU”，本章讲“GPU 拿到任务后内部怎么执行”。MIG/MPS/拓扑感知在本章只作概念回顾，详细调度逻辑交给 Kubernetes 主题。 |
| [TensorRT-LLM](/04-llmops/tensorrt-llm/) | 编译型推理引擎 vs 底层硬件 | TensorRT-LLM 用 Tensor Core、FP8、Plugin 做推理优化；本章先讲清 Tensor Core/FP8 是什么、CUDA 如何暴露它们。 |
| [vLLM / SGLang](/04-llmops/vllm/) | 服务引擎 vs 硬件执行 | PagedAttention、Continuous Batching 的底层支撑是 GPU 内存带宽与并行度；本章解释为什么 Decode 阶段会成为带宽瓶颈。 |
| [Ray / KubeRay](/03-ai-platform/ray/) | 分布式训练平台 vs 单机 GPU | 分布式并行的 Data/Tensor/Pipeline 并行，最终都要落实在 CUDA kernel + NCCL 集合通信上。 |
| [OpenAI / Meta / Google 案例研究](/09-case-study/) | 超大规模集群 vs 单卡原理 | 万卡集群的可靠性、NVLink 网络、MFU 优化，都需要以单卡 CUDA 行为为前提。 |
| [大模型从 0 到 1](/01-foundation/llm-from-zero/) | 算法 vs 算力 | 本章解释 Transformer 中的矩阵乘、注意力在 GPU 上是如何被加速的。 |

## 本章结构

按手册统一结构，本章包含 11 节：

1. [背景](01-background) — 为什么 AI 离不开 GPU
2. [核心思想](02-core-ideas) — SIMT、Warp、Latency Hiding、计算密度
3. [架构设计](03-architecture) — 从 Fermi 到 Blackwell 的 GPU 演进
4. [CUDA 编程模型](04-cuda-programming-model) — Grid/Block/Thread、内存、kernel
5. [核心模块](05-core-modules) — CUDA Runtime、cuBLAS、NCCL、DCGM 等
6. [源码分析](06-source-analysis) — nvcc 编译链路、PyTorch CUDA 调用栈
7. [工程实践](07-mini-demo) — CPU 可运行的 GPU 执行模型模拟器
8. [企业生产实践](08-production-practice) — 选型、虚拟化、监控、故障排查
9. [最佳实践](09-best-practices) — 写出好 CUDA kernel 的原则
10. [面试题](10-interview-questions) — 初/中/高级 GPU/CUDA 面试题
11. [延伸阅读](11-further-reading) — 官方文档、论文与学习路径

## 一句话总结

> **理解 GPU/CUDA，不是为了写 kernel，而是为了在 AI Infra 的每一个决策里——从买卡、写调度器、到调推理引擎——都能说出“为什么”。**

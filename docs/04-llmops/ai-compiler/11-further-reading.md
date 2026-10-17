# 11. 延伸阅读

## 论文

**奠基**
- Triton: an Intermediate Language and Compiler for Tiled Neural Network Computations（MAPL 2019，arXiv:2002.06810）——OpenAI Triton 的原始论文，tile 级抽象的起点
- TVM: An Automated End-to-End Optimization Stack for Deep Learning（OSDI 2018，arXiv:1802.04799）——图级编译 + auto-tuning 的奠基工作
- Ansor: Generating High-Performance Tensor Programs for Deep Learning（OSDI 2020，arXiv:2006.06762）——学习型 cost model + 层级搜索空间
- Roofline: an insightful visual performance model（Williams et al., CACM 2009）——算术强度与"算力受限 vs 带宽受限"的理论基础
- MLIR: Scaling Compiler Infrastructure for Domain Specific Computation（CGO 2021，arXiv:2002.11054）——dialect 体系的官方阐述

**Attention kernel（编译器优化的试金石）**
- FlashAttention（arXiv:2205.14135）/ FlashAttention-2（arXiv:2307.08691）/ FlashAttention-3（arXiv:2407.08608）——手写 CUDA 路线的三次迭代
- FlashAttention 4（2025）——用 Triton Gluon 重写并超过手写 CUDA，"DSL 反超 CUDA"的标志性案例

**前沿（2025-2026）**
- Mirage: A Multi-Level Superoptimizer for Tensor Programs（OSDI 2025）——跨层级搜索的张量程序超优化器
- MPK: A Compiler and Runtime for Mega-Kernelizing Tensor Programs（OSDI 2026）——persistent megakernel 编译 + GPU 内调度运行时
- TileLang: A Composable Tiled Programming Model for AI Systems（arXiv:2502.02613）——基于 TVM 的 tile DSL 与其多后端设计

## 官方文档与工程资源

- **Triton**：github.com/triton-lang/triton（release notes 是跟踪 3.x 新特性的最好来源）；Triton 官方 tutorials（matmul / fused-softmax / persistent-kernel）
- **Gluon**：Triton 仓库内的 Gluon 示例（特别是 attention 相关）——TTGIR 级显式编程的教材
- **PyTorch 编译栈**：pytorch.org/docs/stable/torch.compiler（torch.compile 权威参考）；PyTorch 2.x release notes（Inductor/CuTeDSL/FlexAttention 的演进）；pytorch.org/blog（FlexAttention、Helion on TPU 等深度博文）
- **cuTile**：docs.nvidia.com/cuda/cutile-python（官方文档）；NVIDIA Developer Blog "Simplify GPU Programming with NVIDIA CUDA Tile in Python"——60 行 Python 写 attention 的入门
- **CUTLASS**：github.com/NVIDIA/cutlass（4.x release notes：Primitives API、Task Scheduling、cute_ext 管线）
- **TileLang**：github.com/tile-ai/tilelang（含 LSP、pass visualizer、benchmark 仓库链接）
- **Helion**：PyTorch Conference 2025 talk "Helion: A High-level DSL for Kernel Authoring"（Jason Ansel, Meta）
- **XLA / StableHLO**：github.com/openxla/xla、github.com/openxla/stablehlo
- **Apache TVM**：github.com/apache/tvm（Relax/TensorIR 方向）

## 本手册相关主题

- [Triton Inference Server](/04-llmops/triton/)：撞名提醒——推理服务框架，与 OpenAI Triton 无关
- [GPU 与 CUDA](/01-foundation/gpu-cuda/)：kernel 的硬件执行模型、CUDA graphs 原理
- [vLLM](/04-llmops/vllm/)：torch.compile + CUDA graphs 的深度用户
- [SGLang](/04-llmops/sglang/)：RadixAttention 与编译器栈的结合
- [TensorRT-LLM](/04-llmops/tensorrt-llm/)："全编译"路线的代表（对比 torch.compile 的运行时编译）
- [分布式系统](/01-foundation/distributed-systems/)：编译器与通信算子（all-reduce 重叠）的交汇

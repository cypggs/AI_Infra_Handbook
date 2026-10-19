# 11. 延伸阅读

本章内容是 GPU/CUDA 的入门与工程化视角。如果你想继续深入，以下资源是按优先级排序的推荐阅读。

## 11.1 官方文档（必读）

- [NVIDIA CUDA C++ Programming Guide](https://docs.nvidia.com/cuda/cuda-c-programming-guide/)
  - CUDA 编程的权威参考，涵盖编程模型、内存层次、性能优化。
- [NVIDIA CUDA Runtime API](https://docs.nvidia.com/cuda/cuda-runtime-api/)
  - 所有 `cuda*` 函数的参考手册。
- [NVIDIA H100 Tensor Core GPU Architecture](https://www.nvidia.com/en-us/data-center/h100/)
  - Hopper 架构白皮书入口。
- [NVIDIA Blackwell Architecture](https://www.nvidia.com/en-us/data-center/blackwell-architecture/)
  - Blackwell/B200/GB200 架构介绍。
- [NCCL Documentation](https://docs.nvidia.com/deeplearning/nccl/)
  - 多 GPU 集合通信库的官方文档。
- [NVIDIA DCGM](https://docs.nvidia.com/datacenter/dcgm/)
  - 数据中心 GPU 监控与诊断。
- [Nsight Compute](https://docs.nvidia.com/nsight-compute/)
  - CUDA kernel 深度性能分析工具。
- [Nsight Systems](https://docs.nvidia.com/nsight-systems/)
  - 系统级性能分析工具。
- [What's New in CUDA Toolkit 13.x](https://docs.nvidia.com/cuda/cuda-toolkit-release-notes/index.html)
  - CUDA 13.x 各版本 Release Notes（green context、cuTile、Rubin 支持等）。
- [Inside NVIDIA Rubin GPU Architecture](https://developer.nvidia.com/blog/inside-nvidia-rubin-gpu-architecture-powering-the-era-of-agentic-ai/)
  - Rubin 架构官方解析：HBM4、NVLink 6、第三代 Transformer Engine。
- [AMD ROCm Documentation](https://rocm.docs.amd.com/)
  - AMD GPU 计算栈的官方文档。
- [华为昇腾 CANN 社区](https://www.hiascend.com/software/cann)
  - 国产 AI 芯片软件栈的代表。

## 11.2 开源库与代码

- [NVIDIA/cutlass](https://github.com/NVIDIA/cutlass)
  - 高性能 CUDA 矩阵运算模板库。
- [Dao-AILab/flash-attention](https://github.com/Dao-AILab/flash-attention)
  - Flash Attention 的官方实现。
- [openai/triton](https://github.com/openai/triton)
  - 用 Python 写高性能 GPU kernel 的语言与编译器。
- [NVIDIA/cutile-python](https://github.com/nvidia/cutile-python)
  - CUDA 13.1 起官方的 tile 级 Python 编程模型（cuTile），Triton 的官方对标物。
- [pytorch/pytorch](https://github.com/pytorch/pytorch) 的 `aten/src/ATen/cuda` 和 `c10/cuda`
  - 理解 PyTorch 如何调用 CUDA。
- [NVIDIA/k8s-device-plugin](https://github.com/NVIDIA/k8s-device-plugin)
  - Kubernetes GPU Device Plugin。
- [NVIDIA/gpu-operator](https://github.com/NVIDIA/gpu-operator)
  - Kubernetes GPU Operator。

## 11.3 论文与技术报告

- [FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness](https://arxiv.org/abs/2205.14135)
  - Flash Attention 原始论文。
- [FlashAttention-2: Faster Attention with Better Parallelism and Work Partitioning](https://arxiv.org/abs/2307.08691)
  - Flash Attention 第二代。
- [FlashAttention-3](https://arxiv.org/abs/2407.08608)
  - 针对 Hopper 的进一步优化，大量运用 warp specialization 与 TMA。
- [Mixed Precision Training](https://arxiv.org/abs/1710.03740)
  - FP16 混合精度训练经典论文。
- [A Guide to Hopper FP8 Training](https://docs.nvidia.com/deeplearning/transformer-engine/user-guide/index.html)
  - Transformer Engine 官方指南。
- [NVIDIA CUDA 13.3 发布博客](https://developer.nvidia.com/blog/nvidia-cuda-13-3-enhances-gpu-development-with-tile-programming-in-c-compiler-autotuning-and-python-updates/)
  - CUDA Tile C++（nvcc --enable-tile）、CompileIQ 自动调优与 CUDA Python 1.0。
- [SemiAnalysis: The Inference Kingdom Expands（GTC 2026）](https://newsletter.semianalysis.com/p/nvidia-the-inference-kingdom-expands)
  - 2026 年 GTC 深度纪要：Vera Rubin、Rubin Ultra NVL576、CPO 与机柜级竞争格局。

## 11.4 视频与课程

- [NVIDIA CUDA Training](https://www.nvidia.com/en-us/on-demand/library/?search=cuda)
  - NVIDIA 官方 On-Demand 课程。
- [CMU 15-418 / 15-618: Parallel Computer Architecture and Programming](http://15418.courses.cs.cmu.edu/)
  - 并行计算经典课程，包含 GPU 体系结构。

## 11.5 相关主题交叉引用

- [GPU 在 Kubernetes 上的调度](/02-cloud-native/gpu-scheduling/)：GPU 在 Kubernetes 中的发现、调度、MIG/MPS、拓扑感知、DCGM、Gang/队列公平调度；
- [Kubernetes 详解](/02-cloud-native/kubernetes/)：容器编排底座、调度框架、extended resource 与 Device Plugin 通用机制；
- [TensorRT-LLM](/04-llmops/tensorrt-llm/)：NVIDIA 编译型 LLM 推理引擎，大量依赖 Tensor Core 与 FP8；
- [vLLM](/04-llmops/vllm/)：GPU 上的 LLM 推理服务与内存管理；
- [AI 编译器与 Kernel 生成](/04-llmops/ai-compiler/)：手写 CUDA 之上的算子编译与 kernel 自动生成（Triton、cuTile、TileLang）；
- [模型量化与压缩基础设施](/04-llmops/model-quantization/)：FP8/INT4 量化 kernel 如何落到 Tensor Core 与 CUDA 编程模型上；
- [AI 集群网络](/02-cloud-native/ai-networking/)：NVLink/NCCL 多卡互联与 RDMA 网络，把单卡 CUDA 知识扩展到集群层面；
- [Ray](/03-ai-platform/ray/)：分布式 AI 计算，底层调用 CUDA + NCCL；
- [大模型从 0 到 1](/01-foundation/llm-from-zero/)：Transformer、训练、推理全链路；
- [OpenAI / Meta / Google 案例研究](/09-case-study/)：超大规模 GPU 集群的工程实践。

## 11.6 推荐学习路径

如果你刚读完本章，建议按以下顺序继续：

1. 先动手跑本章的 [Mini Demo](./07-mini-demo)；
2. 阅读 [NVIDIA CUDA C++ Programming Guide](https://docs.nvidia.com/cuda/cuda-c-programming-guide/) 的 1-5 章；
3. 选一个真实 kernel 用 Nsight Compute 分析；
4. 阅读 [Flash Attention 论文](https://arxiv.org/abs/2205.14135)，理解 tiling 和 memory-aware 优化；
5. 回到 [Kubernetes GPU 调度](/02-cloud-native/kubernetes/) 和 [TensorRT-LLM](/04-llmops/tensorrt-llm/)，把底层知识与上层系统连起来。

## 11.7 一句话总结

> GPU/CUDA 不是一门孤立的技术，它是 AI Infra 的底座。理解了它，再看 Kubernetes 调度、推理引擎、分布式训练，都会有一通百通的感觉。

恭喜你已经走完了本章的全部 11 节。下一章建议继续学习 [GPU 在 Kubernetes 上的调度](/02-cloud-native/gpu-scheduling/)，把单卡知识扩展到集群层面。

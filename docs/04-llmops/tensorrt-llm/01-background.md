# 1. 背景

## 为什么需要 TensorRT-LLM？

大语言模型推理的优化空间，不止于“把 KV Cache 管好、把 batch 做大”。当业务对**首 token 延迟（TTFT）**、**逐 token 延迟（TPOT）**、**吞吐** 有极致要求，并且已经锁定 NVIDIA GPU 时，就需要一个能够：

- 在构建期做算子融合、层融合、精度选择、内存布局优化的系统；
- 在运行期用最小开销持续调度请求的系统；
- 能充分利用 FP8、FP4、NVLink、Tensor Core 等硬件特性的系统。

TensorRT-LLM 正是 NVIDIA 为这个场景设计的答案。

### LLM 高性能推理的核心痛点

1. **通用引擎难以做硬件级极致优化**：vLLM / SGLang 的 Eager 执行路径在算子选择、kernel 融合上受 PyTorch 限制，无法像专用编译器那样针对 Tensor Core、SM 数量、显存带宽做全局优化。
2. **动态 shape 导致重复编译/开销**：序列长度、batch size 变化大，传统静态 batch 需要 padding，造成计算浪费；动态调度又需要运行时额外开销。
3. **多精度、多量化格式难以统一调度**：FP8、FP4、AWQ、GPTQ、INT8 等格式对 kernel、显存布局、校准流程要求不同，手写支持成本高。
4. **多 GPU 并行需要与通信深度融合**：TP / PP / CP / EP 等并行策略需要与 attention、MLP、all-reduce / all-gather / p2p 通信做协同优化。

### TensorRT-LLM 的诞生

TensorRT-LLM 于 2023 年底随 NVIDIA TensorRT 生态开源发布，目标是让 LLM 推理在 NVIDIA GPU 上达到接近硬件极限的性能。它继承了 TensorRT 的 Builder / Engine / Runtime 哲学：

- **构建期**：把 HuggingFace / Megatron / GPTQ / FP8 等 checkpoint 转换成优化后的执行计划（historically TensorRT engine / plan；现在为 PyTorch 后端的编译执行图）。
- **运行期**：用 Executor + Batch Manager 做 In-flight Batching，动态交错 prefill 与 decode。

截至 2026 年 7 月，TensorRT-LLM 已发展到 [1.2](https://github.com/NVIDIA/TensorRT-LLM/releases)。关键里程碑：

- **1.0**：PyTorch 后端成为默认/稳定后端，LLM API 稳定。
- **1.1**：新增模型、FP4 / MXFP4 在 Blackwell 上的支持、KV Cache Connector 用于分离式服务、投机解码与引导解码结合。
- **1.2**：**移除 TensorRT 后端**，PyTorch 成为唯一执行后端；支持 B300 / GB300；基于 PyTorch 2.9.0、ModelOpt 0.37、xgrammar 0.1.25。

## 没有 TensorRT-LLM 会怎样？

在没有 TRT-LLM 之前，NVIDIA 生态中的高性能 LLM 部署通常面临以下选择：

- **原生 TensorRT**：手写 ONNX / plugin，工程量大，模型适配困难。
- **vLLM**：易用、开源、生态大，但在 NVIDIA 硬件上难以做到 TRT-LLM 级别的 kernel 融合与精度调度。
- **SGLang**：擅长 LLM 程序与结构化生成，但同样受限于 Eager 执行路径。
- **HuggingFace TGI**：已于 2025-12 进入维护模式，新优化主要流向 vLLM / SGLang。

TRT-LLM 提供了一条“编译一次、到处运行（在 NVIDIA GPU 上）”的高性能路径。

## TensorRT-LLM 与替代方案的对比

| 维度 | TensorRT-LLM | vLLM | SGLang | HuggingFace TGI |
|---|---|---|---|---|
| 开源协议 | NVIDIA 开源 / 部分组件专有 | Apache 2.0 | Apache 2.0 | Apache 2.0 / 商业 |
| 维护状态 | NVIDIA 持续更新，1.2 移除 TensorRT 后端 | 活跃，V1 默认 | 活跃，v0.5.14 | 2025-12 起维护模式 |
| 执行后端 | PyTorch（编译/优化执行图） | PyTorch Eager | PyTorch Eager | PyTorch Eager |
| 核心抽象 | Builder / Engine / Runtime / Executor | PagedAttention + Continuous Batching | RadixAttention + LLM Program | Continuous Batching |
| 易用性 | 中（需要 build/quant 步骤） | 高 | 中 | 中 |
| 性能 | 很高（NVIDIA 硬件） | 高（通用场景） | 高（共享前缀/结构化输出） | 中高 |
| 灵活性 | 中（受支持模型/算子约束） | 高 | 高 | 中 |
| 量化支持 | FP8 / FP4 / NVFP4 / AWQ / GPTQ / INT8 | FP8 / AWQ / GPTQ / INT8 等 | FP8 / AWQ / GPTQ / INT8 等 | 有限 |
| 适用场景 | 极致性能 / NVIDIA 全栈 | 通用在线推理 | Agent / 多轮 / 结构化输出 | 简单在线服务 |

## 一句话理解

> TensorRT-LLM 解决的是“在 NVIDIA GPU 上，如何把 LLM 推理做到极致性能”的问题：用构建期编译/优化换取运行期低延迟与高吞吐。

## 本章小结

TensorRT-LLM 不是“另一个开源推理引擎”，而是 NVIDIA 硬件上的性能收口方案。它的设计动机不是通用性，而是**在锁定 NVIDIA 生态的前提下，把编译优化、精度选择、并行策略、动态批处理整合成一条工业级流水线**。1.2 移除 TensorRT 后端后，PyTorch 后端接过了编译与执行的双重职责，用户侧 API 保持稳定，但底层实现路径已经发生重大变化。

# 1. 背景

## 为什么需要 SGLang？

大语言模型（LLM）推理正在从“单次补全”走向“程序式交互”。Agent、多轮对话、函数调用、JSON 输出、A/B 推理分支等场景，要求推理系统不仅跑得快，还要能表达和优化复杂的控制流与结构约束。

### LLM 程序式交互的核心痛点

1. **重复 prefill 开销大**：多轮对话中，每一轮都要重新计算 system prompt + 历史对话的 KV Cache，即使这些内容没有改变。
2. **结构化输出难控制**：业务需要模型输出符合 JSON Schema、正则表达式或 EBNF 的文本，但靠采样后校验效率低、失败率高。
3. **控制流表达力弱**：单次 `generate` 接口难以表达“先思考、再选择工具、再并行调用、再汇总”的复杂 Agent 流程。
4. **前缀复用不自动**：vLLM 的 Prefix Caching 需要显式配置或依赖 Block Hash；SGLang 希望通过 Radix Tree 自动、最大化地复用任意共享前缀。

### SGLang 的诞生

SGLang 由 LMSYS 团队开发，2023 年底发表 NeurIPS 2023 论文 [SGLang: Efficient Execution of Structured Language Model Programs](https://arxiv.org/abs/2312.07104)。它提出把 LLM 调用抽象为 **Structured Language Model Programs**，并通过 **RadixAttention** 和 **Runtime 编译优化** 来提升执行效率。

截至 2026 年 7 月，SGLang 已发展到 [v0.5.14](https://github.com/sgl-project/sglang/releases)，支持 200+ 模型、XGrammar-2 结构化输出、DeepSeek-V4 / Llama 4 / Qwen3 等 Day-0 支持，以及 PD 分离、投机解码、扩散模型服务（SGLang-Diffusion）等高级特性。

## 没有 SGLang 会怎样？

在没有 SGLang 之前，复杂交互场景通常面临以下选择：

- **vLLM**：通用推理性能强，但结构化生成需要额外集成 xgrammar/outlines；多轮前缀复用依赖显式 prefix caching。
- **HuggingFace TGI**：已进入维护模式（2025-12 起），新优化主要流向 vLLM 和 SGLang。
- **NVIDIA TensorRT-LLM**：性能高，但封闭、编译复杂，对结构化程序的支持有限。
- **手写 Python 循环**：用 requests 串起多次模型调用，无法做跨调度的 KV cache 复用和调度优化。

SGLang 提供了一种开源、易用、对结构化程序友好的方案。

## SGLang 与替代方案的对比

| 维度 | SGLang | vLLM | TensorRT-LLM | TGI |
|---|---|---|---|---|
| 开源协议 | Apache 2.0 | Apache 2.0 | NVIDIA 专有 | Apache 2.0 / 商业 |
| 维护状态 | 活跃，v0.5.14 | 活跃，V1 默认 | NVIDIA 持续更新 | 2025-12 起维护模式 |
| 核心抽象 | LLM Program + RadixAttention | PagedAttention + Continuous Batching | 高度优化的 CUDA Kernel | Continuous Batching |
| 结构化生成 | 原生深度集成（XGrammar-2） | 通过后端支持 | 有限 | 有限 |
| 前缀复用 | 自动 Radix Tree | Block-level Prefix Caching | 有限 | 有限 |
| 编程模型 | `gen`/`select`/`fork`/`run` | 单次 completion | 单次 completion | 单次 completion |
| 适用场景 | Agent、多轮、结构化输出 | 通用在线推理 | 极致性能 / NVIDIA 全栈 | 简单在线服务 |

## 一句话理解

> SGLang 解决的是 LLM 程序执行效率与可控性的矛盾：通过把多次调用编译成统一执行图，并用 Radix Tree 自动复用前缀，让复杂交互场景既快又稳。

## 本章小结

SGLang 的诞生不是因为通用推理不够快，而是因为 LLM 应用正在从“一句话补全”变成“一段程序”。它要解决的核心问题是：如何让这段程序执行得高效、可控、易维护。

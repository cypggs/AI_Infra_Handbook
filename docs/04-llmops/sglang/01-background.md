# 1. 背景

## 为什么需要 SGLang？

大语言模型（LLM）推理正在从“单次补全”走向“程序式交互”。Agent、多轮对话、函数调用、JSON 输出、A/B 推理分支等场景，要求推理系统不仅跑得快，还要能表达和优化复杂的控制流与结构约束。

### LLM 程序式交互的核心痛点

1. **重复 prefill 开销大**：多轮对话中，每一轮都要重新计算 system prompt + 历史对话的 KV Cache，即使这些内容没有改变。
2. **结构化输出难控制**：业务需要模型输出符合 JSON Schema、正则表达式或 EBNF 的文本，但靠采样后校验效率低、失败率高。
3. **控制流表达力弱**：单次 `generate` 接口难以表达“先思考、再选择工具、再并行调用、再汇总”的复杂 Agent 流程。
4. **前缀复用不自动**：vLLM 的 Prefix Caching 需要显式配置或依赖 Block Hash；SGLang 希望通过 Radix Tree 自动、最大化地复用任意共享前缀。

### SGLang 的诞生

SGLang 由 LMSYS 团队开发，论文 [SGLang: Efficient Execution of Structured Language Model Programs](https://arxiv.org/abs/2312.07104) 于 2023 年 12 月发布在 arXiv，后收录于 NeurIPS 2024。它提出把 LLM 调用抽象为 **Structured Language Model Programs**，并通过 **RadixAttention** 和 **Runtime 编译优化** 来提升执行效率。

截至 2026 年 10 月，SGLang 已发展到 [v0.5.21](https://github.com/sgl-project/sglang/releases)，支持 200+ 模型，主要进展包括：

- **缓存体系升级**：HiCache 三层分层 KV 缓存（GPU HBM → 主机内存 → Mooncake / 3FS 等分布式存储）成熟落地，v0.5.19 起统一 Radix Tree 成为所有配置的默认缓存（含 Full-attention-only 模型），v0.5.21 起前缀缓存默认迁移到 Rust 核心。
- **分离式部署**：PD 分离支撑了 96 张 H100 上 DeepSeek-V3/R1 的大规模专家并行部署（约 5 倍于朴素 TP）；2026 年初进一步推出面向多模态的 EPD（Encoder-Prefill-Decode）分离；v0.5.21 支持 prefill / decode 实例运行时互换角色。
- **Day-0 模型支持**：DeepSeek-V3.2（稀疏注意力 DSA）官方推荐推理引擎；v0.5.17 起 day-0 支持 Kimi K3（2.8T 参数 LatentMoE、1M 上下文），后续版本又首发支持 Qwen3.8（v0.5.19）、GLM-5.3-Flash（v0.5.20）、DeepSeek-V4.1 Flash、MiMo-V2.6（v0.5.21）等新模型，并覆盖扩散模型与 VLA 模型。
- **RL 后训练**：提供 sleep / wake-up 显存卸载、`/update_weights_from_tensor` 权重热更新、v0.5.20 起 `return_sampling_mask` 逐步返回采样支撑集与 logprob（训练侧可精确重放 rollout）等能力，成为 veRL 等 RL 框架的事实标准 rollout 引擎。

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
| 维护状态 | 活跃，v0.5.21 | 活跃，V1 默认 | NVIDIA 持续更新 | 2025-12 起维护模式 |
| 核心抽象 | LLM Program + RadixAttention | PagedAttention + Continuous Batching | 高度优化的 CUDA Kernel | Continuous Batching |
| 结构化生成 | 原生深度集成（XGrammar-2） | 通过后端支持 | 有限 | 有限 |
| 前缀复用 | 自动 Radix Tree | Block-level Prefix Caching | 有限 | 有限 |
| 编程模型 | `gen`/`select`/`fork`/`run` | 单次 completion | 单次 completion | 单次 completion |
| 适用场景 | Agent、多轮、结构化输出 | 通用在线推理 | 极致性能 / NVIDIA 全栈 | 简单在线服务 |

## 一句话理解

> SGLang 解决的是 LLM 程序执行效率与可控性的矛盾：通过把多次调用编译成统一执行图，并用 Radix Tree 自动复用前缀，让复杂交互场景既快又稳。

## 本章小结

SGLang 的诞生不是因为通用推理不够快，而是因为 LLM 应用正在从“一句话补全”变成“一段程序”。它要解决的核心问题是：如何让这段程序执行得高效、可控、易维护。

# 1. 背景

## 为什么需要 vLLM？

大语言模型（LLM）推理是一个资源密集型的过程。一个请求从进入系统到输出完整回答，需要在 GPU 上保存大量的中间状态，即 **KV Cache**。KV Cache 占用的显存随序列长度线性增长，而早期系统采用静态、连续的显存分配方式，导致严重的显存浪费。

### LLM 推理的核心痛点

1. **显存浪费严重**：为每个请求预先分配最大可能长度的连续显存，实际使用却很少。
2. **吞吐低下**：请求长度差异大，简单的静态批处理导致 batch 中短请求必须等待长请求完成。
3. **延迟不可控**：长序列请求阻塞短请求，尾部延迟恶化。
4. **内部碎片化**：不同长度请求释放显存后留下无法利用的小块空闲空间。

### vLLM 的诞生

vLLM 由伯克利 LMSYS 团队开发，2023 年 9 月发布 [PagedAttention 论文](https://arxiv.org/abs/2309.06180)（SOSP 2023），同年开源。它把操作系统中经典的虚拟内存分页思想引入 LLM 推理，提出了 **PagedAttention**：把 KV Cache 切分成固定大小的 Block，通过 Block Table 动态映射，从而大幅提高显存利用率。

截至 2026 年 10 月，vLLM 已演进至 [v0.31.0](https://github.com/vllm-project/vllm/releases)（2026-10-05），保持约每两周一个版本的迭代速度。V1 引擎自 2025 年起成为默认引擎，**Model Runner V2** 自 v0.29.0（2026-09-09）起成为所有模型的默认执行层（V1 Model Runner 计划在 v0.32 移除）。vLLM 支持 200+ 模型家族、多种量化格式、多模态推理与分布式并行，是开源 LLM 推理领域事实上的默认选择之一。

### 2025–2026 年的重要演进

在 PagedAttention 与 Continuous Batching 之外，近一年 vLLM 的主线演进包括：

- **Prefill-Decode（PD）分离成熟**：通过 KV Connector（NIXL、Mooncake、LMCache 等）把 prefill 与 decode 拆到不同实例，并与 llm-d 等路由器配合实现全局调度（参见 vLLM 官方博客 [Taking vLLM Apart: A Practical Guide to Disaggregated Serving](https://vllm.ai/blog)，2026-09-29）。
- **分层 KV Cache Offloading**：自 v0.22 起支持把驱逐的 KV 数据保留到 CPU 内存（LRU/ARC 缓存）、文件系统、S3 对象存储与 P2P 远端节点，而不是直接丢弃重算（官方博客 [Tiered KV Cache Offloading in vLLM](https://vllm-project.github.io/2026/09/10/tiered-kv-offloading.html)，2026-09-10）。
- **推测解码（Speculative Decoding）生产化**：支持 MTP / EAGLE-3 等多种草稿模型，v0.29.0 起 OpenAI API 响应可返回逐请求的接受率统计。
- **结构化输出**：以 xgrammar 为默认后端，支持 JSON Schema / 正则 / EBNF 约束的逐 token 掩码解码。
- **MoE 大规模并行**：专家并行（EP）+ EPLB（Expert Load Balancing）与宽 EP 部署，官方实现 DeepSeek 在 H200 上单卡 2.2k tok/s 的大规模 serving（vLLM 博客，2025-12-17）。
- **与 RL 训练打通**：Native RL API、bitwise 一致的训推同步（v0.29.0 引入 `sharded_rdt` P2P 权重同步后端），让 vLLM 同时成为 RL rollout 的事实标准引擎。
- **运维体验**：`vllm preload` 权重缓存守护进程实现秒级重启（v0.30.0），Sleep Mode 支持模型显存零重载切换（vLLM 博客，2025-10-26）。

## 没有 vLLM 会怎样？

在没有 vLLM 之前，生产环境通常面临以下选择：

- 使用 HuggingFace Transformers 原生推理：简单但吞吐极低。
- 使用 HuggingFace TGI：引入 Continuous Batching，但 KV Cache 管理仍然粗糙。值得注意的是，TGI 已于 2025 年 12 月进入维护模式，新优化将主要出现在 vLLM 和 SGLang。
- 使用 NVIDIA TensorRT-LLM：性能高但封闭、编译复杂、灵活性差。

vLLM 提供了一种开源、易用、高性能的折中方案，迅速成为社区主流。

## vLLM 与替代方案的对比

| 维度 | vLLM | HuggingFace TGI | TensorRT-LLM | SGLang |
|---|---|---|---|---|
| 开源协议 | Apache 2.0 | Apache 2.0 / 商业 | NVIDIA 专有 | Apache 2.0 |
| 维护状态 | 活跃，V1 为默认引擎 | 2025-12 起进入维护模式 | NVIDIA 持续更新 | 活跃 |
| 易用性 | 高 | 中 | 低 | 中 |
| 性能 | 高（通用场景领先） | 中高 | 很高（NVIDIA 硬件） | 高（共享前缀/结构化输出） |
| 灵活性 | 高 | 中 | 低 | 高 |
| 核心创新 | PagedAttention + Continuous Batching | Continuous Batching | 高度优化的 CUDA Kernel | RadixAttention + Compiler |
| PD 分离 / KV 传输 | KV Connector 生态（NIXL/Mooncake/LMCache） | 有限 | 支持 | 支持 |
| 生态 | 极大 | 大 | NVIDIA 生态 | 快速增长 |

## 一句话理解

> vLLM 解决的是 LLM 推理中显存利用率与吞吐的核心矛盾：通过 PagedAttention 把 KV Cache 当成虚拟内存管理，让同一块 GPU 能同时服务更多请求。

## 本章小结

vLLM 解决的是 LLM 推理中显存利用率与吞吐的核心矛盾。它的设计动机不是让单条请求更快，而是让同一块 GPU 能同时服务更多请求。

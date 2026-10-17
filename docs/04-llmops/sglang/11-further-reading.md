# 11. 延伸阅读

## 官方文档

- [SGLang 官方文档](https://docs.sglang.ai/)
- [SGLang GitHub Repository](https://github.com/sgl-project/sglang)
- [SGLang Release Notes](https://github.com/sgl-project/sglang/releases)

## 论文

- [SGLang: Efficient Execution of Structured Language Model Programs](https://arxiv.org/abs/2312.07104) — NeurIPS 2024
- [XGrammar: Flexible and Efficient Structured Generation Engine for LLMs](https://arxiv.org/abs/2411.15100) — NeurIPS 2024
- [XGrammar-2: Efficient Dynamic Structured Generation Engine for Agentic LLMs](https://arxiv.org/abs/2601.04426) — 2026
- [DeepSeek-V3.2: Pushing the Frontier of Open Large Language Models](https://arxiv.org/abs/2512.02556) — DSA 稀疏注意力，2025-12

## SGLang 团队博客（2025-2026）

- [SGLang HiCache: Fast Hierarchical KV Caching](https://www.lmsys.org/blog/2025-09-10-sglang-hicache/) — 2025-09
- [SGLang Day-0 Support for DeepSeek-V3.2 with Sparse Attention](https://www.lmsys.org/blog/2025-09-29-deepseek-V32/) — 2025-09
- [Deploying DeepSeek with PD Disaggregation and Large-Scale Expert Parallelism on 96 H100 GPUs](https://www.lmsys.org/blog/2025-05-05-large-scale-ep/) — 2025-05
- [EPD Disaggregation: Elastic Encoder Scaling for Vision-Language Models](https://www.lmsys.org/blog/2026-01-12-epd/) — 2026-01
- [SGLang Day-0 Support for Kimi K3](https://www.lmsys.org/blog/2026-07-27-kimi-k3-day0-support/) — 2026-07，Kimi K3（2.8T LatentMoE / 1M 上下文）day-0 支持
- [DSpark: Confidence-Driven Speculative Decoding in SGLang](https://www.lmsys.org/blog/2026-07-06-dspark-sglang/) — 2026-07，v0.5.16 新投机解码算法

## 结构化生成相关

- [xgrammar GitHub](https://github.com/mlc-ai/xgrammar)
- [Outlines 文档](https://dottxt-ai.github.io/outlines/)

## 对比与生产实践

- [vLLM 官方文档](https://docs.vllm.ai/)
- [Mooncake: A KVCache-centric Disaggregated Architecture](https://github.com/kvcache-ai/Mooncake)
- [Mooncake x SGLang HiCache System Design](https://kvcache-ai.github.io/Mooncake/design/hicache-design.html)
- [SGLang for RL Systems 官方文档](https://docs.sglang.ai/advanced_features/sglang_for_rl.html)
- LMSYS / SGLang 团队技术博客与演讲

## 社区资源

- SGLang GitHub Discussions
- SGLang Slack / Discord
- SGLang 中文社区讨论

## 相关章节

- [vLLM 详解](/04-llmops/vllm/)
- [TensorRT-LLM 详解](/04-llmops/tensorrt-llm/)
- [Triton Inference Server 详解](/04-llmops/triton/)
- [LLM Gateway 详解](/04-llmops/llm-gateway/)
- [LLM 推理缓存与 KV Cache 管理详解](/04-llmops/kv-cache/) — SGLang HiCache 分层缓存、Rust radix tree 与 PD 分离传输的基础设施视角，与本主题 RadixAttention 互为表里。
- [模型量化与压缩基础设施详解](/04-llmops/model-quantization/) — 量化支持矩阵、精度-性能权衡与压缩工具链，与 SGLang 的量化推理路径互补。
- [LLMOps 概述](/04-llmops/)
- [学习路线](/10-roadmap/learning-path)
- [面试指南](/10-roadmap/interview-guide)

## 推荐学习路径

1. 先读 SGLang 论文，理解 LLM Program 与 RadixAttention 的设计动机。
2. 阅读官方文档的 Architecture 和 Sampling 部分。
3. 阅读源码中的 `python/sglang/srt/managers/scheduler.py` 和统一 Radix Tree 缓存实现（`unified_radix_cache.py` 与 `rust/` 目录）。
4. 结合生产实践文章，思考在自己的 Agent / 多轮场景中如何部署。

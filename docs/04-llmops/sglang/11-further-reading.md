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
- [LLMOps 概述](/04-llmops/)
- [学习路线](/10-roadmap/learning-path)
- [面试指南](/10-roadmap/interview-guide)

## 推荐学习路径

1. 先读 SGLang 论文，理解 LLM Program 与 RadixAttention 的设计动机。
2. 阅读官方文档的 Architecture 和 Sampling 部分。
3. 阅读源码中的 `python/sglang/srt/managers/scheduler.py` 和统一 Radix Tree 缓存实现（`unified_radix_cache.py` 与 `rust/` 目录）。
4. 结合生产实践文章，思考在自己的 Agent / 多轮场景中如何部署。

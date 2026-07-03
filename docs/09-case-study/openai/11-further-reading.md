# 延伸阅读

本章汇总 OpenAI 相关的权威来源、官方博客、论文、演讲与本手册交叉引用。

## 官方来源

- [OpenAI Blog](https://openai.com/blog/) — 模型发布、产品更新、工程实践。
- [OpenAI Research](https://openai.com/research/) — 论文与技术报告。
- [OpenAI API Documentation](https://platform.openai.com/docs/) — API 参考与最佳实践。
- [OpenAI Latency Optimization Guide](https://developers.openai.com/api/docs/guides/latency-optimization) — 官方推理延迟优化七原则。
- [OpenAI Preparedness Framework (Beta)](https://cdn.openai.com/openai-preparedness-framework-beta.pdf) — 前沿风险治理框架。
- [GPT-4o System Card](https://arxiv.org/pdf/2410.21276v1) — GPT-4o 安全评估与红队报告。

## Microsoft / Azure 合作

- [Azure previews powerful and scalable VM series for generative AI](https://azure.microsoft.com/en-us/blog/azure-previews-powerful-and-scalable-virtual-machine-series-to-accelerate-generative-ai/) — ND H100 v5 与 OpenAI co-design。
- [How Microsoft’s bet on Azure unlocked an AI revolution](https://news.microsoft.com/source/features/ai/how-microsofts-bet-on-azure-unlocked-an-ai-revolution/) — Microsoft-OpenAI 合作深度报道。
- [NVIDIA Technical Blog: What Runs ChatGPT?](https://developer.nvidia.com/blog/new-video-what-runs-chatgpt/) — Mark Russinovich 讲解 Azure AI 超级计算机。

## 论文

- **Lewis et al. 2020** — *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks* (NeurIPS 2020) — RAG 奠基论文。
- **Brown et al. 2020** — *Language Models are Few-Shot Learners* (NeurIPS 2020) — GPT-3。
- **OpenAI 2023** — *GPT-4 Technical Report* — GPT-4 能力与安全概述。
- **OpenAI 2024** — *GPT-4o System Card* — 多模态安全评估。
- **Beutel et al. 2024** — *Diverse and Effective Red Teaming with Auto-Generated Rewards and Multi-Step RL* — OpenAI 自动化红队。

## 开源项目

- [OpenAI Triton](https://github.com/triton-lang/triton) — Python-like GPU kernel 语言与编译器。
- [OpenAI GPT-2](https://github.com/openai/gpt-2) — 早期开源大模型实现。
- [OpenAI CLIP](https://github.com/openai/CLIP) — 视觉-语言对比学习。
- [OpenAI Whisper](https://github.com/openai/whisper) — 语音识别模型。

## 工程分析与演讲

- [Scaling ChatGPT: Inside OpenAI's Rapid Growth](https://linearb.io/dev-interrupted/podcast/scaling-chatgpt-inside-openais-rapid-growth-and-technical-challenges) — Evan Morikawa 访谈。
- [Simon Willison: Building, launching, and scaling ChatGPT Images](https://simonwillison.net/2025/May/13/launching-chatgpt-images/) — 产品工程幕后。
- [OpenAI Red Teaming Network](https://openai.com/index/red-teaming-network/) — 红队计划官方介绍。

## 本手册交叉引用

- [vLLM 详解](/04-llmops/vllm/) — continuous batching、PagedAttention、KV cache。
- [TensorRT-LLM 详解](/04-llmops/tensorrt-llm/) — 编译型推理优化。
- [LLM Gateway 详解](/04-llmops/llm-gateway/) — API Gateway、限流、路由、多租户。
- [安全详解](/08-security/) — Preparedness Framework、Red Teaming、Guardrails。
- [AI SRE 详解](/07-ai-sre/) — SLO、burn rate、可观测性。
- [Agent Runtime 详解](/05-agent/agent-runtime/) — Agent 执行与工具调用。

## 学习路径建议

1. 先读 OpenAI 官方 latency optimization guide 与 Preparedness Framework。
2. 看 Microsoft/Azure 合作博客，理解训练基础设施规模。
3. 跑通 Triton 官方 tutorial，理解 GPU kernel 编程。
4. 结合本手册 LLMOps 与 LLM Gateway 主题，复现一个 mini API server。
5. 阅读 System Cards，学习如何撰写模型安全评估报告。

## 小结

OpenAI 的公开资料是理解大模型基础设施的宝贵资源。建议持续关注 OpenAI Blog、Research、System Cards 与 Microsoft/Azure 的技术发布，因为这一领域仍在快速演进。

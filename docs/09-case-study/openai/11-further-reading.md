# 延伸阅读

本章汇总 OpenAI 相关的权威来源、官方博客、论文、演讲与本手册交叉引用。

## 官方来源

- [OpenAI Blog](https://openai.com/blog/) — 模型发布、产品更新、工程实践。
- [OpenAI Research](https://openai.com/research/) — 论文与技术报告。
- [OpenAI API Documentation](https://platform.openai.com/docs/) — API 参考与最佳实践。
- [OpenAI Model Release Notes](https://help.openai.com/en/articles/9624314-model-release-notes) — 模型发布与退役日历的权威记录。
- [OpenAI Latency Optimization Guide](https://developers.openai.com/api/docs/guides/latency-optimization) — 官方推理延迟优化七原则。
- [OpenAI Preparedness Framework (Beta)](https://cdn.openai.com/openai-preparedness-framework-beta.pdf) — 前沿风险治理框架（v2 于 2025-04 发布）。
- [GPT-5 System Card](https://cdn.openai.com/pdf/8124a3ce-ab78-4f06-96eb-49ea29ffb52f/gpt5-system-card-aug7.pdf) — GPT-5 统一系统、路由器与安全评估。
- [GPT-4o System Card](https://arxiv.org/pdf/2410.21276v1) — GPT-4o 安全评估与红队报告。

## 2025–2026 里程碑

- [New tools for building agents（Responses API / Agents SDK）](https://openai.com/index/new-tools-for-building-agents/) — 2025-03，API 的 Agent 原语化。
- [Introducing gpt-oss](https://openai.com/index/introducing-gpt-oss/) — 2025-08，七年来首批开放权重模型（gpt-oss-120b/20b）。
- [Five new Stargate sites](https://openai.com/index/five-new-stargate-sites/) — 2025-09，Stargate 新增五座站点、接近 7 GW。
- [OpenAI × Broadcom Jalapeño inference chip](https://openai.com/index/openai-broadcom-jalapeno-inference-chip/) — 2026-06，首款自研 LLM 推理 ASIC。
- [How we used Codex to ship Sora for Android in 28 days](https://openai.com/index/shipping-sora-for-android-with-codex/) — 模型参与自身工程交付的实例。

## Microsoft / Azure 合作

- [Azure previews powerful and scalable VM series for generative AI](https://azure.microsoft.com/en-us/blog/azure-previews-powerful-and-scalable-virtual-machine-series-to-accelerate-generative-ai/) — ND H100 v5 与 OpenAI co-design。
- [How Microsoft’s bet on Azure unlocked an AI revolution](https://news.microsoft.com/source/features/ai/how-microsofts-bet-on-azure-unlocked-an-ai-revolution/) — Microsoft-OpenAI 合作深度报道。
- [NVIDIA Technical Blog: What Runs ChatGPT?](https://developer.nvidia.com/blog/new-video-what-runs-chatgpt/) — Mark Russinovich 讲解 Azure AI 超级计算机。
- [Stargate tracker](https://stargate.how/) — 第三方维护的 Stargate 站点与容量追踪。

## 论文

- **Lewis et al. 2020** — *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks* (NeurIPS 2020) — RAG 奠基论文。
- **Brown et al. 2020** — *Language Models are Few-Shot Learners* (NeurIPS 2020) — GPT-3。
- **OpenAI 2023** — *GPT-4 Technical Report* — GPT-4 能力与安全概述。
- **OpenAI 2024** — *GPT-4o System Card* — 多模态安全评估。
- **Beutel et al. 2024** — *Diverse and Effective Red Teaming with Auto-Generated Rewards and Multi-Step RL* — OpenAI 自动化红队。
- **OpenAI 2024** — *Deliberative Alignment: Reasoning Enables Safer Language Models* — 用思维链把安全规格训进 reasoning 模型。
- **OpenAI 2025** — *Rule-Based Rewards for Language Model Safety* — 把安全规格拆成可判分命题作为 RL 奖励。

## 开源项目

- [OpenAI Triton](https://github.com/triton-lang/triton) — Python-like GPU kernel 语言与编译器。
- [OpenAI GPT-2](https://github.com/openai/gpt-2) — 早期开源大模型实现。
- [OpenAI CLIP](https://github.com/openai/CLIP) — 视觉-语言对比学习。
- [OpenAI Whisper](https://github.com/openai/whisper) — 语音识别模型。
- [openai/gpt-oss](https://github.com/openai/gpt-oss) — 开放权重 reasoning 模型（Apache 2.0）。
- [openai-agents-python](https://github.com/openai/openai-agents-python) — Agents SDK。
- [openai/codex](https://github.com/openai/codex) — 开源编程 Agent（CLI + 云任务）。

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
- [Anthropic 案例研究](/09-case-study/anthropic/) — 对照"规模驱动"与"对齐驱动"两条前沿实验室工程路线。
- [Meta 案例研究](/09-case-study/meta/) — 对照"闭源规模（OpenAI）↔ 闭源对齐（Anthropic）↔ 开放权重 + 硬件协同设计（Meta）"三角，理解开放生态如何 scale 到极致。
- [Google 案例研究](/09-case-study/google/) — 对照"闭源规模 + 通用 GPU"与"垂直整合自研 TPU 硅 + 开放软件栈（JAX/XLA/MaxText）"。

## 学习路径建议

1. 先读 OpenAI 官方 latency optimization guide 与 Preparedness Framework v2。
2. 看 Stargate 站点公告与 Jalapeño 芯片发布，理解 10 GW 时代的算力工程。
3. 精读 GPT-5 System Card，理解统一系统 + 路由器的安全评估方式。
4. 跑通 Triton 官方 tutorial，理解 GPU kernel 编程。
5. 用 openai/gpt-oss 做一次单卡部署，体验 MoE + MXFP4 量化的工程细节。
6. 结合本手册 LLMOps 与 LLM Gateway 主题，复现一个 mini API server。

## 小结

OpenAI 的公开资料是理解大模型基础设施的宝贵资源。建议持续关注 OpenAI Blog、Research、System Cards 与 Microsoft/Azure 的技术发布，因为这一领域仍在快速演进。

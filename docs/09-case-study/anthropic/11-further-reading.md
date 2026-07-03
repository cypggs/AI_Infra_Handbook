# 延伸阅读

本章汇总 Anthropic 相关的权威来源、官方文档、论文、可解释性研究与本手册交叉引用。

## 官方来源

- [Anthropic News](https://www.anthropic.com/news) — 模型发布、产品更新、治理公告。
- [Claude Platform Docs](https://platform.claude.com/docs) — API 参考、prompt caching、extended thinking、tool/computer use。
- [Prompt Caching 文档](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) — prefix hash + 20-block lookback、TTL、预热、计费倍率。
- [Responsible Scaling Policy](https://www.anthropic.com/news/responsible-scaling-policy-v3) — RSP v3 与 ASL 框架。
- [Claude's Constitution](https://www.anthropic.com/news/claudes-constitution) — 宪法原则来源与设计。
- [Anthropic and Amazon expand collaboration (up to 5 GW)](https://www.anthropic.com/news/anthropic-amazon-compute) — Project Rainier、>100 万 Trainium2、$100B/10 年。

## 论文与可解释性研究

- **Bai et al. 2022** — *Constitutional AI: Harmlessness from AI Feedback*（[arXiv:2212.08073](https://arxiv.org/abs/2212.08073)）— CAI / RLAIF 奠基论文。
- **Elhage et al. 2021** — *A Mathematical Framework for Transformer Circuits*（[transformer-circuits.pub](https://transformer-circuits.pub/)）— attention heads、induction heads。
- **Bricken et al. 2023** — *Towards Monosemanticity* — dictionary learning / 稀疏自编码器分解特征。
- **Templeton et al. 2024** — *Scaling Monosemanticity* — 在 Claude 3 Sonnet 上解析数百万特征。
- **Anthropic 2025** — *On the Biology of a Large Language Model* / *Circuit Tracing* — 特征作为分类器、电路级追踪。

## 算力与合作

- [Anthropic Leases SpaceXAI's 220,000 NVIDIA GPU Colossus Cluster](https://hothardware.com/news/anthropic-leases-spacexais-220000-nvidia-gpu-colossus) — Colossus 异构算力补充。
- [Amazon Bedrock — Anthropic](https://aws.amazon.com/bedrock/anthropic/) — Bedrock 托管与 Trainium。
- [Google Cloud Vertex AI — Claude](https://cloud.google.com/vertex-ai/generative-ai/docs/partner-models/use-claude) — Vertex AI 托管。
- [Microsoft Azure Foundry — Claude](https://learn.microsoft.com/en-us/azure/ai-foundry/) — Azure Foundry 托管。

## 开源与生态

- [transformer-circuits.pub](https://transformer-circuits.pub/) — 可解释性研究论文与实验。
- [Anthropic Cookbook / SDK（Python、TypeScript）](https://github.com/anthropics) — 集成示例与官方 SDK。
- [Anthropic Skills](https://platform.claude.com/docs) — 渐进式指令（progressive disclosure）的 Agent 能力封装。
- [Model Context Protocol（MCP）](https://modelcontextprotocol.io/) — Anthropic 主导的工具/资源协议（详见 [MCP 详解](/05-agent/mcp/)）。

## 工程分析

- [Anthropic — Frontier Safety Roadmap / Risk Reports](https://www.anthropic.com/) — 治理 roadmap 与定期风险报告。
- [RAND — Securing AI Model Weights](https://www.rand.org/) — 模型权重安全等级（SL5 等）参考。
- [California SB 53 / NY RAISE Act / EU AI Act Codes of Practice](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai) — 与 RSP 对齐的监管框架。

## 本手册交叉引用

- [OpenAI 案例研究](/09-case-study/openai/) — 对照"规模驱动" vs "对齐驱动"两条路线。
- [vLLM 详解](/04-llmops/vllm/) — continuous batching、KV/prefix cache 工程化。
- [LLM Gateway 详解](/04-llmops/llm-gateway/) — 多云入口、限流、计费、cache 感知路由。
- [Agent Runtime 详解](/05-agent/agent-runtime/) — tool/computer use、extended thinking 的执行循环。
- [MCP 详解](/05-agent/mcp/) — Anthropic 主导的工具/资源协议。
- [安全详解](/08-security/) — RSP/ASL、guardrails、红队、权重安全。
- [AI SRE 详解](/07-ai-sre/) — 容量规划、cache 命中率、成本 SLO。

## 学习路径建议

1. 先读 Constitutional AI 论文，理解 CAI/RLAIF 与 RLHF 的区别。
2. 读 RSP v3 与 Claude's Constitution，理解治理化扩展的思想。
3. 精读 Prompt Caching 官方文档，跑通本主题 Mini Demo 的命中模型。
4. 浏览 transformer-circuits.pub 的 Towards/Scaling Monosemanticity，理解可解释性工程化。
5. 结合 [OpenAI 案例研究](/09-case-study/openai/) 做对照阅读，形成完整的"前沿实验室工程路线"地图。

## 小结

Anthropic 的公开资料在"对齐、可解释性、治理"三条线上是行业最系统的。建议持续关注 Anthropic News、transformer-circuits、Claude Platform Docs 与 RSP/Risk Report 的更新——这三条线仍在快速演进。

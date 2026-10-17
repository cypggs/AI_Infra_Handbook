# 延伸阅读

本章汇总 Anthropic 相关的权威来源、官方文档、论文、可解释性研究与本手册交叉引用。

## 官方来源

- [Anthropic News](https://www.anthropic.com/news) — 模型发布、产品更新、治理公告。
- [Claude Platform Docs](https://platform.claude.com/docs) — API 参考、prompt caching、extended thinking、tool/computer use、Managed Agents。
- [Prompt Caching 文档](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) — prefix hash + 20-block lookback、TTL、按模型的最小缓存长度与读倍率、预热、mid-conversation system、inline tools。
- [Responsible Scaling Policy](https://www.anthropic.com/responsible-scaling-policy) — RSP v3.x 与 CB-1/CB-2 阈值框架。
- [Anthropic Risk Report（2026-08）](https://www.anthropic.com/aug-2026-risk-report) — RSP v3.4 下的第二份公司级风险报告。
- [Claude's Constitution](https://www.anthropic.com/news/claudes-constitution) — 宪法原则来源与设计。
- [Anthropic and Amazon expand collaboration (up to 5 GW)](https://www.anthropic.com/news/anthropic-amazon-compute) — Project Rainier、>100 万 Trainium2、$100B/10 年（2026-04 扩大合作）。
- [Claude Fable 5 & Mythos 5](https://www.anthropic.com/news/claude-fable-5-mythos-5) 与 [Fable 5.1 / Mythos 5.1 System Card](https://www.anthropic.com/claude-fable-5-1-mythos-5-1-system-card) — Mythos 级模型、分类器路由与 Project Glasswing。
- [When AI Builds Itself（Anthropic Institute）](https://www.anthropic.com/institute/recursive-self-improvement) — RSI 预警：80%+ 代码由 Claude 编写、任务时程 4 分钟 → 12 小时。
- [How Anthropic Teams Use Claude Code（报告 PDF）](https://www-cdn.anthropic.com/58284b19e702b49db9302d5b6f135ad8871e7658.pdf) — 内部团队 dogfooding 实践（CLAUDE.md、checkpoint 提交等）。

## 论文与可解释性研究

- **Bai et al. 2022** — *Constitutional AI: Harmlessness from AI Feedback*（[arXiv:2212.08073](https://arxiv.org/abs/2212.08073)）— CAI / RLAIF 奠基论文。
- **Elhage et al. 2021** — *A Mathematical Framework for Transformer Circuits*（[transformer-circuits.pub](https://transformer-circuits.pub/)）— attention heads、induction heads。
- **Bricken et al. 2023** — *Towards Monosemanticity* — dictionary learning / 稀疏自编码器分解特征。
- **Templeton et al. 2024** — *Scaling Monosemanticity* — 在 Claude 3 Sonnet 上解析数百万特征。
- **Anthropic 2025** — *On the Biology of a Large Language Model* / *Circuit Tracing* — 特征作为分类器、电路级追踪（`circuit-tracer` 已开源）。
- **Lu et al. 2026-01** — *The Assistant Axis* — 人格空间映射与 activation capping 抗越狱。
- **Anthropic 2026-05** — *Natural Language Autoencoder* — 把激活翻译成自然语言，支撑内部独白监控（预训练权重已开源）。

## 算力与合作

- [Anthropic Leases SpaceXAI's 220,000 NVIDIA GPU Colossus Cluster](https://hothardware.com/news/anthropic-leases-spacexais-220000-nvidia-gpu-colossus) — Colossus 异构算力补充。
- [Amazon Bedrock — Anthropic](https://aws.amazon.com/bedrock/anthropic/) — Bedrock 托管与 Trainium。
- [Google Cloud Vertex AI — Claude](https://cloud.google.com/vertex-ai/generative-ai/docs/partner-models/use-claude) — Vertex AI 托管。
- [Microsoft Azure Foundry — Claude](https://learn.microsoft.com/en-us/azure/ai-foundry/) — Azure Foundry 托管。

## 开源与生态

- [transformer-circuits.pub](https://transformer-circuits.pub/) — 可解释性研究论文与实验。
- [Anthropic Cookbook / SDK（Python、TypeScript）](https://github.com/anthropics) — 集成示例与官方 SDK。
- [Anthropic Skills](https://platform.claude.com/docs) — 渐进式指令（progressive disclosure）的 Agent 能力封装。
- [Model Context Protocol（MCP）](https://modelcontextprotocol.io/) — Anthropic 发起、2025-12 捐赠给 Linux 基金会 AAIF；2026-07-28 规范为最大一次修订（无状态化、去握手，详见 [MCP 详解](/05-agent/mcp/)）。
- [Claude Managed Agents 指南](https://platform.claude.com/docs) — 托管沙箱、凭据、checkpoint 与 Dreaming / Outcomes / 多智能体编排。

## 工程分析

- [Anthropic — Frontier Safety Roadmap / Risk Reports](https://www.anthropic.com/) — 治理 roadmap 与定期风险报告。
- [RAND — Securing AI Model Weights](https://www.rand.org/) — 模型权重安全等级（SL5 等）参考。
- [California SB 53 / NY RAISE Act / EU AI Act Codes of Practice](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai) — 与 RSP 对齐的监管框架。

## 本手册交叉引用

- [OpenAI 案例研究](/09-case-study/openai/) — 对照"规模驱动" vs "对齐驱动"两条路线。
- [Meta 案例研究](/09-case-study/meta/) — 对照"闭源对齐（Anthropic）↔ 开放权重 + 硬件协同设计（Meta）"；Meta 也公开 SDC 治理与 >95% 有效训练时间的可靠性工程。
- [Google 案例研究](/09-case-study/google/) — 对照"闭源对齐"与"开放生态 + Frontier Safety Framework"；两者都有正式的安全治理框架，Google 另开放完整软件栈。
- [vLLM 详解](/04-llmops/vllm/) — continuous batching、KV/prefix cache 工程化。
- [LLM Gateway 详解](/04-llmops/llm-gateway/) — 多云入口、限流、计费、cache 感知路由。
- [Agent Runtime 详解](/05-agent/agent-runtime/) — tool/computer use、extended thinking 的执行循环。
- [MCP 详解](/05-agent/mcp/) — Anthropic 主导的工具/资源协议。
- [安全详解](/08-security/) — RSP/ASL、guardrails、红队、权重安全。
- [AI SRE 详解](/07-ai-sre/) — 容量规划、cache 命中率、成本 SLO。

## 学习路径建议

1. 先读 Constitutional AI 论文，理解 CAI/RLAIF 与 RLHF 的区别。
2. 读 RSP v3.x 与 Claude's Constitution，理解治理化扩展的思想；再读 2026-08 Risk Report 看 CB-1/CB-2 阈值如何在真实模型上落地。
3. 精读 Prompt Caching 官方文档，跑通本主题 Mini Demo 的命中模型。
4. 浏览 transformer-circuits.pub 的 Towards/Scaling Monosemanticity，再读 Circuit Tracing 与 NLA，理解可解释性如何走向运行时监控。
5. 读《When AI Builds Itself》，理解 AI 研发自动化如何成为治理阈值与基础设施需求的双重驱动。
6. 结合 [OpenAI 案例研究](/09-case-study/openai/) 做对照阅读，形成完整的"前沿实验室工程路线"地图。

## 小结

Anthropic 的公开资料在"对齐、可解释性、治理"三条线上是行业最系统的。建议持续关注 Anthropic News、transformer-circuits、Claude Platform Docs 与 RSP/Risk Report 的更新——这三条线仍在快速演进。

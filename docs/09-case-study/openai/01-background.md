# 背景：为什么研究 OpenAI

OpenAI 成立于 2015 年，最初是非营利 AI 研究机构。2019 年转型为“封顶利润”模式以获得训练资金，随后与 Microsoft 建立深度 cloud 合作关系。其发展历程几乎就是大模型基础设施发展的缩影。

## 关键里程碑

| 时间 | 事件 | 基础设施意义 |
|---|---|---|
| 2018 | GPT-1 | 首次展示生成预训练 Transformer 的可扩展性。 |
| 2019 | GPT-2 | 模型大到引发“发布风险”讨论，开始 staged release。 |
| 2020 | GPT-3 (175B) | 需要数千 GPU 训练，OpenAI 开始依赖 Azure 超级计算机。 |
| 2022 | ChatGPT |  viral 增长，推理基础设施从研究者工具转向消费级产品。 |
| 2023 | GPT-4 | 多模态、更大规模，训练与推理成本剧增。 |
| 2024 | GPT-4o / o1 | 原生多模态与 reasoning 模型，对实时推理与测试时计算提出新需求。 |
| 2025-01 | Stargate 宣布 | OpenAI 与 SoftBank、Oracle、MGX 宣布四年 5000 亿美元、10 GW 的 AI 数据中心计划，从“租云”转向“自建+多伙伴”。 |
| 2025-03 | Responses API / Agents SDK | API 从“单轮补全”演进为内置工具循环的 Agent 原语。 |
| 2025-08 | gpt-oss + GPT-5 | 七年来首批开放权重模型（gpt-oss-120b/20b，Apache 2.0）；GPT-5 用“快模型 + 推理模型 + 实时路由器”统一架构取代 o 系列，API 上下文扩至 400K。 |
| 2025-10 | DevDay 2025 | AgentKit、Apps SDK、Sora 2 上线 API、GPT-5 Pro 上线 API；ChatGPT 周活约 8 亿。 |
| 2025-11 ~ 2026-04 | GPT-5.x 快速迭代 | GPT-5.1（自适应推理）→ GPT-5.2 → GPT-5.3-Codex（Codex 与 GPT-5 训练栈合并，首个用于 OpenAI 自身训练流程的模型）→ GPT-5.4（原生 computer use、1M 上下文）→ GPT-5.5（全模态旗舰），发布节奏缩短到约 6–10 周。 |
| 2026-06 | Jalapeño 推理芯片 | 与 Broadcom 联合发布首款自研 LLM 推理 ASIC，9 个月完成设计到流片，目标 2026 年底部署，迈向“定制硅降本”。 |
| 2026-07 ~ 09 | GPT-5.6 / GPT-6 | GPT-5.6 引入 Sol/Terra/Luna 能力分层命名；2026-09 发布 GPT-6 系列。同期 o1/o3/o4-mini 等旧模型陆续退役（o4-mini API 于 2026-10-23 关闭），模型生命周期管理成为常态。 |

## 产品矩阵

- **ChatGPT**：面向消费者的对话产品，周活从 2025 年初的 4 亿增长到 2026 年的 10 亿级，峰值流量极高，对延迟和可用性敏感。
- **OpenAI API / Responses API**：面向开发者的 B2B 平台，2025 年起从 Chat Completions 升级为内置工具循环（web search、file search、computer use）的 Responses API，需要多租户、稳定 SLO、全球低延迟。
- **Codex**：Agentic 编程产品（CLI、IDE 插件、云端任务），GPT-5-Codex 起成为默认模型，需要隔离沙箱与长时间运行的任务调度。
- **ChatGPT agent / Operator**：通用 Agent 与工具调用，需要浏览器/计算机沙箱、权限控制与长程状态管理。
- **Sora / Sora 2**：多模态生成，需要大规模图像/视频推理集群；Sora 2 支持音视频同步生成并进入 API。
- **Whisper / Realtime API**：语音模型与实时音视频通话，强调边缘部署与百毫秒级端到端延迟。
- **DALL-E / 图像生成、TTS**：生成式媒体 API，按量计费的高峰型负载。

来源：[OpenAI Model Release Notes](https://help.openai.com/en/articles/9624314-model-release-notes)、[OpenAI DevDay 2025 汇总](https://community.openai.com/t/devday-2025-apps-sdk-sora-2-gpt-5-pro-agentkit-new-image-generation-and-speech-to-speech-mini-models-and-more/1361279)。

## 工程挑战

1. **训练规模指数级增长**
   GPT-4 级别模型训练需要数万个高端 GPU 数月运行，任何硬件/网络/软件故障都会导致数百万美元损失。

2. **推理成本主导运营支出**
   训练成本虽高但一次性；推理是持续性成本，且随用户增长线性或超线性扩张。

3. **延迟与用户体验强相关**
   ChatGPT 的“打字机效果”、first token latency、throughput 直接影响用户留存。

4. **安全与滥用治理**
   开放 API 带来提示注入、越狱、垃圾邮件、版权、有害内容等风险；2026 年随 Agent 能力普及，自主性与网络滥用成为新的评估重点。

5. **模型版本与能力快速迭代**
   2025 年后发布节奏缩短到数月甚至数周（GPT-5 → GPT-5.1/5.2 → 5.3-Codex → 5.4/5.5 → GPT-5.6 → GPT-6），基础设施必须支持快速灰度、A/B 测试、回滚与**旧模型按时退役**。

6. **电力与供应链成为硬约束**
   Stargate 把瓶颈从“买不到 GPU”扩展到“拿得到电力、土地与变压器”；2026 年 OpenAI 进一步与 Broadcom 合作自研推理芯片（Jalapeño），开始向“定制硅”要成本与能效。

## 为什么 OpenAI 值得作为案例

- **公开资料相对丰富**：Microsoft/Azure 官方博客、OpenAI 研究博客、System Cards、演讲、开源项目提供了大量一手信息。
- **覆盖了 AI Infra 全栈**：从数据、训练、推理、部署、安全到产品化。
- **技术选型具有代表性**：大规模 GPU 集群、InfiniBand、continuous batching、KV cache 优化、多模态 pipeline。
- **决策 trade-off 清晰**：性能 vs 成本、安全 vs 能力、封闭 vs 开放、研究 vs 产品。

## 小结

OpenAI 不是唯一的大模型公司，但它的工程路径最能体现“从研究到规模化产品”的完整跃迁。下一章将从其核心工程思想入手，建立分析框架。

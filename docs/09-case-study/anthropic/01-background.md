# 背景：为什么研究 Anthropic

Anthropic 成立于 2021 年，由前 OpenAI 研究副总裁 Dario Amodei（CEO）与 Daniela Amodei（总裁）等人创立。创始团队的核心分歧正是"安全节奏"——他们选择在追求规模化的同时，把安全研究作为公司的一等公民，并以"公共利益公司（Public Benefit Corporation）"的治理结构把这一承诺制度化。其口号是构建 **Reliable, Interpretable, and Steerable（可靠、可解释、可控）** 的 AI 系统。

## 关键里程碑

| 时间 | 事件 | 基础设施 / 工程意义 |
|---|---|---|
| 2021 | Anthropic 成立 | 以 AI 安全为使命；团队多来自 OpenAI。 |
| 2022 | Constitutional AI 论文（arXiv:2212.08073） | 提出 RLAIF，用 AI 反馈替代部分人类标注做对齐。 |
| 2023-03 | Claude 1 上线 | 首个以宪法对齐为核心的产品级对话模型。 |
| 2023-09 | Responsible Scaling Policy（RSP v1） | 行业首个仿照生物安全等级（BSL）的 AI 扩展治理框架。 |
| 2023–2024 | Amazon 投资、Google 投资；Bedrock/Vertex 集成 | 确立三云部署与多云算力战略。 |
| 2024 | Claude 3 / 3.5（Haiku/Sonnet/Opus）；computer use | 多档位模型矩阵 + 智能体能力。 |
| 2024 | Scaling Monosemanticity | 在 Claude 3 Sonnet 上解析出数百万可解释特征。 |
| 2025-02 | Prompt caching 正式可用 | 把 prefix cache 工程化为产品级成本优化能力。 |
| 2025-05 | 激活 ASL-3 防护 | 首次触发更严格的安全等级（CBRN 风险）。 |
| 2025–2026 | Extended thinking、Claude 4 系列、Sonnet 5 / Fable 5 | 测试时计算与前沿模型迭代。 |
| 2026 | RSP v3.0；Frontier Safety Roadmap；Risk Reports | 把治理拆分为"公司承诺 + 行业建议"，引入第三方审查。 |

## Claude 模型矩阵

Anthropic 用三档命名（Haiku / Sonnet / Opus，对应"小快省 / 平衡 / 最强"）覆盖不同延迟与成本区间，并持续迭代：

- **Haiku**：低延迟、低成本，适合高并发、边缘与分类场景。
- **Sonnet**：能力与成本平衡，主力生产模型（当前 Sonnet 5）。
- **Opus**：最强能力，适合复杂推理、长程智能体（当前 Opus 4.x 系列）。
- **Fable / Mythos**：前沿研究档（Fable 5），伴随更严格的红队与治理流程。

不同档位直接决定了基础设施的部署形态：Haiku 偏吞吐与成本，Opus 偏显存与算力。

## 工程挑战

1. **异构算力协同**
   Anthropic 同时使用 AWS Trainium2/3（>100 万芯片、Project Rainier）与 NVIDIA GPU（Colossus 22 万 H100/H200）。两套硬件、两套软件栈（Neuron SDK vs CUDA/Triton）并存，对训练框架、可移植性与故障域管理提出极高要求。

2. **算力需求指数级增长**
   run-rate 收入从 2025 年底约 $9B 增长到 2026 年超过 $30B，$100B/10 年、最高 5GW 的 AWS 合作与 Colossus 租约反映了训练与推理算力的爆炸式需求。

3. **消费级增长冲击可靠性**
   企业与开发者需求加速，叠加 Free/Pro/Max/Team 消费级流量，峰值时段可靠性承压——Anthropic 公开承认这一点，并把扩容作为首要任务。

4. **对齐必须是可重复的工程流程**
   Constitutional AI 不是一次性训练技巧，而是一条可重复、可审计的 SL + RLAIF 流水线，需要把"宪法"版本化、把 AI 反馈管线化。

5. **安全要求前置到模型生命周期**
   RSP 的 if-then 承诺意味着：模型达到某能力阈值前，相应的防护（分类器、权重安全、红队）必须就绪。这把安全从"事后补丁"变成"发布门禁"。

6. **可解释性要能指导决策**
   机制可解释性不只是学术研究，目标是能用它发现危险能力（欺骗、双重用途）并指导对齐——这要求研究产出能进入工程流程。

## 为什么 Anthropic 值得作为案例

- **安全工程化的范本**：把抽象的"负责任扩展"翻译成 ASL 等级、if-then 承诺、Risk Reports、第三方审查等可操作机制。
- **异构算力的极端案例**：同时大规模使用自研芯片（Trainium）与租用 GPU 集群，是研究芯片多元化战略的最佳样本。
- **可解释性开源贡献**：transformer-circuits、dictionary learning 公开了大量可读的研究代码与可复现实验。
- **推理工程的差异化**：prompt caching 的 prefix-hash + 20-block lookback 模型，是学习 KV/prefix cache 工程化的活教材。
- **与 OpenAI 的对照价值**：同样信仰规模化，却走出了"对齐与安全驱动"的独立路线。

## 小结

Anthropic 不是规模最大的实验室，但它最能体现"如何把安全变成可工程化、可治理、可规模化"的命题。下一章将从其核心工程思想入手，建立分析框架。

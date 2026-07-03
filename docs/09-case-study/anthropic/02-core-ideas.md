# 核心思想

Anthropic 的工程体系建立在几条高度自洽的思想上。理解这些思想，比记住具体技术选型更重要——它们决定了为什么 Anthropic 会做出"用 AI 反馈做对齐""把 RSP 写成发布门禁""解剖模型而不是只测模型"这些非常规选择。

## 1. HHH：Helpful、Honest、Harmless

Anthropic 把对齐目标形式化为 **HHH** 三角：

- **Helpful（有用）**：尽力完成用户合理请求。
- **Honest（诚实）**：不捏造、不奉承，对不确定保持坦诚。
- **Harmless（无害）**：拒绝会造成伤害的请求。

三者在边缘会冲突（例如"帮我把这段代码改快"可能涉及优化掉安全检查），对齐的本质就是在这三角之间寻找稳健的权衡。HHH 也是 Constitutional AI 与 RLAIF 中"宪法条款"要量化的对象。

## 2. Constitutional AI：用 AI 反馈替代部分人类反馈

这是 Anthropic 区别于 OpenAI RLHF 路线最核心的思想。传统 RLHF 需要大量人类 pairwise 标注（"哪个回答更好"），昂贵、慢、且难以规模化。Constitutional AI（CAI）提出 **RLAIF（RL from AI Feedback）**：让模型自己对照一组"宪法"原则，对回答做 critique（批评）与 revise（修订），并据此生成偏好数据训练偏好模型，再驱动 RL。

两阶段流程：

1. **SL 阶段（Constitutional SL）**：模型先给出初始回答 → 用宪法原则自我批评 → 修订出更好的回答 → 用这些"修订对"做监督微调。
2. **RLAIF 阶段**：让模型对两个回答按宪法给出偏好（"哪个更符合原则"），训练偏好模型，再用 RL（早期为 PPO）优化策略。

核心洞见：**人类的角色从"逐条标注偏好"升级为"撰写与维护宪法"**——这把对齐从 O(标注量) 的劳动密集工作，变成 O(原则数) 的治理工作。

## 3. 可解释性优先（Interpretability as a First-Class Concern）

大多数实验室通过黑盒评估（benchmark、红队）判断模型是否安全。Anthropic 另辟蹊径，相信**只有理解模型内部在算什么，才能真正信任它**：

- **A Mathematical Framework**：把 Transformer 拆成可组合的运算（attention heads、MLP），发现 induction heads 等可解释回路。
- **Dictionary Learning / 稀疏自编码器**：把混乱的神经元激活分解成数以百万计的、人类可理解的"特征"（如"旧金山""欺骗""安全代码"）。
- **Circuit Tracing**：在单条 prompt 上追踪信息如何在电路中流动，定位"模型为什么这么做"。

这条路线的工程意义是：可解释性产出（特征、电路）未来有望成为**对齐与监控的信号源**——例如直接监测"欺骗特征"是否被激活。

## 4. 安全即工程（Safety as Engineering）

Anthropic 反复强调一个立场：**安全研究不能只在论文里，必须工程化进产品生命周期**。RSP/ASL 就是这一思想的制度载体：

- **if-then 承诺**：如果模型能力达到某阈值（如 CBRN 相关能力），那么必须先满足对应 ASL 等级的防护（分类器、权重安全、红队）。
- **发布门禁**：ASL 不是事后报告，而是"未达标准不许上线/不许训练下一代"的硬约束。
- **可审计**：Risk Reports、第三方审查把内部决策暴露给外部专家。

这一思想直接映射到基础设施：分类器部署、模型权重安全（参考 RAND 的 SL 等级）、红队平台、评估流水线都必须与模型开发同节奏。

## 5. 治理化扩展（Governed Scaling）

"Responsible Scaling"这个名字本身就是核心思想——**扩展不是想扩就扩，而是被治理框架约束的**。Anthropic 把生物安全等级（BSL）的概念移植到 AI：

- ASL-1~5，等级越高防护越严。
- 早期 ASL（2/3）定义清晰，晚期（4/5）因能力未达而暂留开放——RSP v3 的诚实之处在于承认"区域模糊"（zone of ambiguity）并提出更现实的单边承诺。

工程上，这意味着基础设施要能**随 ASL 等级切换防护强度**：从 ASL-2 的常规 moderation，到 ASL-3 的输入/输出分类器与加强权重安全，再到更高等级（可能需要国家级安全合作）。

## 6. 异构算力与芯片多元化

与 OpenAI 高度依赖单一云（Azure）和单一芯片（NVIDIA）不同，Anthropic 显著押注**芯片多元化**：

- **AWS Trainium2/3/4**（Neuron SDK）作为主力训练与推理芯片，Project Rainier >100 万芯片、最高 5GW。
- **NVIDIA GPU**（Colossus 22 万 H100/H200）补充峰值训练算力。
- **三云部署**：Bedrock、Vertex AI、Azure Foundry 同时承载 Claude。

这条路线的动机是成本（自研芯片单位算力成本更低）、供应链韧性（不把鸡蛋放在一个篮子）与议价权，但代价是软件栈复杂度——训练框架必须同时高效跑在 Neuron 与 CUDA 上。

## 7. 成本优化是产品的一部分

Anthropic 把推理成本优化做成一等公民，最典型的就是 **prompt caching**：

- 把重复前缀（系统提示、工具定义、长文档）的 KV cache 复用，读成本仅为 base input 的 10%。
- 用 prefix hash + 20-block lookback 精确定位可复用前缀，支持 5 分钟 / 1 小时两档 TTL、最多 4 个断点、pre-warm 预热。
- cache 命中不计入限流额度，鼓励开发者优化。

配合 Batch API（离线批处理折扣）、Haiku 档位分流，Anthropic 展示了"把成本优化做成可组合、可计量的产品能力"的工程审美。

## 小结

Anthropic 的核心思想可以概括为：**用 HHH 定义目标，用宪法对齐实现目标，用可解释性理解目标，用 RSP/ASL 治理达成目标的过程，用异构算力与 prompt caching 让这一切在经济上可持续**。下一章把这些思想映射到具体架构。

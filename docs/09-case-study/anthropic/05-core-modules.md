# 核心模块

Anthropic 的基础设施由若干核心模块组成。与 OpenAI 类似，它覆盖数据→训练→对齐→推理→产品全链路；不同的是，它额外把"可解释性"和"治理（RSP/ASL）"作为独立模块纳入主流程。

## 1. 异构算力与集群管理

- **Trainium 集群（Project Rainier）**：>100 万 Trainium2 芯片，向 Trainium3/4 演进（Trainium3 约 2x 算力、144GB HBM3e）；2026-04 宣布合作扩至 $100B/10 年、最高 5GW，年底 Trainium2+3 合计接近 1GW。Neuron SDK 提供编译、运行时与分布式训练。
- **GPU 集群（Colossus 1）**：22 万 H100/H200、300+MW，2026-05 起独家接入，作为峰值训练与 Claude Code 扩容补充。
- **调度与容错**：长周期训练任务的调度、抢占、checkpoint 与自动恢复；在异构硬件上统一作业抽象。
- **电力与散热**：5GW 级电力供给与液冷是规模化的硬约束。

## 2. 数据平台

- **采集与清洗**：网页、代码、授权与合成数据；去重、质量评分、安全/毒性过滤、PII 处理。
- **版本与血缘**：数据版本、清洗规则与模型表现的可追溯关系。
- **合成数据**：为对齐训练与红队评估定向生成样本。

## 3. 训练框架

- **异构执行抽象**：同时高效跑在 Neuron 与 CUDA 上的分布式框架。
- **并行策略**：数据 / 张量 / 流水线 / 专家并行；all-reduce 与 all-to-all 通信优化。
- **混合精度**：低精度训练与损失缩放。
- **Checkpoint**：高频、可恢复、可校验的 checkpoint 管理。
- **实验追踪**：超参、配置、评估结果的可复现记录。

## 4. 对齐管线（Constitutional AI）

这是 Anthropic 的招牌模块：

- **Constitution Store**：可版本化、可溯源的原则集合（"宪法"）。
- **Critique Generator**：按原则对模型回答生成批评。
- **Revision Engine**：基于批评生成修订回答，产出监督数据（SL 阶段）。
- **Preference Model Trainer**：用 AI 偏好训练偏好模型（RLAIF 阶段）。
- **RL Optimizer**：以偏好模型为奖励做策略优化。

> 与 OpenAI 的 RLHF 管线相比，核心差异在"偏好来源"：Anthropic 用 AI + 宪法，OpenAI 用人类标注。

## 5. 可解释性工具链

- **Sparse Autoencoder（SAE）/ Dictionary Learning**：把神经元激活分解为可解释特征；开源研究代码见 transformer-circuits。
- **Circuit Analysis / Circuit Tracing**：在单 prompt 上追踪信息流动，定位回路级解释；`circuit-tracer` 库 2025-05 开源。
- **Natural Language Autoencoder（NLA，2026-05）**：把激活直接翻译成自然语言（解释方差 0.6–0.8），支撑"内部独白"式运行时监控；预训练 NLA 对已开源（Qwen2.5 / Gemma-3 / Llama-3.3）。
- **Feature Dashboard**：对单个特征展示最大化激活样本，人工或自动标注其语义。
- **Feature Steering**（研究性）：通过调控特征激活来实验性引导模型行为。

> 工程愿景：可解释性产出（如"欺骗特征""危险能力特征"）未来可作为安全监控与对齐的信号源。

## 6. 模型仓库与发布

- **Model Registry**：每个模型版本的唯一标识、权重、tokenizer、配置、宪法版本、ASL 等级。
- **签名与溯源**：确保模型 artifact 可信、可审计。
- **三云灰度**：API → Bedrock / Vertex / Foundry，按 tier、区域、流量比例放量。

## 7. 推理引擎、Prompt Cache 与智能体运行时

- **推理引擎**：continuous batching、KV cache 分页管理、长上下文（1M token）。
- **Prompt Cache**：
  - prefix hash + 20-block lookback 命中判定（tool_use/tool_result 连续块计为一个位置）；
  - 自动 / 显式断点（最多 4 个，混用自动缓存时占用一个名额）；
  - 5m / 1h 双 TTL（TTL 自请求开始计时）；
  - workspace 级隔离（Claude API / Claude Platform on AWS / Foundry）或 org 级（Bedrock / Google Cloud）；
  - pre-warm（`max_tokens=0`，2026 起为官方正式用法）；
  - 按模型分档的最小可缓存长度（512–4096 token）与缓存读倍率（0.1x / 0.05x / 0.025x）；
  - 新型号支持 mid-conversation system 消息与 `inline-tools-2026-09-15` 中途改工具而不破坏缓存。
- **Extended Thinking**：thinking budget、thinking block 保留与缓存复用。
- **Computer / Tool Use**：工具执行、沙箱、权限、多步循环。
- **Managed Agents（2026-04 public beta）**：托管智能体运行时——沙箱执行、OAuth 凭据管理、会话 checkpoint、审计追踪；2026-05 新增 Dreaming（空闲时复盘会话日志自我改进）、Outcomes（评估智能体按 rubric 打分）、多智能体编排（主 agent 派单 + 并行子 agent + 共享文件系统）。计费按会话时长（约 $0.08/会话小时）+ token。

## 8. API Gateway 与平台层

- **认证授权**：`x-api-key`、organization、workspace。
- **限流配额**：按 tier/模型/token/并发；cache 命中豁免限流。
- **计费**：输入/输出/cache 写/cache 读分别计价；支持 Batch API 折扣与 data residency 调节。
- **模型路由**：按模型名、区域负载、容量调度。
- **可观测**：延迟、错误率、cache 命中率、token 用量、成本。

## 9. 安全治理模块（RSP / CB 阈值）

- **Capability Eval Pipeline**：CBRN、网络、说服、自主性等前沿能力评估；RSP v3.4 起用 CB-1/CB-2 阈值（功能替代稀缺专家）与"AI 研发自动化"阈值（AI 可归因的进步速度翻倍）表述。
- **治理演进**：RSP v3.0（2026-02）拆分公司承诺、行业建议（Frontier Safety Roadmap）与定期 Risk Report；2026-08 Risk Report 披露当前模型接近 CB-2 边界。
- **Classifier 服务**：输入/输出分类器，阻断 CBRN 相关有害内容；Fable 5 系列在 API 入口内置分类器，把可疑请求（网络/生化/蒸馏）路由到 Opus 4.8 处理（<5% 会话），Mythos 5 则为经审查用户关闭对应分类器（Project Glasswing）。
- **运行时监控（新）**：自然语言自编码器（NLA）把模型内部激活翻译成可读文本，用于监听推理模型的内部独白，作为欺骗/作弊行为的检测信号。
- **Red Team Platform**：自动化 + 人工红队，多语言、多模态；Fable 5 分类器经外部漏洞赏金测试（1000+ 小时未发现通用越狱）。
- **Weight Security**：参考 RAND SL 等级的模型权重保护。
- **Risk Report / 第三方审查**：每 3–6 个月发布的能力-威胁-缓解-残余风险报告。

## 10. 产品与多云分发

- **Claude API**：直连官方平台，支持最新特性（automatic caching、mid-conversation system messages、inline tools 等）。
- **Amazon Bedrock**：企业级托管，Org 级 cache 隔离；旧版 Bedrock（Opus 4.6 及更早）不支持 automatic caching，需用显式断点。
- **Google Cloud Vertex AI**：托管 Claude，Org 级 cache 隔离。
- **Microsoft Azure Foundry**：托管 Claude，支持 automatic caching 与 workspace 级隔离。
- **Claude Platform on AWS**：同账户、同控制、同计费的原生体验，workspace 级 cache 隔离。

## 模块协作示例

```text
新数据进入数据平台
  → 清洗过滤生成训练集
  → 异构训练框架在 Trainium/GPU 上预训练
  → Constitutional SL 用宪法生成修订监督数据
  → RLAIF 训练偏好模型并做 RL
  → 可解释性工具链分析特征/电路（安全信号）
  → Capability Eval 判定 ASL 等级
  → ASL 防护（分类器/权重安全）就绪后发布
  → 推理引擎 + Prompt Cache 服务在线请求
  → Extended Thinking / Tool Use 支撑智能体
  → 日志、usage、安全事件回流评估与对齐
```

## 小结

Anthropic 的核心模块覆盖了从数据到产品的全链路，并额外把 **可解释性**（已进展到 NLA 运行时监控）与 **RSP/CB 阈值治理** 立为主流程模块；2026 年又补上 **Managed Agents** 这一智能体运行时层。下一章通过开源项目与公开资料，进一步分析这些模块的工程实现。

# 核心模块

Anthropic 的基础设施由若干核心模块组成。与 OpenAI 类似，它覆盖数据→训练→对齐→推理→产品全链路；不同的是，它额外把"可解释性"和"治理（RSP/ASL）"作为独立模块纳入主流程。

## 1. 异构算力与集群管理

- **Trainium 集群（Project Rainier）**：>100 万 Trainium2 芯片，向 Trainium3/4 演进；Neuron SDK 提供编译、运行时与分布式训练。
- **GPU 集群（Colossus）**：22 万 H100/H200，峰值训练补充。
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
- **Feature Dashboard**：对单个特征展示最大化激活样本，人工或自动标注其语义。
- **Circuit Analysis / Circuit Tracing**：在单 prompt 上追踪信息流动，定位回路级解释。
- **Feature Steering**（研究性）：通过调控特征激活来实验性引导模型行为。

> 工程愿景：可解释性产出（如"欺骗特征""危险能力特征"）未来可作为安全监控与对齐的信号源。

## 6. 模型仓库与发布

- **Model Registry**：每个模型版本的唯一标识、权重、tokenizer、配置、宪法版本、ASL 等级。
- **签名与溯源**：确保模型 artifact 可信、可审计。
- **三云灰度**：API → Bedrock / Vertex / Foundry，按 tier、区域、流量比例放量。

## 7. 推理引擎与 Prompt Cache

- **推理引擎**：continuous batching、KV cache 分页管理、长上下文。
- **Prompt Cache**：
  - prefix hash + 20-block lookback 命中判定；
  - 自动 / 显式断点（最多 4 个）；
  - 5m / 1h 双 TTL；
  - workspace 级隔离（Claude API / Foundry）或 org 级（Bedrock / Google Cloud）；
  - pre-warm（`max_tokens=0`）。
- **Extended Thinking**：thinking budget、thinking block 保留与缓存复用。
- **Computer / Tool Use**：工具执行、沙箱、权限、多步循环。

## 8. API Gateway 与平台层

- **认证授权**：`x-api-key`、organization、workspace。
- **限流配额**：按 tier/模型/token/并发；cache 命中豁免限流。
- **计费**：输入/输出/cache 写/cache 读分别计价；支持 Batch API 折扣与 data residency 调节。
- **模型路由**：按模型名、区域负载、容量调度。
- **可观测**：延迟、错误率、cache 命中率、token 用量、成本。

## 9. 安全治理模块（RSP / ASL）

- **Capability Eval Pipeline**：CBRN、网络、说服、自主性等前沿能力评估。
- **ASL Policy Engine**：根据评估判定 ASL 等级，作为训练/发布的硬门禁。
- **Classifier 服务**：输入/输出分类器（ASL-3 强化版），阻断 CBRN 相关有害内容。
- **Red Team Platform**：自动化 + 人工红队，多语言、多模态。
- **Weight Security**：参考 RAND SL 等级的模型权重保护。
- **Risk Report / 第三方审查**：每 3–6 个月发布的能力-威胁-缓解-残余风险报告。

## 10. 产品与多云分发

- **Claude API**：直连官方平台，支持最新特性（automatic caching、Foundry 上的 workspace 隔离等）。
- **Amazon Bedrock**：企业级托管，Org 级 cache 隔离。
- **Google Cloud Vertex AI**：托管 Claude。
- **Microsoft Azure Foundry**：托管 Claude，支持 automatic caching 与 workspace 隔离。
- **Claude Platform on AWS**：同账户、同控制、同计费的原生体验。

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

Anthropic 的核心模块覆盖了从数据到产品的全链路，并额外把 **可解释性** 与 **RSP/ASL 治理** 立为主流程模块。下一章通过开源项目与公开资料，进一步分析这些模块的工程实现。

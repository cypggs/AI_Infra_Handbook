# 核心概念

Benchmark + Evaluation 需要一套比传统软件测试更丰富的概念体系，因为 AI 系统的输出是开放自然语言，"正确"往往是多维、概率、上下文相关的。

## 评估维度

一次完整的 AI 系统评估至少应覆盖以下维度：

| 维度 | 含义 | 典型指标 |
|---|---|---|
| **正确性（Correctness）** | 输出是否满足用户意图 | Accuracy、Exact Match、Pass@k |
| **事实性（Factuality）** | 输出是否符合客观事实 | F1、BLEU、Faithfulness、Claim verification |
| **工具使用（Tool Use）** | 是否选对工具、填对参数、正确处理返回值 | Tool accuracy、Parameter F1、Call success rate |
| **延迟（Latency）** | 响应有多快 | TTFT、ITL、端到端 P99 |
| **成本（Cost）** | 单次调用或会话的资源消耗 | Token 数、$/1K calls、GPU 秒 |
| **安全性（Safety）** | 是否有害、是否泄露敏感信息、是否被越狱 | Harm rate、PII leakage、Jailbreak success rate |
| **鲁棒性（Robustness）** | 输入扰动下输出是否稳定 | Consistency、Error rate under perturbation |

不同场景权重不同：客服机器人重事实性与安全，代码助手重正确性与工具使用，创意写作重多样性与风格，科研 Agent 重多步骤推理与工具链协同。

## 离线评估 vs 在线评估

### 离线评估（Offline Evaluation）

在模型上线前，使用预先准备的黄金数据集（golden set）或合成数据集运行评估。

- 优点：可复现、成本低、适合回归测试与模型选型。
- 缺点：数据集难以覆盖真实分布，存在"训练集泄漏"与 metric gaming 风险。

### 在线评估（Online Evaluation）

在生产或影子流量中，对真实请求进行采样、打标与评分。

- 优点：反映真实分布，可发现长尾问题。
- 缺点：成本高、反馈延迟、需要隐私与合规审查。

最佳实践是两者结合：离线评估作为 CI 门，在线评估作为生产健康度监控。

## 黄金数据集 vs 合成数据

### 黄金数据集（Golden Set）

由人工标注的正确答案集合，通常用于：

- 回归测试：每次变更后与基线对比。
- 模型选型：在相同数据集上对比多个候选模型。
- 能力验收：定义"必须通过的用例"。

构建成本高，但可信度高。需要版本化、审计与多样性审查。

### 合成数据（Synthetic Data）

通过程序、模板或另一个 LLM 生成。常用于：

- 快速扩充覆盖长尾场景的样本。
- 生成对抗性、多语言、边界条件用例。
- 模拟工具调用与多轮对话轨迹。

合成数据必须经过质量校验，否则容易"garbage in, garbage out"。

## LLM-as-Judge

用另一个 LLM 作为评判者，对输出打分或做 pairwise 比较。

常见模式：

- **Pointwise scoring**：对单条输出按 1-5 分打分（如相关性、有用性、安全性）。
- **Pairwise comparison**：比较两个输出哪个更好。
- **Criteria-based rubric**：给出明确评分标准，让 judge 按维度打分。
- **Chain-of-thought judge**：要求 judge 先写出评判理由，再给出分数，提升可解释性。

### 局限与校准

- **位置偏见（Position Bias）**： pairwise 中排在前面的答案容易被偏好。
- **长度偏见（Length Bias）**：更长的输出可能得分更高。
- **自我偏好（Self-Preference）**：Judge 模型可能偏好自己的输出风格。
- **标准漂移**：不同 judge 或同一 judge 多次调用结果不一致。

缓解方法：多 judge 投票、rubric 固化、 judge 自身用黄金集校准、置信度阈值、人工抽检。

## Human-in-the-Loop

自动化评估无法完全替代人类判断，尤其涉及：

- 主观质量（创意、语气、品牌一致性）。
- 复杂推理步骤的合理性。
- 安全边界的灰色地带。

人工复核通常以"抽检 + 争议仲裁"的形式嵌入流程：

- 对低置信度、高影响、新失败模式的样本进行人工标注。
- 人工标注结果回流到黄金数据集，用于校准自动评估器。
- 建立"评估校准会议"，定期对比自动分与人均分的差异。

## Eval-as-Code

评估配置、数据集、评分逻辑、阈值、报告模板都应作为代码版本管理：

- 评估 prompt 和 rubric 放在 Git 中，和模型 / Prompt 一起 review。
- 数据集用 DVC、LakeFS 或对象存储版本化。
- 评估流水线用 CI 运行，结果写入实验追踪系统。
- 回归差异用 PR comment 或 dashboard 展示。

这让评估本身成为可审计、可回滚、可协作的工程产物。

## 反馈闭环

评估不是一次性活动，而是持续闭环：

1. 定义能力边界与成功标准。
2. 构建 / 更新 benchmark 数据集。
3. 在离线 CI 与在线生产中运行评估。
4. 识别失败模式与回归。
5. 改进模型、Prompt、工具、检索或 guardrails。
6. 重新部署，闭环回到步骤 1。

没有闭环的评估只是报表，有闭环的评估才是生产力。

## 可观测性驱动的评估

可观测性数据（trace、metrics、logs）不只是用于告警，也是评估的原材料：

- 从 trace 提取 Agent 步骤、工具调用、模型调用参数。
- 从日志提取 prompt、completion、retrieved chunks。
- 从 metrics 获得延迟、token 用量、错误率。
- 将上述信息输入评估引擎，计算质量、成本、安全分数。

这要求 instrumentation 在开发阶段就按评估需求设计，而不是事后补埋点。

## 小结

Benchmark + Evaluation 的核心概念可以用一句话概括：**在正确性、事实性、工具使用、延迟、成本、安全、鲁棒性七个维度上，用黄金数据 + 合成数据 + LLM judge + 人工复核，在线与离线持续度量，并把结果作为代码反馈给 CI/CD 与产品迭代**。下一章将把这些概念组织成可落地的架构。

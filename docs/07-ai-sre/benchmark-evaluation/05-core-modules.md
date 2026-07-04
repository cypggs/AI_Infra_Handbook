# 核心模块

一个完整的 Benchmark + Evaluation 平台由多个专业化模块组成。本章拆解每个模块的职责、输入输出、设计要点与常见实现选择。

## 1. Benchmark Registry（基准注册中心）

**职责**：集中管理数据集、评估任务、基线结果与血缘关系。

**核心功能**：

- 数据集版本管理（黄金数据、合成数据、采样数据）。
- 评估任务编排：选择数据集、evaluator、阈值、触发方式。
- 基线管理：记录每个版本 / 每个 Prompt 的基准分数。
- 血缘追踪：数据集 ← 标注人 / 生成脚本；评估结果 ← 模型 / Prompt / 工具版本。

**设计要点**：

- 数据集元数据与二进制数据分离，二进制用对象存储，元数据用数据库。
- 支持按能力、按失败模式、按难度、按合规等级打标签。
- 提供 API / CLI 供 CI 与评估引擎查询。

## 2. Prompt / Response Evaluator（Prompt 与响应评估器）

**职责**：对单条 prompt-response pair 打分，是最常用的 evaluator。

**常见实现**：

- **规则 evaluator**：正则、JSON Schema、关键词包含、长度限制。
- **Embedding evaluator**：用向量相似度判断语义接近程度。
- **LLM-as-judge**：让 judge 模型按 rubric 打分。
- **参考匹配 evaluator**：与 golden answer 做 BLEU / ROUGE / F1 / Exact Match。

**设计要点**：

- evaluator 结果应包含分数、置信度、理由、耗时、成本。
- 对 judge LLM 做温度、模型、prompt 版本管理。
- 支持组合 evaluator：先用规则快速过滤，再用 LLM judge 复核。

## 3. Trace Store（Trace 存储与查询）

**职责**：存储 Agent / App 产生的完整调用链，支撑基于 trace 的评估。

**核心能力**：

- 按 trace_id、session_id、模型版本、时间范围查询。
- 支持 span 级别的字段检索（如 tool name、latency、token usage）。
- 导出评估所需的结构化数据（prompt、completion、tool I/O、chunks）。

**设计要点**：

- 与 OpenTelemetry Collector 对接，统一接收 trace。
- 长 trace 需要分页或流式查询，避免单次返回过大。
- 敏感字段（prompt、completion）需要分级脱敏与访问控制。

## 4. Metrics Pipeline（指标流水线）

**职责**：把质量、成本、延迟类评估结果变成可聚合、可告警的指标。

**典型指标**：

- `eval_correctness_score`、 `eval_hallucination_rate`、 `eval_tool_accuracy`
- `eval_latency_p95`、 `eval_cost_per_1k`
- `eval_judge_cost`、 `eval_dataset_coverage`

**设计要点**：

- 指标应支持按模型版本、Prompt 版本、能力标签、失败模式切片。
- 与 Prometheus / Grafana 或云监控集成，实现 burn-rate 告警。
- 区分"系统指标"（如 evaluator 自身失败率）和"业务指标"（如幻觉率）。

## 5. Experiment Tracking（实验追踪）

**职责**：记录每次评估实验的完整上下文，支持横向对比与复现。

**记录内容**：

- 被测系统：模型、Prompt、工具、检索索引版本。
- 评估配置：数据集、evaluator、judge 模型、阈值。
- 环境信息：依赖版本、随机种子、硬件。
- 结果：指标、样本明细、失败案例、可视化。

**常见工具**：MLflow、Weights & Biases、LangSmith、Phoenix、自研平台。

**设计要点**：

- 实验 ID 与 CI pipeline ID、Git commit SHA 关联。
- 支持参数化实验（grid search、Prompt A/B）。
- 失败实验也要记录，避免重复踩坑。

## 6. CI Gate（CI 质量门）

**职责**：在代码 / Prompt / 模型变更进入生产前执行评估，阻止 regression。

**典型规则**：

- 总体正确率不得低于基线 1%。
- 安全评估必须 100% 通过。
- 关键能力集（如多步推理）不得低于指定阈值。
- 延迟 / 成本不得超过预算。

**设计要点**：

- 区分"硬门"（直接 block）与"软门"（告警 + 人工审批）。
- PR 阶段用轻量评估，发布阶段跑完整 benchmark。
- 评估结果以 PR comment、dashboard、邮件等形式反馈。

## 7. Human Review Queue（人工复核队列）

**职责**：把需要人类判断的样本推送给审核员，并管理审核结果。

**入队触发条件**：

- 自动评估置信度低于阈值。
- 涉及安全、合规、医疗、金融等高风险领域。
- 新出现的失败模式或异常分布。
- 用户投诉、差评、举报。

**出队处理**：

- 审核员按维度打分、写备注、选择失败类型。
- 结果写入黄金数据集或 judge 校准集。
- 触发模型 / Prompt / guardrails 修复工单。

**设计要点**：

- 队列需要优先级、分配、SLA、审计日志。
- 审核界面要展示完整上下文（prompt、trace、自动评分理由）。
- 定期统计审核员之间的一致性与审核员-自动评估的一致性。

## 8. Report Generator（报告生成器）

**职责**：把评估结果转化为面向不同受众的报告。

**报告类型**：

- **模型选型报告**：对比多个候选模型在 benchmark 上的表现。
- **发布验收报告**：证明新版本满足上线标准。
- **安全审计报告**：展示有害输出率、越狱测试、PII 测试结果。
- **事故复盘报告**：定位 regression 根因与修复效果。

**设计要点**：

- 报告应包含执行摘要、关键指标、趋势图、失败案例、附录（实验元数据）。
- 支持导出 PDF / Markdown / HTML / API JSON。
- 报告模板可配置，适应不同团队与合规要求。

## 9. Cost / Latency Budget（成本 / 延迟预算）

**职责**：把评估过程本身的资源消耗与业务指标一起管理。

**管理对象**：

- **单次评估成本**：judge 模型调用、embedding、外部 API 费用。
- **在线评估采样率**：在成本与覆盖率之间权衡。
- **延迟预算**：评估不能拖慢 CI 或在线响应。
- **业务成本**：被测系统生成答案的成本、工具调用成本。

**设计要点**：

- 为每个 evaluator 估算并记录成本。
- 支持按数据集大小、采样率、judge 模型档次做预算控制。
- 把成本 / 延迟指标与质量指标一起做帕累托优化。

## 模块间协作示例

一次典型的 CI 评估流程：

1. CI 触发，向 Benchmark Registry 请求本次任务的数据集与配置。
2. Evaluation Engine 调用被测系统，生成 response 与 trace。
3. Trace Store 保存完整 trace，Metrics Pipeline 计算延迟与成本。
4. Prompt / Response Evaluator 对输出打分。
5. Scoring & Aggregation 汇总结果，Experiment Tracking 记录实验。
6. CI Gate 对比基线，判断是否通过。
7. 未通过则进入 Human Review Queue 与根因分析。
8. Report Generator 输出发布验收报告。

## 小结

Benchmark + Evaluation 平台的核心模块包括：基准注册中心、Prompt/Response 评估器、Trace 存储、指标流水线、实验追踪、CI 质量门、人工复核队列、报告生成器、成本 / 延迟预算。模块之间通过统一的数据模型与 API 协作，才能把评估从脚本升级为平台。下一章对比主流开源与商业工具的设计理念。

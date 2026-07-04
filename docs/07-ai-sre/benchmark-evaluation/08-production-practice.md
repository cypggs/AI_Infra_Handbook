# 企业生产实践

把 Benchmark + Evaluation 从 Demo 推广到生产环境，需要在 CI 集成、在线评估、A/B 测试、成本预算、失败模式归因等方面建立工程化流程。本章分享常见落地模式与真实案例片段。

## CI 集成：把评估变成代码门禁

### 评估即 CI 步骤

在 AI 应用的 CI pipeline 中，除了单元测试、类型检查、lint，还应增加评估步骤：

```yaml
# .github/workflows/eval.yml
jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run offline benchmark
        run: |
          python -m eval.run \
            --dataset benchmark/v2.3 \
            --model $MODEL_VERSION \
            --baseline main \
            --output eval-report.json
      - name: Check regression gate
        run: |
          python -m eval.gate \
            --report eval-report.json \
            --rules .eval/gates.yaml
```

### 分层评估策略

| 阶段 | 数据集规模 | 评估重点 | 耗时目标 |
|---|---|---|---|
| PR 预检 | 50-200 条 | 快速回归 + 安全红线 | < 5 分钟 |
| 合并前 | 500-2000 条 | 核心能力 + 失败模式 | < 30 分钟 |
| 发布前 | 全量 benchmark | 全维度 + 成本 / 延迟预算 | 1-4 小时 |

### 门禁规则示例

```yaml
# .eval/gates.yaml
hard_gates:
  - metric: safety.pass_rate
    op: ge
    value: 1.0
  - metric: overall.score
    op: ge
    value: 0.85
soft_gates:
  - metric: coding.score
    op: ge
    value: 0.90
    action: notify
regression:
  max_drop: 0.02
  capabilities: [math, coding, safety]
```

## 影子评估：生产流量的安全对比

影子评估让新版本与旧版本并行接收真实流量，但新版本不返回给用户：

```text
User Request
    ├─> Production Model  →  Response to user
    └─> Shadow Model      →  Evaluated, discarded
```

**适用场景**：

- 模型版本升级前的回归验证。
- Prompt 大改前的风险摸排。
- 成本与延迟的真实环境测算。

**注意事项**：

- 影子调用会 doubled 成本，需要采样或按用户比例开启。
- 必须严格隔离，避免影子输出污染真实用户。
- 评估指标应包含用户实际反馈（如 thumbs up/down）与影子输出的对比。

## A/B 评估：用真实用户反馈校准指标

A/B 测试把用户随机分配到不同版本，通过真实业务指标验证评估结果：

- **在线指标**：用户满意度、任务完成率、转化率、投诉率。
- **离线指标**：正确性、事实性、安全分数。
- **关联分析**：离线指标提升是否真正带来在线指标提升？

常见发现：

- 离线分数高的版本，用户满意度不一定高（可能输出冗长、语气不友好）。
- 离线安全全过的版本，仍可能被创造性 prompt 绕过。

因此 A/B 评估是校准离线 benchmark 与真实业务价值的关键手段。

## 在线反馈：把用户信号变成评估数据

生产环境中，用户本身就是最权威的评估者之一：

- **显式反馈**：点赞 / 点踩、评分、举报、修改建议。
- **隐式反馈**：是否复制答案、是否继续追问、任务是否完成、会话是否中断。
- **下游结果**：客服机器人是否减少了人工介入？代码助手是否减少了 bug？

这些信号应被：

- 写入 Telemetry Store 与评估数据集。
- 用于训练或校准 LLM-as-judge。
- 触发人工复核与失败模式分析。

## 与 Guardrails 联动

评估结果应直接反馈给 guardrails 策略：

- 安全评估发现新越狱模式 → 更新输入过滤器与拒绝策略。
- 事实性评估发现某类问题容易幻觉 → 增加检索要求或降低 temperature。
- 工具使用评估发现参数错误 → 增强工具描述与 schema 校验。

Guardrails 与评估形成"防御 + 度量"双轮：guardrails 拦截已知风险，评估发现未知风险。

## 成本 / 延迟预算

评估本身消耗资源，被评估的系统也消耗资源。企业落地时必须建立预算：

| 预算项 | 管理方法 |
|---|---|
| Judge 模型调用费 | 按数据集大小与 judge 模型档次估算；高价值样本才用强 judge |
| 在线评估采样率 | 核心能力 100%，长尾能力 1%-10%，安全相关 100% |
| 单次 CI 评估耗时 | 超时自动失败，避免阻塞发布 |
| 影子流量成本 | 按流量百分比与模型单价做月度预算 |
| 业务调用成本 | 把 token / cost 指标纳入 SLO，防止 Agent 失控 |

## 失败模式归因

生产事故或 regression 发生后，评估系统需要回答：

1. **哪个模块出了问题？** 模型、Prompt、工具、检索、guardrails。
2. **哪些输入受影响？** 按能力、主题、语言、长度、用户群分组。
3. **影响范围多大？** 时间窗口、请求量、用户量、业务损失。
4. **根因是什么？** 模型版本变更、检索索引更新、工具依赖故障、Prompt 被压缩。

归因手段：

- 端到端失败样本的 trace 回放。
- 模块级单独评估（只换模型、只换 Prompt、只换检索）。
- 控制变量实验（hold-out 数据集 + ablation study）。

## 真实案例片段

### 案例 1：客服机器人升级导致退款政策回答回归

某团队在升级模型后发现"退款政策"相关问题的用户满意度下降。通过 trace-based 评估定位：新模型对长上下文中的细则位置不敏感，导致引用了过时的政策片段。回退模型并增加 retrieval 策略后恢复。

### 案例 2：Agent 工具调用陷入循环

某数据分析 Agent 在特定表格结构下反复调用 `get_column_types`，每次返回相同结果。在线评估的"工具循环检测"evaluator 发现后，团队增加了工具调用去重与最大步数限制。

### 案例 3：Prompt 压缩后安全边界下降

为降低成本，团队对 system prompt 做了压缩。离线安全 benchmark 通过，但在线红队评估发现越狱成功率上升。归因后发现压缩去掉了关键安全指令，重新保留安全相关的显式约束。

## 组织落地 checklist

- [ ] 明确各能力的 SLO 与 Error Budget。
- [ ] 建立黄金数据集与合成数据生成规范。
- [ ] 统一 instrumentation 标准（建议 OpenTelemetry GenAI）。
- [ ] 在 CI 中接入分层评估门禁。
- [ ] 对生产流量启用影子评估与在线采样评估。
- [ ] 建立人工复核队列与 judge 校准机制。
- [ ] 把评估结果接入 guardrails、CI、A/B 平台与事故响应流程。
- [ ] 定期复盘：离线指标是否与在线业务指标一致。

## 小结

生产环境中的 Benchmark + Evaluation 不仅是技术问题，更是流程与组织问题。只有把评估嵌入 CI、影子流量、A/B 测试、guardrails 与事故响应，才能真正实现"可评估的 AI"。下一章总结设计评估体系时的最佳实践与常见陷阱。

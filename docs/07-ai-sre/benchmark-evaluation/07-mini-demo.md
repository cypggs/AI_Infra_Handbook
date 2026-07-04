# Mini Demo

本章配套的 Mini Demo 位于 `docs/07-ai-sre/benchmark-evaluation/mini-demo/`，用纯标准库 Python 实现了一个**可评估 Agent** 的最小闭环：

- 确定性 ReAct Agent（无需外部 LLM API）
- 进程内 Trace / Span 记录
- 多维度 Evaluator（正确性、工具调用、延迟、成本、鲁棒性）
- Benchmark 数据集与聚合报告

所有代码 CPU 可运行，测试无需网络。

## 目录结构

```text
docs/07-ai-sre/benchmark-evaluation/mini-demo/
├── README.md
├── pyproject.toml
├── benchmark_evaluation_mini/
│   ├── __init__.py
│   ├── agent.py          # ReAct Agent：thought → tool call → observation
│   ├── environment.py    # Mock 工具（search / calculator）与故障注入
│   ├── llm_stub.py       # 基于规则的确定性 LLM 响应
│   ├── tracer.py         # 树形 Span / Event 记录
│   ├── evaluators.py     # 正确性、工具调用、延迟、成本、鲁棒性评估器
│   ├── benchmark.py      # Benchmark 数据集、运行器、报告生成
│   └── demo.py           # 一键运行入口
└── tests/
    └── test_all.py
```

## 运行方式

```bash
cd docs/07-ai-sre/benchmark-evaluation/mini-demo
pip install -e ".[dev]"
pytest tests/ -v
python -m benchmark_evaluation_mini.demo
```

## 核心设计

### 1. Agent 与 Trace

`Agent.run(task)` 执行 ReAct 循环，每一步都被记录为 Span：

```python
with tracer.span("llm.complete", step=step):
    tracer.advance(2)
    raw, tokens = llm.complete(task, history, tools)
    tracer.add_event("llm.response", text=raw, tokens=tokens)
```

Tool 调用同样是一个 Span，成功或失败都会以 Event 形式写入：

```python
with tracer.span("tool.call", tool=action.tool, input=action.input):
    try:
        output = tools.execute(action.tool, action.input, scenario)
        tracer.add_event("tool.result", output=output)
    except ToolError as exc:
        tracer.add_event("tool.error", error=str(exc))
```

### 2. 确定性 LLM Stub

`StubLLM` 不调用远程模型，而是根据任务关键词返回固定 ReAct 输出：

- 数学任务 → `Action: calculator(...)` → `Final Answer: 42`
- 事实任务 → `Action: search(...)` → `Final Answer: William Shakespeare`
- 多步任务 → `search` 取人口 → `calculator` 做除法 → 最终答案
- 故障任务 → 工具失败一次后仍给出正确答案，用于验证鲁棒性

### 3. Evaluators

每个 evaluator 只读取 `sample`、`answer` 和 `trace`，与 Agent 实现解耦：

| Evaluator | 输入 | 通过条件 |
|---|---|---|
| `CorrectnessEvaluator` | 参考答案 ∈ 最终答案 | 字符串包含 |
| `ToolUseEvaluator` | trace 中的 tool 序列 | 与期望序列一致 |
| `LatencyEvaluator` | trace 总耗时 | ≤ `max_latency` |
| `CostEvaluator` | trace 中累计 token 估计 | ≤ `max_cost` |
| `RobustnessEvaluator` | 是否注入故障 + 是否仍正确 | 故障后仍能正确回答 |

### 4. Benchmark 运行器

`Benchmark.run(dataset)` 为每个 sample 创建独立的 Agent、Tracer 和 ToolRegistry，避免样本间状态污染，然后聚合所有 evaluator 得分。

```python
results = run_builtin()
print(Benchmark.report(results))
```

## 示例输出

```text
# Benchmark Report

| Sample | Task | Answer | correctness | tool_use | latency | cost | robustness |
|---|---|---|---|---|---|---|---|
| math_1 | What is 15 + 27? | 42 | ✅ 1.00 | ✅ 1.00 | ✅ 8.00 | ✅ 0.00 | ✅ 1.00 |
| fact_1 | Who wrote Romeo and Juliet? | William Shakespeare | ✅ 1.00 | ✅ 1.00 | ✅ 8.00 | ✅ 0.00 | ✅ 1.00 |
| multi_1 | What is the population of Paris divided by 2? | 1050000 | ✅ 1.00 | ✅ 1.00 | ✅ 13.00 | ✅ 0.00 | ✅ 1.00 |
| fault_1 | Fault injection: calculate 20 + 22 despite a failing calculator. | 42 | ✅ 1.00 | ✅ 1.00 | ✅ 8.00 | ✅ 0.00 | ✅ 1.00 |

## Aggregate
- **correctness**: 4/4 passed (100.0%)
- **tool_use**: 4/4 passed (100.0%)
- **latency**: 4/4 passed (100.0%)
- **cost**: 4/4 passed (100.0%)
- **robustness**: 4/4 passed (100.0%)
```

## 测试

`tests/test_all.py` 覆盖：

- LLM 响应解析（action / final answer）
- Mock 工具执行与故障注入
- Agent 在数学、事实、多步任务上的行为
- 每个 evaluator 的评分逻辑
- Benchmark 聚合与报告生成
- Demo 入口无异常运行

运行结果示例：

```text
15 passed in 0.01s
```

## 与真实框架的差异

| 方面 | Mini Demo | 真实框架（LangSmith / Phoenix / Ragas / DeepEval） |
|---|---|---|
| 模型 | 规则 stub | 真实 LLM / Agent / RAG |
| Trace | 内存树形 Span | OpenTelemetry / 原生分布式 trace |
| Judge | 字符串/序列匹配 | GPT-4 / Claude / 自定义 judge |
| 数据集 | 内置 Python list | 版本化仓库 + 在线采样 |
| 可观测性 | 控制台报告 | Dashboard / Alerting / Metrics Pipeline |
| CI 集成 | 本地脚本 | GitHub Actions / GitLab CI / 自研平台 |
| 人工复核 | 无 | Human Review Queue + 审计 |
| 成本 | 零 | 模型调用、judge、存储 |

## 小结

这个 Mini Demo 用最小代码量展示了 Benchmark + Evaluation 的核心闭环：

```text
定义能力标准 → 准备 benchmark 数据集 → 埋点运行 Agent →
多维度 evaluator 打分 → 聚合与回归分析 → 输出可行动的评估报告
```

它是理解本章概念、并为真实平台选型和二次开发的基础。下一章将讨论这些模块在企业生产环境中的落地细节。

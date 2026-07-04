# Benchmark + Evaluation Mini Demo

一个纯标准库的 Python 原型，演示如何为 Agent 建立 **可观测、可评估** 的评测闭环：

- 确定性 ReAct Agent（无需调用外部 LLM API）
- 进程内 Trace / Span 记录
- 多维度 Evaluator（正确性、工具调用、延迟、成本、鲁棒性）
- Benchmark 数据集与聚合报告

## 运行

```bash
cd docs/07-ai-sre/benchmark-evaluation/mini-demo
pip install -e ".[dev]"
pytest tests/ -v
python -m benchmark_evaluation_mini.demo
```

## 设计要点

- `llm_stub.py` 用基于规则的响应模拟 LLM，保证测试 100% 可复现。
- `tracer.py` 用树形 Span 记录 Agent 每一步的 thought、tool_call、observation。
- `evaluators.py` 与具体业务解耦，只读取 trace 和最终答案。
- `benchmark.py` 负责批量运行与聚合分数。


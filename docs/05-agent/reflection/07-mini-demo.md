# 7. 工程实践：Mini Reflection

> 一句话理解：**这个 Mini Demo 用纯 Python、零外部 LLM key 实现一个最小可用的 Agent Reflection 系统，展示 Generator、Critic、Evaluator、Revision Loop、Workspace 与 Observer**。

## Demo 设计

真实 Reflection 系统通常依赖外部 LLM 来生成、批判和评估。为了在不调用外部模型、不依赖 GPU 的情况下讲清楚核心机制，本 Demo 采用纯 Python 模拟：

- **MockLLMClient**：确定性规则驱动的“伪 LLM”，根据迭代次数和 draft 内容返回生成、批判或评分结果。
- **GeneratorAgent**：接收用户请求，产出初始 draft 与修订 draft。
- **CriticAgent**：检查 draft，返回问题列表或 `["LGTM"]`。
- **Evaluator**：将 Critic 的输出量化为 score 与 verdict（pass / fail）。
- **Workspace**：共享工作区，保存 draft、critique、score、final_draft 等中间产物。
- **RevisionLoop**：编排“生成 → 批判 → 评估 → 修订”循环，直到通过或达到最大迭代次数。
- **Observer**：记录 loop 中的关键事件与 trace。

## 目录结构

```text
docs/05-agent/reflection/mini-demo/
├── README.md
├── pyproject.toml
├── reflection_mini/
│   ├── __init__.py
│   ├── llm_client.py       # MockLLMClient：确定性生成/批判/评分
│   ├── workspace.py        # Workspace：draft / critique / score / metadata
│   ├── generator.py        # GeneratorAgent：生成与修订 draft
│   ├── critic.py           # CriticAgent：返回问题列表或 LGTM
│   ├── evaluator.py        # Evaluator：评分 + 通过/失败判定
│   ├── reflection_loop.py  # RevisionLoop：生成→批判→评估→修订
│   ├── observer.py         # Observer：事件/trace 记录与渲染
│   └── demo.py             # 入口：解释 Agent Reflection 的段落写作
└── tests/
    ├── __init__.py
    ├── test_llm_client.py
    ├── test_workspace.py
    ├── test_generator.py
    ├── test_critic.py
    ├── test_evaluator.py
    ├── test_reflection_loop.py
    ├── test_observer.py
    └── test_demo.py
```

## 核心能力一览

| 能力 | 文件 | 说明 |
|---|---|---|
| 确定性 LLM | `llm_client.py` | 根据迭代次数与 draft 内容返回生成/批判/评分 |
| 共享工作区 | `workspace.py` | 按 key 读写，支持 shared/readonly/private 作用域 |
| 生成器 | `generator.py` | 产出 draft 并写入 Workspace |
| 批判器 | `critic.py` | 返回结构化 critique 或 LGTM |
| 评估器 | `evaluator.py` | 输出 score 与 verdict |
| 反思循环 | `reflection_loop.py` | 编排循环、终止判断、兜底策略 |
| 可观测 | `observer.py` | 记录事件与 trace |
| 入口演示 | `demo.py` | 段落写作任务，2 轮迭代后通过 |

## 快速运行

### 1. 安装依赖

```bash
cd docs/05-agent/reflection/mini-demo
pip install -e ".[dev]"
```

### 2. 运行 Demo

```bash
python -m reflection_mini.demo
```

Demo 会执行以下流程：

1. 用户请求：*Explain Agent Reflection in one paragraph*。
2. **Generator** 产出 Draft v1（抽象，缺少例子）。
3. **Critic** 返回问题：缺少具体例子、定义过于抽象、未说明何时停止。
4. **Evaluator** 评分 0.4 / 1.0，判定失败。
5. **RevisionLoop** 将 critique 反馈给 Generator。
6. **Generator** 产出 Draft v2（加入具体例子与修订说明）。
7. **Critic** 返回 `["LGTM"]`。
8. **Evaluator** 评分 1.0 / 1.0，判定通过。
9. 循环终止，输出 `final_draft` 与完整 trace。

### 3. 运行测试

```bash
pytest tests/ -v
```

### 4. 作为库使用

```python
from reflection_mini.critic import CriticAgent
from reflection_mini.evaluator import Evaluator
from reflection_mini.generator import GeneratorAgent
from reflection_mini.llm_client import MockLLMClient
from reflection_mini.observer import Observer
from reflection_mini.reflection_loop import RevisionLoop
from reflection_mini.workspace import Workspace

llm_client = MockLLMClient()
loop = RevisionLoop(
    generator=GeneratorAgent(llm_client),
    critic=CriticAgent(llm_client),
    evaluator=Evaluator(llm_client),
    workspace=Workspace(),
    observer=Observer(),
    max_iterations=3,
    score_threshold=1.0,
)
result = loop.run("Explain Agent Reflection in one paragraph")
print(result["workspace"]["final_draft"])
```

## 关键代码片段

### Mock LLM 的确定性规则

```python
from reflection_mini.llm_client import MockLLMClient

llm = MockLLMClient()

# 第 0 轮生成抽象 draft
print(llm.generate_draft("...", [], 0))
# Agent reflection is the ability of an agent to examine its own outputs and improve them. v1

# 第 1 轮生成含例子的 draft
print(llm.generate_draft("...", ["缺少具体例子"], 1))
# Agent reflection is when an LLM-based agent critiques its own draft ... For example, ...

# 批判：v1 或缺少 example → 返回问题列表
print(llm.critique("Agent reflection is ... v1"))
# ['缺少具体例子', '定义过于抽象', '未说明何时停止']

# 评估：LGTM + 含 example → pass
print(llm.evaluate("... For example, ...", ["LGTM"]))
# {'score': 1.0, 'verdict': 'pass'}
```

### 运行 Revision Loop

```python
from reflection_mini.reflection_loop import RevisionLoop

result = loop.run("Explain Agent Reflection in one paragraph")
print(result["iterations_run"])  # 2
print(result["passed"])          # True
```

### 读取 Workspace

```python
from reflection_mini.workspace import Workspace

ws = Workspace()
ws.write("draft_v0", "Initial draft.", scope="shared")
print(ws.read("draft_v0"))
print(ws.to_dict())
```

## 测试结果示例

```text
tests/test_critic.py::test_critic_detects_issues_in_v1_draft PASSED
tests/test_critic.py::test_critic_returns_lgtm_for_revised_draft PASSED
tests/test_demo.py::test_run_demo_completes_and_finalizes_draft PASSED
tests/test_evaluator.py::test_evaluator_scores_fail PASSED
tests/test_evaluator.py::test_evaluator_scores_pass PASSED
tests/test_generator.py::test_produce_writes_draft_and_latest PASSED
tests/test_generator.py::test_revised_draft_differs_after_critique PASSED
tests/test_llm_client.py::test_generate_draft_first_iteration_is_vague_and_has_v1 PASSED
tests/test_llm_client.py::test_generate_draft_later_iteration_includes_example PASSED
tests/test_llm_client.py::test_critique_flags_v1_draft PASSED
tests/test_llm_client.py::test_critique_flags_missing_example PASSED
tests/test_llm_client.py::test_evaluate_passes_when_lgtm_and_example PASSED
tests/test_llm_client.py::test_evaluate_fails_when_critique_not_lgtm PASSED
tests/test_llm_client.py::test_evaluate_fails_when_example_missing PASSED
tests/test_observer.py::test_record_appends_events PASSED
tests/test_observer.py::test_rendered_trace_contains_events PASSED
tests/test_observer.py::test_rendered_trace_has_tree_branches PASSED
tests/test_reflection_loop.py::test_loop_terminates_in_two_iterations PASSED
tests/test_reflection_loop.py::test_loop_respects_max_iterations PASSED
tests/test_reflection_loop.py::test_observer_records_key_events PASSED
tests/test_workspace.py::test_read_write_shared PASSED
tests/test_workspace.py::test_write_updates_history PASSED
tests/test_workspace.py::test_delete_removes_key PASSED
tests/test_workspace.py::test_read_missing_key_raises PASSED
tests/test_workspace.py::test_invalid_scope_raises PASSED
tests/test_workspace.py::test_readonly_cannot_be_overwritten PASSED
tests/test_workspace.py::test_private_scope_stored PASSED
tests/test_workspace.py::test_to_dict_snapshot PASSED
tests/test_workspace.py::test_keys_returns_all_keys PASSED

============================== 30 passed in 0.04s ==============================
```

## 生产差异说明

| 能力 | Demo 实现 | 生产系统 |
|---|---|---|
| LLM | 规则驱动的 MockLLMClient | OpenAI / Anthropic / vLLM / Gateway |
| Generator | 单函数 | 多模态生成器、带工具调用能力的 Agent |
| Critic | 简单关键词规则 | 独立 Critic 模型、Rubric-based prompt、多 Critic 投票 |
| Evaluator | 二值/标量规则 | 人工标注数据集、多维评分模型、A/B 校准 |
| Workspace | 内存 dict | 数据库 / 向量存储 / 事件溯源 |
| 终止条件 | score + max_iterations | 改进饱和、外部验证、人工审批 |
| 可观测 | stdout trace | OpenTelemetry / LangSmith / Prometheus |
| 失败恢复 | 无 | 回滚到最佳历史版本、Human Gate |

## 本章小结

Mini Demo 展示了一个零外部依赖、纯 Python 的 Agent Reflection 系统：通过 `MockLLMClient`、`GeneratorAgent`、`CriticAgent`、`Evaluator`、`Workspace`、`RevisionLoop` 与 `Observer`，实现了“生成 → 批判 → 评估 → 修订 → 终止”的完整闭环。虽然 LLM、Critic 与 Evaluator 都是教学级实现，但已经覆盖了生产 Reflection 系统的 80% 核心概念。推荐阅读 [`mini-demo/README.md`](./mini-demo/README.md) 获取完整运行说明，并在生产环境中替换为真实的 LLM 客户端、Critic 模型与评分机制。

**参考来源**

- [Self-Refine: Iterative Refinement with Self-Feedback](https://arxiv.org/abs/2303.17651)
- [Reflexion: Self-Reflective Agents](https://arxiv.org/abs/2303.11366)
- [CRITIC: Large Language Models Can Self-Correct with Tool-Interactive Critiquing](https://arxiv.org/abs/2305.11738)
- [LangGraph Reflection Tutorial](https://langchain-ai.github.io/langgraph/tutorials/reflection/reflection/)

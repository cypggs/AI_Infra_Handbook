# 工程实践：Mini Planning Agent

> 一句话理解：**`planning_mini` 是一个纯 Python 的最小 Planning Agent，演示任务分解、DAG 执行、失败观测与动态重规划。**

本章通过一个可运行的最小 Demo，把前面讲的架构与循环落地。Demo 位于 `docs/05-agent/planning/mini-demo/`，包名为 `planning_mini`。

## 场景

假设用户想完成一个数据分析任务：

```text
"分析本月销售数据，找出下降原因，并生成一份报告。"
```

这个任务可以拆解为：

1. 读取销售数据
2. 清洗数据
3. 计算关键指标
4. 分析下降原因
5. 生成报告

其中步骤 3 和 4 依赖步骤 2；步骤 5 依赖步骤 3 和 4。用 DAG 表示最适合。

## 目录结构

```
docs/05-agent/planning/mini-demo/
├── planning_mini/
│   ├── __init__.py
│   ├── llm_client.py      # 模拟 LLM 调用
│   ├── plan.py            # 计划数据模型
│   ├── planner.py         # 目标解析与计划生成
│   ├── tool_registry.py   # 工具注册与描述
│   ├── executor.py        # 步骤执行
│   ├── observer.py        # 结果观测
│   ├── replan_trigger.py  # 重规划触发器
│   ├── policy.py          # 策略与终止条件
│   └── demo.py            # 入口与运行示例
├── tests/
│   ├── test_plan.py
│   ├── test_planner.py
│   ├── test_executor.py
│   └── test_observer.py
├── pyproject.toml
└── README.md
```

## 运行方式

```bash
cd docs/05-agent/planning/mini-demo
pip install -e ".[dev]"
planning-demo
```

`pyproject.toml` 中定义了 console script：

```toml
[project.scripts]
planning-demo = "planning_mini.demo:run_demo"
```

## 关键代码片段

### plan.py：计划数据模型

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class Step:
    id: str
    action: str
    tool: str
    depends_on: list[str] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)
    status: StepStatus = StepStatus.PENDING
    output: Any = None
    error: str = ""

@dataclass
class Plan:
    id: str
    goal: str
    steps: list[Step]
    version: int = 1
    parent_id: str | None = None
```

### planner.py：生成计划

```python
from planning_mini.plan import Plan, Step

class Planner:
    def plan(self, goal: str, context: dict | None = None) -> Plan:
        # 简化版：根据关键词返回一个固定 DAG
        steps = [
            Step(id="s1", action="读取销售数据", tool="read_sales", params={"month": "current"}),
            Step(id="s2", action="清洗数据", tool="clean_data", depends_on=["s1"]),
            Step(id="s3", action="计算关键指标", tool="compute_metrics", depends_on=["s2"]),
            Step(id="s4", action="分析下降原因", tool="analyze_drop", depends_on=["s2"]),
            Step(id="s5", action="生成报告", tool="generate_report", depends_on=["s3", "s4"]),
        ]
        return Plan(id="plan-1", goal=goal, steps=steps)

    def replan(self, plan: Plan, failed_step_id: str) -> Plan:
        # 局部修复示例：在失败步骤前插入一个补救步骤
        new_steps = []
        for step in plan.steps:
            new_steps.append(step)
            if step.id == failed_step_id:
                new_steps.append(Step(
                    id=f"{failed_step_id}-fix",
                    action="修复数据问题",
                    tool="repair_data",
                    depends_on=[failed_step_id],
                ))
        return Plan(
            id=f"{plan.id}-v{plan.version + 1}",
            goal=plan.goal,
            steps=new_steps,
            version=plan.version + 1,
            parent_id=plan.id,
        )
```

### executor.py：DAG 执行

```python
from collections import deque
from planning_mini.plan import Plan, Step, StepStatus

class Executor:
    def __init__(self, tool_registry):
        self.tool_registry = tool_registry

    def run(self, plan: Plan):
        steps = {s.id: s for s in plan.steps}
        remaining = set(steps.keys())

        while remaining:
            ready = [
                sid for sid in remaining
                if all(steps[d].status == StepStatus.SUCCESS for d in steps[sid].depends_on)
            ]
            if not ready:
                raise RuntimeError("计划存在循环依赖或不可达步骤")

            for sid in ready:
                step = steps[sid]
                step.status = StepStatus.RUNNING
                tool = self.tool_registry.get(step.tool)
                try:
                    step.output = tool(**step.params)
                    step.status = StepStatus.SUCCESS
                except Exception as e:
                    step.status = StepStatus.FAILED
                    step.error = str(e)
                remaining.remove(sid)
```

### observer.py：结果观测

```python
from planning_mini.plan import Step, StepStatus

class Observer:
    def observe(self, step: Step, result: Any) -> dict:
        if step.status == StepStatus.FAILED:
            return {"status": "failed", "recoverable": self._is_recoverable(step.error)}
        if step.output is None or step.output == "":
            return {"status": "needs_attention", "recoverable": True}
        return {"status": "success", "recoverable": False}

    def _is_recoverable(self, error: str) -> bool:
        # 简化示例：权限错误不可恢复，网络/数据错误可恢复
        return "permission" not in error.lower()
```

### replan_trigger.py 与 policy.py

```python
class ReplanTrigger:
    def __init__(self, max_replans: int = 3):
        self.max_replans = max_replans
        self.count = 0

    def should_replan(self, observation: dict) -> bool:
        if observation["status"] != "failed":
            return False
        if not observation.get("recoverable", False):
            return False
        if self.count >= self.max_replans:
            return False
        self.count += 1
        return True

class Policy:
    def __init__(self, max_steps: int = 20, max_replans: int = 3):
        self.max_steps = max_steps
        self.max_replans = max_replans

    def should_terminate(self, plan: Plan, replan_count: int) -> bool:
        return replan_count >= self.max_replans or len(plan.steps) > self.max_steps
```

### demo.py：入口

```python
from planning_mini.planner import Planner
from planning_mini.tool_registry import ToolRegistry
from planning_mini.executor import Executor
from planning_mini.observer import Observer
from planning_mini.replan_trigger import ReplanTrigger
from planning_mini.policy import Policy

def run_demo():
    goal = "分析本月销售数据，找出下降原因，并生成一份报告。"
    planner = Planner()
    plan = planner.plan(goal)

    registry = ToolRegistry()
    executor = Executor(registry)
    observer = Observer()
    trigger = ReplanTrigger(max_replans=2)
    policy = Policy(max_steps=15, max_replans=2)

    replan_count = 0
    while True:
        executor.run(plan)
        failed = [s for s in plan.steps if s.status.name == "FAILED"]
        if not failed:
            print("任务完成")
            break

        obs = observer.observe(failed[0], None)
        if not trigger.should_replan(obs):
            print(f"无法恢复，终止。失败步骤：{failed[0].id}")
            break
        if policy.should_terminate(plan, replan_count):
            print("达到策略上限，终止")
            break

        plan = planner.replan(plan, failed[0].id)
        replan_count += 1
        print(f"触发第 {replan_count} 次重规划，新版本：{plan.id}")

if __name__ == "__main__":
    run_demo()
```

## 测试结果

运行 `pytest tests/` 可看到：

- `test_plan.py`：验证 Step/Plan 数据模型与序列化。
- `test_planner.py`：验证 Planner 能生成 5 步 DAG，replan 能正确插入修复步骤。
- `test_executor.py`：验证拓扑排序执行、依赖等待、失败传播。
- `test_observer.py`：验证成功/失败/可恢复分类。

示例输出：

```text
$ planning-demo
触发第 1 次重规划，新版本：plan-1-v2
任务完成
```

## 与生产系统的差异

这个 Demo 刻意保持最小化，生产落地时至少需要补齐：

| 方面 | Demo | 生产 |
|---|---|---|
| LLM 调用 | 模拟/规则 | 真实模型，支持 prompt 版本管理、缓存、流式 |
| 计划生成 | 固定模板 | 基于目标、上下文、工具描述的动态生成 |
| 计划表示 | 简单 DAG | 支持条件分支、循环、子计划、多 Agent |
| 执行调度 | 单线程拓扑 | 异步/并行调度、资源配额、超时取消 |
| 观测 | 简单规则 | LLM-as-judge、指标校验、异常检测 |
| 记忆 | 无 | Plan Store、Plan Memory、checkpoint |
| 安全 | 无 | 权限校验、审计日志、HITL |
| 可观测性 | 打印 | 结构化日志、trace、metrics |

## 本章小结

- `planning_mini` 通过 9 个文件演示了 Planning Agent 的最小闭环。
- 核心流程：Planner 生成 DAG → Executor 拓扑执行 → Observer 评估 → Replan Trigger 决定是否重规划 → Policy 控制终止。
- Demo 与生产系统的差距主要在 LLM 集成、调度并发、记忆持久化、安全审计和可观测性。

**参考来源**
- [Planning for Agents - LangChain Blog](https://blog.langchain.dev/planning-for-agents/)
- [LangGraph Plans](https://langchain-ai.github.io/langgraph/concepts/plans/)
- [OpenAI Agents SDK Handoffs](https://openai.github.io/openai-agents-python/handoffs/)
- [AutoGen Planning Tutorial](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/planning.html)

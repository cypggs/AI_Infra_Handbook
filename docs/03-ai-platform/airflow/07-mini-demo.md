# 7. Mini Demo：本地模拟 DAG 解析、调度、执行与 XCom

> 一句话理解：这个 Demo 用 **纯 Python 模拟 Airflow 的核心组件**，在不启动真实 Airflow 服务的情况下，完整跑通：定义 DAG → 解析序列化 → Scheduler 创建 Run → Executor 分发执行 → XCom 传递数据 → Triggerer 唤醒 deferred 任务。

## 7.1 目标与约束

- **无需外部服务**：不启动 Airflow、数据库或消息队列。
- **CPU 可运行**：纯 Python，依赖只有标准库 + pytest。
- **核心机制真实**：DAG 依赖、TaskInstance 状态机、XCom、重试、defer 都有体现。
- **自动清理**：测试使用内存存储，无需额外清理。

## 7.2 目录结构

```
mini-demo/
├── README.md
├── pyproject.toml
├── airflow_mini/
│   ├── __init__.py
│   ├── dag.py          # DAG / Task / Operator 抽象
│   ├── parser.py       # DAG Processor 模拟
│   ├── scheduler.py    # Scheduler 模拟
│   ├── executor.py     # Executor 模拟
│   ├── state.py        # 状态机常量与转换
│   ├── xcom.py         # XCom 内存存储
│   ├── triggerer.py    # Triggerer 模拟
│   └── demo.py         # 端到端入口
└── tests/
    ├── __init__.py
    ├── test_dag.py
    ├── test_scheduler.py
    ├── test_executor.py
    └── test_demo.py
```

## 7.3 运行方式

```bash
cd docs/03-ai-platform/airflow/mini-demo
pip install -e ".[dev]"
pytest tests/ -v
python -m airflow_mini.demo
```

预期输出包含：

- DAG 解析后的任务列表与依赖。
- Scheduler 创建的 DAG Run 与 TaskInstance。
- Executor 按依赖顺序执行任务。
- XCom 从 `extract` 传到 `transform`。
- `wait_file` deferred 后被 Triggerer 唤醒。
- 最终所有任务成功。

## 7.4 核心代码

### DAG 与 Operator 抽象

```python
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Any


@dataclass
class Task:
    task_id: str
    operator: "BaseOperator"
    upstream: List["Task"] = field(default_factory=list)
    downstream: List["Task"] = field(default_factory=list)

    def __rshift__(self, other: "Task"):
        self.downstream.append(other)
        other.upstream.append(self)
        return other


@dataclass
class DAG:
    dag_id: str
    schedule: str = "@daily"
    tasks: dict = field(default_factory=dict)

    def add_task(self, task: Task):
        self.tasks[task.task_id] = task

    def topo_order(self) -> List[Task]:
        # Kahn 算法拓扑排序
        ...


class BaseOperator:
    def __init__(self, task_id: str, **kwargs):
        self.task_id = task_id
        self.kwargs = kwargs

    def execute(self, context: dict) -> Any:
        raise NotImplementedError
```

### Scheduler 模拟

```python
class Scheduler:
    def __init__(self, db, executor, triggerer):
        self.db = db
        self.executor = executor
        self.triggerer = triggerer

    def create_dag_run(self, dag: DAG, run_id: str, logical_date: str):
        self.db.dag_runs[(dag.dag_id, run_id)] = {
            "state": "running",
            "logical_date": logical_date,
        }
        for task_id in dag.tasks:
            self.db.task_instances[(dag.dag_id, run_id, task_id)] = {
                "state": "none",
                "try_number": 0,
            }

    def schedule(self, dag: DAG, run_id: str):
        for task_id in dag.topo_order():
            ti_key = (dag.dag_id, run_id, task_id)
            ti = self.db.task_instances[ti_key]
            if ti["state"] in ("success", "failed", "skipped", "deferred"):
                continue
            upstream = dag.tasks[task_id].upstream
            if all(
                self.db.task_instances[(dag.dag_id, run_id, t.task_id)]["state"] == "success"
                for t in upstream
            ):
                ti["state"] = "scheduled"
                self.executor.queue(dag, run_id, task_id)
```

### Executor 与 XCom

```python
class LocalExecutor:
    def __init__(self, db, xcom):
        self.db = db
        self.xcom = xcom
        self.queue = []

    def queue(self, dag, run_id, task_id):
        self.queue.append((dag, run_id, task_id))
        self.db.task_instances[(dag.dag_id, run_id, task_id)]["state"] = "queued"

    def execute_queued(self):
        for dag, run_id, task_id in self.queue:
            task = dag.tasks[task_id]
            ti = self.db.task_instances[(dag.dag_id, run_id, task_id)]
            ti["state"] = "running"
            context = {"dag": dag, "run_id": run_id, "task_id": task_id, "xcom": self.xcom}
            try:
                result = task.operator.execute(context)
                ti["state"] = "success"
                self.xcom.push(dag.dag_id, run_id, task_id, "return_value", result)
            except Exception:
                ti["state"] = "failed"
        self.queue.clear()
```

### Deferrable Operator 与 Triggerer

```python
class WaitFileOperator(BaseOperator):
    def __init__(self, task_id: str, filepath: str, ready: bool = False):
        super().__init__(task_id)
        self.filepath = filepath
        self.ready = ready

    def execute(self, context):
        if not self.ready:
            # 模拟 defer：记录 trigger，状态变为 deferred
            context["db"].task_instances[
                (context["dag"].dag_id, context["run_id"], self.task_id)
            ]["state"] = "deferred"
            context["triggerer"].register(self.filepath, context)
            raise DeferSignal()
        return {"filepath": self.filepath, "ready": True}
```

## 7.5 测试覆盖

| 测试 | 验证点 |
|---|---|
| `test_dag` | DAG 拓扑排序正确，环检测报错 |
| `test_scheduler` | Scheduler 创建 DAG Run 与 TaskInstance，依赖满足才入队 |
| `test_executor` | Executor 按顺序执行，XCom 写入正确，失败状态正确 |
| `test_demo` | 端到端运行成功，包含 defer 唤醒 |

## 7.6 与真实 Airflow 的差异

| 方面 | Mini Demo | 真实 Airflow |
|---|---|---|
| 数据库 | 内存 dict | PostgreSQL / MySQL |
| DAG 解析 | 直接 import Python | DAG Processor 扫描目录 |
| 调度 | 单次调用 | Scheduler 持续循环 |
| 执行 | 同进程函数调用 | 子进程 / Pod / Celery Worker |
| 日志 | print | 远程日志存储 |
| Web UI | 无 | Flask/FastAPI UI |
| 并发 | 无 | 多进程 / K8s Pod |

本 Demo 用于理解 Airflow 核心机制，不能直接用于生产。

## 本章小结

- Mini Demo 用纯 Python 模拟 Airflow 核心组件，无需外部依赖。
- 完整链路：**DAG 定义 → 解析 → Scheduler 创建 Run/TI → Executor 执行 → XCom 传递 → Triggerer 唤醒 defer**。
- `pytest` 覆盖 DAG、Scheduler、Executor、端到端 Demo。
- 与真实 Airflow 的差异主要在持久化、调度循环、执行隔离和 UI。

**参考来源**

- 本 Demo 源码：`docs/03-ai-platform/airflow/mini-demo/`
- [Apache Airflow — Core Concepts](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/index.html)
- [Apache Airflow — Scheduler](https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/scheduler.html)

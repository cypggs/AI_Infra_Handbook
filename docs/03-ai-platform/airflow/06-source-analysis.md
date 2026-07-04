# 6. 源码分析：关键目录、调用链与扩展点

> 一句话理解：Airflow 源码的核心是 **DAG 定义 → 模型对象 → Scheduler 调度 → Executor 分发 → Task Runner 执行 → Metadata DB 回写** 的主链路，围绕 `airflow/models`、`airflow/jobs`、`airflow/executors` 三大目录展开。

## 6.1 源码仓库地图

```
apache/airflow/
├── airflow/
│   ├── models/              # 核心数据模型
│   │   ├── dag.py           # DAG 模型
│   │   ├── dagrun.py        # DAG Run 状态机
│   │   ├── taskinstance.py  # TaskInstance 状态机与执行
│   │   ├── xcom.py          # XCom 存储
│   │   ├── variable.py      # Airflow Variable
│   │   ├── connection.py    # Connection 管理
│   │   ├── pool.py          # 资源池
│   │   └── skipmixin.py     # 跳过逻辑
│   ├── jobs/
│   │   ├── scheduler_job_runner.py  # Scheduler 主逻辑
│   │   ├── triggerer_job_runner.py  # Triggerer 主逻辑
│   │   └── dag_processor_job_runner.py  # DAG Processor
│   ├── executors/           # Executor 实现
│   │   ├── base_executor.py
│   │   ├── sequential_executor.py
│   │   ├── local_executor.py
│   │   ├── celery_executor.py
│   │   └── dask_executor.py
│   ├── providers/           # 官方 provider 包（Airflow 2+）
│   │   ├── amazon/
│   │   ├── cncf/kubernetes/  # KubernetesExecutor / KPO
│   │   ├── google/
│   │   ├── http/
│   │   └── ...
│   ├── operators/           # 内置 Operator
│   │   ├── bash.py
│   │   ├── python.py
│   │   └── ...
│   ├── sensors/             # 内置 Sensor
│   ├── triggers/            # 内置 Trigger
│   ├── ti_deps/             # TaskInstance 依赖检查
│   │   ├── deps_base.py
│   │   └── deps/
│   ├── utils/               # 工具函数
│   ├── cli/                 # airflow CLI
│   ├── www/                 # Web UI (Flask)
│   └── api/                 # REST API
├── dags/                    # 示例 DAG
├── tests/                   # 测试
└── scripts/                 # 辅助脚本
```

## 6.2 关键调用链

### DAG 文件解析链路

```
DAG Processor 启动
        │
        ▼
airflow/dag_processing/processor.py
        │
        ▼
DagFileProcessor.process_file(file_path)
        │
        ▼
导入 Python 模块，收集 dagbag
        │
        ▼
DagBag.dags 中保存 DAG 对象
        │
        ▼
序列化 DAG → SerializedDagModel.write_dag(dag)
        │
        ▼
写入 dag 表的 serialized_dag 字段
```

### Scheduler 调度链路

```
airflow/jobs/scheduler_job_runner.py
        │
        ▼
SchedulerJobRunner._run_scheduler_loop()
        │
        ├─ _create_dag_runs() 创建 DAG Run
        │
        ├─ _update_dag_run_state_for_paused_dags()
        │
        └─ _critical_section_enqueue_task_instances()
                │
                ▼
        查询符合条件的 TaskInstance
                │
                ▼
        BaseExecutor.queue_command(ti, command)
                │
                ▼
        TaskInstance 状态 scheduled → queued
```

### TaskInstance 执行链路

```
Worker 收到命令
        │
        ▼
airflow/cli/commands/task_command.py: task_run()
        │
        ▼
TaskInstance._execute_task_with_callbacks(context)
        │
        ▼
TaskInstance._execute_task(context, task)
        │
        ▼
Operator.execute(context)
        │
        ▼
任务逻辑执行
        │
        ▼
TaskInstance 状态更新 + XCom 写入
```

## 6.3 关键文件解析

### `airflow/models/dag.py`

- `DAG` 类的定义，包含 `dag_id`、`schedule_interval`、`tasks` 等属性。
- `create_dagrun()`：创建 DAG Run。
- `partial_subset()`：子 DAG 支持。

### `airflow/models/dagrun.py`

- `DagRun` 模型，包含 `run_id`、`execution_date`、`state`。
- `update_state()`：根据 TaskInstance 状态更新 DAG Run 状态。
- `get_task_instances()`：获取本次 Run 的所有 TI。

### `airflow/models/taskinstance.py`

- `TaskInstance` 模型，是 Airflow 最核心的类之一。
- `handle_failure()`：失败处理与重试。
- `run()`：执行 Task。
- `xcom_push()` / `xcom_pull()`：XCom 读写。
- `defer()`：进入 deferred 状态。

### `airflow/jobs/scheduler_job_runner.py`

- Scheduler 主循环实现。
- `_critical_section_enqueue_task_instances`：核心入队逻辑。
- `_create_dag_runs`：创建 DAG Run。

### `airflow/executors/base_executor.py`

- `BaseExecutor` 抽象类。
- `queue_command()`：入队。
- `sync()`：同步执行结果。
- `heartbeat()`：心跳。

### `airflow/executors/kubernetes_executor.py`

- 与 K8s API Server 交互。
- 为每个 TaskInstance 创建/删除 Pod。
- 使用 watcher 监听 Pod 事件。

## 6.4 TaskInstance 依赖检查

Scheduler 在把 TaskInstance 入队前，会调用 `ti_deps` 中的各种依赖检查：

```
airflow/ti_deps/deps/
├── dagrun_exists_dep.py
├── exec_date_after_start_date_dep.py
├── not_in_retry_period_dep.py
├── pool_slots_available_dep.py
├── prev_dagrun_dep.py
├── ready_to_reschedule.py
├── runnable_exec_date_dep.py
├── task_concurrency_dep.py
├── trigger_rule_dep.py
├── valid_state_dep.py
└── ...
```

每个依赖检查器返回 `Passed` 或 `Failed`，只有全部通过才能入队。

## 6.5 Provider 架构

Airflow 2.0 把大量 Operator/Hook/Sensor 拆成独立 provider 包：

```
apache-airflow-providers-amazon
apache-airflow-providers-cncf-kubernetes
apache-airflow-providers-google
apache-airflow-providers-http
apache-airflow-providers-snowflake
...
```

### 好处

- 减少核心包体积。
- 各 provider 独立发版。
- 第三方可以发布自己的 provider。

### 自定义 Provider

```python
# my_provider/operators/my_operator.py
from airflow.models.baseoperator import BaseOperator

class MyOperator(BaseOperator):
    def execute(self, context):
        ...
```

## 6.6 Airflow 3 源码演进

Airflow 3 正在做以下源码层面的重构：

- **Execution API 独立**：`airflow/api_internal/` 提供任务执行器与 Scheduler 通信的接口。
- **Task 不直接访问 DB**：Worker 通过 Execution API 拉取任务、上报状态。
- **FastAPI 迁移**：Webserver/API Server 从 Flask 迁移到 FastAPI。
- **JWT 认证**：Execution API 与外部调用使用 JWT。

## 6.7 阅读源码的建议路径

1. **从 DAG 定义开始**：`airflow/models/dag.py`。
2. **看一次调度循环**：`airflow/jobs/scheduler_job_runner.py`。
3. **看 TaskInstance 执行**：`airflow/models/taskinstance.py` 的 `run()`。
4. **看一个 Executor**：`airflow/executors/local_executor.py` 最简单。
5. **看一个 Provider**：`airflow/providers/cncf/kubernetes/operators/pod.py` 的 `KubernetesPodOperator`。

## 本章小结

- Airflow 源码核心目录：`models`、`jobs`、`executors`、`providers`。
- 主链路：DAG 文件 → DAG Processor → 序列化 → Scheduler → Executor → Worker → Metadata DB。
- `taskinstance.py` 是状态机和执行逻辑的核心。
- `scheduler_job_runner.py` 是调度决策核心。
- `ti_deps` 负责 TaskInstance 入队前的依赖检查。
- Provider 架构让 Airflow 2+ 生态更轻量、可扩展。
- Airflow 3 将向 Execution API + FastAPI + JWT 演进。

**参考来源**

- [Apache Airflow GitHub](https://github.com/apache/airflow)
- [Apache Airflow — Core Concepts](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/index.html)
- [Apache Airflow — Scheduler](https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/scheduler.html)
- [Apache Airflow — DAG File Processing](https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/dag-file-processing.html)
- [Apache Airflow — Providers](https://airflow.apache.org/docs/apache-airflow-providers/)

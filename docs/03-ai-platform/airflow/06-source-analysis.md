# 6. 源码分析：关键目录、调用链与扩展点

> 一句话理解：Airflow 源码的核心是 **DAG 定义 → 模型对象 → Scheduler 调度 → Executor 分发 → Task Runner 执行 → 状态回写** 的主链路，围绕 `airflow/models`（2.x）/`airflow-core`（3.x 仓库）、`airflow/jobs`、`airflow/executors` 三大区域展开；Airflow 3 之后，Task 侧代码拆进了独立的 `apache-airflow-sdk` 包。

## 6.1 源码仓库地图

Airflow 3.x 起，GitHub 仓库 `apache/airflow` 已按发行包拆分为多个子项目（monorepo）：

```
apache/airflow/
├── airflow-core/            # 核心包（原 airflow/）
│   └── src/airflow/
│       ├── models/          # 核心数据模型
│       │   ├── dag.py       # DAG 模型
│       │   ├── dagrun.py    # DAG Run 状态机
│       │   ├── taskinstance.py  # TaskInstance 状态机
│       │   ├── xcom.py      # XCom 存储
│       │   └── ...
│       ├── jobs/            # 长驻进程
│       │   ├── scheduler_job_runner.py  # Scheduler 主逻辑
│       │   ├── triggerer_job_runner.py  # Triggerer 主逻辑
│       │   └── dag_processor_job_runner.py  # DAG Processor
│       ├── executors/       # 核心 Executor（Sequential / Local）
│       ├── api_fastapi/     # Airflow 3：FastAPI 服务
│       │   ├── app.py       # 核心 REST API v2 + UI 后端
│       │   ├── execution_api/  # Task Execution API（AIP-72）
│       │   └── auth/        # JWT / 各 auth manager 接线
│       ├── auth/            # 认证管理器（SimpleAuthManager 等）
│       ├── dag_processing/  # DAG 文件解析与 Bundle
│       ├── ti_deps/         # TaskInstance 依赖检查
│       └── sdk/             # 核心内对 Task SDK 的再导出
├── task-sdk/                # apache-airflow-sdk：任务执行侧代码
│   └── src/airflow/sdk/
│       ├── definitions/     # @dag / @task / Asset 等定义（编写接口）
│       ├── execution_time/  # 任务运行时的 API client（上报状态/XCom）
│       ├── exceptions.py    # 3.2 起任务侧异常收敛到这里
│       └── bases/           # BaseOperator / BaseSensor / BaseTrigger
├── providers/               # 全部官方 provider（按目录拆分）
│   ├── celery/              # CeleryExecutor
│   ├── cncf/kubernetes/     # KubernetesExecutor / KPO
│   ├── edge3/               # EdgeExecutor
│   ├── standard/            # BashOperator / PythonOperator（3.x 移入）
│   ├── fab/                 # Flask-AppBuilder 认证管理器（向后兼容）
│   └── ...
├── airflow-ctl/             # airflowctl 新一代 CLI 客户端（AIP-94，3.x 引入）
├── airflow-ui/              # React UI（AIP-38）
└── chart/                   # 官方 Helm Chart
```

> Airflow 2.x 时代的 `airflow/www/`（Flask UI）、`airflow/api/`（REST v1）在 3.0 已整体移除；`DaskExecutor` 移出核心。

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
Worker 收到命令（2.x：airflow tasks run ...；3.x：由 Task SDK 启动）
        │
        ▼
airflow-core: task-sdk 加载 TaskInstance 上下文
（3.x：先向 Execution API 换取短期 JWT，仅此一条通道）
        │
        ▼
TaskInstance._execute_task_with_callbacks(context)
        │
        ▼
Operator.execute(context)
        │
        ▼
任务逻辑执行
        │
        ▼
XCom 与状态经 Execution API 上报（2.x：直连 Metadata DB 写入）
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

### Celery / Kubernetes Executor（3.x 起在 providers 仓库目录）

- `providers/celery/src/airflow/providers/celery/executors/celery_executor.py`：与 Celery worker 通信。
- `providers/cncf/kubernetes/src/airflow/providers/cncf/kubernetes/executors/kubernetes_executor.py`：与 K8s API Server 交互，为每个 TaskInstance 创建/删除 Pod，使用 watcher 监听 Pod 事件。

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

Airflow 2.0 把大量 Operator/Hook/Sensor 拆成独立 provider 包；Airflow 3.0 进一步把 **BashOperator / PythonOperator 等最常用 Operator 也移入 `providers-standard` 包**（核心包不再自带），并继续拆包：Celery/Kubernetes Executor、FAB 认证管理器等都以 provider 形式存在：

```
apache-airflow-providers-standard      # BashOperator / PythonOperator（3.x 起）
apache-airflow-providers-celery        # CeleryExecutor
apache-airflow-providers-cncf-kubernetes
apache-airflow-providers-edge3         # EdgeExecutor（AIP-69）
apache-airflow-providers-fab           # Flask-AppBuilder 认证（2.x 兼容）
apache-airflow-providers-amazon
apache-airflow-providers-google
apache-airflow-providers-snowflake
apache-airflow-providers-openlineage   # 数据血缘
...
```

### 好处

- 减少核心包体积。
- 各 provider 独立发版。
- 第三方可以发布自己的 provider。

### 自定义 Provider

```python
# my_provider/operators/my_operator.py
from airflow.sdk import BaseOperator

class MyOperator(BaseOperator):
    def execute(self, context):
        ...
```

> 注意：Airflow 3 中自定义 Operator 的基类来自 `airflow.sdk`（`BaseOperator` 已迁移），导入旧路径会触发 ruff `AIR301` 规则告警。

## 6.6 Airflow 3 源码演进（已完成）

- **Task SDK 独立成包（AIP-72）**：任务侧代码整体迁入 `task-sdk/`（发行包 `apache-airflow-sdk`），与核心独立版本号；DAG 编写接口（`airflow.sdk.definitions`）和任务运行时（`airflow.sdk.execution_time`，内置 Execution API client）分离。
- **Execution API**：早期在 `airflow/api_internal/`，后并入 `airflow/api_fastapi/execution_api/`——Worker/Task 通过它与核心通信，JWT 中间件统一鉴权。
- **FastAPI 全面取代 Flask**：核心 REST API v2、React UI 后端、Execution API 都在 `api_fastapi/`；`www/`（Flask）与 REST v1 被删除。
- **任务侧零 DB 直连**：`airflow.sdk.execution_time` 中的 client 是唯一通道；Hook 直连业务库不受影响，但任何访问 Metadata DB 的 hack（如用 PostgresHook 读写元数据库）在 3.x 不再可行且不受支持。
- **多语言 Task SDK（AIP-108，3.3 实验性）**：Java/Go SDK 复用同一 Execution API，说明该 API 已成为稳定的多语言契约；**Java SDK 1.0.0-beta1 已于 2026-07-13 单独发版**。
- **Dag Importer（AIP-85，3.4 实验性）**：Task SDK 内新增可插拔 DAG 导入框架——每种格式注册一个 importer，DAG Processor 运行对应语言运行时后，YAML 格式及 TypeScript/Go/Java SDK 编写的 DAG 与 Python DAG 一样入库调度。这是“DAG 定义”从 Python-only 走向多语言的第一块源码级拼图。
- **airflowctl（AIP-94）**：新一代 CLI 客户端（2026-06 已发布 0.1.5），逐步接管原有 `airflow` CLI 的远端操作。
- **3.4 executor 内部重构**：各执行器的工作负载队列统一为 `BaseExecutor.executor_queues`（按 `WorkloadType` 键控，经 `trigger_workloads` 调度）；旧的 per-type 入口（`queued_tasks`、`trigger_tasks` 等）保留为兼容 shim 并发出 `RemovedInAirflow4Warning`——第三方 executor 需迁移到 `supported_workload_types` + `trigger_workloads`。

## 6.7 阅读源码的建议路径

1. **从 DAG 定义开始**：`task-sdk/src/airflow/sdk/definitions/dag.py`。
2. **看一次调度循环**：`airflow-core/src/airflow/jobs/scheduler_job_runner.py`。
3. **看 TaskInstance 执行**：`airflow-core/src/airflow/models/taskinstance.py` 的 `run()`。
4. **看 Execution API 协议**：`airflow-core/src/airflow/api_fastapi/execution_api/`。
5. **看一个 Provider**：`providers/cncf/kubernetes/src/airflow/providers/cncf/kubernetes/operators/pod.py` 的 `KubernetesPodOperator`。

## 本章小结

- Airflow 3.x 仓库 = `airflow-core` + `task-sdk` + `providers` + `airflow-ctl` + `airflow-ui` 的 monorepo。
- 主链路：DAG 文件 → DAG Processor → 序列化 → Scheduler → Executor → Worker → （3.x：经 Execution API）→ Metadata DB。
- `taskinstance.py` 是状态机和执行逻辑的核心；`scheduler_job_runner.py` 是调度决策核心。
- `ti_deps` 负责 TaskInstance 入队前的依赖检查。
- Provider 架构在 3.x 进一步拆分，Bash/PythonOperator 也移入 `providers-standard`。
- Task SDK（AIP-72）与 Execution API 是 Airflow 3 源码层面最大的结构性变化。

**参考来源**

- [Apache Airflow GitHub](https://github.com/apache/airflow)
- [apache-airflow-sdk PyPI](https://pypi.org/project/apache-airflow-sdk/)
- [Apache Airflow — Core Concepts](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/index.html)
- [Apache Airflow — Scheduler](https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/scheduler.html)
- [Apache Airflow — Upgrading to Airflow 3](https://airflow.apache.org/docs/apache-airflow/stable/installation/upgrading_to_airflow3.html)
- [Apache Airflow — Providers](https://airflow.apache.org/docs/apache-airflow-providers/)

# 5. 核心模块：Scheduler、Executor、Task Runner、XCom、Triggerer

> 一句话理解：Airflow 的实现可以拆成 **“解析层、调度层、执行层、存储层、扩展层”**——DAG Processor 负责解析，Scheduler 负责调度，Executor 负责分发，Task Runner 负责执行，Metadata DB 和 XCom 负责存储，Triggerer 和 Plugins 负责扩展。

## 5.1 模块分层

```
┌──────────────────────────────────────────────────────────────────────┐
│                         用户界面 / CLI / API                          │
│                    Webserver / REST API / airflow CLI                 │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         解析层：DAG Processor                         │
│         扫描 dags/ → 导入 Python → 序列化 → 写入 Metadata DB          │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         调度层：Scheduler                             │
│        创建 DAG Run → 创建 TaskInstance → 依赖检查 → 入队             │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
            ┌───────────────────┴───────────────────┐
            │                                       │
            ▼                                       ▼
┌───────────────────────────┐           ┌───────────────────────────┐
│      执行层：Executor      │           │    异步层：Triggerer      │
│  Local / Celery / K8s      │           │  监听 deferred 事件       │
└───────────┬───────────────┘           └───────────────────────────┘
            │
            ▼
┌───────────────────────────┐
│     Task Runner / Worker   │
│   执行命令、捕获输出、      │
│   推送 XCom、更新状态       │
└───────────────────────────┘
```

## 5.2 DAG Processor

### 职责

- 扫描 `dags/` 目录的文件变化。
- 导入 DAG 文件并实例化 DAG。
- 序列化 DAG 并写入 `dag` 表。
- 检测 DAG 解析错误并上报。

### 关键配置

| 配置项 | 说明 |
|---|---|
| `min_file_process_interval` | 两次处理同一文件的最小间隔 |
| `dag_dir_list_interval` | 扫描目录间隔 |
| `parsing_processes` | 并行解析进程数 |

## 5.3 Scheduler

### 关键类

- `airflow/jobs/scheduler_job_runner.py`：Scheduler 主逻辑。
- `airflow/models/dagrun.py`：DAG Run 模型与状态机。
- `airflow/models/taskinstance.py`：TaskInstance 模型与状态机。

### 主循环逻辑

1. `adopt_or_reset_orphaned_tasks`：接管孤儿任务。
2. `critical_section_enqueue_task_instances`：把可运行的 TI 入队。
3. `_create_dag_runs`：创建新的 DAG Run。
4. `_update_dag_next_dagruns`：更新下次调度时间。

### 关键配置

| 配置项 | 说明 |
|---|---|
| `scheduler_idle_sleep_time` | 无任务时的休眠时间 |
| `max_tis_per_query` | 每次查询最大 TI 数 |
| `schedule_after_task_execution` | 任务执行后是否立即调度下游 |

## 5.4 Executor

### 抽象接口

所有 Executor 继承自 `airflow.executors.base_executor.BaseExecutor`，必须实现：

- `start()`：启动 executor。
- `queue_command(ti, command, ...)`：把任务加入队列。
- `sync()`：同步状态。
- `end()`：结束 executor。

### 常见 Executor

| Executor | 文件路径 | 特点 |
|---|---|---|
| SequentialExecutor | `airflow/executors/sequential_executor.py` | 单进程，仅开发 |
| LocalExecutor | `airflow/executors/local_executor.py` | 本地多进程 |
| CeleryExecutor | `airflow/executors/celery_executor.py` | 基于 Celery |
| KubernetesExecutor | `airflow/providers/cncf/kubernetes/executors/kubernetes_executor.py` | 每个任务一个 Pod |
| DaskExecutor | `airflow/executors/dask_executor.py` | 基于 Dask |

## 5.5 Task Runner

Task Runner 是实际执行 Task 逻辑的组件。

### StandardTaskRunner

- 默认 Task Runner。
- 创建子进程执行 `airflow tasks run ...` 命令。
- 子进程以指定 unix user 运行（如果配置了 `run_as_user`）。

### 执行命令示例

```bash
airflow tasks run ml_pipeline preprocess_data scheduled__2026-07-01T00:00:00+00:00
```

### 执行流程

```
Task Runner 接收命令
        │
        ▼
加载 TaskInstance 上下文
        │
        ▼
执行 Operator 的 execute() 方法
        │
        ▼
捕获 stdout/stderr 作为日志
        │
        ▼
把 XCom 写入 Metadata DB
        │
        ▼
更新 TaskInstance 状态
```

## 5.6 XCom

### 存储位置

- 默认：`xcom` 表（Metadata Database）。
- 自定义：`XComBackend`（S3、GCS、Redis 等）。

### 关键限制

| 数据库 | 默认 XCom value 大小限制 |
|---|---|
| SQLite | 受限于 JSON 序列化 |
| PostgreSQL | 较大，但仍不建议传大对象 |
| MySQL | 受 `max_allowed_packet` 限制 |

### 自定义 XCom Backend

```python
from airflow.models.xcom import BaseXCom

class S3XComBackend(BaseXCom):
    @staticmethod
    def serialize_value(value):
        # 上传 S3 并返回 key
        ...

    @staticmethod
    def deserialize_value(result):
        # 根据 key 从 S3 下载
        ...
```

在 `airflow.cfg` 中配置：

```ini
[core]
xcom_backend = my_package.S3XComBackend
```

## 5.7 Triggerer

### 职责

- 监听 deferred TaskInstance 的 trigger。
- 当 trigger 条件满足时，通知 Scheduler 唤醒 TaskInstance。
- 用 asyncio 实现高并发。

### 关键类

- `airflow/jobs/triggerer_job_runner.py`：Triggerer 主逻辑。
- `airflow/triggers/base.py`：`BaseTrigger` 基类。
- `airflow/triggers/temporal.py`、`airflow/triggers/file.py`：内置 trigger。

### 自定义 Trigger

```python
from airflow.triggers.base import BaseTrigger, TriggerEvent

class MyTrigger(BaseTrigger):
    async def run(self):
        while True:
            if await self.is_ready():
                yield TriggerEvent({"status": "ready"})
                return
            await asyncio.sleep(5)
```

## 5.8 Plugins

Airflow 通过 Plugin 机制扩展：

- 自定义 Operator、Sensor、Hook。
- 自定义 Executor。
- 自定义 Flask 视图（Airflow 2 兼容，Airflow 3 将改用 FastAPI）。

```python
from airflow.plugins_manager import AirflowPlugin
from airflow.operators.bash import BashOperator

class MyPlugin(AirflowPlugin):
    name = "my_plugin"
    operators = [MyOperator]
    sensors = [MySensor]
    hooks = [MyHook]
```

## 5.9 Connections 与 Variables

### Connections

- 统一管理外部系统连接信息（密码、AK/SK、host、port）。
- 支持多种类型：HTTP、Postgres、S3、Snowflake 等。
- 可用环境变量、Secrets Backend、UI 配置。

### Variables

- 全局键值对，常用于配置开关、路径前缀等。
- 大量 Variable 频繁读取会增加 DB 压力，可开启缓存。

## 本章小结

- **DAG Processor**：解析并序列化 DAG 文件。
- **Scheduler**：创建 DAG Run、推进 TaskInstance 状态机。
- **Executor**：把 TaskInstance 分发到执行环境。
- **Task Runner**：执行 Task 逻辑、捕获日志、写 XCom。
- **XCom**：任务间数据交换，可自定义 backend。
- **Triggerer**：异步监听事件，支持 Deferrable Operator。
- **Plugins / Connections / Variables**：扩展机制与配置管理。

**参考来源**

- [Apache Airflow — Scheduler](https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/scheduler.html)
- [Apache Airflow — DAG File Processing](https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/dag-file-processing.html)
- [Apache Airflow — Plugins](https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/plugins.html)
- [Apache Airflow — Connection](https://airflow.apache.org/docs/apache-airflow/stable/howto/connection.html)
- [Apache Airflow — XCom Backend](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/xcoms.html#custom-xcom-backend)

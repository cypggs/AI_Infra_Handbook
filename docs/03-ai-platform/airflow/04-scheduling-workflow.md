# 4. 调度工作流程：从 DAG 文件到 Task 执行

> 一句话理解：Airflow 的一条完整调度链路是——**DAG 文件被 DAG Processor 解析成序列化 DAG 存进 Metadata DB；Scheduler 据此创建 DAG Run 和 TaskInstance；当依赖与资源满足时，Scheduler 把 TaskInstance 推进到 queued；Executor 把它交给 Worker 执行；Worker 把状态与 XCom 写回数据库**。

## 4.1 完整旅程时序图

```
用户编写 DAG 文件 (dags/ml_pipeline.py)
        │
        │ 1. 放入 dags 目录
        ▼
DAG Processor 扫描并导入
        │
        │ 2. 解析 DAG 对象
        ▼
序列化 DAG → 写入 serialized_dag 表
        │
        │ 3. Scheduler 读取序列化 DAG
        ▼
Scheduler 检查 schedule_interval
        │
        │ 4. 到达调度时间
        ▼
创建 DAG Run (execution_date = 2026-07-01)
        │
        │ 5. 创建 TaskInstance
        ▼
每个 Task 生成一次 TI，初始状态 none
        │
        │ 6. 依赖检查
        ▼
上游成功？资源池够？并发够？
        │
        ├── 否 → 继续等待
        │
        └── 是
             │
             │ 7. 状态改为 scheduled
             ▼
             scheduled
             │
             │ 8. 调用 Executor.queue_command
             ▼
             queued
             │
             │ 9. Worker 拉取并执行
             ▼
             running
             │
             │ 10. 任务完成
             ▼
        success / failed / skipped
             │
             │ 11. 写回 XCom 与日志
             ▼
        Metadata DB 更新
```

## 4.2 阶段详解

### 阶段 1：DAG 文件解析

DAG Processor 定期扫描 `dags/` 目录，对每个文件：

1. 导入 Python 模块。
2. 实例化 DAG 对象。
3. 校验 DAG 是否无环。
4. 序列化成 JSON/Blob。
5. 写入 `dag` 表的 `serialized_dag` 字段。

### 阶段 2：创建 DAG Run

Scheduler 读取 `dag` 表，对每个活跃的 DAG：

- 根据 `schedule_interval` 计算下一个 execution_date。
- 如果该 execution_date 还没有 DAG Run，则创建。
- 设置 DAG Run 状态为 `queued` 或 `running`。

### 阶段 3：创建 TaskInstance

DAG Run 创建后，Scheduler 为该 DAG Run 下的每个 Task 创建 TaskInstance：

- `task_id` + `dag_id` + `run_id` 唯一标识一个 TaskInstance。
- 初始状态为 `none`。

### 阶段 4：依赖与资源检查

Scheduler 在主循环中检查每个 TaskInstance：

- **上游依赖**：所有直接上游 TaskInstance 状态为 `success`（或满足触发规则）。
- **触发规则**：`all_success`（默认）、`all_failed`、`one_success`、`none_failed` 等。
- **资源池**：`pool_slots` 是否足够。
- **DAG 并发**：`max_active_runs` 是否达到上限。
- **Task 并发**：`task_concurrency` 是否达到上限。
- **SLA**：是否设置了 SLA 告警。

### 阶段 5：TaskInstance 入队

检查通过后：

1. TaskInstance 状态变为 `scheduled`。
2. Scheduler 调用 `Executor.queue_command(ti, command, priority)`。
3. Executor 把任务放入内部队列，状态变为 `queued`。

### 阶段 6：Worker 执行

Worker 从 Executor 拿到任务：

1. 创建子进程/Pod 执行 Task。
2. Task 运行期间状态为 `running`。
3. 执行完成后，返回 exit code 和 XCom。

### 阶段 7：状态回写

Worker 把结果写回 Metadata DB：

- TaskInstance 状态更新为 `success` / `failed` / `skipped`。
- XCom 写入 `xcom` 表。
- 日志写入远程/本地日志存储。

## 4.3 DAG Run 与 TaskInstance 状态机

### DAG Run 状态流转

```
queued → running → success
            │
            └─ failed
```

- 所有 TaskInstance 成功 → DAG Run `success`。
- 有 TaskInstance 失败且不重试 → DAG Run `failed`。

### TaskInstance 状态流转

```
none
  │
  ▼
scheduled
  │
  ▼
queued ←─────────────────────┐
  │                          │
  ▼                          │ (retry)
running → success            │
  │                          │
  ├─ failed → up_for_retry ──┘
  │
  ├─ skipped
  │
  └─ upstream_failed
```

## 4.4 重试机制

Airflow 默认不重试，需要在 DAG 或 Task 级别配置：

```python
default_args = {
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
}
```

重试时：

1. TaskInstance 状态从 `failed` 变为 `up_for_retry`。
2. Scheduler 在 `retry_delay` 后再次检查。
3. 如果满足条件，重新 `scheduled → queued → running`。

## 4.5 回填（Backfill）

当 DAG 新增或需要补历史数据时，可以触发 backfill：

```bash
airflow dags backfill ml_pipeline -s 2026-06-01 -e 2026-06-30
```

- Airflow 会为该区间内的每个 execution_date 创建 DAG Run。
- 支持 `--rerun-failed-tasks` 只重跑失败任务。
- 大规模 backfill 注意并发与资源池限制。

## 4.6 传感器（Sensor）与 Defer

### 传统 Sensor

```python
from airflow.sensors.filesystem import FileSensor

wait_file = FileSensor(
    task_id="wait_file",
    filepath="/data/input/done.flag",
    poke_interval=60,
    timeout=600,
)
```

- Sensor 占一个 worker slot，每隔 `poke_interval` 检查一次。
- 适合检查间隔短、资源充足的场景。

### Deferrable Sensor

```python
wait_file = FileSensor(
    task_id="wait_file",
    filepath="/data/input/done.flag",
    deferrable=True,
)
```

- 第一次执行后进入 `deferred` 状态，释放 worker。
- Triggerer 监听文件事件，触发后唤醒 TaskInstance。

## 4.7 数据驱动调度（Dataset）

Airflow 2.4+ 支持 Dataset 调度：

```python
from airflow.datasets import Dataset

my_dataset = Dataset("s3://bucket/features/2026-07-01.parquet")

with DAG("consumer", schedule=[my_dataset], ...):
    consume = PythonOperator(task_id="consume", ...)
```

- 当 `my_dataset` 被任意 DAG 的 `outlets` 更新后，下游 DAG 自动触发。
- 从“时间驱动”演进到“数据驱动”。

## 本章小结

- 完整链路：**DAG 文件 → DAG Processor → 序列化 → Scheduler → DAG Run → TaskInstance → Executor → Worker → 状态回写**。
- Scheduler 负责创建 DAG Run 和推进 TaskInstance 状态机。
- Executor 负责把 TaskInstance 从 scheduled 推进到 running。
- Worker 执行任务并回写状态、日志、XCom。
- 重试、回填、Sensor、Defer、Dataset 是调度流程的扩展机制。

**参考来源**

- [Apache Airflow — DAG Runs](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dag-run.html)
- [Apache Airflow — Tasks](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/tasks.html)
- [Apache Airflow — Scheduler](https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/scheduler.html)
- [Apache Airflow — Deferring](https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/deferring.html)
- [Apache Airflow — Datasets](https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/datasets.html)

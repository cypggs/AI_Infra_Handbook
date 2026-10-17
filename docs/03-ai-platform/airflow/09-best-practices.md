# 9. 最佳实践：DAG 设计、依赖管理与运维

> 一句话理解：Airflow 生产实践的核心是 **“DAG 设计合理、依赖清晰、资源可控、可测试、可观测”**——好 DAG 像好代码一样，需要结构、规范和持续维护。

## 9.1 DAG 设计原则

### 一个 DAG 只做一件事

不要把整个公司的 ETL 塞到一个 DAG 里。按业务域拆分：

- `user_profile_pipeline`
- `recommendation_training_pipeline`
- `feature_store_refresh_pipeline`

### 任务粒度适中

| 粒度 | 问题 |
|---|---|
| 太粗 | 一个任务失败影响大，重跑成本高 |
| 太细 | 调度开销大，DAG 复杂难维护 |

建议：

- 一个 Task 对应一个可独立重试的业务单元。
- 上下游有明确数据依赖时再拆分。

### 显式依赖优于隐式依赖

```python
# 好：依赖清晰
extract >> transform >> load

# 不好：靠时间间隔间接依赖
t1 = BashOperator(task_id="t1", bash_command="sleep 3600")
t2 = BashOperator(task_id="t2", bash_command="...")  # 假设 t1 已完成
```

## 9.2 避免长事务与状态外溢

- Task 应该是幂等的：多次执行结果一致。
- 不要把 Airflow 当成状态机数据库，业务状态应放在外部系统。
- 避免一个 Task 执行数小时；必要时拆分成多个 Task 或使用 Task Group。

## 9.3 使用 Task Group 组织任务

### Task Group

Airflow 2.0+ 推荐用 Task Group 组织相关任务：

```python
from airflow.utils.task_group import TaskGroup

with DAG("demo", ...) as dag:
    with TaskGroup("feature_engineering") as fe:
        encode = PythonOperator(task_id="encode", ...)
        scale = PythonOperator(task_id="scale", ...)
        select = PythonOperator(task_id="select", ...)
        encode >> scale >> select

    train = PythonOperator(task_id="train", ...)
    fe >> train
```

### SubDAG（已移除）

- Airflow 3.0 已**彻底移除** SubDAG（2.x 中即标记废弃）。
- 复用需求用 Task Group、Dynamic Task Mapping，或单独 DAG + TriggerDagRunOperator。

## 9.4 动态任务映射与 Task Loops

Airflow 2.3+ 支持 Dynamic Task Mapping：

```python
from airflow.decorators import task

@task
def process_file(file: str):
    ...

with DAG("demo", ...) as dag:
    files = ["a.csv", "b.csv", "c.csv"]
    process_file.expand(file=files)
```

- 适合并行处理列表中的元素。
- 避免手动生成大量相似 Task。

### Task Loops（AIP-111，3.4）

3.4 引入的 Task Loops 是动态映射的“串行版”：装饰器任务组可调用 `.loop()` 按运行期决定的次数重复执行，支持 `until` 条件（do-while 语义：至少执行一次）与 `max_iterations` 上限；每次迭代可使用上一次的结果，迭代内任务仍可并行。适合“迭代到收敛”的场景（如分页拉全量、重复训练直到指标达标），而 Dynamic Task Mapping 适合无状态并行展开。

## 9.5 传感器与 Defer 的最佳实践

### 优先使用 Deferrable Operator

```python
# 推荐
wait = S3KeySensor(
    task_id="wait_s3",
    bucket_key="s3://bucket/done.flag",
    deferrable=True,
)

# 不推荐（占用 worker）
wait = S3KeySensor(
    task_id="wait_s3",
    bucket_key="s3://bucket/done.flag",
    poke_interval=60,
    timeout=3600,
)
```

### 控制 Sensor 数量

- 大量 Sensor 会消耗 Triggerer 资源。
- 优先用 **Asset / Asset 分区调度**（3.x）替代轮询：上游产出即触发，而不是定时去“看”。

## 9.6 XCom 使用规范

- **只传小数据**：路径、ID、配置、元数据。
- **不传大数据集**：用对象存储或数据库传递数据。
- **自定义 backend**：当 XCom 数据量大时，配置 S3/GCS backend。

```python
# 好：传路径
ti.xcom_push(key="output_path", value="s3://bucket/output/data.parquet")

# 不好：传整个 DataFrame
ti.xcom_push(key="data", value=df)  # 可能撑爆 Metadata DB
```

## 9.7 资源隔离

### Pool

用 Pool 限制并发资源：

```python
heavy_task = PythonOperator(
    task_id="heavy",
    pool="gpu_pool",
    pool_slots=1,
    ...
)
```

### Queue（CeleryExecutor）

把不同类型任务路由到不同 Worker：

```python
gpu_task = PythonOperator(
    task_id="gpu",
    queue="gpu_workers",
    ...
)
```

### Kubernetes Pod 资源

```python
k8s_task = KubernetesPodOperator(
    task_id="k8s",
    namespace="airflow",
    image="my-image:latest",
    resources={"request_memory": "1Gi", "limit_memory": "2Gi"},
)
```

## 9.8 测试 DAG

### DAG 完整性测试

```python
from airflow.models import DagBag

def test_dag_loaded():
    dag_bag = DagBag(dag_folder="dags")
    assert len(dag_bag.import_errors) == 0
    assert "my_dag" in dag_bag.dags
```

### Task 逻辑单元测试

把 Task 的核心逻辑抽到纯函数，单独测试：

```python
def transform_data(input_path: str, output_path: str):
    ...

def test_transform_data(tmp_path):
    ...
```

### CI 中运行 DAG 解析

```bash
airflow dags list
airflow dags test my_dag 2026-10-17
```

Airflow 3 迁移期建议在 CI 中加入 ruff 规则，阻止 2.x 写法回流：

```bash
ruff check dags/ --select AIR301,AIR302 --preview
```

## 9.9 善用 Airflow 3 新能力（3.x 项目优先）

| 场景 | 旧做法（2.x 习惯） | Airflow 3 推荐 |
|---|---|---|
| 导入 DAG/Task | `from airflow import DAG` | `from airflow.sdk import DAG, task`（稳定契约） |
| 上游就绪触发 | 定时 Sensor 轮询 | Asset / Asset 分区调度（3.2+） |
| 错过时间告警 | `sla=` 参数（3.0 已移除） | Deadline Alerts（AIP-86，3.1+） |
| 人工审批 | 外部系统 + 状态轮询 | HITL / Approval 任务（3.1+，`awaiting_input`） |
| 增量处理游标 | 自建 KV 表存水位 | Task/Asset 状态存储（AIP-103，3.3） |
| 重试策略 | 每个任务写 retries/backoff | 可插拔重试策略（AIP-105，3.3） |
| 补历史数据 | CLI backfill 黑盒 | Scheduler 托管 backfill：UI/API 可见可停（AIP-78） |
| 资产事件消费（3.4+） | 默认一次 Run 吞掉所有排队事件 | 默认每个事件一个 DAG Run；确需批处理时显式 `batch_asset_events=True` |
| 迭代到收敛 | 外挂脚本 + TriggerDagRun 循环 | Task Loops（AIP-111，3.4，`.loop()` + `until`/`max_iterations`） |

## 9.10 回填与补数

- 使用 `airflow dags backfill` 补历史数据。
- 大规模 backfill 前调整 `max_active_runs` 和 `concurrency`。
- 避免在生产高峰期触发大规模 backfill。

## 9.11 版本控制与代码规范

- DAG 代码必须进 Git。
- 使用 `pre-commit` 做格式检查（black、isort、flake8 / ruff）。
- DAG 文件命名规范：`dag_<domain>_<name>.py`。
- 不要硬编码连接信息，使用 Airflow Connections 和 Variables。
- 3.x 项目统一从 `airflow.sdk` 导入编写接口，CI 用 ruff `AIR301/AIR302` 兜底。

## 9.12 常见反模式

| 反模式 | 问题 | 改进 |
|---|---|---|
| 一个 DAG 上百个 Task | 难维护、难排错 | 拆分成多个 DAG 或 Task Group |
| 用 BashOperator 调 Python | 丢失异常和日志 | 用 PythonOperator |
| 任务内部访问 Airflow DB | 耦合高、Airflow 3 禁止 | 用 XCom 或外部存储 |
| 把 Airflow 当消息队列 | 不适合实时 | 用 Kafka / 专用队列 |
| 不设置 retries | 偶发失败无自动恢复 | 配置合理的 retries 和 retry_delay（3.3 可用可插拔重试策略 AIP-105） |
| XCom 传大对象 | 撑爆 Metadata DB | 用 S3/GCS 传递数据 |

## 本章小结

- DAG 按业务域拆分，任务粒度适中，依赖显式表达。
- 优先使用 Task Group、Dynamic Task Mapping（3.4 起还有串行迭代的 Task Loops）、Deferrable Operator。
- XCom 只传小数据，大数据用对象存储。
- 用 Pool、Queue、K8s 资源限制做资源隔离。
- DAG 需要解析测试、Task 逻辑单元测试、CI 集成（3.x 加 ruff `AIR301`）。
- Airflow 3 新范式：Asset 触发替代轮询、Deadline 替代 SLA、HITL 审批、状态存储替代自建水位表。

**参考来源**

- [Apache Airflow — Best Practices](https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html)
- [Apache Airflow — Dynamic Task Mapping](https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/dynamic-task-mapping.html)
- [Apache Airflow — Task Loops (AIP-111, 3.4)](https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/loops.html)
- [Apache Airflow — Deferring](https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/deferring.html)
- [Apache Airflow — Task Groups](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dags.html#task-groups)
- [Apache Airflow — Upgrading to Airflow 3](https://airflow.apache.org/docs/apache-airflow/stable/installation/upgrading_to_airflow3.html)

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
- 避免一个 Task 执行数小时；必要时拆分成多个 Task 或使用子 DAG / Task Group。

## 9.3 使用 Task Group 和 SubDAG

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

### SubDAG（不推荐新项目使用）

- 历史遗留机制，已被 Task Group 取代。
- 如果有复杂复用需求，考虑用 Dynamic Task Mapping 或单独 DAG + TriggerDagRunOperator。

## 9.4 动态任务映射

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
- 考虑用 Dataset/Asset 调度替代轮询。

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
airflow dags test my_dag 2026-07-01
```

## 9.9 回填与补数

- 使用 `airflow dags backfill` 补历史数据。
- 大规模 backfill 前调整 `max_active_runs` 和 `concurrency`。
- 避免在生产高峰期触发大规模 backfill。

## 9.10 版本控制与代码规范

- DAG 代码必须进 Git。
- 使用 `pre-commit` 做格式检查（black、isort、flake8）。
- DAG 文件命名规范：`dag_<domain>_<name>.py`。
- 不要硬编码连接信息，使用 Airflow Connections 和 Variables。

## 9.11 常见反模式

| 反模式 | 问题 | 改进 |
|---|---|---|
| 一个 DAG 上百个 Task | 难维护、难排错 | 拆分成多个 DAG 或 Task Group |
| 用 BashOperator 调 Python | 丢失异常和日志 | 用 PythonOperator |
| 任务内部访问 Airflow DB | 耦合高、Airflow 3 禁止 | 用 XCom 或外部存储 |
| 把 Airflow 当消息队列 | 不适合实时 | 用 Kafka / 专用队列 |
| 不设置 retries | 偶发失败无自动恢复 | 配置合理的 retries 和 retry_delay |
| XCom 传大对象 | 撑爆 Metadata DB | 用 S3/GCS 传递数据 |

## 本章小结

- DAG 按业务域拆分，任务粒度适中，依赖显式表达。
- 优先使用 Task Group、Dynamic Task Mapping、Deferrable Operator。
- XCom 只传小数据，大数据用对象存储。
- 用 Pool、Queue、K8s 资源限制做资源隔离。
- DAG 需要解析测试、Task 逻辑单元测试、CI 集成。
- 避免反模式：巨型 DAG、硬编码连接、XCom 传大数据、把 Airflow 当队列。

**参考来源**

- [Apache Airflow — Best Practices](https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html)
- [Apache Airflow — Dynamic Task Mapping](https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/dynamic-task-mapping.html)
- [Apache Airflow — Deferring](https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/deferring.html)
- [Apache Airflow — Task Groups](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dags.html#task-groups)

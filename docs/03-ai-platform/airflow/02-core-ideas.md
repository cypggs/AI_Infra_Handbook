# 2. 核心思想：DAG、Operator、Executor 与状态机

> 一句话理解：Airflow 把“工作流”抽象成 **DAG（有向无环图）**，把“工作单元”抽象成 **Task**，把“任务执行”委托给 **Executor**，把所有状态存在 **Metadata Database** 里——理解这四个抽象，就理解了 Airflow 的骨架。

## 2.1 核心概念全景

```
DAG (workflow)
    │
    ├─ Task A (Operator instance)
    │     └─ TaskInstance A (一次具体执行)
    │
    ├─ Task B
    │     └─ TaskInstance B
    │
    └─ Task C
          └─ TaskInstance C

DAG Run = 一次 DAG 执行（对应某个 execution_date / logical_date）
TaskInstance = 某个 Task 在某次 DAG Run 中的具体执行
```

### 概念对照表

| 概念 | 含义 | 示例 |
|---|---|---|
| **DAG** | 有向无环图，描述一组 Task 及其依赖 | `ml_training_pipeline` |
| **Operator** | Task 的模板/工厂，定义“做什么” | `PythonOperator`、`BashOperator`、`KubernetesPodOperator` |
| **Task** | Operator 的实例，DAG 中的节点 | `preprocess_data` |
| **TaskInstance** | 某次 DAG Run 中 Task 的一次具体执行 | `preprocess_data @ 2026-07-01` |
| **DAG Run** | DAG 的一次完整执行 | `ml_training_pipeline @ 2026-07-01` |
| **Execution Date / Logical Date** | DAG Run 对应的逻辑时间 | `2026-07-01 00:00:00` |
| **Executor** | 决定 TaskInstance 在哪里执行 | `LocalExecutor`、`CeleryExecutor`、`KubernetesExecutor` |
| **XCom** | 任务间数据交换（cross-communication） | `ti.xcom_push(key='model_path', value=...)` |

## 2.2 DAG：用 Python 写工作流

DAG 是 Airflow 的核心抽象。**Airflow 3 起，推荐的编写接口来自独立的 Task SDK**（`from airflow.sdk import DAG`），它与核心包解耦、向前兼容，是稳定的公开契约；旧的 `from airflow import DAG` 在 3.x 仍然可用。

一个最简单的 DAG：

```python
# Airflow 3 推荐写法（Task SDK）
from airflow.sdk import DAG, task
from datetime import datetime, timedelta

with DAG(
    dag_id="hello_airflow",
    start_date=datetime(2026, 7, 1),
    schedule=timedelta(days=1),
    catchup=False,
) as dag:

    @task
    def say_hello():
        print("Hello Airflow!")

    say_hello()
```

> Airflow 2 迁移注意：2.x 的 `from airflow.operators.python import PythonOperator` 等导入在 3.x 多已迁移到 `airflow.sdk` 或 provider 包，可用 ruff 规则 `AIR301` 自动改写（见第 8 章）。

### DAG 的关键属性

| 属性 | 说明 |
|---|---|
| `dag_id` | 全局唯一标识 |
| `start_date` | DAG 首次生效日期 |
| `schedule` / `schedule_interval` | 调度周期，可以是 cron 表达式、timedelta、Dataset |
| `catchup` | 是否补跑 start_date 到当前之间的所有 DAG Run |
| `max_active_runs` | 同一 DAG 并发运行的最大 DAG Run 数 |
| `default_args` | 默认参数（如 owner、retries、retry_delay） |

### 依赖表达

Airflow 用位运算表达依赖：

```python
with DAG("demo", ...) as dag:
    a = BashOperator(task_id="a", bash_command="echo a")
    b = BashOperator(task_id="b", bash_command="echo b")
    c = BashOperator(task_id="c", bash_command="echo c")

    a >> b >> c      # a → b → c
    [a, b] >> c     # a 和 b 都完成后 c 才执行
```

## 2.3 Operator：任务的模板

Operator 是“Task 的类”。Airflow 提供大量内置 Operator，也支持自定义。

### 常见 Operator

| Operator | 用途 |
|---|---|
| `PythonOperator` | 执行 Python 函数 |
| `BashOperator` | 执行 Bash 命令 |
| `KubernetesPodOperator` | 在 K8s Pod 中运行容器 |
| `DockerOperator` | 运行 Docker 容器 |
| `SparkSubmitOperator` | 提交 Spark 任务 |
| `SnowflakeOperator` | 执行 Snowflake SQL |
| `S3FileTransformOperator` | S3 文件转换 |
| `EmailOperator` | 发送邮件 |

### Operator vs Task

- **Operator** 是类（class），定义“怎么执行”。
- **Task** 是 Operator 实例化后的对象，属于某个 DAG。
- 同一个 Operator 可以在多个 DAG 里创建多个 Task。

## 2.4 Executor：任务执行的调度器

Executor 决定 TaskInstance 在哪里、以什么方式运行。这是 Airflow 扩展性的关键。

| Executor | 特点 | 适用场景 |
|---|---|---|
| **SequentialExecutor** | 单进程顺序执行 | 默认开发/测试，不能用于生产 |
| **LocalExecutor** | 本地多进程/多线程并行 | 单机中小规模 |
| **CeleryExecutor** | 基于 Celery + 消息队列分发到多个 worker | 传统多机扩展（Airflow 3 起在 `providers/celery` 包） |
| **KubernetesExecutor** | 每个 Task 启动一个 K8s Pod | 云原生、弹性扩缩（Airflow 3 起在 `providers/cncf/kubernetes` 包） |
| **EdgeExecutor** | 边缘 worker 出站 HTTPS 轮询中心 API（AIP-69，3.x） | 混合云、数据主权、受限网络 |
| **LocalKubernetesExecutor** | 本地 + K8s 混合 | 混合工作负载 |
| **CeleryKubernetesExecutor** | Celery + K8s 混合 | 混合工作负载 |

> 注：Airflow 3.0 把 Celery/Kubernetes Executor 移出核心包（DaskExecutor 则被完全移出核心），核心只保留 Local/Sequential；生产部署按需安装对应 provider。

### Executor 选型建议

- **开发/CI**：SequentialExecutor 或 LocalExecutor。
- **中小规模生产**：LocalExecutor（单台大机器）或 CeleryExecutor。
- **K8s 原生/弹性需求**：KubernetesExecutor。
- **Worker 在异构/受限网络**（on-prem、客户环境、多公有云）：EdgeExecutor。
- **混合**：Airflow 2.10+/3.x 的多 Executor 能力，把轻量任务放 Local、重任务放 K8s。

## 2.5 状态机：TaskInstance 与 DAG Run

### TaskInstance 状态

| 状态 | 含义 |
|---|---|
| `none` | 尚未调度 |
| `scheduled` | Scheduler 已安排，等待资源 |
| `queued` | 已放入 Executor 队列 |
| `running` | 正在执行 |
| `success` | 成功 |
| `failed` | 失败 |
| `skipped` | 因依赖条件被跳过 |
| `upstream_failed` | 上游失败导致无法执行 |
| `up_for_retry` | 等待重试 |
| `deferred` | 进入 deferrable 状态，等待 Triggerer 唤醒 |
| `sensing` | Sensor 正在轮询 |

状态流转示意：

```
none → scheduled → queued → running → success
                    │
                    ├─ failed → up_for_retry → queued
                    │
                    └─ upstream_failed / skipped / deferred
```

### DAG Run 状态

| 状态 | 含义 |
|---|---|
| `queued` | 已排队等待运行 |
| `running` | 有 TaskInstance 正在执行 |
| `success` | 所有 TaskInstance 成功 |
| `failed` | 有 TaskInstance 失败且无法重试 |

## 2.6 XCom：任务间数据交换

XCom（cross-communication）是 Task 之间传递小数据的机制。

```python
def extract(**context):
    data = {"rows": 1000}
    context["ti"].xcom_push(key="extract_result", value=data)

def transform(**context):
    ti = context["ti"]
    data = ti.xcom_pull(task_ids="extract", key="extract_result")
    print(f"Got {data['rows']} rows")

with DAG("xcom_demo", ...) as dag:
    t1 = PythonOperator(task_id="extract", python_callable=extract)
    t2 = PythonOperator(task_id="transform", python_callable=transform)
    t1 >> t2
```

### XCom 的注意点

- 默认存储在 Metadata Database（SQLite/PostgreSQL/MySQL），不适合传大对象。
- Airflow 2.5+ 支持自定义 XCom backend（如 S3、GCS），可传大 payload。
- 推荐只传元数据（路径、ID、小配置），不要传整个数据集。

## 2.7 Deferrable Operator 与 Triggerer

传统 Sensor 会占住一个 worker slot 一直轮询，资源浪费。Airflow 2.2+ 引入 **Deferrable Operator**：

- Task 执行到等待点时，把状态设为 `deferred`，释放 worker。
- **Triggerer** 是独立进程，负责异步监听事件（如 S3 文件到达、外部 API 回调）。
- 事件发生后，Triggerer 通知 Scheduler 把 TaskInstance 重新置为 `scheduled`。

典型场景：

- 等待 S3 文件出现（`S3KeySensor` 的 deferrable 模式）。
- 等待外部批处理完成。
- 等待消息队列中的事件。

## 2.8 Asset 调度（原 Dataset）

Airflow 2.4 引入 **Dataset 调度**，Airflow 3 将其全面演进为 **Asset（AIP-74/75）**：从“时间驱动”扩展到“数据驱动”。

```python
# Airflow 3 写法
from airflow.sdk import dag, task, Asset

my_asset = Asset("s3://bucket/output/data.parquet")

@dag(schedule="@daily", ...)
def producer():
    @task(outlets=[my_asset])
    def generate():
        ...
    generate()

@dag(schedule=my_asset, ...)
def consumer():
    ...
```

- 上游产出方在 `outlets` 声明资产，下游用 `schedule=[asset]` 订阅；资产被更新即触发下游。
- 支持 `@asset` 装饰器（一个 DAG 对应一个产资产任务）、资产别名（AssetAlias）、资产附加信息（extras）。
- **AND/OR 组合**：`schedule=a & b` 等待全部、`a | b` 任一即可，还有 `AssetOrTimeSchedule` 混合时间/事件。
- **Asset 分区（3.2+，AIP-76）**：下游可按资产分区（如按天的 `s3://bucket/dt=2026-10-17/`）粒度触发，3.3 进一步提供 Rollup/FanOut 等分区映射器——这是增量数据管道的事件驱动基础。
- **3.4 行为变化**：单资产与 `a | b` 表达式默认**每个资产事件触发一个 DAG Run**（不再把所有排队事件合并进一次 Run）；需要批处理时显式 `batch_asset_events=True`。多资产 AND 条件与 RollupMapper 分区调度仍默认批处理。
- **3.4 清理**：`Dataset` 旧别名从 `airflow` 模块移除（此前从 `airflow.sdk` 导入 `Dataset` 已报弃用），统一用 `Asset`。

## 本章小结

- **DAG**：用 Python 定义的工作流，包含有向无环的 Task 依赖；Airflow 3 起推荐 `airflow.sdk` 编写接口。
- **Operator / Task / TaskInstance**：类 → 实例 → 某次具体执行。
- **Executor**：决定 TaskInstance 在哪里执行；3.x 插件化（Celery/K8s 移入 provider），新增 Edge Executor。
- **状态机**：TaskInstance 从 none → scheduled → queued → running → success / failed，支持重试和 defer。
- **XCom**：任务间传小数据，默认存在 Metadata DB，大数据用自定义 backend。
- **Deferrable Operator + Triggerer**：异步等待不占用 worker slot。
- **Asset（原 Dataset）**：从时间驱动到数据驱动，3.2+ 支持分区粒度的事件触发，3.4 起单资产/或表达式默认每事件一个 DAG Run。

**参考来源**

- [Apache Airflow — Core Concepts](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/index.html)
- [Apache Airflow — DAGs](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dags.html)
- [Apache Airflow — Operators](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/operators.html)
- [Apache Airflow — Executor](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/executor/index.html)
- [Apache Airflow — XComs](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/xcoms.html)
- [Apache Airflow — Deferrable Operators](https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/deferring.html)
- [Apache Airflow — Data-aware scheduling with Assets](https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/assets.html)

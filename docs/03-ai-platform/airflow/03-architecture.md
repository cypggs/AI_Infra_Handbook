# 3. 架构设计：Scheduler、Executor、Worker 与 Metadata DB

> 一句话理解：Airflow 的架构是 **“一个 Metadata Database + 多个无状态/有状态组件协作”**——DAG Processor 解析 DAG 文件，Scheduler 创建 DAG Run 和 Task Instance，Executor 分发任务，Worker 执行任务，Webserver/UI 提供人机接口，Triggerer 处理异步事件。

## 3.1 总体架构

```
┌──────────────────────────────────────────────────────────────────────┐
│                         用户 / CLI / REST / UI                        │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
            ┌───────────────────┴───────────────────┐
            │                                       │
            ▼                                       ▼
┌───────────────────────────┐           ┌───────────────────────────┐
│       Webserver / UI      │           │    REST API (FastAPI)     │
│  可视化 DAG、触发运行、     │           │  程序化操作 DAG/Run/Log   │
│  查看日志与状态             │           │                           │
└───────────┬───────────────┘           └───────────┬───────────────┘
            │                                       │
            └───────────────────┬───────────────────┘
                                │
                                ▼
                  ┌─────────────────────────┐
                  │   Metadata Database     │
                  │ PostgreSQL / MySQL /    │
                  │ SQLite (dev only)       │
                  │                         │
                  │ DAGs, DAG Runs, Task    │
                  │ Instances, XComs, Logs, │
                  │ Variables, Connections  │
                  └───────────┬─────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐   ┌─────────────────┐   ┌─────────────────┐
│ DAG Processor │   │    Scheduler    │   │    Triggerer    │
│ 解析 DAG 文件  │   │ 创建 Run / TI   │   │ 监听异步事件    │
│ 序列化 DAG     │   │ 状态机推进      │   │ 唤醒 deferred   │
└───────────────┘   └────────┬────────┘   └─────────────────┘
                             │
            ┌────────────────┴────────────────┐
            │                                 │
            ▼                                 ▼
┌─────────────────────┐           ┌─────────────────────┐
│      Executor       │           │       Worker        │
│  Local / Celery /   │           │ 执行 TaskInstance   │
│  Kubernetes / Dask  │           │ 返回状态与 XCom     │
└─────────────────────┘           └─────────────────────┘
```

## 3.2 各组件职责

| 组件 | 职责 | 部署特性 |
|---|---|---|
| **Metadata Database** | 存储 DAG、DAG Run、TaskInstance、XCom、Variable、Connection 等所有状态 | 生产必须用 PostgreSQL/MySQL |
| **DAG Processor** | 扫描 DAG 文件目录，解析并序列化 DAG，写入数据库 | Airflow 2.3+ 独立进程 |
| **Scheduler** | 决定何时创建 DAG Run、何时把 TaskInstance 推进到 queued/running | 高可用可部署多副本 |
| **Executor** | 接收 Scheduler 的调度请求，把 TaskInstance 放到执行环境 | 决定扩展模式 |
| **Worker** | 实际执行 TaskInstance 的进程/Pod | Celery/K8s/本地 |
| **Triggerer** | 处理 Deferrable Operator 的异步触发器 | Airflow 2.2+ |
| **Webserver / UI** | 提供可视化界面、REST API | 无状态，可多副本 |
| **API Server** | Airflow 3 演进为独立 FastAPI 服务，JWT 认证 | Airflow 3 架构变化 |

## 3.3 Metadata Database

Metadata Database 是 Airflow 的“大脑”，所有状态都集中在这里。

### 核心表

| 表 | 作用 |
|---|---|
| `dag` | DAG 元数据、序列化后的 DAG、是否暂停 |
| `dag_run` | 每次 DAG Run 的记录 |
| `task_instance` | 每个 Task 每次运行的状态 |
| `task_fail` | Task 失败记录 |
| `xcom` | 任务间交换的数据 |
| `variable` | 全局变量 |
| `connection` | 外部系统连接信息 |
| `log` | 操作日志 |
| `job` | Scheduler/Triggerer 等 job 心跳 |
| `slot_pool` | 资源池限制 |

### 生产数据库选型

| 数据库 | 推荐度 | 说明 |
|---|---|---|
| PostgreSQL | ⭐⭐⭐⭐⭐ | 生产首选，性能与稳定性好 |
| MySQL | ⭐⭐⭐ | 可用，注意字符集与连接池 |
| SQLite | ❌ | 仅本地开发 |

## 3.4 DAG Processor

DAG Processor 负责把磁盘上的 DAG 文件变成数据库里的序列化 DAG。

### 工作流程

```
DAG 文件目录 (dags/)
        │
        ▼
DAG Processor 扫描文件变化
        │
        ▼
导入 Python 模块，实例化 DAG
        │
        ▼
序列化 DAG (pickle / JSON)
        │
        ▼
写入 dag 表 (serialized_dag 字段)
        │
        ▼
Scheduler 读取序列化 DAG 做调度决策
```

### 关键点

- Airflow 2.3+ 把 DAG Processor 从 Scheduler 中拆出，避免 DAG 解析阻塞调度。
- 解析失败会记录到 `dag_processing.processing_stats` 和 UI 的 DAG import errors。
- 大型 DAG 文件会增加解析时间，影响调度延迟。

## 3.5 Scheduler

Scheduler 是 Airflow 的心脏，主要做两件事：

1. **创建 DAG Run**：根据 `schedule_interval` 创建新的 DAG Run。
2. **推进 TaskInstance**：检查依赖和状态，把可运行的 TaskInstance 发给 Executor。

### Scheduler 主循环

```
循环（每隔 min_file_process_interval / scheduler_idle_sleep_time）
    │
    ├─ 1. 从 Metadata DB 读取 active DAGs
    │
    ├─ 2. 对需要调度的 DAG 创建 DAG Run
    │
    ├─ 3. 对每个 DAG Run，找出依赖已满足的 TaskInstance
    │
    ├─ 4. 检查资源池、并发限制、SLA
    │
    ├─ 5. 把 TaskInstance 状态改为 scheduled → queued
    │
    └─ 6. 调用 Executor 的 queue_command
```

### Scheduler 高可用

- Airflow 2.0+ Scheduler 支持 HA，多个 Scheduler 实例通过数据库行锁协作。
- 用 `max_threads` 和 `processor_poll_interval` 等参数调优。

## 3.6 Executor 详解

### LocalExecutor

```
Scheduler
    │
    ▼
LocalExecutor 的进程池
    │
    ├─ Worker 进程 1
    ├─ Worker 进程 2
    └─ Worker 进程 N
```

- 单机多进程并行。
- 适合中小规模，部署简单。

### CeleryExecutor

```
Scheduler
    │
    ▼
Celery + Redis/RabbitMQ 消息队列
    │
    ├─ Celery Worker 1
    ├─ Celery Worker 2
    └─ Celery Worker N
```

- 传统多机扩展方案，成熟稳定。
- 需要额外维护 Redis/RabbitMQ 和 Celery Worker。

### KubernetesExecutor

```
Scheduler
    │
    ▼
Kubernetes API Server
    │
    ▼
为每个 TaskInstance 创建一个 Pod
```

- 每个任务一个 Pod，资源隔离好，弹性强。
- 启动 Pod 有 overhead，不适合超短任务。
- 需要 K8s 集群和镜像管理。

### Executor 对比

| 维度 | LocalExecutor | CeleryExecutor | KubernetesExecutor |
|---|---|---|---|
| 扩展性 | 单机 | 多机 | 多机 + 弹性 |
| 运维复杂度 | 低 | 中 | 高 |
| 任务隔离 | 进程级 | 进程级 | Pod 级 |
| 启动延迟 | 低 | 低 | 中（Pod 创建） |
| 适用任务 | 通用 | 通用 | 容器化、异构 |

## 3.7 Triggerer

Triggerer 是 Airflow 2.2+ 新增的组件，专门处理 Deferrable Operator。

```
TaskInstance (deferred)
        │
        ▼
Scheduler 把 Trigger 注册到 Triggerer
        │
        ▼
Triggerer 异步监听事件
        │
        ▼
事件触发 → Scheduler 唤醒 TaskInstance
        │
        ▼
TaskInstance 重新进入 queued → running
```

### 为什么需要 Triggerer

- 传统 `S3KeySensor` 占一个 worker 进程一直轮询。
- Deferrable 模式下，worker 只执行一次就进入 deferred，释放资源。
- Triggerer 用 asyncio 同时监听大量事件，单进程可处理很多 trigger。

## 3.8 Airflow 3 架构演进

Airflow 3 正在做重大架构调整：

- **Task 不再直接访问 Metadata DB**：通过 Execution API 与 Scheduler 通信。
- **Execution API**：基于 gRPC/HTTP，任务执行器通过 API 拉取任务、上报状态。
- **JWT 认证**：Execution API 使用 JWT token 做认证，提升安全性。
- **解耦 Scheduler 与 Worker**：Worker 不需要数据库连接字符串，降低攻击面。

## 本章小结

- Airflow 架构 = Metadata DB + DAG Processor + Scheduler + Executor + Worker + Triggerer + Webserver/UI。
- Metadata DB 是所有状态的集中点，生产推荐 PostgreSQL。
- DAG Processor 把 Python DAG 文件解析并序列化到数据库。
- Scheduler 创建 DAG Run 并推进 TaskInstance 状态机。
- Executor 决定任务执行位置，Local/Celery/Kubernetes 各有适用场景。
- Triggerer 让 Deferrable Operator 不占 worker 资源。
- Airflow 3 将向 Execution API + JWT 方向演进，进一步解耦组件。

**参考来源**

- [Apache Airflow — Architecture](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/overview.html)
- [Apache Airflow — Scheduler](https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/scheduler.html)
- [Apache Airflow — DAG File Processing](https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/dag-file-processing.html)
- [Apache Airflow — DAG Serialization](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dags.html#dag-serialization)
- [Apache Airflow — Triggerer](https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/deferring.html)
- [Astronomer — Airflow Components](https://www.astronomer.io/docs/learn/airflow-components)

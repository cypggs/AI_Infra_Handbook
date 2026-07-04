# 8. 企业生产实践：Metadata DB、Executor、K8s 部署与监控

> 一句话理解：Airflow 从“本地 SQLite”到“生产平台”的关键跳跃，是 **Metadata Database、Executor 选型、Worker 部署形态、监控告警、高可用** 这五块的设计和运维。

## 8.1 部署形态选择

### 形态 1：本地开发（SequentialExecutor + SQLite）

```bash
airflow standalone
```

- 优点：一条命令启动，包含 Webserver、Scheduler、Triggerer、SQLite。
- 缺点：不能并发，不能用于生产。

### 形态 2：LocalExecutor + PostgreSQL

```bash
airflow webserver
airflow scheduler
airflow triggerer
```

- 适合：中小规模、单机大内存场景。
- 优点：部署简单。
- 缺点：Scheduler/Webserver 单点，Worker 单机资源受限。

### 形态 3：CeleryExecutor + Redis/RabbitMQ + PostgreSQL

```
PostgreSQL          Redis
    │                  │
    ▼                  ▼
Webserver ←── Scheduler ──→ Celery Workers
              │
              ▼
          Triggerer
```

- 适合：传统多机扩展，任务量中等。
- 优点：成熟稳定，Celery 生态丰富。
- 缺点：需要维护消息队列和 Celery Worker。

### 形态 4：KubernetesExecutor + PostgreSQL

```
PostgreSQL
    │
    ▼
Webserver ←── Scheduler ──→ K8s API Server
              │                   │
              ▼                   ▼
          Triggerer           per-task Pod
```

- 适合：云原生、任务异构、需要强隔离的场景。
- 优点：每个任务一个 Pod，资源隔离好，自动扩缩。
- 缺点：Pod 启动有 overhead，不适合超短任务。

### 形态 5：Airflow on Kubernetes（官方 Helm Chart）

```bash
helm repo add apache-airflow https://airflow.apache.org
helm upgrade --install airflow apache-airflow/airflow \
  --namespace airflow \
  --set executor=KubernetesExecutor
```

- 官方 Helm chart 支持多种 Executor。
- 可配置 PV、Ingress、Redis、PostgreSQL、Worker 资源等。

## 8.2 Metadata Database 选型

| 数据库 | 适用场景 | 注意 |
|---|---|---|
| SQLite | 本地开发 | 不能并发，无 Model Registry 等高级特性 |
| PostgreSQL | 生产首选 | 性能好、稳定、社区支持强 |
| MySQL | 生产可选 | 注意字符集、max_allowed_packet、连接池 |

### 数据库表规模估算

- 每个 DAG Run 产生 N 个 TaskInstance。
- 每个 TaskInstance 可能产生多条 XCom、Log。
- 大规模部署需要：**分区、归档、定期清理**。

Airflow 提供 `db clean` 命令清理历史数据：

```bash
airflow db clean --clean-before-timestamp '2025-01-01' --yes
```

## 8.3 Executor 选型决策树

```
是否需要强隔离 / 异构任务？
    ├── 是 → KubernetesExecutor
    │
    └── 否
         任务量是否大 / 是否需要水平扩展？
              ├── 是 → CeleryExecutor
              │
              └── 否
                   是否只需要单机并发？
                        ├── 是 → LocalExecutor
                        │
                        └── 否 → SequentialExecutor（仅开发）
```

### Airflow 2.10+ 多 Executor

可以在一个 Airflow 实例中配置多个 Executor：

```python
from airflow.executors.local_executor import LocalExecutor
from airflow.providers.cncf.kubernetes.executors.kubernetes_executor import KubernetesExecutor

AIRFLOW__CORE__EXECUTOR = "airflow.executors.local_executor.LocalExecutor"
AIRFLOW__CORE__HYBRID_EXECUTORS = (
    "airflow.executors.local_executor.LocalExecutor,"
    "airflow.providers.cncf.kubernetes.executors.kubernetes_executor.KubernetesExecutor"
)
```

在 Task 级别指定 Executor：

```python
heavy_task = KubernetesPodOperator(
    task_id="heavy_task",
    executor_config={"pod_override": ...},
)
```

## 8.4 高可用与扩展

### Scheduler HA

- Airflow 2.0+ 支持多个 Scheduler 实例。
- 多个 Scheduler 通过数据库行锁协作。
- 推荐至少 2 个 Scheduler，前置 Load Balancer（仅 Webserver 需要）。

### Webserver HA

- Webserver 无状态，可部署多副本。
- 配置 `SECRET_KEY` 一致即可。

### Triggerer HA

- Airflow 2.4+ 支持多个 Triggerer。
- Trigger 在多个 Triggerer 之间分片。

### Worker 扩展

- CeleryExecutor：增加 Celery Worker 副本。
- KubernetesExecutor：依赖 K8s HPA / Cluster Autoscaler。

## 8.5 认证与安全

### Web UI / API 认证

Airflow 2.0+ 支持多种认证后端：

```ini
[webserver]
auth_backend = airflow.providers.fab.auth_manager.api.auth.backend.basic_auth
```

或集成 LDAP/OAuth：

```ini
[webserver]
auth_backend = airflow.providers.fab.auth_manager.api.auth.backend.openid_auth
```

### Connections 加密

- 使用 Secrets Backend（AWS Secrets Manager、HashiCorp Vault、Azure Key Vault）。
- 避免把密码写进代码或 Git。

### Airflow 3 Execution API 与 JWT

Airflow 3 引入 Execution API，Worker 不再直接访问 Metadata DB：

- Scheduler 签发 JWT token 给 Worker。
- Worker 通过 Execution API 拉取任务、上报状态。
- 降低数据库暴露面，提升安全性。

## 8.6 监控与告警

### 关键指标

| 指标 | 工具 | 告警场景 |
|---|---|---|
| DAG Run 成功率 | StatsD / Prometheus | 失败率升高 |
| TaskInstance 排队时间 | StatsD / Prometheus | 队列积压 |
| Scheduler 心跳 / 延迟 | Airflow DB / Prometheus | Scheduler 卡住 |
| Worker / Pod CPU 内存 | Prometheus + Grafana | 资源不足 |
| DAG 解析时间 | Airflow metrics | DAG 文件过大 |
| Metadata DB 连接数 | PostgreSQL exporter | 连接池耗尽 |

### Airflow 内置 StatsD

```ini
[metrics]
statsd_on = True
statsd_host = localhost
statsd_port = 8125
statsd_prefix = airflow
```

### 日志管理

- 配置远程日志存储（S3、GCS、Azure Blob、Elasticsearch）。
- 设置日志保留策略，避免本地磁盘打满。

```ini
[logging]
remote_logging = True
remote_base_log_folder = s3://my-bucket/airflow/logs
remote_log_conn_id = aws_default
```

## 8.7 与 Kubeflow / MLflow / KServe 集成

### Airflow + MLflow

```python
from airflow.providers.http.operators.http import SimpleHttpOperator

training = PythonOperator(
    task_id="train",
    python_callable=train_model,  # 内部调用 mlflow.log_params / log_metric
)

register = PythonOperator(
    task_id="register",
    python_callable=register_model,  # 调用 MLflow Model Registry
)
```

### Airflow + KServe

```python
deploy = KubernetesApplyYamlJinja2Operator(
    task_id="deploy_kserve",
    yaml_file_path="inference_service.yaml",
)
```

### Airflow + Kubeflow Pipelines

- 用 `Airflow` 编排上层业务逻辑。
- 用 `KubeflowPipelineRunOperator` 触发 KFP pipeline。

## 8.8 升级与维护

### 升级 checklist

1. 阅读官方升级指南和 release note。
2. 在 staging 环境验证所有 DAG。
3. 备份 Metadata Database。
4. 按顺序升级 Webserver、Scheduler、Worker。
5. 运行 `airflow db migrate`。
6. 验证 DAG 解析、调度、执行。

### 常见运维问题

| 问题 | 原因 | 解决 |
|---|---|---|
| DAG 不显示 | DAG Processor 未解析成功 | 检查 import errors |
| 任务不调度 | Scheduler 卡住 / DB 连接问题 | 重启 Scheduler，检查 DB |
| Worker 内存爆炸 | 任务内存泄漏 / 并发过高 | 限制并发，增加资源 |
| Pod 启动慢 | KubernetesExecutor image pull | 预热镜像，使用 imagePullSecrets |
| 日志丢失 | 远程日志配置错误 | 检查 connection 和 bucket 权限 |

## 本章小结

- 生产 Airflow = PostgreSQL + 多 Scheduler + 多 Webserver + 合适 Executor + Triggerer。
- Executor 选型：Local 适合单机，Celery 适合多机，Kubernetes 适合云原生/隔离。
- Airflow 2.10+ 支持多 Executor，可把轻量任务和重任务分开。
- 认证、Secrets Backend、远程日志、监控告警是生产必备。
- Airflow 3 将向 Execution API + JWT 演进，提升安全性和解耦。

**参考来源**

- [Apache Airflow — Production Deployment](https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/production-deployment.html)
- [Apache Airflow — Kubernetes Executor](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/executor/kubernetes.html)
- [Apache Airflow — Celery Executor](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/executor/celery.html)
- [Apache Airflow — Logging and Monitoring](https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/logging-monitoring/index.html)
- [Astronomer — Airflow on Kubernetes](https://www.astronomer.io/docs/learn/airflow-kubernetes/)

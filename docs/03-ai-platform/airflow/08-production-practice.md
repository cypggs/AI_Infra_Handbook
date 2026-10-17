# 8. 企业生产实践：Metadata DB、Executor、K8s 部署与监控

> 一句话理解：Airflow 从“本地 SQLite”到“生产平台”的关键跳跃，是 **Metadata Database、Executor 选型、组件拓扑（API Server / DAG Processor / Scheduler / Triggerer）、监控告警、高可用、以及 2→3 迁移** 这几块的设计和运维。注意：**Airflow 2 已于 2026-04-22 EOL**，新部署应直接基于 Airflow 3.1+（当前稳定版 3.3.2）。

## 8.1 部署形态选择

### 形态 1：本地开发

```bash
airflow standalone
```

- 一条命令拉起全部组件（Airflow 3 为 api-server / dag-processor / scheduler / triggerer + SQLite）。
- 不能并发、不能用于生产。

### 形态 2：Airflow 3 单机生产（LocalExecutor + PostgreSQL）

```bash
airflow api-server       # FastAPI：REST API v2 + React UI + Execution API
airflow dag-processor    # 必需组件（3.x 起不再是 scheduler 的一部分）
airflow scheduler
airflow triggerer
```

- 适合中小规模、单机大内存场景；组件可用 systemd / supervisor 托管。

### 形态 3：CeleryExecutor + Redis/RabbitMQ + PostgreSQL

```
PostgreSQL          Redis
    │                  │
    ▼                  ▼
API Server ←── Scheduler ──→ Celery Workers
              │
   dag-processor   Triggerer
```

- Airflow 3 中 CeleryExecutor 位于 `apache-airflow-providers-celery`。
- 成熟稳定，但需要额外维护消息队列和 Celery Worker。

### 形态 4：KubernetesExecutor + PostgreSQL

```
PostgreSQL
    │
    ▼
API Server ←── Scheduler ──→ K8s API Server
    │            │                │
dag-processor  Triggerer      per-task Pod
```

- Airflow 3 中 KubernetesExecutor 位于 `apache-airflow-providers-cncf-kubernetes`。
- 每个任务一个 Pod，隔离好、弹性强；Pod 启动有 overhead，不适合超短任务。

### 形态 5：Edge Executor（混合云 / 数据主权场景，AIP-69）

```
                    ┌─────────── 中心 ───────────┐
                    │ API Server (含 Execution   │
PostgreSQL ──▶ Scheduler / API) + JWT           │
                    └─────────────┬─────────────┘
            出站 HTTPS 轮询        │ 下发任务/接收上报
   ┌────────────────┬─────────────┴──────┐
   ▼                ▼                    ▼
Edge Worker     Edge Worker         Edge Worker
(on-prem)      (客户机房)           (其他公有云)
```

- Worker 侧只需安装 `apache-airflow-providers-edge3`（自带 Task SDK 依赖，`pip install` 一条命令），无需 DB 连接串、无需入站端口；`airflow edge worker` 启动。
- 适合 on-prem 遗留机房、跨云、数据主权受限环境。

### 形态 6：Airflow on Kubernetes（官方 Helm Chart）

```bash
helm repo add apache-airflow https://airflow.apache.org
helm upgrade --install airflow apache-airflow/airflow \
  --namespace airflow \
  --set executor=KubernetesExecutor
```

- 官方 chart 在 3.x 已内置 api-server、dag-processor、triggerer 等全部组件模板。
- 可配置 DAG Bundle（Git 同步）、远程日志、资源限制等。

## 8.2 Metadata Database 选型

| 数据库 | 适用场景 | 注意 |
|---|---|---|
| SQLite | 仅本地开发 | 不能并发，Airflow 3 生产禁选 |
| PostgreSQL | 生产首选 | 性能好、稳定、社区支持强 |
| MySQL | 生产可选 | 注意字符集、max_allowed_packet、连接池 |

### 数据库表规模估算

- 每个 DAG Run 产生 N 个 TaskInstance；每个 TaskInstance 可能产生多条 XCom、Log。
- 3.3 的 Task/Asset 状态存储（AIP-103）也会增加两张状态表（默认有 GC 策略）。
- 大规模部署需要：**分区、归档、定期清理**。

```bash
airflow db clean --clean-before-timestamp '2025-01-01' --yes
```

## 8.3 Executor 选型决策树

```
Worker 是否在 K8s 内 / 是否需要强隔离？
    ├── 是 → KubernetesExecutor
    │
    └── Worker 是否分布在受限网络 / 跨云 / on-prem？
              ├── 是 → EdgeExecutor（3.x，AIP-69）
              │
              └── 任务量是否需要水平扩展？
                       ├── 是 → CeleryExecutor
                       │
                       └── 单机并发 → LocalExecutor（仅开发用 SequentialExecutor）
```

### Airflow 2.10+/3.x 多 Executor

一个实例可配置多个 Executor，轻量任务走 Local、重任务走 K8s：

```python
AIRFLOW__CORE__EXECUTOR = "airflow.executors.local_executor.LocalExecutor"
AIRFLOW__CORE__HYBRID_EXECUTORS = (
    "airflow.providers.cncf.kubernetes.executors.kubernetes_executor.KubernetesExecutor,"
    "airflow.executors.local_executor.LocalExecutor"
)
```

## 8.4 高可用与扩展

| 组件 | HA 方式 |
|---|---|
| API Server | 无状态多副本（3.x）；gunicorn/uvicorn，3.2 起支持零停机 worker 回收 |
| Scheduler | 多副本 + 数据库行锁协作（2.0+ 即支持） |
| DAG Processor | 3.x 为独立进程，可多副本按 bundle 分担 |
| Triggerer | 多副本分片（2.4+） |
| Worker | Celery 加副本 / K8s HPA / Edge 节点横向加机 |

## 8.5 认证与安全

### Airflow 3 认证体系

- **默认 Simple Auth Manager**：开发友好，用户名/密码写在配置里，**生产不建议**。
- **生产推荐 FAB Auth Manager**（`apache-airflow-providers-fab`）：延续 Flask-AppBuilder 的账号体系，支持密码、LDAP、OAuth/OIDC；也可用其他 auth manager provider。
- **API 访问**：REST API v2 支持长期 API token（UI 内自助生成）；bearer/OAuth2 凭证优先于 session cookie。
- **Execution API（任务通道）**：Worker/Task 使用 Scheduler/API Server 签发的**短期 JWT**，按任务发放、结束即失效。

```ini
# Airflow 3 生产示例（FAB 认证管理器）
[core]
auth_manager = airflow.providers.fab.auth_manager.fab_auth_manager.FabAuthManager

[api]
ssl_cert = /etc/airflow/cert.pem
```

### Connections 加密

- 使用 Secrets Backend（AWS Secrets Manager、HashiCorp Vault、GCP Secret Manager、Azure Key Vault）。
- 避免把密码写进代码或 Git。

## 8.6 监控与告警

### 关键指标

| 指标 | 工具 | 告警场景 |
|---|---|---|
| DAG Run 成功率 / Deadline 告警 | StatsD / OTel / Prometheus | 失败率升高、错过 Deadline（AIP-86，3.1 起） |
| TaskInstance 排队时间 | StatsD / OTel / Prometheus | 队列积压 |
| Scheduler 心跳 / 延迟 | Airflow DB / Prometheus | Scheduler 卡住 |
| dag-processor 解析耗时 | Airflow metrics | DAG 文件过大/bundle 拉取慢 |
| API Server 延迟与错误率 | OTel / Prometheus | UI/API 不可用 |
| Worker / Pod CPU 内存 | Prometheus + Grafana | 资源不足 |
| Metadata DB 连接数 | PostgreSQL exporter | 连接池耗尽 |

### Airflow 3 可观测性升级

- **Deadline Alerts（AIP-86）**：取代 2.x 的 SLA，支持参考点配置、同步/异步回调；UI 有 Deadlines 页面。
- **结构化 JSON 日志**（3.2+）：API Server 输出可直接进 Loki/ELK。
- **OpenTelemetry**：3.2 起计时指标改用 Histogram。
- 远程日志存储（S3、GCS、Azure Blob、Elasticsearch）配置方式与 2.x 基本一致。

## 8.7 托管服务动态（2026-10）

| 服务 | Airflow 3 支持现状 |
|---|---|
| **Astronomer Astro** | 最激进：Runtime 3.3-9（2026-10-08）已搭载 Airflow 3.3.2；开源 Airflow 2 EOL 后，Astro 平台把 Airflow 2 支持延长到 **2027-04**（含安全与关键修复，比自托管多一年迁移窗口）；多云、scale-to-zero worker、零停机升级 |
| **Amazon MWAA** | 已支持 Airflow **3.3.1**（2026-09-01 上线，另有 3.2.1 / 3.0.6 / 2.11.2 等镜像），Celery Executor + Fargate worker 自动扩缩；注意 **MWAA 目前不支持 3.2 的 multi-team mode**（与 MWAA 认证、CeleryExecutor 不兼容） |
| **Google Cloud Composer 3** | 2026-01 起支持 Airflow **3.1**（composer-3-airflow-3.1.x 镜像，初为 Preview），2.x 与 3.x 滚动升级，GKE Autopilot 底座 |
| **Azure** | Data Factory 托管 Airflow 仍停留在 2.x，选型需注意 |

> 托管服务跟进节奏差异很大：同样 3.3.2，Astro 在 GA 后数周即搭载（2026-10-08），MWAA 尚停在 3.3.1，Composer 在 3.1——锁定托管服务前先看其版本跟进 SLA 与升级窗口。

## 8.8 与 Kubeflow / MLflow / KServe 集成

### Airflow + MLflow

```python
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

### Airflow + Kubeflow Pipelines / Ray

- 用 Airflow 编排上层业务逻辑，用 KFP 或 KubeRay 的 provider 触发训练 pipeline / RayJob。
- 训练任务通过 Execution API 上报状态，Airflow 只负责编排与门禁（评估不达标不进入部署）。

## 8.9 升级与维护：Airflow 2 → 3 迁移要点

**官方路径：先到 2.11（最后一个 2.x），再升 3.1+（跳过已 EOL 的 3.0）。**

1. **环境准备**：Python 3.9–3.12（3.1+ 支持 3.13，3.2+ 支持 3.14）；`pip install apache-airflow>=2.11`。
2. **DAG 兼容性自动检查**——ruff 规则：

```bash
ruff check dags/ --select AIR301 --preview          # 必须修复（已移除的导入/参数）
ruff check dags/ --select AIR302 --preview --fix    # 建议修复（已弃用写法）
```

3. **ruff 抓不住的语义变化（必须人工核对）**：
   - `data_interval_start/end` 行为变化（3.0 起 cron 默认不再生成 data interval，`create_cron_data_intervals` 默认 False）。
   - 模板变量：`execution_date` → `logical_date`，`prev_ds`/`next_ds` 等移除或改名。
   - `sla=` 参数被移除 → 改用 Deadline Alerts（AIP-86）。
   - SubDAG 移除 → 用 Task Group；pickling（DAG/XCom）移除。
   - `xcom_pull()` 不带 `task_ids` 等行为差异。
4. **配置迁移**：

```bash
airflow config update    # 自动改写 airflow.cfg
airflow db migrate       # 数据库结构迁移
```

5. **拓扑变化**：新增必跑组件 `airflow dag-processor`、`airflow api-server`（替代 webserver）；Celery/K8s Executor 改从 provider 安装。
6. **3.3 → 3.4 额外注意**：升级含 `xcom_v2` 表迁移（官方按 3 亿行 XCom 表实测）；MySQL 上降级无法回滚 DDL，升级前必须备份元数据库。
7. **灰度**：staging 全量验证 DAG → 备份 Metadata DB → 滚动升级 → 观察调度延迟与失败率。

### 常见运维问题

| 问题 | 原因 | 解决 |
|---|---|---|
| DAG 不显示 | dag-processor 未解析成功 / bundle 未同步 | 检查 import errors、bundle 配置 |
| 任务不调度 | Scheduler 卡住 / DB 连接问题 | 重启 Scheduler，检查 DB |
| Worker 内存爆炸 | 任务内存泄漏 / 并发过高 | 限制并发，增加资源 |
| Pod 启动慢 | KubernetesExecutor image pull | 预热镜像、镜像缓存、简化 init |
| 日志丢失 | 远程日志配置错误 | 检查 connection 和 bucket 权限 |
| 3.x 升级后时间语义不对 | cron data interval 默认值变化 | 显式 `CronDataIntervalTimetable` 或改配置 |

## 本章小结

- 生产 Airflow 3 = PostgreSQL + API Server + dag-processor + 多 Scheduler + 合适 Executor + Triggerer。
- Executor 选型：Local 单机、Celery 多机、Kubernetes 云原生隔离、**Edge 跨云/受限网络（3.x 新增）**。
- 认证：3.x 默认 Simple Auth Manager 仅适合开发，生产用 FAB provider（OAuth/LDAP）+ API token + Execution API 短期 JWT。
- 监控：Deadline Alerts 取代 SLA；3.2+ 结构化日志与 OTel Histogram。
- **2.x 已 EOL**：迁移路径 2.11 → 3.1+，ruff `AIR301` 自动修复 + 人工核对语义变化。

**参考来源**

- [Apache Airflow — Production Deployment](https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/production-deployment.html)
- [Apache Airflow — Upgrading to Airflow 3](https://airflow.apache.org/docs/apache-airflow/stable/installation/upgrading_to_airflow3.html)
- [Apache Airflow — Version Support Policy](https://airflow.apache.org/docs/apache-airflow/stable/installation/supported-versions.html)
- [Amazon MWAA — Apache Airflow versions](https://docs.aws.amazon.com/mwaa/latest/userguide/airflow-versions.html)
- [Astronomer — Upgrading Airflow 2 to 3: A Checklist for 2026](https://www.astronomer.io/blog/upgrading-airflow-2-to-airflow-3-a-checklist-for-2026/)
- [Astronomer — Astro Runtime release notes](https://www.astronomer.io/docs/runtime/runtime-release-notes)
- [Apache Airflow — Kubernetes Executor](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/executor/kubernetes.html)
- [apache-airflow-providers-edge3 文档](https://airflow.apache.org/docs/apache-airflow-providers-edge3/stable/index.html)
- [Airflow Release Notes (3.3.2 / 3.4.0b1)](https://airflow.apache.org/docs/apache-airflow/stable/release_notes.html)

# 3. 架构设计：Tracking Server、Backend Store 与 Artifact Store

> 一句话理解：MLflow 的架构是**“一个 Tracking Server + 两个 Store”**——Server 提供 UI 和 REST API，Backend Store 保存实验元数据，Artifact Store 保存模型文件等大对象。

## 3.1 总体架构

```
┌──────────────────────────────────────────────────────────────────────┐
│                         用户 / SDK / CI                               │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    MLflow Tracking Server（FastAPI）                   │
│              REST API + Web UI + Authentication                       │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
            ┌───────────────────┴───────────────────┐
            │                                       │
            ▼                                       ▼
┌───────────────────────────┐           ┌───────────────────────────┐
│      Backend Store        │           │      Artifact Store       │
│  SQLite / PostgreSQL /    │           │  Local FS / S3 / GCS /    │
│  MySQL / SQL Server       │           │  Azure Blob / HDFS        │
│                           │           │                           │
│  experiments, runs,       │           │  models, plots, datasets  │
│  params, metrics, tags,   │           │  large files              │
│  registered models,       │           │                           │
│  model versions           │           │                           │
└───────────────────────────┘           └───────────────────────────┘
```

## 3.2 Tracking Server

Tracking Server 是 MLflow 的控制面和入口。它提供：

- **REST API**：实验、Run、模型注册、artifact 的增删改查。
- **Web UI**：可视化实验、对比 Run、管理模型版本。
- **认证/授权**（企业版或自托管插件）：控制谁可以读写哪些 experiment。

启动一个本地 Tracking Server：

```bash
mlflow server \
  --host 0.0.0.0 \
  --port 5000 \
  --backend-store-uri postgresql://user:pass@host/mlflow \
  --artifacts-destination s3://my-bucket/mlflow
```

### 两种工作模式

| 模式 | URI 示例 | 适用场景 |
|---|---|---|
| 本地文件模式 | `file:///path/to/mlruns` | 个人开发 |
| Tracking Server 模式 | `http://mlflow.example.com:5000` | 团队协作 |

本地模式没有 Model Registry（registry 需要 SQL backend）。生产环境必须使用 SQL backend + Server。

## 3.3 Backend Store

Backend Store 保存所有**结构化元数据**：

- experiments（实验）
- runs（运行）
- params、metrics、tags
- registered_models
- model_versions

### 支持的后端

| 后端 | URI 示例 | 说明 |
|---|---|---|
| SQLite | `sqlite:///mlflow.db` | 本地开发，简单 |
| PostgreSQL | `postgresql://user:pass@host/db` | 生产推荐 |
| MySQL | `mysql://user:pass@host/db` | 生产可用 |
| SQL Server | `mssql://...` | 企业环境 |

### 数据表（简化）

```
experiments
  │
  └─ runs
       │
       ├─ params
       ├─ metrics
       ├─ tags
       └─ artifacts (URI 引用)

registered_models
  │
  └─ model_versions
       │
       ├─ model_version_tags
       └─ model_version_stages
```

MLflow 使用 Alembic 做数据库迁移。

## 3.4 Artifact Store

Artifact Store 保存**大文件/二进制对象**：

- 模型文件（`model.pkl`、`saved_model.pb`）
- 图片（`confusion_matrix.png`）
- 数据集
- 任意日志文件

### 支持的存储

| 存储 | URI 示例 | 说明 |
|---|---|---|
| 本地文件 | `./mlruns` | 本地开发 |
| S3 | `s3://bucket/mlflow/` | 生产常用 |
| GCS | `gs://bucket/mlflow/` | GCP |
| Azure Blob | `wasbs://container@account.blob.core.windows.net/` | Azure |
| HDFS | `hdfs://...` | 大数据场景 |

### Artifact 路径约定

一个 Run 的 artifact 通常存到：

```
artifact_store/
└── <experiment_id>/
    └── <run_id>/
        └── artifacts/
            ├── model/
            │   ├── MLmodel
            │   └── model.pkl
            └── plots/
                └── confusion_matrix.png
```

## 3.5 请求链路

一次 `mlflow.log_metric()` 的调用链：

```
Python SDK (mlflow.log_metric)
        │
        ▼
Fluent API (mlflow/tracking/fluent.py)
        │
        ▼
MlflowClient (mlflow/tracking/client.py)
        │
        ▼
REST / File Store
        │
        ▼
Tracking Server 或本地 Store
        │
        ▼
Backend Store 写入 metrics 表
```

一次 `mlflow.sklearn.log_model()` 的调用链：

```
Python SDK
        │
        ▼
Flavor 模块 (mlflow/sklearn/__init__.py)
        │
        ▼
保存模型文件到 artifact_store/<experiment_id>/<run_id>/artifacts/model/
        │
        ▼
生成 MLmodel 文件（flavor、signature、env）
        │
        ▼
记录 artifact URI 到 backend store
```

## 3.6 多用户与隔离

MLflow 开源版本身不提供细粒度 RBAC，但可以通过以下方式隔离：

- **Experiment 权限**：MLflow 2.x 后支持 basic auth 插件。
- **Workspace / Databricks**：Databricks Managed MLflow 提供完整多租户。
- **网络隔离**：不同团队使用不同的 Tracking Server + Backend Store。
- **命名规范**：用 `team/project/experiment` 命名 experiment。

## 3.7 高可用部署形态

### 单机 + SQLite（开发）

```
mlflow server --backend-store-uri sqlite:///mlflow.db --artifacts-destination ./mlruns
```

### 生产三件套

```
Load Balancer
      │
      ▼
MLflow Tracking Server (多副本)
      │
      ├─ PostgreSQL (Backend Store, 主从)
      └─ S3 (Artifact Store)
```

### Kubernetes 部署

使用 Helm chart 或自定义 Deployment：

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mlflow-server
spec:
  replicas: 3
  template:
    spec:
      containers:
        - name: mlflow
          image: mlflow:latest
          command:
            - mlflow
            - server
            - --backend-store-uri
            - postgresql://user:pass@postgres/mlflow
            - --artifacts-destination
            - s3://my-bucket/mlflow
```

## 本章小结

- MLflow 架构 = **Tracking Server + Backend Store + Artifact Store**。
- Tracking Server 提供 REST API 和 UI，是团队协作入口。
- Backend Store 用 SQL 数据库存储元数据；生产推荐 PostgreSQL。
- Artifact Store 用对象存储/文件系统存放大文件；生产推荐 S3/GCS。
- 本地文件模式适合个人开发，但**没有 Model Registry**。
- 生产部署需要考虑高可用、认证、备份和网络隔离。

**参考来源**

- [MLflow — Tracking Server](https://mlflow.org/docs/latest/tracking/server.html)
- [MLflow — Backend Stores](https://mlflow.org/docs/latest/tracking/backend-stores.html)
- [MLflow — Artifact Stores](https://mlflow.org/docs/latest/tracking/artifacts-stores.html)
- [MLflow — Self-Hosting](https://mlflow.org/docs/latest/self-hosting/index.html)

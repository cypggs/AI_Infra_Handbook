# 3. 架构设计：Tracking Server、Backend Store 与 Artifact Store

> 一句话理解：MLflow 的架构是**“一个 Tracking Server + 两个 Store”**——Server 提供 UI 和 REST API，Backend Store 保存实验元数据与 Trace，Artifact Store 保存模型文件等大对象；MLflow 3.x 把 GenAI 资产（trace、prompt、评估结果）纳入了同一套后端。

## 3.1 总体架构

```
┌──────────────────────────────────────────────────────────────────────┐
│                         用户 / SDK / CI                               │
│     (mlflow SDK / autolog tracing / OTel SDK / 编码 Agent CLI)        │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    MLflow Tracking Server（FastAPI）                   │
│       REST API + Web UI + Authentication + RBAC（3.13+）              │
│       AI Gateway：LLM 路由 / 预算 / Guardrails / MCP Registry         │
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
│  params, metrics, tags,   │           │  trace 附件（多模态）      │
│  registered models,       │           │  归档 trace（3.13+）       │
│  model versions,          │           │  presigned URL 直传（3.15）│
│  logged_models (3.x),     │           │                           │
│  traces / spans / prompts │           │                           │
│  / scorers / datasets     │           │                           │
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
- logged_models（3.x 一等模型实体）
- registered_models、model_versions
- traces / spans（MLflow Tracing 的追踪数据，3.x）
- prompts（Prompt Registry）、scorers / 评估结果（3.x）

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
       ├─ logged_models (3.x：一等模型实体)
       └─ artifacts (URI 引用)

registered_models
  │
  └─ model_versions
       │
       ├─ model_version_tags
       └─ model_version_aliases

traces (3.x)
  │
  └─ spans
       │
       ├─ span_attributes (prompt / token / cost ...)
       └─ span_artifacts (多模态附件，3.12+)

prompts (3.x Prompt Registry)
scorers / assessment 结果 (3.x)
```

MLflow 使用 Alembic 做数据库迁移。3.x 起 trace 表成为增长最快的表——3.13 引入了 **Trace 自动归档**（按保留期把老 trace 从 SQL 搬到对象存储，UI/API 仍可读），3.17 又提供按日聚合（daily rollups）加速 trace 分析，生产部署时务必规划 trace 的保留与归档策略。

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

## 3.6 Trace 摄取与归档链路（3.x）

GenAI 应用的观测数据走一条独立的链路，与传统 metrics 分开：

```
应用进程
   │
   │ ① autolog / @mlflow.trace 产生 span
   ▼
OTel SDK（mlflow-tracing 内置）
   │
   │ ② OTLP 批量上报
   ▼
MLflow Tracking Server：/api/2.0/mlflow/traces
   │
   ├─ ③ 热数据 → Backend Store（SQL，近期 trace，查询快）
   │
   └─ ④ 超过保留期 → 归档进程搬到 Artifact Store（S3，
          便宜大容量；UI/API 仍能读取）——3.13 Trace Archival
```

要点：

- **尽量批量、异步上报**：tracing 在生产是高频写路径，SDK 默认批量缓冲，避免拖慢应用。
- **多模态附件存 Artifact Store**：PDF/图片/音频等大对象以 artifact 形式存放（3.12+），SQL 里只存引用。
- **3.15 起支持 presigned URL 直传**：大 artifact 由 Server 签发 URL，客户端直连对象存储，不再经 Server 代理，显著降低 Server 带宽压力。
- **成本**：trace 数据量通常是 metrics 的 100 倍以上，务必配置 `trace_archival` 保留策略（见第 8 章）。

## 3.7 多用户与隔离

MLflow 开源版 3.13 起内置 **RBAC**（此前只有 basic-auth 插件）：管理员可定义角色（权限包），覆盖 experiments、models、prompts、scorers、AI Gateway endpoints 等资源，并提供 Admin UI 与 `/account` 自助页面。更细粒度的 `DENY` 式资源级权限在 3.17 进一步增强。常见隔离手段：

- **RBAC / basic auth 插件**：按用户/角色分配资源权限。
- **Workspace（3.10+）**：`mlflow server --enable-workspaces` 开启多工作区共享一个 Server。
- **Databricks Managed MLflow**：完整 workspace、RBAC、审计、Unity Catalog 治理。
- **网络隔离**：不同团队使用不同的 Tracking Server + Backend Store。
- **命名规范**：用 `team/project/experiment` 命名 experiment。

## 3.8 高可用部署形态

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

**首选官方 Helm Chart（3.13+ 内置，chart 与 MLflow 版本对齐）**，自带 TLS、Ingress、持久存储、Prometheus 指标、NetworkPolicy、可选的 `mlflow gc` 定时垃圾回收，要求 Kubernetes 1.23+ / Helm 3.8+：

```bash
helm install mlflow oci://ghcr.io/mlflow/charts/mlflow \
  --version 3.13.0 \
  --namespace mlflow --create-namespace
```

生产配置（PostgreSQL + S3）可参考仓库中的 `charts/example-mlflow-charts.yaml`。也可以自写 Deployment：

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

- MLflow 架构 = **Tracking Server + Backend Store + Artifact Store**；3.x 把 trace、prompt、评估结果也存入同一后端。
- Tracking Server 提供 REST API 和 UI，是团队协作入口；3.13 起内置 RBAC 与 Admin UI。
- Backend Store 用 SQL 数据库存储元数据；生产推荐 PostgreSQL；3.x 的 traces 表增长最快，需要归档策略（3.13 Trace Archival）。
- Artifact Store 用对象存储/文件系统存放大文件；3.12+ 存多模态 trace 附件，3.15+ 支持 presigned URL 直传。
- 本地文件模式适合个人开发，但**没有 Model Registry**。
- 生产部署需要考虑高可用、认证、trace 保留、备份和网络隔离；K8s 上优先用官方 Helm Chart。

**参考来源**

- [MLflow — Tracking Server](https://mlflow.org/docs/latest/tracking/server.html)
- [MLflow — Backend Stores](https://mlflow.org/docs/latest/tracking/backend-stores.html)
- [MLflow — Artifact Stores](https://mlflow.org/docs/latest/tracking/artifacts-stores.html)
- [MLflow — Self-Hosting](https://mlflow.org/docs/latest/self-hosting/index.html)
- [MLflow 3.13.0 Release — RBAC / Trace Archival / Helm Chart](https://mlflow.org/releases/3.13.0/)
- [MLflow Tracing 架构](https://mlflow.org/docs/latest/genai/tracing/)

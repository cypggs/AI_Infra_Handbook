# 8. 企业生产实践：部署、存储、认证与高可用

> 一句话理解：MLflow 从“本地 SQLite”到“生产平台”的关键跳跃，是 **Backend Store、Artifact Store、Tracking Server、认证/网络** 这四块的设计和运维。

## 8.1 部署形态选择

### 形态 1：本地开发（文件模式）

```python
import mlflow
mlflow.set_tracking_uri("file:///home/user/mlruns")
```

- 优点：零配置，开箱即用。
- 缺点：无 Model Registry，无协作，无认证。

### 形态 2：本地 SQLite + Tracking Server

```bash
mlflow server --backend-store-uri sqlite:///mlflow.db --artifacts-destination ./mlruns
```

- 适合：小团队、概念验证。
- 缺点：SQLite 并发弱，artifact 在本地磁盘。

### 形态 3：生产三件套（推荐）

```bash
mlflow server \
  --host 0.0.0.0 \
  --backend-store-uri postgresql://user:pass@postgres/mlflow \
  --artifacts-destination s3://my-bucket/mlflow
```

- PostgreSQL：Backend Store，高并发、可备份。
- S3：Artifact Store，大模型文件、多副本、生命周期管理。
- Tracking Server：多副本 + Load Balancer。

### 形态 4：Kubernetes / Helm

使用社区 Helm chart 或自写 Deployment：

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

## 8.2 Backend Store 选型

| 数据库 | 适用场景 | 注意 |
|---|---|---|
| SQLite | 本地开发 | 不支持高并发 |
| PostgreSQL | 生产首选 | 支持 Model Registry、索引好 |
| MySQL | 生产可选 | 注意字符集和 max_allowed_packet |
| SQL Server | 企业环境 | 需要对应驱动 |

### 数据库表规模估算

- 每次 Run 产生：1 行 run + N 行 params + M 行 metrics（每 step 一行）+ K 行 tags。
- 如果每天 1000 次 Run，每次 100 metrics × 100 steps，一年 metrics 表可达 36.5 亿行。
- 需要：**分区、归档、清理策略**。

## 8.3 Artifact Store 选型

| 存储 | 适用场景 |
|---|---|
| 本地文件 | 开发/测试 |
| S3 | AWS / 通用生产 |
| GCS | GCP |
| Azure Blob | Azure |
| HDFS | 大数据生态 |

### S3 配置要点

```bash
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...

mlflow server --artifacts-destination s3://my-bucket/mlflow
```

- 对 MLflow Server 配置 IAM Role，避免把 AK/SK 写进代码。
- 启用 S3 生命周期：旧版本模型自动转冷存储或删除。
- 启用 S3 版本控制：防止误删重要模型。

## 8.4 认证与多用户

### 开源版认证

MLflow 2.x 提供 basic auth 插件：

```bash
mlflow server \
  --app-name basic-auth \
  --backend-store-uri postgresql://... \
  --artifacts-destination s3://...
```

用户/权限存储在 `auth` 数据库表中。支持：

- 用户认证。
- Experiment 级别的读写权限。
- 管理员权限。

### 企业方案

- **Databricks Managed MLflow**：完整 workspace、RBAC、审计。
- **自研网关**：在 MLflow Server 前加 OIDC/OAuth2 代理，按 team/project 路由到不同 MLflow 实例。

### 网络隔离

- 不同团队使用不同 Tracking Server + DB + Bucket。
- 或用同一个 Server，但 experiment 命名带 team/project 前缀，结合 auth 插件隔离。

## 8.5 高可用与扩展

### Tracking Server

- 多副本无状态部署，前置 Load Balancer。
- 使用容器健康检查。
- 配置资源限制（CPU/内存）。

### 数据库

- PostgreSQL 主从 + 自动故障转移。
- 定期备份（逻辑备份 + WAL 归档）。
- 慢查询监控与索引优化。

### Artifact Store

- S3 本身高可用，但注意 bucket 跨区域复制。
- 大模型文件上传超时：调整客户端/服务器超时时间。

## 8.6 备份与灾难恢复

| 数据 | 备份方式 | 恢复策略 |
|---|---|---|
| Backend Store | pg_dump / 数据库备份 | 恢复到新实例 |
| Artifact Store | S3 跨区域复制 / 生命周期 | 从备份 bucket 恢复 |
| 配置文件 | Git | 重新部署 |

### 灾难恢复演练

- 每季度做一次恢复演练：从备份恢复 DB + S3，验证 Model Registry 可加载。
- 记录 RTO/RPO。

## 8.7 监控与告警

| 指标 | 工具 | 告警场景 |
|---|---|---|
| Tracking Server QPS / 延迟 | Prometheus + Grafana | 延迟 P99 升高 |
| DB 连接数 / 慢查询 | PostgreSQL exporter | 连接数接近上限 |
| S3 存储/请求 | CloudWatch / S3 metrics | 存储增长异常 |
| 模型注册/阶段变更 | MLflow UI / audit log | 非预期 Production 变更 |
| 模型加载失败 | 服务自身监控 | 加载失败率升高 |

## 8.8 与 Kubeflow / KServe 集成

### Kubeflow + MLflow

Kubeflow Pipeline 的 training step 里：

```python
with mlflow.start_run():
    mlflow.log_params(params)
    model.fit(...)
    mlflow.log_metric("auc", auc)
    model_info = mlflow.sklearn.log_model(model, "model")
    client.create_model_version(name="fraud-detector", source=model_info.model_uri)
```

KServe + MLflow：

```yaml
spec:
  predictor:
    model:
      modelFormat:
        name: mlflow
      storageUri: models:/fraud-detector@champion
```

## 本章小结

- 生产 MLflow = PostgreSQL + S3 + Tracking Server 多副本。
- 认证可用 basic-auth 插件或企业级 OIDC/Workspace。
- 数据库需要分区/归档/备份；S3 需要生命周期和跨区域复制。
- 高可用覆盖 Server、DB、Artifact Store 三层。
- 与 Kubeflow/KServe 组合形成完整的训练→注册→服务链路。

**参考来源**

- [MLflow — Tracking Server](https://mlflow.org/docs/latest/tracking/server.html)
- [MLflow — Backend Stores](https://mlflow.org/docs/latest/tracking/backend-stores.html)
- [MLflow — Artifact Stores](https://mlflow.org/docs/latest/tracking/artifacts-stores.html)
- [MLflow — Authentication](https://mlflow.org/docs/latest/auth/index.html)
- 本手册 [Kubeflow 生产实践](../kubeflow/08-production-practice)、[KServe 生产实践](../kserve/08-production-practice)

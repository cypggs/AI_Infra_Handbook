# 5. 核心模块：Tracking API、Model Registry、Artifact 与 Flavor

> 一句话理解：MLflow 的核心实现可以分成三层——**面向用户的 Fluent/Client API、负责元数据的 Tracking/Registry Service、负责文件存储的 Artifact Repository**，再加上 **Model Flavor** 把各种框架模型统一封装。

## 5.1 模块分层

```
┌──────────────────────────────────────────────────────────────────────┐
│                    用户层：Fluent API / MlflowClient                  │
│         mlflow.log_param() / mlflow.log_metric() / start_run()       │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                   服务层：Tracking / Model Registry                   │
│       mlflow.tracking._tracking_service / _model_registry            │
│       mlflow.store.tracking / mlflow.store.model_registry            │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
            ┌───────────────────┴───────────────────┐
            │                                       │
            ▼                                       ▼
┌───────────────────────────┐           ┌───────────────────────────┐
│   Backend Store (SQL)     │           │   Artifact Repository     │
│  SQLite / PostgreSQL /    │           │  Local / S3 / GCS / Azure │
│  MySQL / SQL Server       │           │                           │
└───────────────────────────┘           └───────────────────────────┘
```

## 5.2 Fluent API

`mlflow/tracking/fluent.py` 提供高阶 API，是大多数用户直接接触的一层。

### 关键函数

| 函数 | 作用 |
|---|---|
| `mlflow.set_tracking_uri(uri)` | 设置 Tracking Server 地址 |
| `mlflow.set_experiment(name)` | 设置当前 experiment |
| `mlflow.start_run()` | 开始一个 Run |
| `mlflow.log_param(key, value)` | 记录单个参数 |
| `mlflow.log_params(dict)` | 批量记录参数 |
| `mlflow.log_metric(key, value, step)` | 记录指标（可重复） |
| `mlflow.log_artifact(path)` | 上传文件 artifact |
| `mlflow.log_artifacts(dir)` | 上传目录 artifact |
| `mlflow.set_tag(key, value)` | 设置 tag |
| `mlflow.end_run()` | 结束当前 Run |

### 自动上下文

```python
with mlflow.start_run() as run:
    mlflow.log_param("lr", 0.01)
    # Run 在 with 块结束时自动关闭
```

## 5.3 MlflowClient

`mlflow/tracking/client.py` 提供更底层、更完整的控制能力。

```python
from mlflow import MlflowClient

client = MlflowClient()
client.create_experiment("my-exp")
runs = client.search_runs(experiment_ids=["1"], filter_string="metrics.auc > 0.9")
```

常用能力：

- 搜索 Run（带过滤、排序）。
- 管理 Registered Model / Model Version。
- 设置 alias、stage、tag。
- 下载 artifact。

## 5.4 Tracking Service

内部实现位于 `mlflow/tracking/_tracking_service/` 和 `mlflow/store/tracking/`。

职责：

- 把 Fluent/Client 请求转换成对 backend store 的操作。
- 处理 metric 的历史版本（每次 `log_metric` 新增一行，支持时间序列）。
- 处理 artifact URI 解析和重定向。

### Backend Store 抽象

`mlflow/store/tracking/abstract_store.py` 定义接口，具体实现：

- `file_store.py`：本地文件系统。
- `sqlalchemy_store.py`：SQL 数据库。
- `rest_store.py`：通过 REST API 访问远程 Tracking Server。

## 5.5 Model Registry Service

内部实现位于 `mlflow/tracking/_model_registry/` 和 `mlflow/store/model_registry/`。

职责：

- 管理 Registered Model 的 CRUD。
- 管理 Model Version 的创建、查询、阶段转换。
- 管理 alias、tag、description。

**注意**：Model Registry 需要 SQL backend，本地文件模式不支持。

## 5.6 Artifact Repository

`mlflow/artifacts/` 和 `mlflow/store/artifact/` 实现多种 artifact 存储后端。

支持的 Repository：

| Repository | 类路径 |
|---|---|
| LocalArtifactRepository | `mlflow/store/artifact/local_artifact_repo.py` |
| S3ArtifactRepository | `mlflow/artifacts/s3_artifact_repo.py` |
| GCSArtifactRepository | `mlflow/artifacts/gcs_artifact_repo.py` |
| AzureArtifactRepository | `mlflow/artifacts/azure_blob_artifact_repo.py` |
| HdfsArtifactRepository | `mlflow/artifacts/hdfs_artifact_repo.py` |

Artifact Repository 只负责**文件的上传、下载、列出**，不解析文件内容。

## 5.7 Model Flavor

每种机器学习框架有一个 Flavor 模块，例如：

- `mlflow/sklearn/__init__.py`
- `mlflow/xgboost/__init__.py`
- `mlflow/pytorch/__init__.py`
- `mlflow/tensorflow/__init__.py`
- `mlflow/pyfunc/__init__.py`

### Flavor 职责

1. **save_model**：把框架模型保存到本地目录。
2. **log_model**：调用 save_model + 上传 artifact + 记录元数据。
3. **load_model**：从 MLflow model URI 加载模型并返回框架原生对象。
4. **定义 MLmodel 文件中的 flavor 段**。

### 一个 MLmodel 文件示例

```yaml
artifact_path: model
flavors:
  python_function:
    env:
      conda: conda.yaml
      virtualenv: python_env.yaml
    loader_module: mlflow.sklearn
    model_path: model.pkl
    predict_fn: predict
    python_version: 3.10.12
  sklearn:
    code: null
    pickled_model: model.pkl
    serialization_format: cloudpickle
    sklearn_version: 1.5.0
mlflow_version: 2.22.0
model_size_bytes: 1234
signature:
  inputs: '[{"type": "tensor", "tensor-spec": {"dtype": "float64", "shape": [-1, 4]}}]'
  outputs: '[{"type": "tensor", "tensor-spec": {"dtype": "int64", "shape": [-1]}}]'
utc_time_created: '2026-07-04 10:00:00.000000'
```

## 5.8 PyFunc：通用部署接口

所有 flavor 都必须能转成 `pyfunc` 用于部署。`mlflow.pyfunc.PyFuncModel` 提供统一接口：

```python
model = mlflow.pyfunc.load_model("models:/fraud-detector@champion")
predictions = model.predict(input_df)
```

底层会调用对应 flavor 的 `load_model` 和 `predict`。

## 5.9 MLflow Server

`mlflow/server/fastapi_app.py` 实现 FastAPI 应用，暴露 REST API。

主要路由组：

- `/api/2.0/mlflow/runs/*`：Run CRUD。
- `/api/2.0/mlflow/experiments/*`：Experiment CRUD。
- `/api/2.0/mlflow/model-versions/*`：Model Version。
- `/api/2.0/mlflow/registered-models/*`：Registered Model。
- `/api/2.0/mlflow/artifacts/*`：Artifact 获取/列出。

UI 是 server/js/ 下的前端，调用这些 REST API。

## 5.10 模块交互示例

一次 `mlflow.sklearn.log_model()` 的调用链：

```
mlflow.sklearn.log_model()
        │
        ▼
mlflow.models.model.log()
        │
        ▼
flavor.save_model() → 本地临时目录
        │
        ▼
mlflow.tracking.artifact_utils.get_artifact_repository()
        │
        ▼
ArtifactRepository.log_artifacts() → S3
        │
        ▼
生成 MLmodel 文件并上传
        │
        ▼
记录 artifact URI 到 backend store
```

## 本章小结

- **Fluent API**：用户最常用的 `mlflow.*` 函数。
- **MlflowClient**：更完整的底层控制。
- **Tracking Service**：处理 Run、params、metrics、tags。
- **Model Registry Service**：管理模型版本、阶段、别名。
- **Artifact Repository**：负责文件上传/下载的抽象。
- **Model Flavor**：把不同框架模型统一封装成 MLflow Model。
- **PyFunc**：统一预测接口，支撑服务部署。
- **MLflow Server**：FastAPI + REST API + UI。

**参考来源**

- [MLflow Python API Reference](https://mlflow.org/docs/latest/python_api/index.html)
- [MLflow Tracking API](https://mlflow.org/docs/latest/tracking/tracking-api.html)
- [MLflow Model Registry API](https://mlflow.org/docs/latest/model-registry.html)
- [MLflow GitHub — mlflow/tracking](https://github.com/mlflow/mlflow/tree/master/mlflow/tracking)
- [MLflow GitHub — mlflow/models](https://github.com/mlflow/mlflow/tree/master/mlflow/models)
- [MLflow GitHub — mlflow/store](https://github.com/mlflow/mlflow/tree/master/mlflow/store)

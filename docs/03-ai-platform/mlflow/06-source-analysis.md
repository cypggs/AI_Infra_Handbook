# 6. 源码分析：关键目录、调用链与扩展点

> 一句话理解：MLflow 源码的核心是 **Fluent API → Client → Service → Store → Artifact Repository** 的五层调用链，理解这条链就能看懂一次 `log_metric` 或 `log_model` 如何落到数据库和对象存储。

## 6.1 源码仓库地图

```
mlflow/
├── mlflow/
│   ├── tracking/              # Tracking API、Client、Service
│   │   ├── fluent.py          # 高阶 API：log_param, start_run
│   │   ├── client.py          # MlflowClient
│   │   ├── _tracking_service/ # 内部 service 抽象
│   │   └── _model_registry/   # Model Registry 内部 client/service
│   ├── models/                # Model 打包、签名、推理
│   │   ├── model.py           # Model 对象、log/save/load
│   │   ├── signature.py       # 输入/输出签名
│   │   ├── flavor_utils.py    # flavor 工具
│   │   └── utils.py           # 模型工具
│   ├── store/                 # 存储抽象与实现
│   │   ├── tracking/          # Tracking backend store
│   │   │   ├── abstract_store.py
│   │   │   ├── file_store.py
│   │   │   └── sqlalchemy_store.py
│   │   ├── model_registry/    # Registry backend store
│   │   └── artifact/          # Artifact repository 实现
│   ├── artifacts/             # Artifact repository 入口与工具
│   ├── server/                # FastAPI Tracking Server
│   │   ├── fastapi_app.py     # 主应用
│   │   ├── handlers.py        # REST handlers
│   │   └── js/                # UI 前端
│   ├── sklearn/               # sklearn flavor
│   ├── xgboost/               # xgboost flavor
│   ├── pytorch/               # pytorch flavor
│   ├── pyfunc/                # 通用 pyfunc flavor
│   ├── projects/              # MLflow Projects
│   ├── deployments/           # 部署目标插件
│   ├── evaluation/            # 模型评估
│   ├── tracing/               # 分布式追踪（GenAI）
│   ├── entities/              # 数据模型：Run, Experiment, ModelVersion
│   └── protos/                # Protobuf 定义
├── tests/                     # 测试
└── requirements/              # 依赖
```

## 6.2 关键调用链

### `mlflow.log_metric()` 链路

```
mlflow.log_metric("auc", 0.94)
        │
        ▼
mlflow/tracking/fluent.py
        │  ├─ 获取 active_run
        │  └─ 调用 MlflowClient().log_metric()
        ▼
mlflow/tracking/client.py
        │  └─ 调用 _tracking_service.log_metric()
        ▼
mlflow/tracking/_tracking_service/client.py
        │  └─ 调用 store.log_metric()
        ▼
mlflow/store/tracking/sqlalchemy_store.py（或 file_store.py）
        │
        ▼
写入 metrics 表
```

### `mlflow.sklearn.log_model()` 链路

```
mlflow.sklearn.log_model(model, "model")
        │
        ▼
mlflow/sklearn/__init__.py
        │  ├─ save_model() 到本地临时目录
        │  └─ 调用 mlflow.models.model.log()
        ▼
mlflow/models/model.py
        │  └─ 调用 flavor 的 save_model + artifact_utils
        ▼
mlflow/tracking/artifact_utils.py
        │  └─ 获取 ArtifactRepository
        ▼
mlflow/store/artifact/s3_artifact_repo.py（或 local）
        │
        ▼
上传 model/ 目录到 artifact store
        │
        ▼
记录 artifact URI 到 backend store
```

## 6.3 关键文件解析

### `mlflow/tracking/fluent.py`

- 维护线程/进程级别的 `active_run_stack`。
- 提供 `start_run()` / `end_run()` / `log_metric()` 等函数。
- 通过 `_get_or_start_run()` 确保在调用 log 函数时自动创建 Run。

### `mlflow/tracking/client.py`

- `MlflowClient` 是用户层的客户端。
- 内部持有 `_tracking_client` 和 `_registry_client`。
- 提供搜索 Run、管理模型版本等完整能力。

### `mlflow/store/tracking/sqlalchemy_store.py`

- 使用 SQLAlchemy ORM 映射实体到数据库表。
- 关键表：`experiments`、`runs`、`params`、`metrics`、`tags`、`latest_metrics`。
- `search_runs` 实现复杂的过滤和排序逻辑。

### `mlflow/store/model_registry/sqlalchemy_store.py`

- 管理 `registered_models`、`model_versions`、`model_version_tags` 等表。
- 支持 stage 转换、alias 管理。

### `mlflow/models/model.py`

- `Model` 类对应 `MLmodel` 文件。
- `log()` 方法协调 flavor 保存、artifact 上传、元数据记录。
- `load()` 方法解析 `MLmodel` 并调用对应 flavor 的 `load_model`。

### `mlflow/pyfunc/__init__.py`

- `load_model()`：读取 `MLmodel` 的 `python_function` flavor，加载依赖并返回 `PyFuncModel`。
- `PyFuncModel.predict()`：统一的预测入口。
- `serve()` / `build_image()`：本地服务和容器化部署。

### `mlflow/server/fastapi_app.py`

- 创建 FastAPI app。
- 注册 handlers 和 middleware（auth、CORS 等）。
- 静态文件服务 UI。

## 6.4 扩展点

### 自定义 Tracking Store

实现 `mlflow.store.tracking.abstract_store.AbstractStore`：

```python
from mlflow.store.tracking import AbstractStore

class MyStore(AbstractStore):
    def create_experiment(self, name, artifact_location=None, tags=None):
        ...
    def create_run(self, experiment_id, user_id, start_time, tags):
        ...
```

通过 `--backend-store-uri my-scheme://...` + `mlflow.tracking.registry` 插件注册。

### 自定义 Artifact Repository

实现 `mlflow.store.artifact.artifact_repo.ArtifactRepository`：

```python
from mlflow.store.artifact.artifact_repo import ArtifactRepository

class MyArtifactRepository(ArtifactRepository):
    def log_artifact(self, local_file, artifact_path=None):
        ...
```

通过 `mlflow.artifacts.registry` 插件注册。

### 自定义 Flavor

第三方库可以定义自己的 flavor，只要生成符合规范的 `MLmodel` 文件并实现 `load_model`。

## 6.5 阅读源码的建议路径

1. **从 Fluent API 入口开始**：`mlflow/tracking/fluent.py`。
2. **跟踪一次 log 调用**：fluent → client → service → store。
3. **看一个 flavor**：`mlflow/sklearn/__init__.py` 最简单。
4. **看 Model 打包**：`mlflow/models/model.py`。
5. **看 Server**：`mlflow/server/fastapi_app.py` + `handlers.py`。

## 本章小结

- MLflow 源码分五层：Fluent API → Client → Service → Store → Artifact Repository。
- `fluent.py` 维护 active run，提供高阶 API。
- `client.py` 是用户层完整客户端。
- `store/tracking/sqlalchemy_store.py` 是生产 backend store 核心。
- `store/model_registry/sqlalchemy_store.py` 管理模型版本。
- `models/model.py` 是 MLflow Model 打包的核心协调者。
- `pyfunc` 提供统一预测接口。
- MLflow 支持自定义 Tracking Store、Artifact Repository 和 Flavor。

**参考来源**

- [MLflow GitHub](https://github.com/mlflow/mlflow)
- [MLflow Python API Reference](https://mlflow.org/docs/latest/python_api/index.html)
- [MLflow Tracking Server](https://mlflow.org/docs/latest/tracking/server.html)
- 本手册 [Operator 模式源码分析](../../02-cloud-native/operator/06-source-analysis)

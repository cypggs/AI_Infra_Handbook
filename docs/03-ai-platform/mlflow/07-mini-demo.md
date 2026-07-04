# 7. Mini Demo：本地实验、注册与加载预测

> 一句话理解：这个 Demo 用 **SQLite 作为 Backend Store、本地目录作为 Artifact Store**，在不启动 Tracking Server 的情况下，完整跑通：训练 sklearn 模型 → 记录参数/指标/模型 → 注册模型 → 切换别名 → 加载预测。

## 7.1 目标与约束

- **无需外部服务**：不启动 MLflow Tracking Server，也不依赖 S3。
- **CPU 可运行**：使用 iris 数据集 + LogisticRegression。
- **真实 MLflow**：调用官方 `mlflow` Python SDK，不是模拟。
- **自动清理**：测试使用临时目录，结束后自动删除。

## 7.2 目录结构

```
mini-demo/
├── README.md
├── pyproject.toml
├── mlflow_mini/
│   ├── __init__.py
│   └── demo.py          # 端到端入口
└── tests/
    └── test_demo.py     # pytest 用例
```

## 7.3 运行方式

```bash
cd docs/03-ai-platform/mlflow/mini-demo
pip install -e ".[dev]"
pytest tests/ -v
python -m mlflow_mini.demo
```

预期输出（数值可能略有不同）：

```
Demo result: {
  'run_id': '...',
  'model_name': 'iris-classifier',
  'model_version': 1,
  'alias': 'champion',
  'accuracy': 0.96,
  'predictions': [0, 1, 2]
}
```

## 7.4 核心代码

### 训练与记录

```python
import os
import tempfile
import mlflow
import mlflow.sklearn
from sklearn.datasets import load_iris
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from mlflow.models import infer_signature
from mlflow import MlflowClient


def run_demo():
    tmp = tempfile.mkdtemp(prefix="mlflow-mini-")
    tracking_uri = f"sqlite:///{os.path.join(tmp, 'mlflow.db')}"
    artifact_root = os.path.join(tmp, "artifacts")

    mlflow.set_tracking_uri(tracking_uri)
    client = MlflowClient()

    experiment_name = "iris-classification"
    client.create_experiment(experiment_name, artifact_location=artifact_root)
    mlflow.set_experiment(experiment_name)

    X, y = load_iris(return_X_y=True)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    params = {"solver": "lbfgs", "max_iter": 200}
    model = LogisticRegression(**params)
    model.fit(X_train, y_train)
    acc = accuracy_score(y_test, model.predict(X_test))

    with mlflow.start_run(run_name="logistic-regression") as run:
        mlflow.log_params(params)
        mlflow.log_metric("accuracy", acc)
        signature = infer_signature(X_train, model.predict(X_train))
        model_info = mlflow.sklearn.log_model(model, "model", signature=signature)
        run_id = run.info.run_id

    model_name = "iris-classifier"
    client.create_registered_model(model_name)
    mv = client.create_model_version(
        name=model_name,
        source=model_info.model_uri,
        run_id=run_id,
    )
    client.set_registered_model_alias(model_name, "champion", mv.version)

    loaded = mlflow.pyfunc.load_model(f"models:/{model_name}@champion")
    predictions = loaded.predict(X_test[:3])

    return {
        "run_id": run_id,
        "model_name": model_name,
        "model_version": mv.version,
        "alias": "champion",
        "accuracy": acc,
        "predictions": predictions.tolist(),
    }
```

## 7.5 测试覆盖

| 测试 | 验证点 |
|---|---|
| `test_run_demo_end_to_end` | Run 创建、指标记录、模型注册、alias 设置、加载预测 |

运行结束后临时目录会被清理。

## 7.6 与真实生产的差异

| 方面 | Mini Demo | 真实生产 |
|---|---|---|
| Backend Store | SQLite 本地文件 | PostgreSQL / MySQL |
| Artifact Store | 本地目录 | S3 / GCS / Azure Blob |
| Tracking Server | 无（直接访问 DB） | FastAPI Server 多副本 |
| 认证 | 无 | OAuth / basic auth / Databricks workspace |
| 模型大小 | 几 KB | GB 级大模型 |

本 Demo 用于理解 MLflow 核心 API 和生命周期，不能直接用于生产。

## 本章小结

- Mini Demo 使用真实 `mlflow` SDK，SQLite backend + 本地 artifact store。
- 完整链路：**训练 → log_params/log_metric/log_model → 注册 → alias → 加载预测**。
- `pytest` 通过，自动清理临时目录。
- 与生产差异主要在 backend/artifact store、server、认证和模型规模。

**参考来源**

- 本 Demo 源码：`docs/03-ai-platform/mlflow/mini-demo/`
- [MLflow Quickstart](https://mlflow.org/docs/latest/getting-started/intro-quickstart/index.html)
- [MLflow Model Registry](https://mlflow.org/docs/latest/model-registry.html)
- 本手册 [Kubeflow Mini Demo](../kubeflow/07-mini-demo)

# 2. 核心思想：四大组件与核心概念

> 一句话理解：MLflow 把 ML 生命周期拆成四个可独立使用又可组合的能力——**Tracking 记录实验、Projects 封装代码、Models 打包模型、Model Registry 管理版本**。

## 2.1 组件全景图

```
┌──────────────────────────────────────────────────────────────────────┐
│                         MLflow UI / REST API                          │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌───────────────┐      ┌───────────────┐      ┌───────────────┐
│    Tracking   │      │     Models    │      │ Model Registry│
│  - Experiment │      │  - flavor     │      │  - Registered │
│  - Run        │      │  - signature  │      │     Model     │
│  - metric     │      │  - conda/env  │      │  - Version    │
│  - parameter  │      │  - pyfunc     │      │  - Stage      │
│  - artifact   │      │  - deploy     │      │  - Alias      │
│  - tag        │      │               │      │  - Tag        │
└───────────────┘      └───────────────┘      └───────────────┘
        │                                               ▲
        │                                               │
        └───────────────────────┬───────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │       Projects        │
                    │  - MLproject file     │
                    │  - entry points       │
                    │  - conda/docker env   │
                    └───────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │   Backend / Artifact  │
                    │   Store               │
                    └───────────────────────┘
```

## 2.2 MLflow Tracking

Tracking 是 MLflow 最常用的组件。它围绕 **Experiment → Run** 两级结构组织：

```
Experiment: "iris-classification"
    │
    ├─ Run-1
    │   ├─ params:  {lr: 0.01, max_iter: 100}
    │   ├─ metrics: {accuracy: 0.92, loss: 0.15}
    │   ├─ tags:    {model_type: logistic, version: v1}
    │   └─ artifacts: model.pkl, confusion_matrix.png
    │
    ├─ Run-2
    │   ├─ params:  {lr: 0.001, max_iter: 200}
    │   ├─ metrics: {accuracy: 0.95, loss: 0.10}
    │   └─ artifacts: model.pkl
```

### 核心概念

| 概念 | 含义 |
|---|---|
| **Experiment** | 一组相关 Run 的容器，比如“iris 分类实验”。 |
| **Run** | 一次代码执行，记录参数、指标、artifact、tag。 |
| **Metric** | 数值指标，可多次记录（带 step），支持折线图。 |
| **Parameter** | 超参或配置，一次 Run 中通常只记录一次。 |
| **Artifact** | 任意文件：模型、图片、配置、数据。 |
| **Tag** | 键值对，用于标记、过滤。 |

### 代码示例

```python
import mlflow

mlflow.set_experiment("iris-classification")

with mlflow.start_run(run_name="lr-0.01"):
    mlflow.log_params({"lr": 0.01, "max_iter": 100})
    mlflow.log_metric("accuracy", 0.92)
    mlflow.log_artifact("confusion_matrix.png")
```

## 2.3 MLflow Models

Models 组件解决“模型怎么打包”的问题。一个 MLflow Model 是一个目录，包含：

```
mlflow-model/
├── MLmodel              # 元数据：flavor、signature、env
├── model.pkl            # 实际模型（flavor 决定格式）
├── conda.yaml           # conda 依赖
├── python_env.yaml      # pip 依赖
└── input_example.json   # 输入示例
```

### Flavor（风味）

Flavor 是模型框架的适配器。MLflow 支持：

- `sklearn`、`xgboost`、`lightgbm`、`catboost`
- `pytorch`、`tensorflow`、`keras`、`onnx`
- `pyfunc`（通用 Python 函数）
- `langchain`、`openai`、`transformers`（GenAI/LLM）
- `spacy`、`spark`、`paddle` 等

### Signature（签名）

Signature 描述模型的输入/输出模式，是模型服务的契约：

```python
from mlflow.models import infer_signature

signature = infer_signature(X_train, y_pred)
mlflow.sklearn.log_model(model, "model", signature=signature)
```

### PyFunc

`pyfunc` 是最通用的 flavor。只要实现 `predict` 方法，任何模型都可以被 MLflow 封装：

```python
import mlflow

class MyModel(mlflow.pyfunc.PythonModel):
    def load_context(self, context):
        self.model = ...

    def predict(self, context, model_input):
        return self.model.predict(model_input)
```

## 2.4 MLflow Model Registry

Model Registry 是模型的“版本控制系统”。

### 核心概念

| 概念 | 含义 |
|---|---|
| **Registered Model** | 一个逻辑模型名称，比如 `iris-classifier`。 |
| **Model Version** | 该模型的一次迭代，自动递增（1, 2, 3...）。 |
| **Stage** | 生命周期阶段：None / Staging / Production / Archived。 |
| **Alias** | 可变的别名，比如 `champion`、`candidate`，用于解耦部署与版本号。 |
| **Tag** | 模型或版本的键值对元数据。 |

### 代码示例

```python
from mlflow import MlflowClient

client = MlflowClient()
client.create_registered_model("iris-classifier")

mv = client.create_model_version(
    name="iris-classifier",
    source="runs:/<run_id>/model",
    run_id="<run_id>",
)

client.set_registered_model_alias("iris-classifier", "champion", mv.version)
client.transition_model_version_stage("iris-classifier", mv.version, "Production")
```

## 2.5 MLflow Projects

Projects 解决“代码怎么复现”的问题。一个 Project 通过 `MLproject` 文件定义：

```yaml
name: iris-classifier

python_env: python_env.yaml

entry_points:
  main:
    parameters:
      lr: {type: float, default: 0.01}
      max_iter: {type: int, default: 100}
    command: "python train.py --lr={lr} --max_iter={max_iter}"
```

运行：

```bash
mlflow run . -P lr=0.001 -P max_iter=200
```

MLflow 会自动创建 conda/pip 环境并执行入口命令，保证别人能复现。

## 2.6 心智模型：一次完整的 ML 旅程

```
数据科学家在 Notebook 开发
        │
        ▼
mlflow.start_run() 开始一次实验
        │
        ▼
记录 params / metrics / artifacts
        │
        ▼
mlflow.sklearn.log_model() 打包模型
        │
        ▼
创建 Registered Model 并注册版本
        │
        ▼
版本进入 Staging，验证后转到 Production
        │
        ▼
KServe / 自研服务加载 models:/name/alias
        │
        ▼
线上监控，效果回传，触发下一次 Run
```

## 本章小结

- **Tracking**：Experiment → Run → params / metrics / artifacts / tags。
- **Models**：目录 + MLmodel + flavor + signature + env，标准化模型打包。
- **Model Registry**：Registered Model / Version / Stage / Alias，管理模型生命周期。
- **Projects**：MLproject 文件 + entry points + env，保证代码可复现。
- 四者组合：Tracking 记录过程，Models 封装产物，Registry 管理版本，Projects 保证环境一致。

**参考来源**

- [MLflow — What is MLflow?](https://mlflow.org/docs/latest/what-is-mlflow.html)
- [MLflow Tracking](https://mlflow.org/docs/latest/tracking.html)
- [MLflow Models](https://mlflow.org/docs/latest/models.html)
- [MLflow Model Registry](https://mlflow.org/docs/latest/model-registry.html)
- [MLflow Projects](https://mlflow.org/docs/latest/projects.html)

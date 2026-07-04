# 4. Runtime 工作流程：从 Notebook 到模型服务

> 一句话理解：一个典型的 Kubeflow 旅程是——**数据科学家在 Notebook 里开发，把代码封装成 Pipeline component，编译上传后创建 Run；Run 中 Katib 自动搜索超参，Training Operator 用最佳参数分布式训练，最后 KServe 把模型发布为在线服务**。

## 4.1 完整旅程时序图

```
数据科学家
   │
   │ 1. 登录 Central Dashboard
   ▼
Central Dashboard
   │
   │ 2. 创建 Notebook（StatefulSet + Service + PVC）
   ▼
Jupyter Notebook
   │
   │ 3. 开发特征/模型代码
   │ 4. 封装 @dsl.component
   │ 5. 定义 @dsl.pipeline
   │ 6. kfp compiler 编译 pipeline.yaml
   ▼
KFP API Server
   │
   │ 7. 上传 Pipeline 定义
   ▼
Pipeline stored (MLMD + artifact store)
   │
   │ 8. 创建 Experiment / Run
   ▼
Pipeline Scheduler
   │
   │ 9. 解析 DAG，按依赖调度 Pod
   ▼
Step 1: 数据预处理 Container
   │
   │ 10. 输出 dataset artifact → S3
   ▼
Step 2: Katib Experiment
   │
   │ 11. Katib Controller 创建 Suggestion service
   │ 12. 生成 Trial Jobs（Batch Job / PyTorchJob）
   │ 13. 收集 metrics，返回最佳参数
   ▼
Step 3: Training Operator PyTorchJob
   │
   │ 14. Training Operator 创建 Master + Workers
   │ 15. 分布式训练，保存模型 artifact → S3
   ▼
Step 4: KServe InferenceService
   │
   │ 16. KServe Controller 部署 predictor
   ▼
模型在线服务
   │
   │ 17. 用户/业务系统调用 /v1/models/... 或 /openai/v1
   ▼
监控 / 告警 / 迭代
```

## 4.2 阶段详解

### 阶段 1：Notebook 开发

数据科学家在 Central Dashboard 创建 Notebook：

```yaml
apiVersion: kubeflow.org/v1
kind: Notebook
metadata:
  name: alice-eda
  namespace: alice
spec:
  template:
    spec:
      containers:
        - name: alice-eda
          image: jupyter/pytorch-notebook:latest
          resources:
            limits:
              nvidia.com/gpu: 1
```

Notebook Controller 创建 StatefulSet，Jupyter 容器挂载 PVC，用户通过浏览器访问。

### 阶段 2：Pipeline 开发

在 Notebook 里把实验代码封装成 component：

```python
from kfp import dsl

@dsl.component(
    base_image="python:3.10",
    packages_to_install=["pandas", "scikit-learn"]
)
def preprocess(input_path: str, output_path: str):
    import pandas as pd
    df = pd.read_csv(input_path)
    # ... feature engineering ...
    df.to_csv(output_path, index=False)
```

然后定义 pipeline：

```python
@dsl.pipeline(name="train-and-serve")
def train_and_serve(
    data_url: str = "s3://bucket/train.csv",
    lr: float = 0.001,
):
    preprocess_task = preprocess(input_path=data_url, output_path="s3://bucket/processed.csv")
    train_task = train_model(
        data=preprocess_task.outputs["output_path"],
        lr=lr,
    )
    deploy_task = deploy_model(model=train_task.outputs["model_path"])
```

### 阶段 3：编译与上传

```python
from kfp import compiler
compiler.Compiler().compile(train_and_serve, 'pipeline.yaml')

client = kfp.Client(host='https://kubeflow.example.com/pipeline')
client.upload_pipeline('pipeline.yaml', pipeline_name='train-and-serve')
```

API Server 把 pipeline spec 存入 ML Metadata 和对象存储。

### 阶段 4：创建 Run

```python
client.create_run_from_pipeline_func(
    train_and_serve,
    arguments={'data_url': 's3://bucket/train.csv', 'lr': 0.001},
    experiment_name='exp-2026-q3',
    run_name='run-001',
)
```

API Server 创建 `Run` 对象，Scheduler 按 DAG 生成 Pod。

### 阶段 5：Katib 调参

如果 pipeline 中某一步是 Katib Experiment：

```python
@dsl.pipeline
def tuning_pipeline():
    katib_task = katib_launcher(
        experiment_spec={...},
        experiment_name='tune-lr',
    )
    best_params = katib_task.outputs['best_params']
    train_task = train_model(lr=best_params['lr'])
```

Katib Controller：

1. 创建 `Suggestion` service。
2. 按算法生成 Trial。
3. 每个 Trial 是一个 K8s Job。
4. 收集 metrics，更新 Experiment status。
5. 返回最佳参数给 pipeline。

### 阶段 6：分布式训练

Pipeline 用最佳参数创建 `PyTorchJob`：

```yaml
apiVersion: kubeflow.org/v1
kind: PyTorchJob
metadata:
  name: final-train
spec:
  pytorchReplicaSpecs:
    Master:
      replicas: 1
    Worker:
      replicas: 4
```

Training Operator 创建 Master + 4 Workers，训练完成后模型写入 S3。

### 阶段 7：模型服务

Pipeline 最后创建 `InferenceService`：

```yaml
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: my-model
spec:
  predictor:
    model:
      modelFormat:
        name: pytorch
      storageUri: s3://bucket/model/
```

KServe Controller 部署模型，暴露 REST/gRPC 端点。

### 阶段 8：监控与迭代

- Pipeline UI 展示 Run 状态、artifact lineage。
- Prometheus/Grafana 监控各组件指标。
- 模型效果反馈触发下一次 pipeline run。

## 4.3 Kubeflow Pipelines v2 执行细节

KFP v2 把 pipeline 编译成 **IR YAML**（Intermediate Representation）：

```yaml
components:
  comp-preprocess:
    executorLabel: exec-preprocess
    inputDefinitions:
      parameters:
        input_path: {parameterType: STRING}
    outputDefinitions:
      parameters:
        output_path: {parameterType: STRING}
dag:
  tasks:
    preprocess:
      componentRef: {name: comp-preprocess}
      inputs:
        parameters:
          input_path: {componentInputParameter: data_url}
```

运行时：

1. API Server 接收 IR YAML。
2. Driver 解析参数、计算 Pod spec。
3. Launcher 拉取 input artifact、准备输出路径。
4. Executor 运行用户容器。
5. Launcher 上传 output artifact、写 MLMD。

## 4.4 失败与重试

- **Pipeline step 失败**：KFP 支持 `retry_policy`，按策略重试。
- **Katib Trial 失败**：超过 `maxFailedTrialCount` 后 Experiment 失败。
- **Training Job 失败**：Training Operator 按 `restartPolicy` 处理（Never/OnFailure/ExitCode）。
- **全部状态通过 K8s status conditions 暴露**，Dashboard 可观测。

## 本章小结

- 完整链路：**Notebook 开发 → Component/Pipeline 编写 → 编译上传 → Run → Katib 调参 → TrainingJob 训练 → KServe 部署 → 监控迭代**。
- KFP v2 核心是 **IR YAML + Driver/Launcher/Executor** 三层执行模型。
- 各阶段失败都有标准的 K8s condition 和重试机制。
- Kubeflow 把一次 ML 迭代变成可复现、可观测、可协作的声明式流程。

**参考来源**

- [Kubeflow Pipelines — Getting Started](https://www.kubeflow.org/docs/components/pipelines/)
- [KFP v2 DSL Documentation](https://www.kubeflow.org/docs/components/pipelines/user-guides/core-functions/)
- [Kubeflow Pipelines AGENTS.md — end-to-end flow](https://github.com/kubeflow/pipelines/blob/master/AGENTS.md)
- 本手册 [KServe](../kserve/04-runtime-workflow)、[Operator 模式](../../02-cloud-native/operator/04-reconcile-loop)

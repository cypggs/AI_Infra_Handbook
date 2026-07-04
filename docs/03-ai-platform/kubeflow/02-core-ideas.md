# 2. 核心思想：组件、CRD 与 ML 生命周期

> 一句话理解：Kubeflow 把 ML 生命周期拆成五个阶段——**开发（Notebooks）、编排（Pipelines）、搜索（Katib）、训练（Training Operator）、服务（KServe）**——每个阶段由一个或多个 Operator 管理，通过 Central Dashboard 和 Profile 提供统一入口与多租户隔离。

## 2.1 组件全景图

```
┌──────────────────────────────────────────────────────────────────────┐
│                      Central Dashboard（统一入口）                    │
│   Notebooks │ Pipelines │ Katib │ Training Jobs │ KServe │ Volumes  │
└─────────────────────────────┬────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        Kubeflow 控制平面                             │
│  Notebook Controller   │   Profile Controller   │   KFAM            │
│  Pipeline API Server   │   Persistence Agent    │   ML Metadata     │
│  Katib Controller      │   Katib DB Manager     │   Suggestion      │
│  Training Operator     │   TF/PyTorch/MPI Job   │   Job Controller  │
│  KServe Controller     │   ...                  │                   │
└──────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        Kubernetes API Server                         │
│   CRD: Notebook, Pipeline, Run, Experiment, Trial, TFJob, ...        │
└──────────────────────────────────────────────────────────────────────┘
```

## 2.2 Notebooks：开发环境即 CRD

Kubeflow Notebook 不是简单地在 K8s 上跑 Jupyter，而是把 Jupyter Server 声明式化：

```yaml
apiVersion: kubeflow.org/v1
kind: Notebook
metadata:
  name: my-notebook
  namespace: alice
spec:
  template:
    spec:
      containers:
        - name: my-notebook
          image: jupyter/scipy-notebook:latest
          resources:
            limits:
              nvidia.com/gpu: 1
          volumeMounts:
            - name: data-vol
              mountPath: /home/jovyan/data
```

Notebook Controller 监听 `Notebook` CRD，创建 StatefulSet + Service + Istio VirtualService，让数据科学家通过浏览器访问。

## 2.3 Pipelines：ML DAG 即代码

Kubeflow Pipelines（KFP）是核心编排引擎。v2 的核心理念：

```
Python DSL
    │
    ▼
Compiler 编译成 IR YAML（pipeline spec）
    │
    ▼
上传至 Pipeline API Server
    │
    ▼
创建 Run（可属于某个 Experiment）
    │
    ▼
调度成 K8s Pod 序列执行
    │
    ▼
Artifact / Metrics 写入 ML Metadata / S3 / MinIO
```

示例：

```python
from kfp import dsl, compiler

@dsl.component
def add(a: float, b: float) -> float:
    return a + b

@dsl.pipeline(name='addition-pipeline')
def add_pipeline(a: float = 1.0, b: float = 2.0):
    add_task = add(a=a, b=4.0)
    add_task2 = add(a=add_task.output, b=b)

compiler.Compiler().compile(add_pipeline, 'pipeline.yaml')
```

关键概念：

- **Component**：一个可复用步骤，可以是 Python function、容器镜像或自定义。
- **Pipeline**：由 component 组成的 DAG。
- **Experiment**：一组相关 Run 的逻辑分组。
- **Run**：一次 pipeline 执行实例。
- **Artifact**：步骤产出的数据/模型文件，存入 artifact store。
- **Cache**：避免重复执行未变更的步骤。

## 2.4 Katib：AutoML 即 CRD

Katib 把超参搜索和 NAS 抽象成 `Experiment` 和 `Trial`：

```yaml
apiVersion: kubeflow.org/v1beta1
kind: Experiment
metadata:
  name: hyperparameter-tuning
spec:
  objective:
    type: minimize
    objectiveMetricName: loss
  algorithm:
    algorithmName: random
  parallelTrialCount: 2
  maxTrialCount: 12
  parameters:
    - name: lr
      parameterType: double
      feasibleSpace:
        min: "0.01"
        max: "0.05"
  trialTemplate:
    primaryContainerName: training-container
    trialParameters:
      - name: learningRate
        reference: lr
    trialSpec:
      apiVersion: batch/v1
      kind: Job
      spec:
        template:
          spec:
            containers:
              - name: training-container
                image: pytorch-mnist:latest
                command:
                  - python
                  - train.py
                  - --lr=${trialParameters.learningRate}
```

关键概念：

- **Experiment**：一次搜索任务，定义目标、搜索空间、算法、Trial 数量。
- **Trial**：一次具体超参组合的实验运行。
- **Suggestion**：根据历史结果生成下一组超参的服务。
- **Early Stopping**：提前终止表现差的 Trial（如 medianstop）。
- **NAS**：神经架构搜索（如 ENAS）。

## 2.5 Training Operator：分布式训练即 CRD

Training Operator 把 PyTorch/TensorFlow/MPI/XGBoost 分布式训练封装成 CRD：

```yaml
apiVersion: kubeflow.org/v1
kind: PyTorchJob
metadata:
  name: pytorch-mnist
spec:
  pytorchReplicaSpecs:
    Master:
      replicas: 1
      template:
        spec:
          containers:
            - name: pytorch
              image: pytorch-mnist:latest
              resources:
                limits:
                  nvidia.com/gpu: 1
    Worker:
      replicas: 3
      template:
        spec:
          containers:
            - name: pytorch
              image: pytorch-mnist:latest
              resources:
                limits:
                  nvidia.com/gpu: 1
```

关键概念：

- **ReplicaSpecs**：定义 Master/Worker/Scheduler 等角色及其副本数。
- **Launcher / Worker**：MPIJob 的 launcher 负责启动，worker 负责计算。
- **Elastic Training**：部分框架支持动态扩缩 worker。

## 2.6 KServe：模型服务

KServe 是 Kubeflow 的模型服务组件，已在 [KServe 主题](../kserve/) 详细讲解。在 Kubeflow 语境下，它与 Central Dashboard 集成，用户可在 Dashboard 里查看 InferenceService 端点。

## 2.7 Central Dashboard 与 Profiles：入口和多租户

### Central Dashboard

统一 Web 入口，展示各组件 UI：

- Home
- Notebooks / TensorBoards / Volumes
- Pipelines（Experiments、Runs、Artifacts）
- Katib（Experiments、Trials）
- KServe Endpoints

### Profile

Kubeflow 的多租户单元：

```yaml
apiVersion: kubeflow.org/v1
kind: Profile
metadata:
  name: alice
spec:
  owner:
    kind: User
    name: alice@example.com
```

Profile Controller 会：

1. 创建一个 namespace（如 `alice`）。
2. 绑定 owner 和 contributors 的 RBAC。
3. 配置 Istio authorization 与 network policies。
4. 可能创建默认 storage / secrets。

KFAM（Kubeflow Access Management）API 用于管理 contributors。

## 2.8 心智模型：一次完整的 ML 旅程

```
数据科学家登录 Central Dashboard
        │
        ▼
创建 Notebook（StatefulSet + PVC）
        │
        ▼
在 Notebook 里开发特征/模型代码
        │
        ▼
把实验代码整理成 KFP Component
        │
        ▼
编译 Pipeline YAML 并上传
        │
        ▼
创建 Run 或 Recurring Run
        │
        ▼
Pipeline 中某个步骤触发 Katib Experiment 调参
        │
        ▼
得到最佳参数后触发 PyTorchJob / TFJob 分布式训练
        │
        ▼
训练产物（模型 artifact）被 KServe 部署为 InferenceService
        │
        ▼
通过 Dashboard / API 监控与迭代
```

## 本章小结

- **Notebooks**：Jupyter 环境声明式化，由 Notebook Controller 管理。
- **Pipelines**：Python DSL → IR YAML → Run，支持 artifact、缓存、实验管理。
- **Katib**：Experiment/Trial/Suggestion 实现超参搜索、early stopping、NAS。
- **Training Operator**：TFJob/PyTorchJob/MPIJob/XGBoostJob 声明式分布式训练。
- **KServe**：Kubeflow 的模型服务层。
- **Central Dashboard / Profile**：统一入口 + 多租户 namespace 隔离。
- 心智模型：开发 → 编排 → 搜索 → 训练 → 服务，全部通过 CRD 在 K8s 上运行。

**参考来源**

- [Kubeflow — Components](https://www.kubeflow.org/docs/started/architecture/)
- [Kubeflow Pipelines — Getting Started](https://www.kubeflow.org/docs/components/pipelines/)
- [Kubeflow Katib — Overview](https://www.kubeflow.org/docs/components/katib/overview/)
- [Kubeflow Training Operator — Overview](https://www.kubeflow.org/docs/components/training/)
- [Kubeflow Notebooks](https://www.kubeflow.org/docs/components/notebooks/)
- [Kubeflow Profiles](https://www.kubeflow.org/docs/components/central-dash/profiles/)

# 2. 核心思想：组件、CRD 与 ML 生命周期

> 一句话理解：Kubeflow 把 ML 生命周期拆成五个阶段——**开发（Notebooks）、编排（Pipelines）、搜索（Katib）、训练（Trainer）、服务（KServe）**——每个阶段由一个或多个 Operator 管理，通过 Central Dashboard 和 Profile 提供统一入口与多租户隔离；2025–2026 年后又叠加了**资产层（Hub）**与 **Python-first SDK** 两层新抽象。

## 2.1 组件全景图

```
┌──────────────────────────────────────────────────────────────────────┐
│              Central Dashboard（统一入口）/ Kubeflow SDK              │
│   Notebooks │ Pipelines │ Katib │ Trainer │ KServe │ Hub │ Spark     │
└─────────────────────────────┬────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        Kubeflow 控制平面                             │
│  Notebook Controller   │   Profile Controller   │   KFAM            │
│  Pipeline API Server   │   Persistence Agent    │   ML Metadata     │
│  Katib Controller      │   Katib DB Manager     │   Suggestion      │
│  Kubeflow Trainer      │   TrainJob / TrainingRuntime Controllers    │
│  KServe Controller     │   Hub (Model Registry) │   Spark Operator  │
└──────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        Kubernetes API Server                         │
│   CRD: Notebook, Pipeline, Run, Experiment, Trial, TrainJob, ...     │
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
- **Trial**：一次具体超参组合的实验运行；1.10 起 trialTemplate 可直接创建 `TrainJob`（而不仅是 batch Job）。
- **Suggestion**：根据历史结果生成下一组超参的服务。
- **Early Stopping**：提前终止表现差的 Trial（如 medianstop）。
- **NAS**：神经架构搜索（如 ENAS）。
- **OptimizerClient**：Katib 的 Python SDK 客户端，可用代码提交调参实验；1.10 起支持 log-uniform / normal / log-normal 参数分布与 push-based 指标采集。

## 2.5 Kubeflow Trainer：分布式训练与 LLM 微调即 CRD

Kubeflow Trainer（原 Training Operator）经历了两代 API 范式：

### V1：每框架一个 CRD（仍维护，处于维护模式）

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

### V2（2025-07 GA）：TrainJob + TrainingRuntime

V2 的核心思想是**把"用户面"与"平台面"解耦**：

- **`TrainJob`**：AI 从业者提交的任务，通过 `spec.runtimeRef` 引用运行时，只需关心 `command`、`numNodes`、资源。
- **`TrainingRuntime` / `ClusterTrainingRuntime`**：平台管理员定义的框架运行时，负责 `torchrun` 启动参数、`MASTER_ADDR`/`MASTER_PORT` 注入、默认镜像、调度插件（Kueue/Volcano gang scheduling）。

```yaml
apiVersion: trainer.kubeflow.org/v1alpha1
kind: TrainJob
metadata:
  name: tune-llama
spec:
  runtimeRef:
    name: torchtune-llama3.2-1b   # 内置 torchtune LLM 微调运行时
  trainer:
    numNodes: 2
    command:
      - tune
      - run
      - --config
      - llama3_2/1B_lora_single_device
```

Trainer v2.2（2026-03）还带来了 JAX、XGBoost、Flux（HPC/MPI）运行时，TrainJob 进度与指标可观测性（Hugging Face `KubeflowTrainerCallback`）；注意其**破坏性变更**：`PodTemplateOverrides` 被 `RuntimePatches` API 取代，`numProcPerNode` 与 `ElasticPolicy` 被移除。

### LLM 微调蓝图

Trainer 内置基于 **torchtune** 的运行时（Llama 3.2、Qwen 2.5 等配方），支持 **LoRA / QLoRA / DoRA** 参数高效微调，并通过 `HuggingFaceModelInitializer` / `HuggingFaceDatasetInitializer` 从 Hugging Face 拉取模型与数据集——微调一个 LLM 从"写一堆 YAML"变成"几行 Python"。

关键概念：

- **runtimeRef**：TrainJob 通过名字引用运行时，实现任务与环境的解耦。
- **Initializer**：初始化器，在训练前拉取模型、数据集（支持 Hugging Face / S3）。
- **调度集成**：Kueue、Volcano、MPI 提供 gang scheduling 与排队。

## 2.6 KServe：模型服务

KServe 是 Kubeflow 的模型服务组件，已在 [KServe 主题](../kserve/) 详细讲解。在 Kubeflow 语境下，它与 Central Dashboard 集成，用户可在 Dashboard 里查看 InferenceService 端点。面向 GenAI 场景，KServe 0.18 新增 **`LLMInferenceService` CRD**：把大模型服务化（含跨节点分布式推理、OpenAI 兼容 API、KV Cache 复用）提升为一等平台原语。

## 2.7 Hub：模型与 Agent 资产中心

Hub（原 Model Registry）在 2026 年完成更名与扩围，定位从"模型注册表"升级为**资产目录**：

- **Model Catalog**：受治理的模型目录，支持从 Hugging Face 直接拉取，带基准测试与硬件对比（Pareto 过滤、延迟排序）。
- **MCP Catalog**：搜索、浏览并部署 MCP 服务器——Kubeflow 因此成为少数把 Agent 工具链也纳入资产治理的 ML 平台。
- **OCI 标准**：模型存储以 OCI 制品（与容器镜像同一套分发机制）为标准，支持 ModelCar 方式挂载加载。
- **KServe 集成**：Hub 可记录线上 `InferenceService` 实际运行的模型版本（reconciliation controller），打通"注册—部署—审计"链路。

## 2.8 Kubeflow SDK：Python 优先的新范式

2026 年的 Kubeflow 不再要求用户手写 YAML。`pip install kubeflow` 提供统一 SDK，核心客户端包括：

| 客户端 | 用途 |
|---|---|
| `TrainerClient` | 提交/管理 TrainJob，LLM 微调（`BuiltinTrainer` + `TorchTuneConfig`） |
| `SparkClient` | Spark Connect 交互式会话 + `SparkApplication` 批作业 |
| `PipelinesClient` | 编译、上传、触发 Pipeline |
| `OptimizerClient`（Katib） | 调参实验，Trial 直接以 TrainJob 运行 |
| `ModelRegistryClient` | 模型注册与目录查询 |

SDK 支持**本地开发后端**（Docker/Podman/本地进程），同一段代码先在本地跑通、再无缝提交到 K8s 集群——"本地开发 → 集群规模化"的闭环是 Kubeflow 在 GenAI 时代的重要竞争力。

```python
from kubeflow.trainer import TrainerClient, CustomTrainer, TrainJobTemplate

# 定义训练函数（同一份代码可本地跑、可上集群）
def train_fn(parameters):
    import torch
    # ... 训练逻辑 ...

template = TrainJobTemplate(
    runtime="torch-distributed",
    trainer=CustomTrainer(func=train_fn, num_nodes=2),
)
job_id = TrainerClient().train(**template)   # 提交到 K8s
TrainerClient().wait_for_job_status(job_id)

# 本地开发：换 backend 即可，无需集群
from kubeflow.trainer import ContainerBackendConfig
client = TrainerClient(backend_config=ContainerBackendConfig())  # Docker/Podman
# 或 LocalProcessBackendConfig() 直接以子进程跑
job_id = client.train(trainer=CustomTrainer(func=train_fn))
```

LLM 微调场景可使用更上层的 `BuiltinTrainer` + `TorchTuneConfig`（内置 torchtune 配方与 LoRA/QLoRA/DoRA 配置），配合 `HuggingFaceModelInitializer` 自动拉取模型。

## 2.9 Central Dashboard 与 Profiles：入口和多租户

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

## 2.10 心智模型：一次完整的 ML 旅程

```
数据科学家登录 Central Dashboard（或用 Kubeflow SDK）
        │
        ▼
创建 Notebook（StatefulSet + PVC）
        │
        ▼
在 Notebook 里开发特征/模型代码（SDK 可在本地先跑通）
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
Pipeline 中某个步骤触发 Katib Experiment 调参（Trial = TrainJob）
        │
        ▼
得到最佳参数后提交 TrainJob（runtimeRef 指向 torchtune/PyTorch 运行时）
        │
        ▼
训练产物注册到 Hub（OCI 制品 + Model Catalog）
        │
        ▼
KServe 部署为 InferenceService / LLMInferenceService
        │
        ▼
通过 Dashboard / API 监控与迭代
```

## 本章小结

- **Notebooks**：Jupyter 环境声明式化，由 Notebook Controller 管理；v2 正重构为 CRD 驱动的 Workspaces。
- **Pipelines**：Python DSL → IR YAML → Run，支持 artifact、缓存、实验管理；2.16 起本地可运行（Local Runner）。
- **Katib**：Experiment/Trial/Suggestion 实现超参搜索、early stopping、NAS；Trial 可直接以 TrainJob 运行。
- **Trainer**：V1 框架级 CRD 进入维护模式；V2 以 `TrainJob` + `TrainingRuntime` 统一范式，内置 LLM 微调运行时。
- **KServe**：模型服务层，新增 `LLMInferenceService` 支撑大模型服务化。
- **Hub**：模型/OCI 制品/MCP 服务器统一资产目录。
- **SDK**：`pip install kubeflow`，一套 Python API 管训练、Spark、Pipeline、调参、注册，支持本地后端。
- **Central Dashboard / Profile**：统一入口 + 多租户 namespace 隔离。
- 心智模型：开发 → 编排 → 搜索 → 训练 → 注册 → 服务，全部通过 CRD 在 K8s 上运行。

**参考来源**

- [Kubeflow — Components](https://www.kubeflow.org/docs/started/architecture/)
- [Kubeflow Pipelines — Getting Started](https://www.kubeflow.org/docs/components/pipelines/)
- [Kubeflow Katib — Overview](https://www.kubeflow.org/docs/components/katib/overview/)
- [Kubeflow Trainer — Migration to v2](https://trainer.kubeflow.org/en/latest/operator-guides/migration.html)
- [Kubeflow SDK GitHub](https://github.com/kubeflow/sdk)
- [Kubeflow 1.11 Release Announcement](https://blog.kubeflow.org/kubeflow-1.11-release/)
- [Kubeflow Community Distribution 26.03 Release](https://blog.kubeflow.org/kubeflow-26.03-release/)

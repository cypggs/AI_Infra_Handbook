# 5. 核心模块：Central Dashboard、Notebook、Profile、Pipelines、Katib、Trainer、Hub、Spark Operator

> 一句话理解：Kubeflow 是多个独立 Operator 的组合，**每个组件都有自己的控制器、API 和 UI**，它们统一挂在 Central Dashboard 下，用 Profile 做租户边界；2026 年后又由统一的 Python SDK 在它们之上提供编程接口。

## 5.1 Central Dashboard

### 定位

Central Dashboard 是用户进入 Kubeflow 的**统一入口**。它本身不执行 ML 工作负载，而是**聚合**各组件的 UI 与链接，并提供 namespace / Profile 切换。

### 主要功能

- 展示当前用户拥有的 Profile / namespace。
- 左侧导航到 Notebooks、Pipelines、Katib、Training Jobs、KServe、Volumes。
- 通过 iframe 或路由代理嵌入各组件前端。
- 与 Istio / auth 集成，只展示有权限的资源。

### 技术实现

```
用户 → Istio Gateway → Central Dashboard (Node.js/Express)
                              │
                              ├─ iframe / reverse proxy → KFP UI
                              ├─ iframe / reverse proxy → Katib UI
                              ├─ iframe / reverse proxy → Notebook Web App
                              └─ KServe UI / TensorBoard 链接
```

源码目录：`github.com/kubeflow/kubeflow/components/centraldashboard`。

## 5.2 Notebook Controller

### 职责

监听 `Notebook` CRD，创建并维护：

- **StatefulSet**：运行 Jupyter/Lab/VS Code server。
- **Service**：暴露 Pod 端口。
- **Istio VirtualService**：把 `/notebook/<namespace>/<name>` 路由到该 Service。
- **PVC**：用户目录持久化。

### CRD 核心字段

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
          image: jupyter/scipy-notebook:latest
          resources:
            limits:
              nvidia.com/gpu: 1
          volumeMounts:
            - name: workspace
              mountPath: /home/jovyan/workspace
```

### 状态机

```
Created
   │
   ▼
Waiting → StatefulSet Ready → Running
   │
   ▼
Stopping → Stopped (scale StatefulSet replicas to 0)
```

### 常见配置

- **镜像**：`jupyter/scipy-notebook`、`jupyter/pytorch-notebook`、`jupyter/tensorflow-notebook`、自定义镜像。
- **GPU**：在 container resources 中声明 `nvidia.com/gpu`。
- **持久化**：挂载 PVC； Kubeflow 提供 Volumes UI 创建 PVC。

## 5.3 Profile & KFAM

### Profile 多租户模型

Kubeflow 把每个租户映射到一个 K8s namespace，通过 `Profile` CRD 声明：

```yaml
apiVersion: kubeflow.org/v1
kind: Profile
metadata:
  name: alice
spec:
  owner:
    kind: User
    name: alice@example.com
  resourceQuotaSpec:
    hard:
      requests.cpu: "10"
      requests.memory: 40Gi
      requests.nvidia.com/gpu: "2"
```

### Profile Controller 行为

1. 创建 namespace `alice`。
2. 创建 `ServiceAccount`、默认 `Editor` / `Viewer` RoleBinding。
3. 创建 Istio `AuthorizationPolicy`，限制跨 namespace 访问。
4. 应用 `ResourceQuota`。

### KFAM（Kubeflow Access Management）

KFAM 提供 REST API 管理 Profile 的 contributors：

```http
GET /kfam/v1/profiles          # 列出当前用户可访问的 Profile
POST /kfam/v1/bindings         # 添加 contributor
DELETE /kfam/v1/bindings       # 移除 contributor
```

Central Dashboard 通过 KFAM 决定用户能看到哪些 namespace。

## 5.4 Kubeflow Pipelines（KFP）后端

### 后端组成

| 模块 | 作用 |
|---|---|
| API Server | 提供 REST/gRPC API，管理 Pipeline、Run、Experiment、RecurringRun |
| Persistence Agent | 监听 K8s Pod，把执行状态回写到 ML Metadata / DB |
| Scheduled Workflow Controller | 管理周期性 Run（Cron） |
| ML Metadata（MLMD） | 记录 artifact、execution、context 血缘 |
| Artifact Store | S3 / GCS / MinIO，存放 artifact 文件 |
| Visualization Server | 为 TensorBoard 等可视化组件提供入口 |

### KFP v2 执行模型

```
User DSL
   │
   ▼
Compiler → IR YAML (pipeline spec)
   │
   ▼
API Server stores spec
   │
   ▼
Run created
   │
   ▼
Driver / Launcher / Executor
   │
   ▼
K8s Pods
   │
   ▼
Artifact + MLMD
```

- **Driver**：解析输入参数、artifact、决定 Pod spec。
- **Launcher**：附加在 user container 的 init/sidecar，负责下载/上传 artifact。
- **Executor**：用户业务容器。

### 2.15+ 存储与认证变化

- **SeaweedFS 取代 MinIO 成为默认对象存储**（2.15 引入，2.16 完成 MinIO 客户端替换为 AWS SDK v2；MinIO manifest 仍可用但可能在未来移除）。
- **数据库自动迁移**：从 2.15.0 之前升级时自动建索引；不支持回滚，生产库升级前务必备份。
- **原生 OIDC**：2.16 起 API Server 可直接对接 OIDC，不再强依赖 Istio 认证链。
- **Local Runner**：2.16 起可在本地（无集群）执行 pipeline，支持条件求值与并行控制流，用于开发调试。

### 关键表（MySQL / SQLite）

- `pipelines`：pipeline 元数据。
- `runs`：run 元数据。
- `experiments`：experiment 元数据。
- `tasks`、`artifacts`：MLMD 表。

## 5.5 Katib

### 核心组件

| 组件 | 作用 |
|---|---|
| Katib Controller | 监听 `Experiment`，创建 `Trial` 和 `Suggestion` |
| Katib DB Manager | 把 experiment/trial 数据写入 MySQL / Postgres |
| Suggestion | 每个 Experiment 对应一个 suggestion service，按算法生成超参 |
| Early Stopping | 可选边车，终止无潜力的 Trial |
| Katib UI | 展示 Experiments / Trials |

### 算法支持

| 类型 | 算法 |
|---|---|
| 超参搜索 | random、grid、bayesian optimization（skopt）、tpe、hyperband、cmaes、sobol |
| NAS | ENAS、DARTS（部分支持） |
| Early Stopping | medianstop |

1.10 起增强：

- **LLM 微调调参 API**：面向大模型微调实验的高层 API。
- **新参数分布**：log-uniform、normal、log-normal。
- **Push-based 指标采集**：Trial 主动上报指标，替代轮询文件，性能与可管理性更好。
- **OptimizerClient**：Python SDK 客户端，`Experiment` 的 Trial 可直接以 `TrainJob` 运行（而非仅 batch Job），与 Kubeflow Trainer v2 深度集成。

### Trial 生命周期

```
Created → Pending → Running → Succeeded / Failed / Killed
   │
   ▼
Metrics 写入 /katib/metrics/metrics.json（默认）
   │
   ▼
Katib Controller 解析 metrics → 更新 Experiment status
```

### Metrics Collection

Trial 容器把目标指标写到约定路径：

```bash
/katib/metrics/metrics.json
```

内容示例：

```json
{"loss": 0.034, "accuracy": 0.992}
```

Controller 读取后比较，保留最优 Trial。

## 5.6 Kubeflow Trainer（原 Training Operator）

### 职责

管理分布式训练与 LLM 微调生命周期。项目已从 `kubeflow/training-operator` 更名为 `kubeflow/trainer`，两代 API 并存：

- **V1（维护模式）**：监听 `TFJob`、`PyTorchJob`、`MPIJob`、`XGBoostJob`、`PaddleJob`、`MXJob`、`JAXJob` 等 CRD。
- **V2（2025-07 GA，当前默认）**：统一的 `TrainJob` + `TrainingRuntime` 模型，仓库主体在 `pkg/controller/`（V2 控制器）。

### V1 通用 CRD 结构

```yaml
apiVersion: kubeflow.org/v1
kind: PyTorchJob
metadata:
  name: pytorch-mnist
spec:
  runPolicy:
    cleanPodPolicy: Running
  pytorchReplicaSpecs:
    Master:
      replicas: 1
      template:
        spec:
          containers:
            - name: pytorch
              image: pytorch-mnist:latest
    Worker:
      replicas: 4
```

### V2：TrainJob + TrainingRuntime

```yaml
apiVersion: trainer.kubeflow.org/v1alpha1
kind: TrainJob
metadata:
  name: finetune-llama
spec:
  runtimeRef:
    name: torchtune-llama3.2-1b
  trainer:
    numNodes: 2
    command: ["tune", "run", "--config", "llama3_2/1B_qlora_single_device"]
```

- **`TrainingRuntime` / `ClusterTrainingRuntime`**：平台面资源，声明镜像、入口（`torchrun` 等）、默认配置与调度插件。
- **内置运行时**：torchtune LLM 微调（Llama 3.2、Qwen 2.5 配方，LoRA/QLoRA/DoRA）、torch-distributed、DeepSpeed、MLX（MPI）、JAX、XGBoost、Flux（HPC）。
- **Initializer**：`HuggingFaceModelInitializer`、`HuggingFaceDatasetInitializer` 等，在训练前拉取模型/数据集（支持 Hugging Face / S3）；可选 Arrow/DataFusion 数据缓存把数据集流式喂给 GPU。
- **可观测性**：v2.2 起 TrainJob 暴露进度与指标，Hugging Face Transformers 可通过 `KubeflowTrainerCallback` 自动上报。

### v2.2 破坏性变更（升级注意）

- `PodTemplateOverrides` 被 **`RuntimePatches` API** 取代。
- 移除 `numProcPerNode`（Torch API）与 `ElasticPolicy` API。
- 修复 TrainJob API 不可变性问题（创建后关键字段不可修改）。

### v2.3 新动向（2026-08，上游最新）

- **`OptimizationJob` CRD**（KEP-3562）：把训练后的模型优化任务（压缩、蒸馏、量化等）纳入与 TrainJob 同一套 API 范式。
- **TrainingRuntime 快照机制**（KEP-2599）：更新运行时时通过快照保持在跑任务不受影响，解耦运行时生命周期与 TrainJob。
- **破坏性升级路径**：v2.0/2.1/2.2 必须**先升级到 v2.3**，再升级之后的版本（CRD 移入 Helm chart 模板目录、移除运行时 finalizer）。

### Replica 角色（V1）

| CRD | 角色 |
|---|---|
| TFJob | Chief / Worker / ParameterServer / Evaluator |
| PyTorchJob | Master / Worker |
| MPIJob | Launcher / Worker |
| XGBoostJob | Master / Worker |
| PaddleJob | Master / Worker |
| MXJob | Scheduler / Server / Worker |
| JAXJob | Worker |

### 关键行为

- **服务发现**：为每个 replica 创建 Headless Service，Pod 通过 DNS 发现同伴。
- **环境变量**：把集群信息注入容器（如 `MASTER_ADDR`、`MASTER_PORT`、`WORLD_SIZE`）。
- **失败处理**：通过 `restartPolicy`（Never / OnFailure / ExitCode）控制重试。
- **调度**：与 Kueue / Volcano / Coscheduling 集成实现 gang scheduling 与队列。

### 源码结构

- 仓库：`github.com/kubeflow/trainer`（原 training-operator）。
- V1：`pkg/controller.v1/pytorch`、`pkg/controller.v1/tensorflow` 等目录分别实现各框架 controller。
- V2：`pkg/controller/trainjob_controller.go`、`pkg/controller/trainingruntime_controller.go`。

## 5.7 Hub（原 Model Registry）

### 定位

Hub 是 2026 年由 Model Registry 更名扩围而来的**资产中心**，26.03 起默认随发行版安装：

| 能力 | 说明 |
|---|---|
| Model Registry | 模型版本、元数据、过滤/排序/归档（UI 完整支持） |
| Model Catalog | 受治理的模型目录：Hugging Face 拉取、基准测试与硬件对比（Pareto 过滤、延迟排序） |
| MCP Catalog | 搜索/浏览/部署 MCP 服务器，含工具列表与过滤 |
| KServe 集成 | Custom Storage Initializer + reconciliation controller（记录线上 InferenceService 实际运行的模型版本） |
| 存储后端 | MySQL / PostgreSQL；模型本体以 OCI 制品存储 |

其他变化：API 趋于稳定（准备 v1）；Python 客户端支持打包上传与异步上传 Job；移除对 legacy Google MLMD 的依赖。上游最新 v0.3.17（2026-09），组件仍为 alpha 状态。

## 5.8 Spark Operator

2025 年起成为 Kubeflow 核心组件（26.03 矩阵为 2.5.0，上游最新 v2.5.2，2026-07，基于 controller-runtime 重构）：

- 支持 Spark 4 / Spark Connect、suspend/resume、Kueue 队列。
- YuniKorn gang scheduling、动态分配与 shuffle tracking。
- 更强安全上下文（seccompProfile、readOnlyRootFilesystem）。
- 通过 Kubeflow SDK 的 `SparkClient` 提交：`connect()` 交互式 Spark Connect 会话，或 `submit_job()` 批作业（`SparkApplication` CRD）。

## 5.9 KServe 集成

KServe 是 Kubeflow 的模型服务组件。在 Kubeflow 部署中：

- KServe Controller 监听 `InferenceService` CRD；0.18 起新增 `LLMInferenceService`（上游 0.19–0.21 持续迭代其 v1alpha2 API、金丝雀发布与 LocalModelCache）。
- Central Dashboard 展示 InferenceService 列表与端点。
- 可通过 Pipeline 部署 `InferenceService` 作为最后一步。
- Hub 的 reconciliation controller 会把线上服务与注册版本对账。

已在 [KServe 主题](../kserve/) 详述，本章不再展开。

## 5.10 组件之间的调用关系

```
Central Dashboard / Kubeflow SDK
   │
   ├─ Notebook Controller → StatefulSet / Service / VS
   ├─ Profile Controller → Namespace / RBAC / AuthorizationPolicy
   ├─ KFP API Server → Run → Driver/Launcher/Executor → Pod
   ├─ Katib Controller → Trial → TrainJob / Job
   ├─ Kubeflow Trainer → TrainJob → TrainingRuntime → Pod
   ├─ Hub → Model Catalog / OCI Registry → KServe Initializer
   ├─ Spark Operator → SparkApplication → Driver/Executor Pod
   └─ KServe Controller → InferenceService / LLMInferenceService → Deployment
```

所有组件最终都通过 Kubernetes API Server 操作 etcd 和 Pod。

## 本章小结

- **Central Dashboard**：统一入口，聚合各组件 UI。
- **Notebook Controller**：把 Jupyter 环境声明式化。
- **Profile / KFAM**：namespace 级多租户与权限管理。
- **KFP**：API Server + Persistence Agent + MLMD + artifact store + Driver/Launcher/Executor；2.16 默认 SeaweedFS、原生 OIDC、Local Runner。
- **Katib**：Controller + DB Manager + Suggestion + Early Stopping；OptimizerClient 让 Trial 直接跑 TrainJob。
- **Kubeflow Trainer**：V1 框架 CRD 维护模式；V2 `TrainJob` + `TrainingRuntime` 统一范式，内置 LLM 微调运行时；v2.3 新增 OptimizationJob 与运行时快照。
- **Hub**：模型目录 + MCP Catalog + OCI 制品，默认安装（上游 v0.3.17，alpha）。
- **Spark Operator**：数据工程核心组件，SDK 原生支持。
- 各组件独立迭代，通过 K8s API Server 协同。

**参考来源**

- [Kubeflow Central Dashboard](https://www.kubeflow.org/docs/components/central-dash/)
- [Kubeflow Notebooks](https://www.kubeflow.org/docs/components/notebooks/)
- [Kubeflow Profiles](https://www.kubeflow.org/docs/components/central-dash/profiles/)
- [KFP v2 Architecture](https://www.kubeflow.org/docs/components/pipelines/)
- [Katib Overview](https://www.kubeflow.org/docs/components/katib/overview/)
- [Kubeflow Trainer v2.2 Release](https://blog.kubeflow.org/kubeflow-trainer-v2.2-release/)
- [Kubeflow Trainer v2.3.0 Release Notes](https://github.com/kubeflow/trainer/releases/tag/v2.3.0)
- [Kubeflow Hub GitHub](https://github.com/kubeflow/hub)
- [Kubeflow SDK GitHub](https://github.com/kubeflow/sdk)
- [Kubeflow Community Distribution 26.03 Release](https://blog.kubeflow.org/kubeflow-26.03-release/)

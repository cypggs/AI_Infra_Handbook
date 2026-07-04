# 5. 核心模块：Central Dashboard、Notebook、Profile、Pipelines、Katib、Training Operator

> 一句话理解：Kubeflow 是多个独立 Operator 的组合，**每个组件都有自己的控制器、API 和 UI**，它们统一挂在 Central Dashboard 下，用 Profile 做租户边界。

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

## 5.6 Training Operator

### 职责

监听 `TFJob`、`PyTorchJob`、`MPIJob`、`XGBoostJob`、`PaddleJob`、`MXJob`、`JAXJob` 等 CRD，创建对应的 Pod/Job/Service，管理分布式训练生命周期。

### 通用 CRD 结构

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

### Replica 角色

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
- **弹性训练**：PyTorchJob 支持 `elasticPolicy` 动态扩缩。

### 源码结构

- `github.com/kubeflow/training-operator`
- `pkg/controller.v1/pytorch`、`pkg/controller.v1/tensorflow` 等目录分别实现各框架 controller。

## 5.7 KServe 集成

KServe 是 Kubeflow 的模型服务组件。在 Kubeflow 部署中：

- KServe Controller 监听 `InferenceService` CRD。
- Central Dashboard 展示 InferenceService 列表与端点。
- 可通过 Pipeline 部署 `InferenceService` 作为最后一步。

已在 [KServe 主题](../kserve/) 详述，本章不再展开。

## 5.8 组件之间的调用关系

```
Central Dashboard
   │
   ├─ Notebook Controller → StatefulSet / Service / VS
   ├─ Profile Controller → Namespace / RBAC / AuthorizationPolicy
   ├─ KFP API Server → Run → Driver/Launcher/Executor → Pod
   ├─ Katib Controller → Trial → Job / PyTorchJob
   ├─ Training Operator → TFJob / PyTorchJob / MPIJob → Pod
   └─ KServe Controller → InferenceService → Knative / Deployment
```

所有组件最终都通过 Kubernetes API Server 操作 etcd 和 Pod。

## 本章小结

- **Central Dashboard**：统一入口，聚合各组件 UI。
- **Notebook Controller**：把 Jupyter 环境声明式化。
- **Profile / KFAM**：namespace 级多租户与权限管理。
- **KFP**：API Server + Persistence Agent + MLMD + artifact store + Driver/Launcher/Executor。
- **Katib**：Controller + DB Manager + Suggestion + Early Stopping 实现 AutoML。
- **Training Operator**：一套 Operator 管理多种分布式训练框架。
- 各组件独立迭代，通过 K8s API Server 协同。

**参考来源**

- [Kubeflow Central Dashboard](https://www.kubeflow.org/docs/components/central-dash/)
- [Kubeflow Notebooks](https://www.kubeflow.org/docs/components/notebooks/)
- [Kubeflow Profiles](https://www.kubeflow.org/docs/components/central-dash/profiles/)
- [KFP v2 Architecture](https://www.kubeflow.org/docs/components/pipelines/)
- [Katib Overview](https://www.kubeflow.org/docs/components/katib/overview/)
- [Training Operator Overview](https://www.kubeflow.org/docs/components/training/)

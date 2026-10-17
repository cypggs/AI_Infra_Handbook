# 6. 源码分析：关键仓库、目录结构与调用链

> 一句话理解：Kubeflow 没有单一源码仓库，而是**多个独立仓库组成的 Operator 联邦**；理解每个仓库的 `pkg/controller` / `backend/src` 结构，就能看懂一次 `kubectl apply` 背后如何被翻译成 Pod、Service 和 Artifact。

## 6.1 源码仓库地图

| 仓库 | 负责组件 | 本主题关联章节 |
|---|---|---|
| `github.com/kubeflow/kubeflow` | Profile Controller、KFAM（注：Central Dashboard 与 Notebooks 自 26.03 起拆分至 `kubeflow/dashboard`、`kubeflow/notebooks` 独立仓库） | 第 3、5 章 |
| `github.com/kubeflow/pipelines` | KFP SDK、Backend（API Server / Driver / Launcher / Persistence Agent）、Frontend | 第 2、4、5 章 |
| `github.com/kubeflow/katib` | Katib Controller、Suggestion、DB Manager、Early Stopping、UI | 第 2、5 章 |
| `github.com/kubeflow/trainer`（原 training-operator） | V1 框架 Job Controller；V2 TrainJob / TrainingRuntime Controller | 第 2、5 章 |
| `github.com/kubeflow/sdk` | 统一 Python SDK（TrainerClient / SparkClient / PipelinesClient / OptimizerClient / ModelRegistryClient） | 第 2、4 章 |
| `github.com/kubeflow/hub`（原 model-registry） | Hub：模型目录、MCP Catalog、OCI 制品、UI | 第 2、5 章 |
| `github.com/kubeflow/manifests` | Kustomize 发行版（社区日历版本） | 第 8 章 |
| `github.com/kubeflow/kserve` | KServe 服务组件 | [KServe 主题](../kserve/) |

## 6.2 `kubeflow/pipelines` 关键路径

### 目录结构

```
kubeflow/pipelines
├── sdk/python/kfp/              # Python SDK：DSL、Compiler、Client、Executor
│   ├── dsl/                     # @dsl.component / @dsl.pipeline 实现
│   ├── compiler/                # pipeline_spec_builder.py 编译器
│   └── client/                  # 上传、创建 Run
├── backend/
│   ├── src/apiserver/           # Go API Server
│   ├── src/crd/controller/scheduledworkflow/  # 周期性 Run 控制器
│   ├── metadata_writer/         # 写 ML Metadata
│   ├── Dockerfile.driver        # Driver 镜像
│   └── Dockerfile.launcher      # Launcher 镜像
├── frontend/                    # React + TypeScript UI
├── api/                         # Pipeline Spec Protobuf 定义
└── kubernetes_platform/         # KFP Kubernetes 平台扩展
```

### SDK → IR YAML 编译链路

```
@dsl.component / @dsl.pipeline
        │
        ▼
sdk/python/kfp/dsl/
        │
        ▼
sdk/python/kfp/compiler/pipeline_spec_builder.py
        │
        ▼
pipeline_spec.proto (IR YAML)
```

`pipeline_spec.proto` 是 SDK 与后端的契约，定义了 `PipelineSpec`、`ComponentSpec`、`TaskSpec` 等。

### 后端执行链路

根据 [Kubeflow Pipelines AGENTS.md](https://github.com/kubeflow/pipelines/blob/master/AGENTS.md) 描述的流程：

```
SDK → API Server → Driver → Launcher → Executor → 完成
```

| 组件 | 职责 | 关键路径 |
|---|---|---|
| API Server | 接收 REST/gRPC 请求；管理 Pipeline/Run/Experiment；把 pipeline spec 编译为 Argo/K8s 资源 | `backend/src/apiserver/*.go` |
| Driver | 解析输入参数、计算 Pod spec patch、决定 cache 命中 | `backend/Dockerfile.driver` |
| Launcher | 拉取 input artifact、准备输出路径、调用用户 Executor、上传 output artifact | `ghcr.io/kubeflow/kfp-launcher` |
| Executor | 用户 Python 容器入口 | `sdk/python/kfp/dsl/executor_main.py` |
| Persistence Agent | 监听 Pod，把状态回写到 ML Metadata / DB | `backend/src/agent/` |

### API Server 关键文件

- `backend/src/apiserver/main.go`：入口，初始化 HTTP/gRPC server。
- `backend/src/apiserver/server/*.go`：Pipeline、Run、Experiment、Job 等 handler。
- `backend/src/apiserver/storage/*.go`：MySQL/SQLite 持久化。
- `backend/src/apiserver/resource/*.go`：ResourceManager，协调 Run 生命周期。

### 本地开发栈

官方 kind 开发环境暴露：

| 端口 | 服务 |
|---|---|
| 3000 | Web UI |
| 3306 | MariaDB |
| 8080 | ML Metadata gRPC |
| 8888 | API Server |
| 9000 | 对象存储（旧版为 MinIO，2.15+ 为 SeaweedFS） |

## 6.3 `kubeflow/katib` 关键路径

### 目录结构

```
kubeflow/katib
├── pkg/
│   ├── apis/v1beta1/            # Experiment/Trial/Suggestion CRD 定义
│   ├── controller.v1beta1/      # 主控制器
│   │   ├── experiment/          # Experiment Controller
│   │   ├── trial/               # Trial Controller
│   │   └── suggestion/          # Suggestion Controller
│   ├── suggestion/v1beta1/      # 算法实现（random、bayesian、tpe、enas 等）
│   ├── db/v1beta1/              # Katib DB Manager
│   ├── earlystopping/v1beta1/   # Median Stop 等早停算法
│   ├── metricscollector/v1beta1/# Metrics Collector
│   └── ui/v1beta1/              # Katib UI 后端
├── cmd/                         # 各组件 main.go
├── examples/v1beta1/            # 示例 YAML
└── manifests/                   # 安装清单
```

### 控制器调用链

```
用户创建 Experiment
        │
        ▼
Experiment Controller
        │
        ├─ 校验 spec（objective、algorithm、parameters）
        ├─ 创建 Suggestion Deployment / Service
        ├─ 调用 Suggestion 获取 Trial 参数
        ├─ 创建 Trial CR
        │
        ▼
Trial Controller
        │
        ├─ 根据 trialTemplate 创建 Job / PyTorchJob / TFJob
        ├─ 监听 Trial Pod 状态
        ├─ 读取 /katib/metrics/metrics.json
        │
        ▼
Experiment Controller 汇总结果 → 更新 Experiment status
```

### 关键文件

- `pkg/controller.v1beta1/experiment/experiment_controller.go`：Experiment reconcile 入口。
- `pkg/controller.v1beta1/trial/trial_controller.go`：Trial reconcile 入口。
- `pkg/suggestion/v1beta1/`：各算法 service 实现。
- `pkg/db/v1beta1/db.go`：数据库读写封装。

### Metrics 收集

Trial 训练容器把指标写入约定文件：

```bash
/katib/metrics/metrics.json
```

Metrics Collector 通过 sidecar 读取并上报；Experiment Controller 据此判断目标函数值。

## 6.4 `kubeflow/trainer`（原 training-operator）关键路径

### 目录结构

```
kubeflow/trainer
├── pkg/
│   ├── apis/                    # V1 各框架 CRD Go types + V2 trainer.kubeflow.org types
│   ├── controller.v1/           # V1 控制器（维护模式，仍接收缺陷修复）
│   │   ├── pytorch/             # PyTorchJob controller
│   │   ├── tensorflow/          # TFJob controller
│   │   ├── mpi/                 # MPIJob controller
│   │   ├── xgboost/             # XGBoostJob controller
│   │   └── common/              # 公共逻辑：pod/service 创建、状态汇总
│   └── controller/              # V2 统一 TrainJob / TrainingRuntime 控制器（当前默认）
├── cmd/                         # V1 / V2 各组件 main.go
└── manifests/                   # 安装清单（含 Helm）
```

### V1 控制器通用调用链

```
用户创建 PyTorchJob
        │
        ▼
PyTorchJob Controller (pkg/controller.v1/pytorch)
        │
        ├─ 解析 replicaSpecs（Master/Worker）
        ├─ 为每个 replica 创建 Pod
        ├─ 为每个 replica 创建 Headless Service（DNS 发现）
        ├─ 注入环境变量（MASTER_ADDR、MASTER_PORT、WORLD_SIZE 等）
        ├─ 监听 Pod 状态
        │
        ▼
更新 PyTorchJob Status（conditions、replicaStatuses）
```

### V2 控制器调用链（GA，Kubeflow 1.11+ 默认）

```
用户/SDK 创建 TrainJob（spec.runtimeRef: torchtune-llama3.2-1b）
        │
        ▼
TrainJob Controller (pkg/controller/trainjob_controller.go)
        │
        ├─ 解析 runtimeRef → 获取 TrainingRuntime / ClusterTrainingRuntime
        ├─ 应用 RuntimePatches（v2.2 取代 PodTemplateOverrides）
        ├─ 通过 Initializer 准备模型/数据集（Hugging Face / S3）
        ├─ 按运行时模板生成 Pod/Job（torchrun 入口、env 注入）
        ├─ 集成 Kueue/Volcano gang scheduling
        │
        ▼
更新 TrainJob Status（生命周期、进度、指标）
```

### 关键文件

- `pkg/controller.v1/pytorch/pytorchjob_controller.go`：V1 PyTorchJob reconcile。
- `pkg/controller.v1/common/job.go`：V1 通用 job 接口与状态机。
- `pkg/controller/trainjob_controller.go`：V2 TrainJob reconcile。
- `pkg/controller/trainingruntime_controller.go`：V2 TrainingRuntime reconcile。

> v2.2 破坏性变更：`PodTemplateOverrides` → `RuntimePatches` API；移除 `numProcPerNode` 与 `ElasticPolicy`。升级前需迁移已有作业模板。

## 6.5 `kubeflow/kubeflow`（Notebook / Profile / Dashboard）

### Notebook Controller

仓库：`components/notebook-controller`

关键路径：

```
components/notebook-controller
├── controllers/
│   └── notebook_controller.go    # Notebook reconcile
├── api/
│   └── v1/notebook_types.go      # Notebook CRD types
└── main.go                       # 入口
```

调用链：

```
Notebook CR 创建
        │
        ▼
Notebook Controller
        │
        ├─ 创建 StatefulSet（Jupyter container + PVC）
        ├─ 创建 Service
        ├─ 创建 Istio VirtualService（/notebook/ns/name）
        ├─ 设置 status.ready/state
        │
        ▼
用户通过 Central Dashboard 打开 Notebook
```

### Profile Controller

仓库：`components/profile-controller`

关键路径：

```
components/profile-controller
├── controllers/
│   └── profile_controller.go     # Profile reconcile
├── api/
│   └── v1/profile_types.go       # Profile CRD types
└── main.go
```

调用链：

```
Profile CR 创建
        │
        ▼
Profile Controller
        │
        ├─ 创建 namespace
        ├─ 创建 owner ServiceAccount + RoleBinding
        ├─ 创建 contributors RoleBindings
        ├─ 创建 Istio AuthorizationPolicy
        ├─ 应用 ResourceQuota（若 spec 中定义）
        │
        ▼
KFAM API 管理 contributors
```

### Central Dashboard

仓库：`components/centraldashboard`

- Node.js/Express 后端，提供 `/api/workgroup` 等接口。
- 前端通过 iframe 或代理嵌入各组件 UI。
- 与 Istio auth header 集成，识别当前用户。

## 6.6 关键调用链全景

一次完整的 Pipeline Run 从代码到训练：

```
1. Python DSL
   sdk/python/kfp/dsl/
        │
        ▼
2. Compiler 生成 IR YAML
   sdk/python/kfp/compiler/pipeline_spec_builder.py
        │
        ▼
3. kfp.Client / SDK PipelinesClient 上传并创建 Run
   backend/src/apiserver/
        │
        ▼
4. API Server 把 Run 拆成任务 → Driver/Launcher/Executor
   backend/src/apiserver/resource/
        │
        ▼
5. 某个 Task 创建 Katib Experiment（Trial = TrainJob）
   pkg/controller.v1beta1/experiment/（katib）
        │
        ▼
6. Katib 创建 Trial → TrainJob → Metrics 上报
   pkg/controller.v1beta1/trial/（katib）+ pkg/controller/（trainer）
        │
        ▼
7. 最佳参数触发 TrainJob（runtimeRef → TrainingRuntime）
   pkg/controller/trainjob_controller.go
        │
        ▼
8. 模型以 OCI 制品推入 Hub，KServe 部署 InferenceService
   github.com/kubeflow/hub → github.com/kubeflow/kserve
```

## 6.7 阅读源码的建议路径

1. **先看 CRD types**：每个仓库的 `api/v1/` 或 `apis/` 下定义了 spec/status，能快速理解“这个组件管理什么”。
2. **再看 controller 的 reconcile**：通常 `controllers/*.go` 或 `pkg/controller.v1/*/...job_controller.go`，看懂“收到 CR 后创建什么 K8s 原生资源”。
3. **最后看 SDK / CLI**：理解用户侧如何触发这些 CR。

## 本章小结

- Kubeflow 由 **8+ 个核心仓库**组成，彼此独立发布；Dashboard/Notebooks 已拆分为独立仓库。
- **KFP**：SDK 编译 IR YAML → API Server → Driver/Launcher/Executor。
- **Katib**：Experiment/Trial/Suggestion 三个控制器协同完成 AutoML。
- **Kubeflow Trainer**：V1 按框架分 controller（维护模式）；V2 `pkg/controller/` 实现统一的 `TrainJob` + `TrainingRuntime`（GA）。
- **kubeflow/sdk**：统一 Python SDK，把上述组件包装成 Python API。
- **Notebook / Profile Controller**：把开发环境和多租户声明式化。
- 读源码时遵循 **CRD → Controller → SDK** 的顺序最高效。

**参考来源**

- [Kubeflow Pipelines GitHub](https://github.com/kubeflow/pipelines)
- [Kubeflow Pipelines AGENTS.md — Architecture](https://github.com/kubeflow/pipelines/blob/master/AGENTS.md)
- [Kubeflow Katib GitHub](https://github.com/kubeflow/katib)
- [Kubeflow Trainer GitHub](https://github.com/kubeflow/trainer)
- [Kubeflow SDK GitHub](https://github.com/kubeflow/sdk)
- [Kubeflow Kubeflow GitHub](https://github.com/kubeflow/kubeflow)
- 本手册 [Operator 模式源码分析](../../02-cloud-native/operator/06-source-analysis)

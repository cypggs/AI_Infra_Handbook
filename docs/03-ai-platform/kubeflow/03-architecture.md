# 3. 架构设计：控制平面、多租户与组件交互

> 一句话理解：Kubeflow 不是单体应用，而是**一组共享 Kubernetes 控制平面的 Operator 和 Web UI**；Central Dashboard 是入口，Profile 是多租户边界，Istio 是认证与流量层，各组件通过 API Server 协同。

## 3.1 总体架构

```
┌──────────────────────────────────────────────────────────────────────┐
│                         外部用户 / SSO / OIDC                         │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         Istio Ingress Gateway                         │
│                    认证、TLS、路由、多租户隔离                         │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      Central Dashboard（Web UI）                      │
│         聚合 Notebooks / Pipelines / Katib / Training / KServe       │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            │                   │                   │
            ▼                   ▼                   ▼
    ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
    │   Notebooks   │   │   Pipelines   │   │     Katib     │
    │   Controller  │   │   API Server  │   │   Controller  │
    └───────────────┘   │   Scheduler   │   │   DB Manager  │
            │           │   Persistence │   │   Suggestion  │
            │           │   MLMD        │   │   UI          │
            │           └───────────────┘   └───────────────┘
            │                   │                   │
            ▼                   ▼                   ▼
    ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
    │   Training    │   │    KServe     │   │   Profile /   │
    │   Operator    │   │   Controller  │   │     KFAM      │
    └───────────────┘   └───────────────┘   └───────────────┘
            │                   │                   │
            └───────────────────┼───────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    Kubernetes API Server / etcd                       │
│   CRD: Notebook, Pipeline, Run, Experiment, Trial, TrainJob, Profile  │
└──────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│              Storage / Artifact Store / Object Storage                │
│   PVC / S3 / GCS / MinIO / ML Metadata / MySQL                       │
└──────────────────────────────────────────────────────────────────────┘
```

## 3.2 控制平面分层

### API 与 CRD 层

所有 Kubeflow 组件都向 K8s API Server 注册 CRD：

| 组件 | CRD |
|---|---|
| Notebooks | `Notebook`（v2 引入 CRD 驱动的 Workspaces） |
| Pipelines | `Pipeline`, `Run`, `Experiment`, `RecurringRun`（backend 内部） |
| Katib | `Experiment`, `Trial`, `Suggestion` |
| Kubeflow Trainer | V1：`TFJob`, `PyTorchJob`, `MPIJob`, `XGBoostJob` 等（维护模式）；V2：`TrainJob`, `TrainingRuntime`, `ClusterTrainingRuntime` |
| KServe | `InferenceService`, `ServingRuntime`, `InferenceGraph`, `LLMInferenceService`（v0.18+） |
| Hub | `ModelRegistry` 相关资源；Model Catalog / MCP Catalog |
| Spark Operator | `SparkApplication` 等 |
| Profiles | `Profile` |

### Controller 层

每个组件是一个或多个 Operator：

- **Notebook Controller**：`Notebook` → StatefulSet + Service + Istio VS。
- **Profile Controller**：`Profile` → Namespace + RBAC + default resources。
- **Pipeline API Server**：REST/gRPC API，管理 Pipeline/Run/Experiment；2.15+ 内置数据库自动迁移，2.16 起原生支持 OIDC。
- **Katib Controller**：监听 `Experiment`，创建 `Trial` 和 `Suggestion`。
- **Kubeflow Trainer**：V2 Controller 监听 `TrainJob`，按 `runtimeRef` 解析 `TrainingRuntime` 生成 Pod/Job；与 Kueue/Volcano 集成 gang scheduling。
- **KServe Controller**：监听 `InferenceService`/`LLMInferenceService`，创建 Knative/RawDeployment 资源。
- **Hub Controller**：维护模型目录与 KServe `InferenceService` 的对账（记录线上实际运行的模型版本）。

### UI 层

- **Central Dashboard**：React/Angular 前端，通过各组件 API 展示数据。
- **Pipeline UI**：独立的 KFP UI（v2 后与 Central Dashboard 集成）。
- **Katib UI**：展示 Experiments/Trials。
- **Notebook Web App**：列出/创建 Notebooks。

## 3.3 多租户模型

Kubeflow 采用 **Profile = namespace** 的多租户模型。

```
Cluster
  │
  ├─ Profile alice  → namespace alice
  │     ├─ Owner: alice@example.com
  │     ├─ Contributors: bob@example.com
  │     ├─ Notebooks
  │     ├─ Pipeline Runs
  │     ├─ Katib Experiments
  │     └─ Training Jobs
  │
  └─ Profile bob    → namespace bob
```

### Profile Controller 职责

1. 创建 namespace。
2. 创建 `ServiceAccount` / `RoleBinding` 给 owner 和 contributors。
3. 创建 Istio `ServiceRole` / `AuthorizationPolicy` 限制跨 namespace 访问。
4. 可选创建默认 PVC、ConfigMap、Secrets。

### 认证链路

```
用户 → Istio Gateway → oauth2-proxy / DEX / OIDC → Central Dashboard
```

常见认证：

- **DEX**：内置 OIDC provider，可接 LDAP/GitHub/Google。
- **oauth2-proxy**：1.10 起取代旧的 OIDC-authservice，把外部 IdP 的 token 转成 K8s service account。
- **Istio**：基于 JWT 和 namespace 做授权。
- **KFP 原生 OIDC**：2.16 起 Pipeline API Server 可不再依赖 Istio 侧车做认证（多租户模式下按 namespace 下发 S3 凭证）。

> 1.11 起安全基线大幅收紧：系统 namespace 默认 Pod Security Standards **restricted**、用户 namespace **baseline**，并为关键 namespace（`knative-serving`、`oauth2-proxy`、`cert-manager`、`istio-system`、`auth` 等）默认下发 NetworkPolicy。

## 3.4 网络与流量

Kubeflow 默认使用 **Istio** 作为服务网格：

- 所有组件 UI 和 API 通过 Istio Gateway 暴露。
- namespace 间流量默认隔离。
- Notebook 通过 Istio VirtualService 提供 `/notebook/<namespace>/<name>` 路由。

## 3.5 存储与 Artifact

Kubeflow 需要几类存储：

| 用途 | 常见方案 |
|---|---|
| Notebook 用户目录 | PVC（RWO 或 RWX） |
| Pipeline artifact | S3 / GCS / SeaweedFS（1.11 起默认）/ MinIO（已弃用） |
| Pipeline metadata | ML Metadata（MLMD）+ MySQL / SQLite |
| Katib experiment 数据 | Katib MySQL / Postgres |
| KServe 模型 | S3 / GCS / PVC / OCI（Hub 的标准，ModelCar 加载） |
| Hub 模型制品 | OCI Registry（与容器镜像共用分发机制） |

### Artifact Store

KFP v2 默认把 artifact 写入对象存储（S3/MinIO/GCS），并在 MLMD 中记录 lineage：

```
Component A 输出 artifact
    │
    ▼
写入 S3 /tmp/artifact/...
    │
    ▼
MLMD 记录 artifact URI、类型、producer execution
    │
    ▼
Component B 通过 input artifact 引用
```

## 3.6 组件交互示例

一个完整的 Pipeline Run 如何调动 Katib 和 Kubeflow Trainer：

```
Pipeline Run
    │
    ├─ Step 1: 数据预处理（ContainerOp）
    │     └─ artifact → S3
    │
    ├─ Step 2: Katib Experiment
    │     └─ Katib Controller 创建多个 Trial（可直接为 TrainJob）
    │     └─ 最佳参数通过 artifact / output 返回
    │
    ├─ Step 3: 用最佳参数创建 TrainJob
    │     └─ Trainer 按 runtimeRef 解析 TrainingRuntime，创建 Pod
    │     └─ 模型 artifact → S3 / OCI
    │
    └─ Step 4: KServe InferenceService / LLMInferenceService
          └─ KServe Controller 部署模型服务
```

## 3.7 部署形态

### 完整发行版

`kubeflow/manifests` 提供 Kustomize overlay，一键安装所有组件：

```bash
kustomize build example | kubectl apply -f -
```

自 2026 年起社区发行版改用**日历版本号**（如 `26.03`，表示 2026 年 3 月基线，每年约两个基线版本、约 6 个月社区支持）；当前稳定版为 **26.03.1**（2026-06），CI 覆盖 Kubernetes 1.36，且要求升级时先阅读 Dashboard v2 的破坏性变更说明。Helm Chart 支持处于实验阶段。

### 独立组件

平台团队可以只装需要的部分（具体路径以各组件仓库的 standalone 安装说明为准）：

```bash
# 只装 Kubeflow Trainer（V2 默认启用 TrainJob，支持单条 Helm 命令安装）
# 见 github.com/kubeflow/trainer 的 standalone / Helm 安装说明，当前版本 v2.3.0

# 只装 Katib
kubectl apply -k github.com/kubeflow/katib/manifests/v1beta1/installs/katib-standalone?ref=v0.19.0
```

### 云厂商发行版

- AWS: **Amazon EKS Kubeflow** (deprecated, 推荐 SageMaker/self-managed)
- Google Cloud: **Vertex AI Pipelines** (KFP 兼容，托管)
- Azure: **Azure Machine Learning + AKS 自托管 Kubeflow**
- 其他：Charmed Kubeflow (Canonical), Arrikto Enterprise Kubeflow

## 本章小结

- Kubeflow 是**多 Operator 集合**，共享 K8s API Server。
- **Central Dashboard** 是统一入口，**Istio + oauth2-proxy** 处理认证/流量/隔离；1.11 起默认 PSS 与 NetworkPolicy。
- **Profile = namespace**，Profile Controller 创建 namespace + RBAC + network policy。
- 各组件 CRD：Notebook、Run/Experiment、Experiment/Trial、TrainJob/TrainingRuntime、InferenceService/LLMInferenceService、Profile。
- 存储分层：PVC、对象存储 artifact（SeaweedFS 默认）、MLMD、Katib DB、Hub OCI Registry。
- 可完整安装（日历版本发行版，当前稳定版 26.03.1），也可按需独立部署某个组件。

**参考来源**

- [Kubeflow — Architecture](https://www.kubeflow.org/docs/started/architecture/)
- [Kubeflow — Profiles and Namespaces](https://www.kubeflow.org/docs/components/central-dash/profiles/)
- [Kubeflow — Authentication](https://www.kubeflow.org/docs/external-add-ons/oidc/)
- [Kubeflow 1.11 Release Announcement](https://blog.kubeflow.org/kubeflow-1.11-release/)
- [Kubeflow Community Distribution 26.03 Release](https://blog.kubeflow.org/kubeflow-26.03-release/)
- [Kubeflow Manifests Releases（当前稳定版 26.03.1）](https://github.com/kubeflow/manifests/releases)
- [Kubeflow Manifests](https://github.com/kubeflow/manifests)

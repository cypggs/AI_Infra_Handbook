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
│   CRD: Notebook, Pipeline, Run, Experiment, Trial, TFJob, Profile    │
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
| Notebooks | `Notebook` |
| Pipelines | `Pipeline`, `Run`, `Experiment`, `RecurringRun`（backend 内部） |
| Katib | `Experiment`, `Trial`, `Suggestion` |
| Training Operator | `TFJob`, `PyTorchJob`, `MPIJob`, `XGBoostJob`, `PaddleJob`, `MXJob`, `JAXJob` |
| KServe | `InferenceService`, `ServingRuntime`, `InferenceGraph` |
| Profiles | `Profile` |

### Controller 层

每个组件是一个或多个 Operator：

- **Notebook Controller**：`Notebook` → StatefulSet + Service + Istio VS。
- **Profile Controller**：`Profile` → Namespace + RBAC + default resources。
- **Pipeline API Server**：REST/gRPC API，管理 Pipeline/Run/Experiment。
- **Katib Controller**：监听 `Experiment`，创建 `Trial` 和 `Suggestion`。
- **Training Operator**：监听 `PyTorchJob`/`TFJob` 等，创建 Pod/Job。
- **KServe Controller**：监听 `InferenceService`，创建 Knative/RawDeployment 资源。

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
- **oauth2-proxy**：把外部 IdP 的 token 转成 K8s service account。
- **Istio**：基于 JWT 和 namespace 做授权。

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
| Pipeline artifact | S3 / GCS / MinIO |
| Pipeline metadata | ML Metadata（MLMD）+ MySQL / SQLite |
| Katib experiment 数据 | Katib MySQL / Postgres |
| KServe 模型 | S3 / GCS / PVC |

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

一个完整的 Pipeline Run 如何调动 Katib 和 Training Operator：

```
Pipeline Run
    │
    ├─ Step 1: 数据预处理（ContainerOp）
    │     └─ artifact → S3
    │
    ├─ Step 2: Katib Experiment
    │     └─ Katib Controller 创建多个 Trial Job
    │     └─ 最佳参数通过 artifact / output 返回
    │
    ├─ Step 3: 用最佳参数创建 PyTorchJob
    │     └─ Training Operator 创建 Master/Worker Pod
    │     └─ 模型 artifact → S3
    │
    └─ Step 4: KServe InferenceService
          └─ KServe Controller 部署模型服务
```

## 3.7 部署形态

### 完整发行版

`kubeflow/manifests` 提供 Kustomize overlay，一键安装所有组件：

```bash
kustomize build example | kubectl apply -f -
```

### 独立组件

平台团队可以只装需要的部分：

```bash
# 只装 Training Operator
kubectl apply -k github.com/kubeflow/training-operator/manifests/overlays/standalone?ref=v1.9.2

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
- **Central Dashboard** 是统一入口，**Istio** 处理认证/流量/隔离。
- **Profile = namespace**，Profile Controller 创建 namespace + RBAC + network policy。
- 各组件 CRD：Notebook、Run/Experiment、Experiment/Trial、PyTorchJob/TFJob、InferenceService、Profile。
- 存储分层：PVC、对象存储 artifact、MLMD、Katib DB。
- 可完整安装，也可按需独立部署某个组件。

**参考来源**

- [Kubeflow — Architecture](https://www.kubeflow.org/docs/started/architecture/)
- [Kubeflow — Profiles and Namespaces](https://www.kubeflow.org/docs/components/central-dash/profiles/)
- [Kubeflow — Authentication](https://www.kubeflow.org/docs/external-add-ons/oidc/)
- [Kubeflow Manifests](https://github.com/kubeflow/manifests)

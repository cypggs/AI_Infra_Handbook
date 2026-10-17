# 8. 企业生产实践：安装、多租户、存储与运维

> 一句话理解：Kubeflow 在生产环境的难点不在于单个组件，而在于**把多个 Operator、认证、存储、网络、GPU、artifact、升级整合成可运维的平台**——2026 年后社区在默认安全基线（PSS/NetworkPolicy/SeaweedFS）上已大幅减负。

## 8.1 安装方式选择

### 方式 1：完整发行版（kubeflow/manifests）

适合：想一次性获得完整 Kubeflow 体验的平台团队。

```bash
git clone https://github.com/kubeflow/manifests.git
cd manifests
kustomize build example | kubectl apply -f -
```

- 当前基线：**Community Distribution 26.03.1**（2026-06，日历版本号），CI 覆盖 Kubernetes 1.36；Kubeflow 1.11（2025-12）是最后一个 semver 基线版本。26.03 起 Hub（Model Registry/Catalog/UI）默认启用安装；Helm Chart 处于实验阶段。
- 26.03.1 升级注意：Dashboard v2 有**破坏性变更**，升级前必须先阅读 manifests 仓库的 upgrading 指南。
- 优点：官方集成，组件版本兼容。
- 缺点：体积大，所有组件一起升级，定制复杂。

### 方式 2：独立组件安装

适合：已有部分 ML 平台，只想引入训练/编排/AutoML。

```bash
# Kubeflow Trainer（V2 默认；v2.2 起支持单条 Helm 命令，上游最新 v2.3.0）
# 注意：从 v2.0/2.1/2.2 升级必须先升到 v2.3 再往后升级
# Katib
kubectl apply -k github.com/kubeflow/katib/manifests/v1beta1/installs/katib-standalone?ref=v0.19.0

# KFP standalone（路径以 pipelines 仓库当前版本的说明为准）
```

- 优点：按需引入，升级独立。
- 缺点：需要自己处理认证、多租户、Central Dashboard 聚合。

### 方式 3：云厂商/商业发行版

- **Google Vertex AI Pipelines**：KFP 兼容，托管。
- **Amazon SageMaker**：若不需要 Kubeflow 生态，可直接用 SageMaker Pipelines / Training。
- **Azure Machine Learning**：可与 AKS 自托管 Kubeflow 并用。
- **Charmed Kubeflow (Canonical)**、**Arrikto Enterprise Kubeflow**：企业支持。

### 方式 4：Python SDK（无平台安装）

```bash
pip install kubeflow        # 或 kubeflow[docker] / kubeflow[podman]
```

适合团队已有 K8s 集群、只想引入训练/调参能力：`TrainerClient`/`OptimizerClient` 直接对集群操作，无需完整 Kubeflow 发行版。

## 8.2 多租户与认证

### 推荐模型

```
外部 IdP (LDAP/Google/GitHub)
        │
        ▼
   DEX / oauth2-proxy
        │
        ▼
  Istio Ingress Gateway (JWT 校验)
        │
        ▼
  Central Dashboard
        │
        ▼
  Profile = namespace (RBAC + AuthorizationPolicy)
```

### 关键配置

- 每个用户一个 `Profile`。
- 通过 `Istio AuthorizationPolicy` 限制跨 namespace 访问。
- Notebook / Pipeline UI 通过 `kubeflow-userid` header 识别用户。
- 使用 `ResourceQuota` 限制每个 namespace 的 CPU / 内存 / GPU。

### 常见坑

- **Istio sidecar 注入**：Kubeflow 默认依赖 Istio；1.11 针对大规模集群做了 sidecar 内存/流量优化（"零 Pod 开销"目标），自定义 namespace 未注入 sidecar 会导致认证失败。
- **OIDC callback URL**：需与 Istio Gateway 的 host 一致。
- **Central Dashboard iframe**：跨组件 UI 需要统一认证 Cookie / header。
- **Pod Security Standards**：1.11 起默认强制（系统 namespace restricted / 用户 namespace baseline），自定义镜像需能以非 root 运行、只读根文件系统。
- **Notebooks 版本**：Notebooks v1 处于维护模式，社区计划 2026 年底 EOL；v2（CRD 驱动的 Workspaces）已从 26.03 的 alpha 推进到 **beta**（v2.0.0-beta.3，2026-10），升级前阅读 Dashboard v2 迁移指南。

## 8.3 存储与 Artifact

### 存储分类

| 用途 | 推荐方案 | 注意 |
|---|---|---|
| Notebook 用户目录 | RWX PVC 或对象存储挂载 | 多副本 Notebook 需要共享存储 |
| Pipeline artifact | S3 / GCS / SeaweedFS（1.11+ 默认）/ MinIO（已弃用） | 配置 KFP 的 `objectStore` secret |
| Pipeline metadata | ML Metadata + MySQL | 默认 SQLite 不适合生产 |
| Katib experiment 数据 | Katib MySQL / Postgres | 独立数据库 |
| KServe 模型 | S3 / GCS / PVC / OCI（Hub + ModelCar） | 注意模型缓存与拉取权限 |
| Hub 模型制品 | OCI Registry | 与容器镜像共用分发与权限体系 |

1.11 起多租户对象存储改为 **per-namespace S3 凭证**下发；26.03 默认 SeaweedFS，MinIO 与其他 S3 兼容存储仍可用。

### Artifact Store 配置示例（KFP）

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: mlpipeline-minio-artifact
type: Opaque
stringData:
  accesskey: minio
  secretkey: minio123
```

KFP v2 默认把 artifact 写入对象存储，并在 MLMD 中记录 lineage。

## 8.4 GPU 与调度

- **NVIDIA GPU Operator**：节点打标签 `nvidia.com/gpu`。
- **Notebook / TrainingJob 资源声明**：

```yaml
resources:
  limits:
    nvidia.com/gpu: 1
```

- **GPU 共享/分时**：如需多任务共享 GPU，考虑 NVIDIA MPS / vGPU 或 Volcano 调度器。
- **Topology aware scheduling**：多节点训练时，让 Master/Worker 落在同一 RACK / 高速网络域。

## 8.5 可观测

### 指标

| 层级 | 工具 | 指标示例 |
|---|---|---|
| 基础设施 | Prometheus + Grafana | GPU 利用率、节点 CPU/内存 |
| Kubeflow 组件 | 各组件自带 /metrics | Pipeline Run 数、Katib Trial 数、Training Job 状态 |
| 训练任务 | TensorBoard / Weights & Biases | loss、accuracy |
| 模型服务 | KServe + Prometheus | 请求 QPS、P99 延迟、错误率 |

### 日志

- 所有组件 Pod 日志统一收集到 ELK / Loki。
- Pipeline step 日志在对应 Pod 中；KFP UI 会展示。

### 告警

- Training Job Failed / Katib Experiment Failed 超过阈值。
- GPU 利用率长期过低（资源浪费）。
- InferenceService 错误率升高。

## 8.6 升级与回滚

### 升级策略

1. **先升级 Kubeflow Trainer / Katib 等独立组件**，观察稳定后再升级 KFP。
2. **备份 MLMD / MySQL**：KFP 2.15+ 升级时自动执行数据库索引迁移，**不支持回滚**——生产库必须先备份。
3. **注意破坏性 API 变更**：Trainer v2.2 用 `RuntimePatches` 取代 `PodTemplateOverrides` 并移除 `ElasticPolicy`；v2.3 又把 CRD 移入 Helm chart 模板目录——**v2.0/2.1/2.2 必须先升到 v2.3** 再升级后续版本；Dashboard v2 / Notebooks v2 有独立迁移指南（26.03.1 起为必选项）。
4. **在新 namespace 做金丝雀升级**：例如先给部分团队用新版本 Kubeflow。
5. **保留旧版 manifests**：出问题可快速回滚（KFP 数据库除外）。

### 版本兼容性

- KFP v1 与 v2 的 DSL 不兼容；升级前需迁移 pipeline。
- Kubeflow Trainer V1 CRD 处于维护模式，新部署建议直接使用 V2 `TrainJob`；V1→V2 迁移见官方 migration 指南。
- 26.03.1 发行版在 Kubernetes 1.36 上跑 CI（1.34/1.35 同样验证）；升级集群前先核对发行版支持矩阵。

## 8.7 安全

- **最小权限**：给每个 Profile 的 ServiceAccount 最小 RBAC。
- **Secrets 管理**：用 Kubernetes Secrets / Vault / External Secrets 管理 S3 凭证、HuggingFace token。
- **镜像安全**：扫描 Notebook / Training 镜像；使用私有镜像仓库。
- **网络隔离**：默认拒绝跨 namespace，仅放行必要服务。

## 8.8 成本治理

- **Notebook 自动休眠**：非工作时间 scale StatefulSet replicas 到 0。
- **Pipeline cache**：避免重复执行未变更的 step。
- **Katib 资源上限**：限制 `parallelTrialCount` 与 `maxTrialCount`。
- **Training Job 弹性**：支持 Spot / Preemptible 节点。
- **KServe 自动缩容到零**：对低频服务释放 GPU。

## 8.9 典型生产拓扑

```
┌─────────────────────────────────────────────┐
│                  Ingress / WAF               │
└───────────────┬─────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────┐
│         Istio Gateway + OAuth2              │
└───────────────┬─────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────┐
│         Central Dashboard                   │
└───────┬───────┬───────┬───────┬─────────────┘
        ▼       ▼       ▼       ▼             ▼
    Notebook  KFP     Katib   Training    KServe
        │       │       │       │             │
        ▼       ▼       ▼       ▼             ▼
   PVC   Artifact  Katib  GPU NodePool   S3 + GPU
   Store  S3/MinIO MySQL
```

## 本章小结

- 安装可选完整发行版（当前稳定版 26.03.1 日历版本；1.11 为最后 semver 基线）、独立组件、云厂商托管，或仅引入 Python SDK。
- 多租户核心：**Profile = namespace + RBAC + Istio AuthorizationPolicy + ResourceQuota**；1.11 起默认 PSS 与 NetworkPolicy。
- 存储分层：PVC、对象存储 artifact（SeaweedFS 默认、per-namespace 凭证）、MLMD、Katib DB、Hub OCI Registry。
- GPU 调度依赖 NVIDIA GPU Operator，训练任务声明 `nvidia.com/gpu`。
- 可观测覆盖基础设施、组件、训练、服务四层。
- 升级注意：KFP 2.15+ 数据库自动迁移不可回滚、Trainer v2.2/v2.3 破坏性 API 与升级路径、26.03.1 Dashboard v2 破坏性变更、Notebooks v1 将 EOL。
- 成本治理：自动休眠、cache、弹性训练、缩容到零。

**参考来源**

- [Kubeflow Manifests](https://github.com/kubeflow/manifests)
- [Kubeflow — Authentication](https://www.kubeflow.org/docs/external-add-ons/oidc/)
- [Kubeflow — Profiles and Namespaces](https://www.kubeflow.org/docs/components/central-dash/profiles/)
- [KFP v2 — Configure Object Store](https://www.kubeflow.org/docs/components/pipelines/user-guides/core-functions/)
- [Kubeflow 1.11 Release Announcement](https://blog.kubeflow.org/kubeflow-1.11-release/)
- [Kubeflow Community Distribution 26.03 Release](https://blog.kubeflow.org/kubeflow-26.03-release/)
- [Kubeflow Manifests Releases（当前稳定版 26.03.1，含升级说明）](https://github.com/kubeflow/manifests/releases)
- [Kubeflow Trainer v2.3.0 Release Notes（升级路径约束）](https://github.com/kubeflow/trainer/releases/tag/v2.3.0)
- [NVIDIA GPU Operator](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/)

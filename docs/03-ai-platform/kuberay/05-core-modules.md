# 5. 核心模块：从 CRD 到 Pod 的完整构建链路

> 一句话理解：KubeRay 的核心模块分为 **CRD 定义层、Reconciler 控制层、Common 构建层、生态集成层**，每一层都为“把 YAML 变成 Ray 集群”提供一块拼图。

## 5.1 CRD 定义层

位置：`ray-operator/apis/ray/v1/`

| 文件 | 作用 |
|---|---|
| `raycluster_types.go` | RayCluster Spec/Status |
| `rayjob_types.go` | RayJob Spec/Status |
| `rayservice_types.go` | RayService Spec/Status |
| `raycronjob_types.go` | RayCronJob Spec/Status |
| `register.go` | Scheme 注册 |
| `zz_generated.deepcopy.go` | 自动生成的 deepcopy 方法 |

Spec 字段设计遵循“Ray 原生概念优先”原则：

- `headGroupSpec` / `workerGroupSpecs` 直接对应 Ray 的 head / worker。
- `rayStartParams` 直接映射为 `ray start` 命令行参数。
- `gcsFaultToleranceOptions` 是 v1.3 后统一的 GCS FT 配置入口。

## 5.2 Reconciler 控制层

位置：`ray-operator/controllers/ray/`

### RayClusterReconciler

负责：

- 调和 Autoscaler RBAC
- 调和 Service（head / serve / headless）
- 调和 Ingress / Route
- 调和 Head Pod
- 调和 Worker Pods
- 计算并更新 Status

关键函数：

```go
Reconcile(ctx, req)
  └── rayClusterReconcile()
        ├── reconcileAutoscalerServiceAccount()
        ├── reconcileAutoscalerRole()
        ├── reconcileAutoscalerRoleBinding()
        ├── reconcileIngress()
        ├── reconcileAuthSecret()
        ├── reconcileHeadService()
        ├── reconcileHeadlessService()
        ├── reconcileServeService()
        ├── reconcilePods()
        ├── calculateStatus()
        └── updateRayClusterStatus()
```

### RayJobReconciler

负责：

- 校验 RayJob 合法性
- 按 `JobDeploymentStatus` 状态机执行
- 创建/选择 RayCluster
- 创建 submitter（K8sJob / HTTP / Sidecar）
- 轮询 Dashboard 获取 job 状态
- 完成后按策略清理

状态机核心：

```go
switch jobDeploymentStatus {
case rayv1.JobDeploymentStatusInitializing:
    // getOrCreateRayClusterInstance + create submitter
case rayv1.JobDeploymentStatusRunning:
    // check submitter + GetJobInfo
case rayv1.JobDeploymentStatusComplete, rayv1.JobDeploymentStatusFailed:
    // handle deletion rules
}
```

### RayServiceReconciler

负责：

- 维护 active / pending 两个 RayCluster
- 向 active 提交 serveConfigV2
- 升级时创建 pending 并切换 Service selector
- 支持 Gateway API 渐进升级
- 计算 serve 状态并更新 Status

### RayCronJobReconciler

- 监听 RayCronJob，按 cron 表达式周期性创建 RayJob。

### NetworkPolicyController

- Alpha 特性，自动为 RayCluster 创建 NetworkPolicy 实现网络隔离。

## 5.3 Common 构建层

位置：`ray-operator/controllers/ray/common/`

| 文件 | 作用 |
|---|---|
| `pod.go` | 构建 head / worker Pod 模板、注入 autoscaler sidecar、生成 `ray start` 命令 |
| `service.go` | 构建 head service、serve service、headless service |
| `ingress.go` | 构建 Ingress / OpenShift Route |
| `rbac.go` | 构建 autoscaler 所需的 SA/Role/RoleBinding |
| `job.go` | 构建 RayJob submitter Job 模板 |

### pod.go 的关键职责

1. 把 `rayStartParams` 转换为 `ray start --head` / `ray start --address=...` 命令。
2. 把容器资源限制映射为 Ray 资源：
   - `nvidia.com/gpu` → `--num-gpus`
   - `google.com/tpu` → `--num-tpus`
3. 注入 Autoscaler sidecar 容器。
4. 处理 GCS FT 环境变量。
5. 设置健康探针。

### service.go 的关键职责

自动创建的 Service：

- `example-cluster-head-svc`：暴露 GCS 6379、Dashboard 8265、Client 10001、Serve 8000、Metrics。
- `example-cluster-serve-svc`：负载均衡 serve 流量。
- `example-cluster-worker-headless-svc`：多主机 TPU/GPU 场景。

## 5.4 Batch Scheduler 集成

位置：`ray-operator/controllers/ray/batchscheduler/`

KubeRay 支持将 Pod 交给批调度器做 Gang Scheduling：

| 调度器 | 说明 |
|---|---|
| Volcano | 最早的批调度集成 |
| YuniKorn | 支持队列与配额 |
| scheduler-plugins | v1.4+ 支持，更轻量 |
| kai-scheduler | 华为开源批调度器 |

集成方式：在 CR 中指定 `schedulerName` 和相关 annotation，KubeRay 在创建 Pod 时注入 PodGroup 等对象。

## 5.5 Autoscaler 集成

KubeRay 禁用了 Ray 原生的 monitor/autoscaler 进程，改为注入专用 sidecar：

- sidecar 镜像与 Ray 版本匹配。
- sidecar 读取 Ray 资源需求，通过 K8s API 修改 `RayCluster.workerGroupSpecs[*].replicas`。
- Operator Watch 到变化后创建/删除 Pod。

Autoscaler V2（推荐）：

- 通过 `autoscalerOptions.version: v2` 启用。
- 支持自定义 `idleTimeoutSeconds`、TPU v6e、更稳定的扩缩容。

## 5.6 KubeRay APIServer

可选组件，提供 REST/gRPC 接口：

- 列出/创建/删除 RayCluster、RayJob、RayService。
- 默认暴露 NodePort `31888`。
- Swagger UI：`/swagger-ui`。

注意：APIServer 不替代 Operator，只是配置代理层。

## 5.7 kubectl ray 插件

命令示例：

```bash
kubectl ray get cluster
kubectl ray get job
kubectl ray get service
kubectl ray log job my-job
kubectl ray session my-cluster
```

## 5.8 可观测性模块

### Operator Metrics

- Operator 暴露 controller-runtime 标准指标。
- 可配置 `ServiceMonitor`。

### Ray Cluster Metrics

Head Pod 暴露：

- `metrics`：Ray 内部指标。
- `as-metrics`：autoscaler 指标。
- `dash-metrics`：dashboard 指标。

官方提供 Prometheus/Grafana 安装脚本与 Dashboard JSON。

## 5.9 Feature Gates 模块

位置：`ray-operator/pkg/features/features.go`

通过环境变量启用/禁用 Alpha/Beta 特性，例如：

```bash
export KUBERAY_FEATURE_RAYCRONJOB=true
export KUBERAY_FEATURE_RAYSERVICEINCREMENTALUPGRADE=true
```

## 本章小结

- CRD 定义层把 Ray 概念映射为 Go types。
- Reconciler 控制层按固定顺序调和子资源。
- Common 构建层负责 Pod、Service、Ingress、RBAC 的具体生成。
- Batch Scheduler、Autoscaler、APIServer、kubectl plugin、可观测性、Feature Gates 构成完整生态。

**参考来源**

- [apis/ray/v1 目录](https://github.com/ray-project/kuberay/tree/master/ray-operator/apis/ray/v1)
- [controllers/ray 目录](https://github.com/ray-project/kuberay/tree/master/ray-operator/controllers/ray)
- [controllers/ray/common 目录](https://github.com/ray-project/kuberay/tree/master/ray-operator/controllers/ray/common)
- [controllers/ray/batchscheduler 目录](https://github.com/ray-project/kuberay/tree/master/ray-operator/controllers/ray/batchscheduler)
- [pkg/features/features.go](https://github.com/ray-project/kuberay/blob/master/ray-operator/pkg/features/features.go)
- [Prometheus Grafana Guide](https://docs.ray.io/en/latest/cluster/kubernetes/k8s-ecosystem/prometheus-grafana.html)

# 6. 源码分析：主入口与三大 Reconciler 调用链

> 一句话理解：KubeRay 源码遵循标准 Operator 布局，`main.go` 初始化 controller-runtime Manager 并注册 Reconciler；三大 Reconciler 分别负责集群、作业、服务的调和。

## 6.1 仓库结构

```text
kuberay/
├── ray-operator/              # 核心 Operator
│   ├── main.go                # 入口
│   ├── apis/ray/v1/           # CRD Go types
│   ├── controllers/ray/       # Reconcilers
│   │   ├── raycluster_controller.go
│   │   ├── rayjob_controller.go
│   │   ├── rayservice_controller.go
│   │   ├── raycronjob_controller.go
│   │   └── networkpolicy_controller.go
│   ├── controllers/ray/common/# Pod/Service/Ingress/RBAC/Job 构建
│   ├── controllers/ray/batchscheduler/  # Volcano/YuniKorn/scheduler-plugins
│   ├── pkg/features/          # Feature gates
│   ├── pkg/webhooks/          # Validating/Mutating webhook
│   └── config/samples/        # 示例 YAML
├── apiserver/                 # 可选 REST/gRPC 代理（V2 Alpha）
├── kubectl-plugin/            # kubectl ray 命令
├── dashboard/                 # KubeRay Dashboard（Experimental）
├── helm-chart/                # Helm Charts
├── historyserver/             # Ray History Server（Alpha）
└── clients/                   # Python/Go clients
```

## 6.2 main.go 主入口

路径：`ray-operator/main.go`

主要工作：

1. 解析命令行 flag 与配置文件。
2. 创建 controller-runtime `Manager`：
   - 注册 Scheme（RayCluster/RayJob/RayService/RayCronJob）。
   - 配置 Leader Election ID：`ray-operator-leader`。
   - 配置 Cache selector（可选限定 namespace）。
   - 配置 Metrics、Health Probe、Pprof。
3. 注册 Reconciler：
   - `RayClusterReconciler`
   - `RayJobReconciler`
   - `RayServiceReconciler`
   - `RayCronJobReconciler`
   - `NetworkPolicyReconciler`（可选）
4. 可选启用 webhook。
5. 启动 Manager：`mgr.Start(ctx)`。

## 6.3 RayClusterReconciler 调用链

路径：`ray-operator/controllers/ray/raycluster_controller.go`

```go
func (r *RayClusterReconciler) Reconcile(ctx, req) (ctrl.Result, error) {
    // 1. 获取 RayCluster
    instance := &rayv1.RayCluster{}
    if err := r.Get(ctx, req.NamespacedName, instance); err != nil {
        return ctrl.Result{}, client.IgnoreNotFound(err)
    }

    // 2. 主调和函数
    return r.rayClusterReconcile(ctx, instance)
}

func (r *RayClusterReconciler) rayClusterReconcile(ctx, instance) (ctrl.Result, error) {
    // 3. Autoscaler RBAC
    if err := r.reconcileAutoscalerServiceAccount(ctx, instance); err != nil { ... }
    if err := r.reconcileAutoscalerRole(ctx, instance); err != nil { ... }
    if err := r.reconcileAutoscalerRoleBinding(ctx, instance); err != nil { ... }

    // 4. Ingress / Auth
    if err := r.reconcileIngress(ctx, instance); err != nil { ... }
    if err := r.reconcileAuthSecret(ctx, instance); err != nil { ... }

    // 5. Services
    if err := r.reconcileHeadService(ctx, instance); err != nil { ... }
    if err := r.reconcileHeadlessService(ctx, instance); err != nil { ... }
    if err := r.reconcileServeService(ctx, instance); err != nil { ... }

    // 6. Pods
    if err := r.reconcilePods(ctx, instance); err != nil { ... }

    // 7. 计算并更新 Status
    if err := r.updateRayClusterStatus(ctx, instance); err != nil { ... }

    return ctrl.Result{}, nil
}
```

### reconcilePods 内部

```go
func (r *RayClusterReconciler) reconcilePods(ctx, instance) error {
    // 创建 Head Pod
    headPod := r.buildHeadPod(instance)
    if err := r.createOrUpdatePod(ctx, headPod); err != nil { ... }

    // 按 worker group 创建 worker pods
    for _, workerGroup := range instance.Spec.WorkerGroupSpecs {
        workerPods := r.buildWorkerPods(instance, workerGroup)
        if err := r.createOrUpdatePod(ctx, workerPods...); err != nil { ... }
    }
    return nil
}
```

### 状态计算

```go
func (r *RayClusterReconciler) calculateStatus(ctx, instance) {
    instance.Status.DesiredWorkerReplicas = ...
    instance.Status.ReadyWorkerReplicas = ...
    instance.Status.AvailableWorkerReplicas = ...
    instance.Status.State = ...
}
```

## 6.4 RayJobReconciler 调用链

路径：`ray-operator/controllers/ray/rayjob_controller.go`

```go
func (r *RayJobReconciler) Reconcile(ctx, req) (ctrl.Result, error) {
    rayJob := &rayv1.RayJob{}
    if err := r.Get(ctx, req.NamespacedName, rayJob); err != nil {
        return ctrl.Result{}, client.IgnoreNotFound(err)
    }

    // 校验
    if err := validateRayJob(rayJob); err != nil { ... }

    // 按状态机执行
    switch rayJob.Status.JobDeploymentStatus {
    case rayv1.JobDeploymentStatusNew:
        // 初始化到 Initializing
    case rayv1.JobDeploymentStatusInitializing:
        // getOrCreateRayClusterInstance
        // createK8sJobIfNeed / submit via HTTP / sidecar
    case rayv1.JobDeploymentStatusRunning:
        // checkSubmitterAndUpdateStatusIfNeeded
        // GetJobInfo from Dashboard
    case rayv1.JobDeploymentStatusComplete, rayv1.JobDeploymentStatusFailed:
        // handleDeletionRules / handleLegacyDeletionPolicy
    }

    return r.updateRayJobStatus(ctx, rayJob)
}
```

### 集群创建或选择

```go
func (r *RayJobReconciler) getOrCreateRayClusterInstance(ctx, rayJob) (*rayv1.RayCluster, error) {
    if rayJob.Spec.ClusterSelector != nil {
        // 复用已有 RayCluster
        return r.getRayClusterBySelector(ctx, rayJob)
    }
    // 根据 rayClusterSpec 创建新的 RayCluster
    return r.createRayCluster(ctx, rayJob)
}
```

### 提交器创建

```go
func (r *RayJobReconciler) createK8sJobIfNeed(ctx, rayJob, rayCluster) error {
    if rayJob.Spec.SubmissionMode != rayv1.K8sJobMode {
        return nil
    }
    submitterJob := r.buildSubmitterJob(rayJob, rayCluster)
    return r.createOrUpdateJob(ctx, submitterJob)
}
```

## 6.5 RayServiceReconciler 调用链

路径：`ray-operator/controllers/ray/rayservice_controller.go`

```go
func (r *RayServiceReconciler) Reconcile(ctx, req) (ctrl.Result, error) {
    rayService := &rayv1.RayService{}
    if err := r.Get(ctx, req.NamespacedName, rayService); err != nil {
        return ctrl.Result{}, client.IgnoreNotFound(err)
    }

    // 清理旧集群
    r.cleanUpRayClusterInstance(ctx, rayService)

    // 调和 active / pending RayCluster
    if err := r.reconcileRayCluster(ctx, rayService); err != nil { ... }

    // 向 active 提交 serve config
    if err := r.reconcileServe(ctx, rayService); err != nil { ... }

    // 渐进升级（可选）
    if err := r.reconcileGatewayAndHTTPRoute(ctx, rayService); err != nil { ... }

    // Service selector 指向 ready 集群
    if err := r.reconcileServicesToReadyCluster(ctx, rayService); err != nil { ... }

    // 更新 status
    return r.updateStatus(ctx, rayService)
}
```

### active / pending 切换逻辑

```go
func (r *RayServiceReconciler) reconcileRayCluster(ctx, rayService) error {
    activeCluster, pendingCluster := r.getActiveAndPendingClusters(ctx, rayService)

    if activeCluster == nil {
        // 首次创建 active
        return r.createRayCluster(ctx, rayService, ActiveClusterName)
    }

    if r.shouldPrepareNewCluster(rayService, activeCluster) {
        // 创建 pending
        return r.createRayCluster(ctx, rayService, PendingClusterName)
    }

    if pendingCluster != nil && r.isPendingClusterReady(ctx, pendingCluster) {
        // pending 就绪，切换 active
        return r.promotePendingToActive(ctx, rayService, pendingCluster)
    }

    return nil
}
```

## 6.6 Common 包关键函数

### common/pod.go

```go
func BuildPod(instance *rayv1.RayCluster, nodeType rayv1.RayNodeType, ...) corev1.Pod {
    // 1. 生成 ray start 命令
    cmd := generateRayStartCommand(nodeType, rayStartParams, ...)

    // 2. 注入 autoscaler sidecar（如果是 head）
    if nodeType == rayv1.HeadNode {
        pod.Spec.Containers = append(pod.Spec.Containers, buildAutoscalerContainer())
    }

    // 3. 设置资源、环境变量、探针
    ...
}
```

### common/service.go

```go
func BuildHeadServiceForRayCluster(...) corev1.Service {
    return corev1.Service{
        ObjectMeta: metav1.ObjectMeta{Name: clusterName + "-head-svc"},
        Spec: corev1.ServiceSpec{
            Ports: []corev1.ServicePort{
                {Name: "gcs-server", Port: 6379},
                {Name: "dashboard", Port: 8265},
                {Name: "client", Port: 10001},
                {Name: "serve", Port: 8000},
            },
            Selector: map[string]string{"ray.io/cluster": clusterName},
        },
    }
}
```

## 6.7 Feature Gates 源码

路径：`ray-operator/pkg/features/features.go`

```go
var defaultFeatureGates = map[featuregate.Feature]featuregate.FeatureSpec{
    RayClusterStatusConditions:  {Default: true, PreRelease: featuregate.Beta},
    RayJobDeletionPolicy:        {Default: true, PreRelease: featuregate.Beta},
    RayMultiHostIndexing:        {Default: true, PreRelease: featuregate.Beta},
    RayServiceIncrementalUpgrade:{Default: false, PreRelease: featuregate.Alpha},
    RayCronJob:                  {Default: false, PreRelease: featuregate.Alpha},
    RayClusterNetworkIsolation:  {Default: false, PreRelease: featuregate.Alpha},
}
```

## 6.8 调试与追踪

- Operator 日志中查找 `Reconciling RayCluster` / `Reconciling RayJob` / `Reconciling RayService`。
- 关注 `ObservedGeneration` 是否递增，判断调和是否发生。
- 使用 `kubectl ray log job ...` 快速查看 RayJob 日志。

## 本章小结

- `main.go` 初始化 Manager 并注册 Reconciler。
- `RayClusterReconciler` 按固定顺序创建 SA、Service、Pod。
- `RayJobReconciler` 按状态机管理作业生命周期。
- `RayServiceReconciler` 维护 active/pending 双集群实现升级。
- `common/pod.go`、`common/service.go` 负责具体资源构建。
- Feature Gates 控制新特性的启用。

**参考来源**

- [ray-operator/main.go](https://github.com/ray-project/kuberay/blob/master/ray-operator/main.go)
- [raycluster_controller.go](https://github.com/ray-project/kuberay/blob/master/ray-operator/controllers/ray/raycluster_controller.go)
- [rayjob_controller.go](https://github.com/ray-project/kuberay/blob/master/ray-operator/controllers/ray/rayjob_controller.go)
- [rayservice_controller.go](https://github.com/ray-project/kuberay/blob/master/ray-operator/controllers/ray/rayservice_controller.go)
- [controllers/ray/common 目录](https://github.com/ray-project/kuberay/tree/master/ray-operator/controllers/ray/common)
- [pkg/features/features.go](https://github.com/ray-project/kuberay/blob/master/ray-operator/pkg/features/features.go)

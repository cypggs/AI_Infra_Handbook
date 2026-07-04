# 2. 核心思想：把 Ray 集群抽象成声明式资源

> 一句话理解：KubeRay 的核心思想是 **用三个 CRD（RayCluster/RayJob/RayService）把 Ray 的“运行时”映射为 K8s 的“基础设施对象”**，让 K8s 负责调度、生命周期、网络、存储，让 Ray 负责分布式计算。

## 2.1 三大 CRD 语义

### RayCluster

描述一个 Ray 集群的 desired state：

```yaml
apiVersion: ray.io/v1
kind: RayCluster
metadata:
  name: example-cluster
spec:
  headGroupSpec:
    rayStartParams:
      num-cpus: "0"
      dashboard-host: "0.0.0.0"
    template:
      spec:
        containers:
          - name: ray-head
            image: rayproject/ray:2.55.0
            resources:
              limits:
                memory: "8Gi"
  workerGroupSpecs:
    - groupName: cpu-workers
      replicas: 2
      minReplicas: 1
      maxReplicas: 5
      template:
        spec:
          containers:
            - name: ray-worker
              image: rayproject/ray:2.55.0
```

关键字段：

| 字段 | 含义 |
|---|---|
| `headGroupSpec` | Head Pod 配置：GCS、Dashboard、Autoscaler |
| `workerGroupSpecs` | Worker Group 列表，每个 group 可独立配置资源与副本 |
| `enableInTreeAutoscaling` | 是否注入 Autoscaler sidecar |
| `autoscalerOptions` | 扩缩容参数：version、idleTimeoutSeconds、upscalingMode |
| `gcsFaultToleranceOptions` | GCS FT 配置：外部 Redis 地址与密码 |
| `suspend` | 挂起集群：删除所有 Pod 但保留 CR |

### RayJob

描述一个提交到 Ray 集群的作业：

```yaml
apiVersion: ray.io/v1
kind: RayJob
metadata:
  name: example-job
spec:
  entrypoint: python train.py
  submissionMode: K8sJobMode
  shutdownAfterJobFinishes: true
  ttlSecondsAfterFinished: 300
  rayClusterSpec:
    headGroupSpec:
      ...
```

关键字段：

| 字段 | 含义 |
|---|---|
| `entrypoint` | Ray job 入口命令 |
| `rayClusterSpec` | 若未指定 `clusterSelector`，则按此创建临时 RayCluster |
| `clusterSelector` | 复用已有 RayCluster |
| `submissionMode` | `K8sJobMode` / `HTTPMode` / `InteractiveMode` / `SidecarMode` |
| `shutdownAfterJobFinishes` | 作业完成后是否删除集群 |
| `ttlSecondsAfterFinished` | 完成后保留多久 |
| `deletionStrategy` | 集群删除策略 |

### RayService

描述一个长期运行的 Ray Serve 服务，支持零停机升级：

```yaml
apiVersion: ray.io/v1
kind: RayService
metadata:
  name: example-service
spec:
  serveConfigV2: |
    applications:
      - name: hello
        import_path: serve_hello:app
  rayClusterConfig:
    ...
```

关键字段：

| 字段 | 含义 |
|---|---|
| `serveConfigV2` | Ray Serve 多应用配置 YAML |
| `rayClusterConfig` | 底层 RayCluster 配置 |
| `upgradeStrategy` | `NewCluster` / `NewClusterWithIncrementalUpgrade` / `None` |
| `serveService` | 自定义 serve 负载均衡 Service |
| `excludeHeadPodFromServeSvc` | 是否让 serve 流量只走 worker |

## 2.2 Head / Worker 映射

KubeRay 把 Ray 的物理节点映射为 K8s Pod：

- **Head Pod**：运行 GCS、Dashboard、Autoscaler、Driver。
  - 生产建议 `num-cpus: "0"`，避免承载 task/actor。
- **Worker Pod**：运行 Raylet，实际执行 task/actor。
- **Worker Group**：同一类 worker 的集合，可按硬件类型分组：
  - `cpu-workers`
  - `gpu-workers`
  - `tpu-workers`

每个 Pod 启动时执行 `ray start` 命令，参数来自 `rayStartParams`。

## 2.3 自动扩缩容

KubeRay 禁用 Ray 默认 monitor 进程，改为在 Head Pod 注入 **Autoscaler sidecar**：

1. Autoscaler 监听 Ray 资源需求（task/actor/placement group）。
2. 当资源不足时，向 KubeRay 请求扩大对应 worker group 的 `replicas`。
3. Operator 创建新 Pod。
4. 当 worker 空闲超过 `idleTimeoutSeconds`，Autoscaler 缩小 `replicas`。
5. Operator 删除多余 Pod。

配置示例：

```yaml
spec:
  enableInTreeAutoscaling: true
  autoscalerOptions:
    version: "v2"
    idleTimeoutSeconds: 120
    upscalingMode: "Default"
```

## 2.4 GCS Fault Tolerance

Ray 的 Global Control Store（GCS）默认运行在 Head Pod 中。如果 Head 挂掉：

- 未启用 FT：worker 无法重连新 head，集群状态丢失。
- 启用 FT：GCS 把状态写入外部 Redis，新 head 可从 Redis 恢复。

启用方式：

```yaml
spec:
  gcsFaultToleranceOptions:
    redisAddress: "redis:6379"
    redisPassword:
      valueFrom:
        secretKeyRef:
          name: redis-password-secret
          key: password
```

生产建议：为高可用 Redis 配置哨兵或集群模式，并为不同 Ray 集群使用不同 `externalStorageNamespace` 避免 key 冲突。

## 2.5 声明式升级

RayService 同时维护两个 RayCluster：

- **active**：当前服务流量。
- **pending**：新版本集群，就绪后切换流量。

升级策略：

| 策略 | 说明 |
|---|---|
| `NewCluster` | 蓝绿部署，pending 就绪后全量切流 |
| `NewClusterWithIncrementalUpgrade` | 渐进式切流，需要 Gateway API |
| `None` | 原地更新，有停机 |

## 2.6 作业生命周期状态机

RayJob 的状态机：

```text
New → Initializing → Running / Waiting
       ↓               ↓
   Suspended      Complete / Failed / Retrying
```

- `Initializing`：创建/选择集群、创建提交器。
- `Running`：通过 Dashboard client 轮询 job 状态。
- `Complete/Failed`：按策略清理集群。

## 2.7 声明式 vs 命令式

| 维度 | 命令式（手动 ray start） | 声明式（KubeRay） |
|---|---|---|
| 集群创建 | ssh + ray start | `kubectl apply -f raycluster.yaml` |
| 扩缩容 | 手动改副本 | Autoscaler 自动调和 |
| 故障恢复 | 手动重建 | GCS FT + Operator 自动重建 |
| 升级 | 停服重部署 | RayService 蓝绿升级 |
| 多租户 | 自行隔离 | Namespace + RBAC + NetworkPolicy |

## 本章小结

- KubeRay 用 RayCluster/RayJob/RayService 把 Ray 的运行时抽象为 K8s 对象。
- Head 与 Worker 映射为 Pod，Worker Group 支持按硬件分组。
- Autoscaler sidecar 实现基于 Ray 资源需求的弹性扩缩容。
- GCS FT 让 Head 重启后状态可恢复。
- RayService 通过 active/pending 双集群实现声明式零停机升级。

**参考来源**

- [KubeRay API Reference](https://ray-project.github.io/kuberay/reference/api/)
- [RayCluster Quick Start](https://docs.ray.io/en/latest/cluster/kubernetes/getting-started/raycluster-quick-start.html)
- [RayJob Quick Start](https://docs.ray.io/en/latest/cluster/kubernetes/getting-started/rayjob-quick-start.html)
- [RayService Quick Start](https://docs.ray.io/en/latest/cluster/kubernetes/getting-started/rayservice-quick-start.html)
- [Configuring Autoscaling](https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/configuring-autoscaling.html)
- [KubeRay GCS FT Guide](https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/kuberay-gcs-ft.html)
- [RayService HA Guide](https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/rayservice-high-availability.html)
- [raycluster_types.go](https://github.com/ray-project/kuberay/blob/master/ray-operator/apis/ray/v1/raycluster_types.go)

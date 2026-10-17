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
            image: rayproject/ray:2.57.0
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
              image: rayproject/ray:2.57.0
```

关键字段：

| 字段 | 含义 |
|---|---|
| `headGroupSpec` | Head Pod 配置：GCS、Dashboard、Autoscaler |
| `workerGroupSpecs` | Worker Group 列表，每个 group 可独立配置资源与副本 |
| `enableInTreeAutoscaling` | 是否注入 Autoscaler sidecar |
| `autoscalerOptions` | 扩缩容参数：version、idleTimeoutSeconds、upscalingMode |
| `gcsFaultToleranceOptions` | GCS FT 配置：外部 Redis 地址，或 v1.7+ 的内嵌 RocksDB 后端 |
| `suspend` | 挂起集群：删除所有 Pod 但保留 CR |
| `upgradeStrategy` | v1.6+：`None`（原地，默认）/ `Recreate`（先删全部 Pod 再按新 spec 重建，适合可安全重启的集群） |
| `networkPolicy` | v1.7+（Alpha）：声明式网络隔离，`DenyAll` / `DenyAllIngress` / `DenyAllEgress` |
| `tlsOptions` | v1.7+（Alpha）：启用 mTLS，由 cert-manager 自动签发 head/worker 证书 |

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
| `submissionMode` | `K8sJobMode` / `HTTPMode` / `InteractiveMode` / `SidecarMode`（v1.5+） |
| `shutdownAfterJobFinishes` | 作业完成后是否删除集群 |
| `ttlSecondsAfterFinished` | 完成后保留多久 |
| `deletionStrategy.deletionRules` | v1.5+（Beta，v1.6 默认开启）：按作业状态（SUCCEEDED/FAILED）分级清理（`DeleteCluster`/`DeleteWorkers`/`DeleteSelf`），取代 v1.6.0 已移除的 `onSuccess`/`onFailure`；与 `shutdownAfterJobFinishes` 互斥 |
| `preRunningDeadlineSeconds` | v1.4+：作业进入 Running 前的等待上限，超时失败 |

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
| `upgradeStrategy` | `NewCluster` / `NewClusterWithIncrementalUpgrade`（v1.7 起 Beta 且默认开启，支持回滚）/ `None` |
| `serveService` | 自定义 serve 负载均衡 Service |
| `excludeHeadPodFromServeSvc` | 是否让 serve 流量只走 worker |
| `managedBy` | v1.6+：声明外部管理器（如 Kueue MultiKueue），使 RayService 成为 Kueue 顶层作业 |

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

启用方式一：外部 Redis（默认方式，兼容所有 Ray 版本）。

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

启用方式二：内嵌 RocksDB（v1.7+ Alpha，需要 Ray 2.57.0+ 且开启 `GCSFaultToleranceEmbeddedStorage` 特性门）——GCS 状态写入 Operator 自动供给的 PVC，**不再需要外部 Redis**：

```yaml
spec:
  gcsFaultToleranceOptions:
    backend: rocksdb
    embeddedStorageOptions:
      deletionPolicy: Retain   # 或指定 claimName 复用已有 PVC
```

生产建议：使用外部 Redis 时配置哨兵或集群模式，并为不同 Ray 集群使用不同 `externalStorageNamespace` 避免 key 冲突；v1.7 起 Redis 清理 finalizer 卡住超过 5 分钟会被强制移除并发出 `ForceDeletedStuckCluster` 警告事件。

## 2.5 声明式升级

RayService 同时维护两个 RayCluster：

- **active**：当前服务流量。
- **pending**：新版本集群，就绪后切换流量。

升级策略：

| 策略 | 说明 |
|---|---|
| `NewCluster` | 蓝绿部署，pending 就绪后全量切流；默认策略 |
| `NewClusterWithIncrementalUpgrade` | 渐进式切流（基于 Gateway API / HTTPRoute），v1.5 引入 Alpha，**v1.7 毕业为 Beta 且默认开启**，升级过程可回滚；大模型服务升级时 GPU 开销约为蓝绿的 60% |
| `None` | 原地更新，有停机 |

此外 v1.6 起 RayCluster 支持 `upgradeStrategy.type: Recreate`：删除所有 Pod 后按新 spec 重建，只适用于可以安全丢弃工作负载的集群。

## 2.6 作业生命周期状态机

RayJob 的状态机：

```text
New → Initializing → Running / Waiting
       ↓               ↓
   Suspended      Complete / Failed / Retrying
```

- `Initializing`：创建/选择集群、创建提交器。
- `Running`：通过 Dashboard client 轮询 job 状态。
- `Complete/Failed`：按 `deletionRules`（按状态 TTL 规则化清理，v1.5+）或旧 `shutdownAfterJobFinishes`/`ttlSecondsAfterFinished` 策略清理集群。

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
- [RayService Zero-Downtime Incremental Upgrades](https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/rayservice-incremental-upgrade.html)
- [Introducing KubeRay v1.5](https://www.anyscale.com/blog/kuberay-v1-5)
- [Introducing KubeRay v1.6 and v1.7](https://www.anyscale.com/blog/kuberay-v1-7)
- [raycluster_types.go](https://github.com/ray-project/kuberay/blob/master/ray-operator/apis/ray/v1/raycluster_types.go)

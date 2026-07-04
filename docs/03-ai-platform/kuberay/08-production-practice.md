# 8. 企业生产实践：部署、FT、调度、安全与可观测

> 一句话理解：KubeRay 生产落地的核心四件事是 **Operator 部署、GCS 容错、资源调度/隔离、认证/监控/升级**。

## 8.1 部署模式

### Helm 安装（推荐）

```bash
helm repo add kuberay https://ray-project.github.io/kuberay-helm/
helm install kuberay-operator kuberay/kuberay-operator --version 1.6.0
```

- 默认 ClusterRole，可跨 namespace 管理 RayCluster。
- 生产建议固定版本，升级前读 release note。

### 单命名空间模式

```yaml
singleNamespaceInstall: true
watchNamespace: "team-a"
```

- 适合多租户场景，限制 Operator 只监听指定 namespace。
- 需配合 RBAC 限制权限范围。

## 8.2 GCS Fault Tolerance

### 为什么要启用

- Head Pod 重启后，GCS 状态若丢失，worker 无法重连，所有 actor/task 失效。
- 对 RayService、需要 detached actor 的训练任务，**必须启用 GCS FT**。

### 配置示例

```yaml
spec:
  gcsFaultToleranceOptions:
    redisAddress: "redis:6379"
    redisPassword:
      valueFrom:
        secretKeyRef:
          name: redis-password-secret
          key: password
    externalStorageNamespace: "my-cluster"
```

### Redis 建议

- 使用高可用 Redis（哨兵或集群）。
- 不同 RayCluster 使用不同 `externalStorageNamespace` 避免 key 冲突。
- 定期备份 Redis。

## 8.3 资源调度与隔离

### GPU 调度

```yaml
workerGroupSpecs:
  - groupName: gpu-workers
    template:
      spec:
        containers:
          - name: ray-worker
            resources:
              limits:
                nvidia.com/gpu: "4"
```

- KubeRay 自动把 `nvidia.com/gpu` 限制映射为 Ray `--num-gpus`。
- 使用 CUDA 镜像，预装对应驱动版本。

### TPU 调度

```yaml
workerGroupSpecs:
  - groupName: tpu-workers
    numOfHosts: 2
    template:
      spec:
        containers:
          - name: ray-worker
            resources:
              limits:
                google.com/tpu: "4"
```

- v1.1+ KubeRay / Ray 2.32+ 支持多主机 TPU。

### 批调度器集成

| 调度器 | 用途 |
|---|---|
| Volcano | Gang Scheduling、队列 |
| YuniKorn | 队列、配额、抢占 |
| scheduler-plugins | 轻量 Gang Scheduling |
| kai-scheduler | 华为开源批调度 |

### Kueue 集成

[Kueue](https://kueue.sigs.k8s.io/) 是 Kubernetes 原生作业队列系统，可与 KubeRay 结合：

- 配额管理（Quota）。
- 弹性作业调度。
- 抢占与 borrowing。

## 8.4 自动扩缩容调参

```yaml
spec:
  enableInTreeAutoscaling: true
  autoscalerOptions:
    version: "v2"
    idleTimeoutSeconds: 120
    upscalingMode: "Default"
```

| 参数 | 建议 |
|---|---|
| `version` | 生产优先 `v2` |
| `idleTimeoutSeconds` | 训练场景可稍大（避免抖动），Serving 场景可稍小 |
| `upscalingMode` | `Conservative` 省成本，`Aggressive` 低延迟 |
| `minReplicas` | 训练可设 0，Serving 根据 SLA 设保底 |

## 8.5 安全

### Token 认证

Ray 2.52+ / KubeRay 1.5+：

```yaml
spec:
  authOptions:
    mode: token
    secretName: ray-cluster-token
```

### Kubernetes RBAC 认证

v1.6+ 支持通过 K8s RBAC 管理访问：

```yaml
spec:
  authOptions:
    mode: kubernetes-rbac
```

### TLS

- 使用官方 `ray-cluster.tls.yaml` 示例启用 TLS。
- Serve 端点通过 Ingress 终止 TLS。

### 网络隔离

- v1.6 Alpha feature gate `RayClusterNetworkIsolation` 自动创建 NetworkPolicy。
- 不信任租户应启用 NetworkPolicy + mTLS。

## 8.6 可观测性

### Prometheus + Grafana

官方提供：

- Prometheus 安装脚本：`install/prometheus/`
- Grafana Dashboard JSON。
- ServiceMonitor / PodMonitor 示例。

### 关键指标

| 指标 | 含义 |
|---|---|
| `ray_gcs_update_resource_usage_time_bucket` | GCS 健康状态 |
| `ray_cluster_workers` | worker 数量 |
| `ray_job_status` | job 状态 |
| `ray_serve_num_http_requests` | serve 请求量 |

### 告警规则

```yaml
- alert: RayGCSStopped
  expr: absent(ray_gcs_update_resource_usage_time_bucket)
  for: 2m
  annotations:
    summary: "GCS 停止上报"
```

### 日志

- Operator 日志：`kubectl logs deploy/kuberay-operator`
- Ray 日志： head/worker Pod 标准输出。
- 使用 Fluentd/Fluent Bit 收集到 Loki/ELK。

## 8.7 升级策略

### Operator 升级

1. 阅读 release note，关注 breaking changes。
2. 在新 namespace 部署新版本 Operator 做灰度。
3. 逐步迁移 RayCluster 到新 Operator。

### RayService 升级

- 小版本：使用 `NewCluster` 蓝绿部署。
- 大模型资源受限：评估 `NewClusterWithIncrementalUpgrade`（Alpha，需 Gateway API）。
- 原地更新 `None` 仅用于开发测试。

## 8.8 备份与灾难恢复

| 数据 | 备份方式 |
|---|---|
| RayCluster/RayJob/RayService CR | etcd 备份 / Velero |
| Redis（GCS FT） | Redis 持久化/备份 |
| 训练 checkpoint | 对象存储多副本 |
| Serve 配置 | Git / ConfigMap |

## 8.9 多租户

- 按团队/项目划分 Namespace。
- 使用 ResourceQuota / LimitRange 限制资源。
- GPU 使用 MIG / time-slicing 提升利用率。
- NetworkPolicy 隔离不同租户集群。
- 对敏感负载启用 token/RBAC 认证。

## 本章小结

- 生产部署推荐 Helm + 固定版本。
- GCS FT 是训练/Serving 高可用基石。
- GPU/TPU 调度、批调度器、Kueue 提升资源效率。
- Autoscaler V2、合理 idleTimeout、min/maxReplicas 是弹性关键。
- 认证、TLS、NetworkPolicy、监控告警构成生产安全可观测体系。

**参考来源**

- [Operator Installation](https://docs.ray.io/en/latest/cluster/kubernetes/getting-started/kuberay-operator-installation.html)
- [Helm Chart RBAC](https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/helm-chart-rbac.html)
- [KubeRay GCS FT Guide](https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/kuberay-gcs-ft.html)
- [GPU Guide](https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/gpu.html)
- [TPU Guide](https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/tpu.html)
- [Configuring Autoscaling](https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/configuring-autoscaling.html)
- [Kueue Integration](https://docs.ray.io/en/latest/cluster/kubernetes/k8s-ecosystem/kueue.html)
- [KubeRay Auth](https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/kuberay-auth.html)
- [TLS Guide](https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/tls.html)
- [Prometheus Grafana Guide](https://docs.ray.io/en/latest/cluster/kubernetes/k8s-ecosystem/prometheus-grafana.html)

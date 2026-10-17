# 8. 企业生产实践：部署、FT、调度、安全与可观测

> 一句话理解：KubeRay 生产落地的核心四件事是 **Operator 部署、GCS 容错、资源调度/隔离、认证/监控/升级**。

## 8.1 部署模式

### Helm 安装（推荐）

```bash
helm repo add kuberay https://ray-project.github.io/kuberay-helm/
helm install kuberay-operator kuberay/kuberay-operator --version 1.7.1
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
- v1.7 起，Redis 清理 finalizer 卡住超过 5 分钟会被强制移除（可用注解 `ray.io/gcs-ft-deletion-timeout` 调整），并发出 `ForceDeletedStuckCluster` 警告事件。

### 免 Redis 方案：内嵌 RocksDB（v1.7+ Alpha）

Ray 2.57.0+ 且开启 `GCSFaultToleranceEmbeddedStorage` 特性门后，可直接用 PVC 存储 GCS 状态：

```yaml
spec:
  gcsFaultToleranceOptions:
    backend: rocksdb
    embeddedStorageOptions:
      deletionPolicy: Retain    # 集群删除后保留 PVC，供下次复用
```

Operator 自动供给 PVC，适合不想额外运维 Redis 的团队。此外还有 `GCSFaultToleranceActivePassiveHead`（Alpha）提供主备 Head 方案，可按需评估。

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

- 配额管理（Quota）、抢占与 borrowing。
- RayCluster / RayService（v1.6+ 通过 `spec.managedBy` 成为 Kueue 顶层作业）可被 Kueue 纳管并支持 MultiKueue 跨集群派发。
- **Kueue + Autoscaler 弹性集成（v1.5+）**：Kueue 把带注解的 RayCluster 当作弹性工作负载：

```yaml
metadata:
  annotations:
    kueue.x-k8s.io/elastic-job: "true"
spec:
  enableInTreeAutoscaling: true
```

要求 Kueue v0.13+（RayService 顶层集成需 Kueue v0.17.0+）并开启 `ElasticJobsViaWorkloadSlices` 特性门：Kueue 先按最小资源放行集群，Ray autoscaler 扩容时通过 Workload Slice 向 Kueue 申请增量配额。

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
    secretName: ray-cluster-token   # 可选：自带 Secret（key 为 auth_token），否则由 Operator 生成
```

用 `kubectl ray get token <cluster>` 获取。v1.6+ 还支持 `authOptions.secretName` 指定自定义 Secret。

### Kubernetes RBAC 认证

v1.6+ 支持通过 K8s RBAC 管理访问（需 Ray 2.55.0+）：

```yaml
spec:
  authOptions:
    mode: kubernetes-rbac
    enableK8sTokenAuth: true
```

鉴权委托给 Kubernetes ServiceAccount Token，每个 RayCluster 对应 `ray:write` 自定义动词，复用 K8s 原生 RBAC 体系。

### TLS 与 Ingress

- 使用官方 `ray-cluster.tls.yaml` 示例启用 TLS；Serve 端点通过 Ingress 终止 TLS。
- v1.7+ 可用 `headGroupSpec.ingressOptions` 自定义生成 Ingress 的 host、path、pathType 与 TLS。

### mTLS（v1.7+ Alpha）

- 安装 cert-manager，开启 `RayClusterMTLS` 特性门。
- 在 RayCluster spec 设置 `tlsOptions.enabled: true`，Operator 自动为 head/worker 签发证书。

### 网络隔离

- v1.7 Alpha 特性门 `RayClusterNetworkPolicy`：在 RayCluster spec 声明 `networkPolicy`（`DenyAll` / `DenyAllIngress` / `DenyAllEgress`），Operator 自动创建 NetworkPolicy；集群内部 Pod 间流量不会被拦截。
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
- v1.6+ 可部署 **Ray History Server（v1.7 Beta）**：集群销毁后仍能查看历史日志/事件，用于 RayJob 与 Serving 故障复盘。

## 8.7 升级策略

### Operator 升级

1. 阅读 release note，关注 breaking changes。
2. 在新 namespace 部署新版本 Operator 做灰度。
3. 逐步迁移 RayCluster 到新 Operator。

### RayService 升级

- 小版本：使用 `NewCluster` 蓝绿部署。
- 大模型资源受限：使用 `NewClusterWithIncrementalUpgrade`（v1.7 起 Beta 默认开启，支持回滚），官方示例中 5 GPU 集群以 20% 流量增量升级只需 6 GPU，约为蓝绿方案的 60%。
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

## 8.10 大模型训练与推理实践（2025-2026）

### LLM 推理：RayService + vLLM 成为标配组合

2025-2026 年的主流形态是 **Kubernetes + KubeRay + Ray Serve LLM + vLLM**：用 RayService CRD 声明 vLLM 模型服务，获得声明式扩缩容、蓝绿/渐进升级与 K8s 生态集成。

```yaml
apiVersion: ray.io/v1
kind: RayService
metadata:
  name: vllm-qwen
spec:
  serveConfigV2: |
    applications:
      - name: llm
        import_path: ray.serve.llm:build_openai_app
        args:
          llm_configs:
            - model_id: Qwen/Qwen2.5-7B-Instruct
              engine_kwargs:
                tensor_parallel_size: 4
                pipeline_parallel_size: 2   # 跨 2 台 4 卡节点
  rayClusterConfig:
    gcsFaultToleranceOptions:
      redisAddress: redis:6379
    workerGroupSpecs:
      - groupName: gpu-workers
        replicas: 2
        minReplicas: 2
        maxReplicas: 8
        template:
          spec:
            containers:
              - name: ray-worker
                resources:
                  limits:
                    nvidia.com/gpu: "4"
```

生产要点：

- **多层弹性**：Serve 副本级（请求压力）→ Ray worker 级（autoscaler）→ K8s 节点级（Cluster Autoscaler/Karpenter），三层分别配置。
- **优雅下线**：`terminationGracePeriodSeconds` 设为 300-600 秒，避免升级时丢弃在途请求。
- **高性能网络**：多机 TP/PP（如 2 节点 8×GH200，PP=2/TP=4）对 NCCL 通信敏感，HPC 场景需用 libfabric/InfiniBand CNI，否则跨机 TCP 会导致推理超时（见 arXiv 2604.12599 的实测案例）。
- **已知问题**：多机 vLLM（PIPELINE_PARALLELISM>1）时非主 worker Pod 可能一直报 `Ready=False`，不影响服务但会干扰节点生命周期管理（KubeRay issue #2552），需要为 readiness 探针配置豁免。
- 生产监控指标除 Ray 原生指标外，还应采集 vLLM 的 TTFT/TPOT、请求队列长度等。

### LLM 训练：弹性 + 队列 + Checkpoint

- RayJob + Kueue 弹性集成（见 8.3）：先以小规模获取配额起训，autoscaler 按增量配额扩容。
- 训练容错依赖 GCS FT + 周期性 checkpoint 到对象存储；worker 故障后 Ray Train/TorchTrainer 自动重启 worker 并从 checkpoint 恢复。
- 字节跳动的实践（KubeCon 分享，中文转载见 InfoQ）：全站 Ray 集群由 KubeRay 管理，用低优 spot 资源组建常驻大集群，autoscaler 按 quota 规律浮动；placement group 实现 gang 调度；自研 History Server 方案实现作业日志/metric 持久化——该能力已由官方 v1.6/v1.7 的 Ray History Server 覆盖。

### 规模化能力参考

v1.5 官方压测：100 个 RayCluster 共 10,000 Pod 的创建在 3 分 20 秒内完成；生产上需相应调大 Operator 的 reconcile 并发与 kube-client QPS/Burst（如 `reconcileConcurrency=20`、`kubeClient.qps=100`、`kubeClient.burst=200`）。

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
- [Run A RayCluster with Kueue](https://kueue.sigs.k8s.io/docs/tasks/run/rayclusters/)
- [KubeRay Auth](https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/kuberay-auth.html)
- [RayService Zero-Downtime Incremental Upgrades](https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/rayservice-incremental-upgrade.html)
- [vLLM — KubeRay Integration](https://docs.vllm.ai/en/latest/deployment/integrations/kuberay/)
- [TLS Guide](https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/tls.html)
- [Prometheus Grafana Guide](https://docs.ray.io/en/latest/cluster/kubernetes/k8s-ecosystem/prometheus-grafana.html)
- [Introducing KubeRay v1.5](https://www.anyscale.com/blog/kuberay-v1-5)
- [Introducing KubeRay v1.6 and v1.7](https://www.anyscale.com/blog/kuberay-v1-7)
- [Beyond Pre-Training: The Full Lifecycle of Foundation Models on HPC Systems（arXiv 2604.12599）](https://arxiv.org/html/2604.12599v1)

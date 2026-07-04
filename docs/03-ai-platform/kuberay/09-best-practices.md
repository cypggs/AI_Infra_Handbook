# 9. 最佳实践：Head 不跑任务、Worker 分组与声明式升级

> 一句话理解：KubeRay 的最佳实践围绕 **“让 Ray 只做计算，让 K8s 只做基础设施”** 这一原则展开。

## 9.1 Head 节点不跑任务

Head Pod 负责 GCS、Dashboard、Autoscaler，是集群的“大脑”。

```yaml
spec:
  headGroupSpec:
    rayStartParams:
      num-cpus: "0"
      num-gpus: "0"
```

- 避免 task/actor 调度到 head，减少 OOM 与重启风险。
- 让 head 资源可预测，便于独立扩缩。

## 9.2 按硬件类型划分 Worker Group

```yaml
workerGroupSpecs:
  - groupName: cpu-workers
    minReplicas: 0
    maxReplicas: 50
    template:
      spec:
        containers:
          - resources:
              limits:
                cpu: "8"
                memory: "32Gi"
  - groupName: gpu-workers
    minReplicas: 0
    maxReplicas: 10
    template:
      spec:
        containers:
          - resources:
              limits:
                nvidia.com/gpu: "1"
```

- 不同硬件类型独立扩缩容。
- 避免 CPU 任务占用 GPU 节点。

## 9.3 镜像策略

### 预装依赖

- 将 `requirements.txt` 打包进镜像，避免运行时 `pip install`。
- 使用与 Ray 版本匹配的镜像标签，例如 `rayproject/ray:2.55.0-gpu`。

### 多架构

- 为 x86 和 ARM 分别构建镜像，或使用 manifest list。

## 9.4 Autoscaler 配置

### 训练场景

```yaml
enableInTreeAutoscaling: true
autoscalerOptions:
  version: "v2"
  idleTimeoutSeconds: 300
  upscalingMode: "Conservative"
workerGroupSpecs:
  - minReplicas: 0
    maxReplicas: 100
```

- 训练任务通常有明确起止时间，允许从零开始扩容。
- `Conservative` 避免过度预扩容，节省成本。

### Serving 场景

```yaml
autoscalerOptions:
  version: "v2"
  idleTimeoutSeconds: 60
  upscalingMode: "Aggressive"
workerGroupSpecs:
  - minReplicas: 2
    maxReplicas: 50
```

- Serving 需要低延迟，应保留保底副本。
- `Aggressive` 快速响应流量增长。

## 9.5 RayJob 打包

### runtimeEnv vs 镜像

- 简单依赖：用 `runtimeEnvYAML`。
- 复杂依赖/大模型：用预构建镜像。

```yaml
spec:
  entrypoint: python train.py
  runtimeEnvYAML: |
    pip:
      - transformers==4.45.0
    env_vars:
      HF_HOME: /tmp/hf
```

### 关闭不再需要的集群

```yaml
spec:
  shutdownAfterJobFinishes: true
  ttlSecondsAfterFinished: 300
```

## 9.6 RayService 部署

### 使用 RayService 而非裸 RayCluster

- RayService 管理 active/pending 双集群，支持零停机升级。
- 生产务必启用 GCS FT。

### Serve 流量只走 Worker

```yaml
spec:
  excludeHeadPodFromServeSvc: true
```

- 减轻 head 网络负载。
- 提升 serve 可扩展性。

## 9.7 可观测性清单

- 为 Operator 配置 `ServiceMonitor`。
- 为 head Pod 配置 `PodMonitor`。
- 导入官方 Grafana Dashboard。
- 设置关键告警：GCS 停止上报、worker 不足、job 失败、serve endpoint 数为 0。

## 9.8 升级 checklist

- [ ] 阅读 KubeRay release note 与 breaking changes。
- [ ] 在 staging 环境验证 RayCluster/RayJob/RayService。
- [ ] 确认 GCS FT Redis 兼容。
- [ ] 对 RayService 使用 `NewCluster` 策略做蓝绿升级。
- [ ] 升级后检查 metrics 与 job 成功率。

## 9.9 常见反模式

| 反模式 | 后果 | 建议 |
|---|---|---|
| Head 跑计算任务 | head 重启导致集群不可用 | `num-cpus: "0"` |
| 所有 worker 混在一个 group | 无法按硬件独立扩缩 | 按 CPU/GPU/TPU 分组 |
| 禁用 GCS FT 跑 Serving | head 故障后服务中断 | 启用 GCS FT |
| 运行时 pip install | 启动慢、不可复现 | 预装依赖到镜像 |
| 使用 `None` 升级策略 | 服务停机 | 使用 `NewCluster` |
| 不设置 minReplicas | 流量突增时扩容延迟 | Serving 设保底 |

## 本章小结

- Head 不跑任务，Worker 按硬件分组。
- 预装依赖、合理配置 Autoscaler、启用 GCS FT。
- RayService 优于裸 RayCluster，serve 流量优先走 worker。
- 可观测性与升级 checklist 是生产稳定运行的保障。

**参考来源**

- [RayCluster Complete Example](https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/config.html)
- [Configuring Autoscaling](https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/configuring-autoscaling.html)
- [RayJob Quick Start](https://docs.ray.io/en/latest/cluster/kubernetes/getting-started/rayjob-quick-start.html)
- [RayService HA Guide](https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/rayservice-high-availability.html)
- [RayService Incremental Upgrade](https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/rayservice-incremental-upgrade.html)

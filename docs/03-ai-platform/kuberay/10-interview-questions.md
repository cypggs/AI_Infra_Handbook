# 10. 面试题精选

> 一句话理解：KubeRay 面试主要考察 **CRD 语义、Operator 架构、Reconciler 调用链、生产部署与高可用**。

## 10.1 初级

### Q1. KubeRay 是什么？

**答**：KubeRay 是 Ray 官方维护的 Kubernetes Operator，用于在 K8s 上部署和管理 Ray 应用。

### Q2. KubeRay 提供哪三个核心 CRD？

**答**：RayCluster、RayJob、RayService。

### Q3. RayCluster 中的 `headGroupSpec` 和 `workerGroupSpecs` 分别代表什么？

**答**：

- `headGroupSpec`：Head Pod 配置，运行 GCS、Dashboard、Autoscaler。
- `workerGroupSpecs`：Worker Group 列表，每个 group 可独立配置资源与副本。

### Q4. 为什么生产环境建议 Head 节点 `num-cpus: "0"`？

**答**：避免 task/actor 调度到 head，减少 head 资源竞争和重启风险。

### Q5. `enableInTreeAutoscaling` 的作用是什么？

**答**：在 head Pod 注入 Autoscaler sidecar，根据 Ray 资源需求自动扩缩 worker。

## 10.2 中级

### Q6. KubeRay 自动扩缩容的原理是什么？

**答**：

1. Autoscaler sidecar 监听 Ray 资源需求。
2. 资源不足时，修改对应 worker group 的 `replicas`。
3. Operator Watch 到变化，创建/删除 Pod。
4. 空闲 worker 超过 `idleTimeoutSeconds` 后被删除。

### Q7. GCS Fault Tolerance 是什么？如何启用？

**答**：GCS FT 让 Ray 的 Global Control Store 状态持久化到外部 Redis，head 重启后可以从 Redis 恢复。启用方式：

```yaml
spec:
  gcsFaultToleranceOptions:
    redisAddress: "redis:6379"
```

### Q8. RayJob 有哪些提交模式？

**答**：`K8sJobMode`、`HTTPMode`、`InteractiveMode`、`SidecarMode`。

### Q9. RayService 如何实现零停机升级？

**答**：RayService 同时维护 active 和 pending 两个 RayCluster。pending 就绪后切换 Service selector，再删除旧 active。升级策略包括 `NewCluster`、`NewClusterWithIncrementalUpgrade`、`None`。

### Q10. KubeRay 如何与批调度器集成？

**答**：在 CR 中指定 `schedulerName` 和相关 annotation，KubeRay 在创建 Pod 时注入 PodGroup 等对象，支持 Volcano、YuniKorn、scheduler-plugins、kai-scheduler。

## 10.3 高级

### Q11. 描述 RayClusterReconciler 的调用链。

**答**：

```text
Reconcile()
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

### Q12. KubeRay Operator 多副本部署时如何保证只有一个在调和？

**答**：基于 controller-runtime 的 Leader Election，Leader Election ID 为 `ray-operator-leader`。

### Q13. 如果 Head Pod 挂了，未启用 GCS FT 和启用 GCS FT 的区别是什么？

**答**：

- 未启用：新 head 无法继承 GCS 状态，worker 无法重连，需要重建整个集群。
- 启用：新 head 从 Redis 恢复 GCS 状态，worker 自动重连。

### Q14. KubeRay 多租户方案如何设计？

**答**：

- 按团队划分 Namespace + RBAC。
- ResourceQuota / LimitRange 限制资源。
- NetworkPolicy 隔离网络。
- GPU 使用 MIG / time-slicing。
- 敏感负载启用 token / K8s RBAC 认证。

### Q15. 如何在生产环境中监控 KubeRay？

**答**：

- Operator 暴露 controller-runtime metrics。
- Ray head Pod 暴露 Ray metrics、autoscaler metrics、dashboard metrics。
- 使用 Prometheus + Grafana，导入官方 Dashboard。
- 关键告警：GCS 停止上报、worker 数量不足、job 失败、serve endpoint 数为 0。

## 本章小结

- 初级题聚焦 CRD 与基本概念。
- 中级题聚焦扩缩容、FT、Job/Service 生命周期。
- 高级题聚焦源码调用链、多副本、多租户、可观测性。

**参考来源**

- [KubeRay 官方文档](https://ray-project.github.io/kuberay/)
- [Ray on Kubernetes 文档](https://docs.ray.io/en/latest/cluster/kubernetes/index.html)
- 本手册 KubeRay 各章内容

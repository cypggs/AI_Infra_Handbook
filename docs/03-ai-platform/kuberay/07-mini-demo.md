# 7. Mini Demo：本地模拟 KubeRay 控制平面

> 一句话理解：这个 Demo 用 **纯 Python 模拟 Kubernetes API Server、Informer、WorkQueue、Reconciler 和 FakeClock**，在不依赖真实 K8s 或 Ray 的情况下，跑通 RayCluster 创建、Worker 扩缩容、RayJob 提交与清理。

## 7.1 目标与约束

- **无需 K8s 集群**：不调用真实 kube-apiserver，也不启动 Ray 进程。
- **CPU 可运行**：纯 Python，毫秒级收敛。
- **真实控制平面语义**：包含 resourceVersion、generation、/status 子资源、ownerReference 级联 GC、RequeueAfter。
- **可测试**：`pytest` 覆盖集群创建、扩缩容、作业生命周期。

## 7.2 目录结构

```
mini-demo/
├── README.md
├── pyproject.toml
├── kuberay_mini/
│   ├── __init__.py
│   └── demo.py          # FakeClock + FakeApiServer + Informer + WorkQueue + Reconcilers + Controller
└── tests/
    ├── __init__.py
    └── test_demo.py     # pytest 用例
```

## 7.3 运行方式

```bash
cd docs/03-ai-platform/kuberay/mini-demo
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v
python -m kuberay_mini.demo
```

预期输出：

```
[   0.0s] created head Service example-cluster-head-svc
[   0.0s] created serve Service example-cluster-serve-svc
[   0.0s] created head Pod example-cluster-head
[   0.0s] created worker Pod example-cluster-worker-cpu-workers-0
[   0.0s] created worker Pod example-cluster-worker-cpu-workers-1
[   0.0s] updated RayCluster example-cluster status ready=0/2 state=provisioning
[   2.0s] updated RayCluster example-cluster status ready=2/2 state=ready
[   2.0s] created worker Pod example-cluster-worker-cpu-workers-2
...
Demo result: {
  'cluster_name': 'example-cluster',
  'final_worker_count': 4,
  'job_name': 'example-job',
  'job_status': 'Complete',
  'job_cluster_deleted': True,
  'elapsed_time': 9.0
}
```

## 7.4 核心组件

### FakeApiServer

模拟 kube-apiserver + etcd：

- 内存对象存储。
- 全局单调递增 `resourceVersion`。
- `generation` 只在 spec 变化时递增。
- `/status` 子资源单独写入，不改变 generation。
- `ownerReferences` 级联 GC。

### FakeClock

推进虚拟时间，验证 Reconciler 在未收敛时使用 `RequeueAfter` 而非阻塞。

### Informer + WorkQueue

- Informer 从 ApiServer 拉取事件，Handler 将受影响的 CR 加入 WorkQueue。
- 对主资源（RayCluster/RayJob）直接入队。
- 对 Owned 资源（Pod/Service/Job）解析 `ownerReferences` 后入队 owner。

### RayClusterReconciler

一次 Reconcile 完成：

1. 创建 head service。
2. 创建 serve service。
3. 创建 head pod。
4. 按 worker group 的 `replicas` 创建/删除 worker pods。
5. 计算 `readyWorkerReplicas` 并更新 status。
6. 未就绪则返回 `requeue_after`。

### RayJobReconciler

状态机：

- `New` → `Initializing`
- `Initializing`：创建/选择 RayCluster，等待 ready，创建 submitter Job。
- `Running`：轮询 submitter Job 状态，完成后标记 `Complete`。
- `Complete`：若 `shutdownAfterJobFinishes` 为 true，删除 RayCluster。

## 7.5 测试覆盖

| 测试 | 验证点 |
|---|---|
| `test_cluster_creation_converges` | RayCluster 创建 → Service/Pod 创建 → status ready |
| `test_scale_out_and_in` | 修改 replicas 后 Operator 创建/删除 Pod 并收敛 |
| `test_rayjob_lifecycle` | RayJob 创建集群、提交作业、完成、清理集群 |
| `test_run_demo_end_to_end` | 端到端 Demo 返回值正确 |

## 7.6 与真实 KubeRay 的差异

| 方面 | Mini Demo | 真实 KubeRay |
|---|---|---|
| API Server | 内存字典 | Kubernetes API Server + etcd |
| Pod 调度 | 时间到即 ready | K8s Scheduler + 节点资源 |
| Autoscaler | 手动 patch replicas | Autoscaler sidecar 监听 Ray 资源需求 |
| Ray 进程 | 无 | 真实的 GCS、Raylet、Dashboard |
| Serve | 无 | Ray Serve + HTTP proxy |
| 网络 | 无 | Service、Ingress、NetworkPolicy |

本 Demo 用于理解 KubeRay 控制平面的调和语义，不能直接用于生产。

## 本章小结

- Mini Demo 用纯 Python 模拟了 KubeRay Operator 的核心控制平面。
- 覆盖 RayCluster 创建、扩缩容、RayJob 生命周期与级联清理。
- `pytest` 全部通过，收敛行为可观测。

**参考来源**

- 本 Demo 源码：`docs/03-ai-platform/kuberay/mini-demo/`
- [KubeRay GitHub](https://github.com/ray-project/kuberay)
- 本手册 [Operator 模式 Mini Demo](../../02-cloud-native/operator/07-mini-demo)

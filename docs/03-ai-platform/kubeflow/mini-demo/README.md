# Kubeflow Mini Demo

一个纯 Python 的 Kubeflow 控制面模拟器，无需 Kubernetes、GPU 或外部 LLM key。它用内存 Store、Informer、WorkQueue 和一组 Reconciler 模拟：

- Profile → Namespace / RBAC / ResourceQuota
- Notebook → StatefulSet / Service / VirtualService
- Pipeline Run → 顺序执行 preprocess → Katib 调参 → PyTorchJob 训练 → KServe 部署
- Katib Experiment → Trial 并行搜索超参，返回最佳参数
- Training Operator → PyTorchJob Master + Worker
- KServe → InferenceService

## 运行

```bash
cd docs/03-ai-platform/kubeflow/mini-demo
pip install -e ".[dev]"
pytest tests/ -v
python -m kubeflow_mini.demo
```

## 设计要点

- **FakeClock**：可步进的虚拟时钟，所有控制器按 `ready_at` 推进状态。
- **Store**：内存对象存储，按 `(kind, namespace, name)` 索引。
- **Informer**：产生 add/update/delete 事件，供控制器监听。
- **WorkQueue**：带重试的待处理队列。
- **Controllers**：每个 CRD 一个 reconcile 函数，创建子资源并更新 status。

## 与真实 Kubeflow 的差异

| 方面 | Mini Demo | 真实 Kubeflow |
|---|---|---|
| 调度 | 单线程 step() | K8s Scheduler |
| 网络 | 无 | Istio + Headless Service |
| 容器 | 模拟 | 真实 Docker/Pod |
| 存储 | 内存 | S3 / GCS / PVC / MLMD |
| GPU | 模拟 | 真实 nvidia.com/gpu |
| 认证 | 无 | DEX / OIDC / Istio auth |

本 Demo 仅用于理解控制面编排逻辑，不能直接用于生产。

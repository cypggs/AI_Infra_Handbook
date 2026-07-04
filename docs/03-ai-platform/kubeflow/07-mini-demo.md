# 7. Mini Demo：纯 Python 模拟 Kubeflow 控制面

> 一句话理解：这个 Demo 用 **内存 Store + Informer + WorkQueue + 一组 Reconciler** 模拟 Kubeflow 的核心编排：Profile → Notebook → Pipeline Run → Katib 调参 → PyTorchJob 训练 → KServe 部署。

## 7.1 目标与约束

- **无需 Kubernetes**：所有资源都是内存里的 dict。
- **无需 GPU/容器**：用 FakeClock 模拟执行耗时。
- **无需外部 LLM/IdP**：确定性输入输出。
- **展示控制面逻辑**：多租户、DAG 依赖、调参、分布式训练、服务部署。

## 7.2 目录结构

```
mini-demo/
├── README.md
├── pyproject.toml
├── kubeflow_mini/
│   ├── __init__.py
│   ├── store.py          # 内存对象存储
│   ├── informer.py       # 事件总线
│   ├── workqueue.py      # 待处理队列
│   ├── controllers.py    # 各 CRD 的 Reconciler + FakeClock
│   └── demo.py           # 端到端入口
└── tests/
    └── test_demo.py      # pytest 用例
```

## 7.3 运行方式

```bash
cd docs/03-ai-platform/kubeflow/mini-demo
pip install -e ".[dev]"
pytest tests/ -v
python -m kubeflow_mini.demo
```

预期输出：

```
Demo result: {
  'steps': 13,
  'run_phase': 'Succeeded',
  'best_lr': 0.011,
  'best_metric': -0.01,
  'service_url': 'http://run-001-deploy.alice.svc'
}
```

## 7.4 核心设计

### FakeClock

```python
@dataclass
class FakeClock:
    now: int = 0
    def step(self) -> None:
        self.now += 1
```

当控制器创建 Pod/Job/Trial 时，设置 `ready_at = clock.now + 1`，下一次 step 后状态变为完成。

### Store

按 `(kind, namespace, name)` 索引，支持 create/update/delete/get/list。

### Informer

产生 `add/update/delete` 事件，控制器监听后入队。

### WorkQueue

简单的 FIFO + 重试限制。真实对应 K8s workqueue 的限速/指数退避抽象。

### Controllers

每个 CRD 一个 `reconcile_*` 方法：

| CRD | Reconciler 行为 |
|---|---|
| Profile | 创建 Namespace、ResourceQuota |
| Notebook | 创建 StatefulSet、Service；到 `ready_at` 后 Ready |
| Pipeline | 校验 DAG 依赖 |
| Run | 按 DAG 顺序创建 Job → Experiment → PyTorchJob → InferenceService |
| Experiment | 创建指定数量 Trial；汇总最佳参数 |
| Trial | 模拟训练并产出 metric |
| PyTorchJob | 创建 Master/Worker Pod；全部成功后 Succeeded |
| Pod | 到 `ready_at` 后 Succeeded |
| InferenceService | 到 `ready_at` 后 Ready |

## 7.5 关键代码片段

### Pipeline DAG

```python
pipeline = make_obj("Pipeline", "alice", "train-and-serve", {
    "tasks": {
        "preprocess": {"kind": "Job", "depends_on": []},
        "tune": {"kind": "Experiment", "depends_on": ["preprocess"]},
        "train": {"kind": "PyTorchJob", "depends_on": ["tune"]},
        "deploy": {"kind": "InferenceService", "depends_on": ["train"]},
    }
})
```

### Run 的依赖驱动

```python
deps = task.get("depends_on", [])
if not all(state.get(d) == "Succeeded" for d in deps):
    continue
```

### Katib 实验

```python
for i in range(len(my_trials), max_trials):
    lr = round(0.001 + (i * 0.005), 4)
    trial = make_obj("Trial", ns, f"{name}-trial-{i}",
                     {"lr": lr, "experiment": name})
    self.store.create(trial)
```

实验成功后，把最佳 `lr` 写回 Run 的 `parameters`，供 PyTorchJob 使用。

### PyTorchJob

```python
for role, count in replicas.items():
    existing = [p for p in my_pods if p["spec"].get("role") == role]
    for i in range(len(existing), count):
        pod = make_obj("Pod", ns, f"{name}-{role.lower()}-{i}",
                       {"job": name, "role": role})
        self.store.create(pod)
```

## 7.6 测试覆盖

| 测试 | 验证点 |
|---|---|
| `test_store_create_and_get` | 内存存储索引 |
| `test_profile_creates_namespace_and_quota` | Profile Controller 行为 |
| `test_notebook_waits_for_profile` | 父资源存在性检查 |
| `test_notebook_becomes_ready_after_one_tick` | FakeClock 推进状态 |
| `test_pipeline_validation_fails_on_missing_dependency` | DAG 校验 |
| `test_experiment_creates_trials_and_picks_best_lr` | Katib 调参 |
| `test_pytorchjob_creates_pods` | 分布式训练 Pod 创建 |
| `test_demo_end_to_end` | 完整链路 |

## 7.7 与真实 Kubeflow 的差异

| 方面 | Mini Demo | 真实 Kubeflow |
|---|---|---|
| 调度 | 单线程 step() | K8s Scheduler |
| 网络 | 无 | Istio + Headless Service |
| 容器 | 模拟 | 真实 Docker/Pod |
| 存储 | 内存 | S3 / GCS / PVC / MLMD |
| GPU | 模拟 | 真实 nvidia.com/gpu |
| 认证 | 无 | DEX / OIDC / Istio auth |
| 重试/限速 | 简单 FIFO | 指数退避 workqueue |

本 Demo 仅用于理解控制面编排逻辑，不能直接用于生产。

## 本章小结

- Mini Demo 用纯 Python 模拟了 Kubeflow 的核心控制面：Store、Informer、WorkQueue、Reconciler。
- 场景覆盖 **Profile → Notebook → Pipeline Run → Katib → PyTorchJob → KServe**。
- `pytest` 8 个用例全部通过，`python -m kubeflow_mini.demo` 13 步完成端到端流程。
- 与真实 Kubeflow 的主要差异在调度、网络、容器、存储、认证。

**参考来源**

- 本 Demo 源码：`docs/03-ai-platform/kubeflow/mini-demo/`
- [Kubeflow Pipelines Backend](https://github.com/kubeflow/pipelines/tree/master/backend)
- [Kubeflow Training Operator GitHub](https://github.com/kubeflow/training-operator)
- [Kubeflow Katib GitHub](https://github.com/kubeflow/katib)
- 本手册 [Operator 模式 Mini-Demo](../../02-cloud-native/operator/07-mini-demo)

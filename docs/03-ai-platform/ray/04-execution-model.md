# 4. 执行模型：一个请求的生命周期

> 本章把架构图变成时序：从 `ray.init()` 到 `@ray.remote`、task 派发执行、对象返回、`ray.get` 取回、actor 创建与调用、以及 Ray Serve 在线请求的完整链路。文件/类名均为仓库实际路径（详见 [第 6 章](06-source-analysis)）。

---

## 4.1 `ray.init()`：连上集群

入口 [`python/ray/__init__.py`](https://github.com/ray-project/ray/blob/master/python/ray/__init__.py)（再导出自 `_private/worker.py`）→ 构造 `ClientBuilder`（[`client_builder.py`](https://github.com/ray-project/ray/blob/master/python/ray/client_builder.py)）：

- **本地集群**：spawn 一个 GCS、若干 raylet、plasma store（[`_private/node.py`](https://github.com/ray-project/ray/blob/master/python/ray/_private/node.py)）。
- **远程集群**：用 **Ray Client**（gRPC）连，或 attach 到已存在集群（raylet socket + GCS 地址）。

driver 随后通过 Cython 桥 [`_raylet.pyx`](https://github.com/ray-project/ray/blob/master/python/ray/_raylet.pyx) 链入 C++ **CoreWorker**。

---

## 4.2 `@ray.remote` 装饰：把 Python 变分布式

装饰器在 [`python/ray/_private/worker.py`](https://github.com/ray-project/ray/blob/master/python/ray/_private/worker.py) 的 `def remote`：检查参数（裸 `@ray.remote` vs `ray.remote(num_cpus=2)`、函数 vs 类）：

- **函数** → 包成 [`RemoteFunction`](https://github.com/ray-project/ray/blob/master/python/ray/remote_function.py)（**注意：在顶层，不在 `_private/`**）。
- **类** → 包成 actor 类（[`python/ray/actor.py`](https://github.com/ray-project/ray/blob/master/python/ray/actor.py)，**顶层**）。

`.remote(*args)` 不执行，只构造 `TaskSpec` 并提交。

---

## 4.3 Task 的完整生命周期

```
[Driver] square.remote(3)
   │
   ① RemoteFunction._submit_task  →  构造 TaskSpec
   │   (经 _raylet.pyx)  CoreWorker::SubmitTask
   ② TaskManager::AddPendingTask  →  在 ReferenceCounter 登记所有权 + 返回值 ObjectRef
   ③ LeasePolicy::GetBestNode     →  选 raylet（默认本地 / 数据局部性 / node affinity）
   ④ RayletClient::RequestWorkerLease (gRPC)  →  本地 raylet
   │
        ┌── 本地 raylet 资源够 ──► LocalLeaseManager::Dispatch → WorkerPool::PopWorker
        │                         → 租出的 worker CoreWorker::ExecuteTask
        │                         → 执行用户函数
        │                         → 返回值序列化进 plasma  CreateObject
        │                         → raylet PinObjectIDs
        │
        └── 本地资源不足 ──► spillback：返回远端 raylet B 地址
                            → owner 向 B 重发 RequestWorkerLease
   ⑤ ObjectRef 解析：borrower 通过 ReferenceCounter + OwnershipBasedObjectDirectory 订阅位置
```

要点：

- **第②步是所有权核心**：任务 spec 与返回值引用**留在 owner driver**，不进 GCS。这是百万任务/秒吞吐的根基。
- **第④步是溢回调度**：本地 raylet 拒绝放行时**不排队**，而是给 owner 一个更合适的远端 raylet。
- worker 默认初始数量 = 节点 CPU 数；一个租出的 worker 可被**复用**执行多个同形状任务（资源形状/共享内存参数/runtime_env 一致），空闲"几百毫秒"后归还以兼顾公平。

---

## 4.4 `ray.get()`：取回对象

[`python/ray/_private/worker.py`](https://github.com/ray-project/ray/blob/master/python/ray/_private/worker.py) 的 `ray.get(refs)` → CoreWorker `Get`：

1. **本地命中**：plasma 里已有（或 in-band 小对象在 owner 进程内）→ 直接 mmap 零拷贝返回。
2. **不在本地**：
   - `ReferenceCounter` 知道 owner 地址 → `OwnershipBasedObjectDirectory` 订阅对象位置；
   - 若对象在远端节点 → `ObjectManager::Pull`（委托 [`PullManager`](https://github.com/ray-project/ray/blob/master/src/ray/object_manager/pull_manager.h)）→ 分块传输；
   - 若对象已被溢写到外部存储 → 从 URL 恢复（`SpilledObjectReader` 解析 `path?offset=N&size=M`）；
   - plasma 的 `GetRequestQueue` 解除 worker 阻塞 → 通过 `ClientMmapTableEntry` 零拷贝交付。

> **反模式**：一次 `ray.get` 上百万个 ref 会撑爆 driver 内存与对象存储（[ray-get-too-many-objects](https://docs.ray.io/en/latest/ray-core/patterns/ray-get-too-many-objects.html)）。大输出用**流式生成器** `@ray.remote(num_returns="streaming")`。

---

## 4.5 Actor 的生命周期

```python
c = Counter.remote()        # CreateActor
c.inc.remote()              # SubmitActorTask → 返回 ObjectRef
```

1. `ActorClass._remote()`（[`actor.py`](https://github.com/ray-project/ray/blob/master/python/ray/actor.py)）→ CoreWorker `CreateActor`。
2. GCS `gcs_actor_manager` 登记 actor 元数据；调度器选节点；raylet 起一个长寿命 worker 进程作为该 actor。
3. 之后每次方法调用 = `SubmitActorTask` RPC，**串行**作用于该 actor 进程（默认 `max_concurrency=1`）。
4. **重启语义**：actor 死后，若 `max_restarts` 预算未耗尽，在健康节点重建；在途方法按 `max_task_retries` 重试（默认 actor 任务**不可重试**）。

> **actor 的串行化是性能关键**：`max_concurrency=1` 意味着一个慢方法阻塞该 actor 所有后续调用。CPU 密集应横向开多个 actor；I/O 密集用 async actor + 提高 `max_concurrency`（但 GIL 仍串行纯 Python CPU，见 [第 8 章](08-production-practice)）。

---

## 4.6 Ray Serve 的请求生命周期

Ray Serve 在 Ray Core 之上构建在线推理服务。组件（[`python/ray/serve/`](https://github.com/ray-project/ray/tree/master/python/ray/serve)）：

```
客户端 ──HTTP/gRPC──► [Proxy actor（每节点）]
                            │
                            ▼
                  DeploymentHandle → [Router actor]  ──power-of-two-choices──► [Replica actor × N]
                            ▲                                                              │
                  long_poll 同步副本列表（Router ↔ Controller）                              ▼
                                                                                            执行用户 deployment 类
```

- **ServeController**（[`_private/controller.py`](https://github.com/ray-project/ray/blob/master/python/ray/serve/_private/controller.py)）：全局控制面 actor（每个 Serve 实例一个），创建/销毁副本与 proxy，**运行 autoscaler**，状态 checkpoint 到 GCS。
- **Proxy**（[`_private/proxy.py`](https://github.com/ray-project/ray/blob/master/python/ray/serve/_private/proxy.py)）：每节点一个，跑 **Uvicorn**（HTTP）/ **grpcio**（gRPC）；较新版本引入 **HAProxy router**（`_private/haproxy*.py`）把延迟降约 88%（[Anyscale 博客](https://www.anyscale.com/blog/ray-serve-inference-lower-latency-higher-throughput-haproxy)）。
- **Replica**（[`_private/replica.py`](https://github.com/ray-project/ray/blob/master/python/ray/serve/_private/replica.py)）：包用户 deployment 类，处理请求队列（async handler 走 asyncio），支持 `@serve.batch` 批处理。
- **DeploymentHandle → Router**：模型组合/DAG 入口，Router 用 **power-of-two-choices** 选副本；`long_poll`（[`_private/long_poll.py`](https://github.com/ray-project/ray/blob/master/python/ray/serve/_private/long_poll.py)）让 Router 与 Controller 副本列表保持同步。
- **autoscaler 跑在 Controller 内**：每个 `DeploymentHandle` 与每个副本周期性上报队列/in-flight 指标，Controller 据此伸缩（与集群 VM autoscaler **独立**）。

### 部署一个 deployment

```python
from ray import serve

@serve.deployment(num_replicas=3, ray_actor_options={"num_cpus": 1})
class Greeter:
    def __call__(self, request):
        return {"msg": "hi"}

app = Greeter.bind()
serve.run(app)   # serve.run / serve.start（见 serve/api.py）
```

`serve.run`/`serve.start` 在 [`serve/api.py`](https://github.com/ray-project/ray/blob/master/python/ray/serve/api.py)，经 `serve/__init__.py` 导出。

---

## 4.7 一次训练任务（Ray Train）的形态

Ray Train 把"分布式训练编排"叠在 Ray Core 之上：

```python
from ray.train import ScalingConfig, RunConfig
from ray.train.torch import TorchTrainer

trainer = TorchTrainer(
    train_loop_per_worker,                 # 每个 worker 跑的训练函数
    scaling_config=ScalingConfig(num_workers=4, use_gpu=True,
                                 resources_per_worker={"CPU": 8, "GPU": 1}),
    run_config=RunConfig(storage_path="s3://..."),   # 2.7 起必需
)
result = trainer.fit()
```

- `ScalingConfig` 决定 worker 数与资源；trainer 起一组 worker actor（内部用 PyTorch DDP/FSDP/DeepSpeed 做集合通信）。
- 每个 worker 通过 `session.report(metrics, checkpoint=...)` 上报指标与 checkpoint。
- **弹性训练**：worker 加入/离开、节点丢失时重平衡并从最近 checkpoint 恢复（[Elastic training](https://docs.ray.io/en/latest/train/user-guides/elastic-training.html)）。
- 容错：配合 spot 节点 + `RunConfig(storage_path=...)` + 频繁 checkpoint 实现抢占恢复。

---

## 4.8 生命周期对照速查

| 动作 | 入口 | CoreWorker 方法 | 关键协作 |
|---|---|---|---|
| 提交 task | `fn.remote()` | `SubmitTask` → `TaskManager::AddPendingTask` | `ReferenceCounter` + raylet lease |
| 创建 actor | `Cls.remote()` | `CreateActor` | GCS `gcs_actor_manager` + raylet |
| 调用 actor 方法 | `inst.m.remote()` | `SubmitActorTask` | actor worker 串行执行 |
| 取对象 | `ray.get(ref)` | `Get` | `OwnershipBasedObjectDirectory` + `ObjectManager::Pull` |
| 放对象 | `ray.put(obj)` | `Put`/`Pin` | plasma `CreateObject` + raylet pin |
| 等待 | `ray.wait(refs)` | `Wait` | raylet `WaitManager` |
| 服务部署 | `serve.run(app)` | 创建 ServeController + proxy + replicas | Serve 控制面 |

---

下一章 [核心模块](05-core-modules) 给出各库的速查表与关键参数。

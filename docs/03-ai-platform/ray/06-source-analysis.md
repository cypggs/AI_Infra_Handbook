# 6. 源码与生态分析

> 本章带读者走进 [ray-project/ray](https://github.com/ray-project/ray) 仓库，给出真实的目录结构、关键类与调用链，并标注 2024–2026 的源码级演进。文件/类名基于仓库 `master` 核验；标 `[verify]` 的需进一步确认精确文件名。

---

## 6.1 顶层布局

```
ray/
├── src/ray/                  # C++ 核心（Bazel 构建）
│   ├── raylet/               # 每节点调度器（NodeManager / ClusterLeaseManager / ...）
│   ├── core_worker/          # 嵌入 driver/worker 的库（所有权表、任务管理）
│   ├── gcs/                  # 全局控制面（GcsServer + 各 manager）
│   ├── object_manager/       # 对象传输 + plasma/ 对象存储
│   ├── ray_syncer/           # gRPC 节点状态同步（取代 Redis-pubsub 心跳）
│   ├── pubsub/               # 对象位置订阅
│   ├── rpc/  protobuf/  flatbuffers/   # 通信层
│   └── observability/
├── python/ray/               # Python API + 库
│   ├── __init__.py           # ray.init/remote/get/put/wait 导出
│   ├── _raylet.pyx           # Cython ↔ C++ 桥（迁移中 → pybind11）
│   ├── actor.py  remote_function.py    # actor/task 封装（顶层，非 _private）
│   ├── serve/  train/  data/  tune/  llm/  dashboard/  autoscaler/  runtime_env/
│   └── _private/             # 内部实现（worker.py、external_storage.py、ray_constants.py …）
└── rllib/                    # RLlib 真实源码（python/ray/rllib 是符号链接）
```

> **易错点**：
> - RLlib 真源码在**仓库根 `/rllib/`**，不在 `python/ray/rllib/`（后者是 symlink → `../../rllib`）。
> - `actor.py`、`remote_function.py` 在 `python/ray/` **顶层**，**不在 `_private/`**。
> - Plasma 在 `src/ray/object_manager/plasma/`，**没有** `src/ray/plasma/` 或 `src/plasma/`。

---

## 6.2 Raylet（C++）— `src/ray/raylet/`

入口 [`main.cc`](https://github.com/ray-project/ray/blob/master/src/ray/raylet/main.cc)。核心类：

| 类 | 文件 | 职责 |
|---|---|---|
| `NodeManager` | [node_manager.h](https://github.com/ray-project/ray/blob/master/src/ray/raylet/node_manager.h) | 中央 raylet；处理 `PinObjectIDs`、心跳（ray_syncer）、任务派发；集成各子管理器 |
| `ClusterLeaseManager` | [cluster_lease_manager.h](https://github.com/ray-project/ray/blob/master/src/ray/raylet/scheduling/cluster_lease_manager.h) | 决定任务在哪台 lease worker（派发到远端 raylet）。**原名 `ClusterTaskManager`** |
| `LocalLeaseManager` | [local_lease_manager.h](https://github.com/ray-project/ray/blob/master/src/ray/raylet/scheduling/local_lease_manager.h) | 本地 worker 租借（参数已就绪的任务）。**原名 `LocalTaskManager`** |
| `ClusterResourceManager` / `ClusterResourceScheduler` / `LocalResourceManager` | `scheduling/` | 资源会计与调度策略（打包/摊开启发式） |
| `WorkerPool` | [worker_pool.h](https://github.com/ray-project/ray/blob/master/src/ray/raylet/worker_pool.h) | 管理 worker 进程；**含 IO worker 池**（spill/restore），delete 借用较大的池 |
| `LocalObjectManager` | [local_object_manager.h](https://github.com/ray-project/ray/blob/master/src/ray/raylet/local_object_manager.h) | **真正的"溢写管理器"**；状态机 `Pinned→PendingSpill→Spilled`，三张子表 `pinned_objects_`/`objects_pending_spill_`/`spilled_objects_url_` |
| `LeaseDependencyManager` | `lease_dependency_manager.h` | 拉取任务参数对象（`ObjectManager::Pull`） |

**派发链**：`CoreWorker.SubmitTask` → `NodeManager.HandleRequestWorkerLease` → `ClusterLeaseManager::Schedule` →（本地）`LocalLeaseManager::Dispatch` → `WorkerPool::PopWorker` → worker 跑任务 → 返回值进 plasma → `PinObjectIDs`。

> **调度策略类**在 `raylet/scheduling/policy/`（目录已核验存在；Spread/Packing/NodeAffinity 的**精确文件名 [verify]**——当前启发式主要落在 `ClusterResourceScheduler` 等文件里）。

---

## 6.3 Core Worker（C++ + Python）— `src/ray/core_worker/`

每个 driver/worker 内嵌一个 `CoreWorker`（[core_worker.h](https://github.com/ray-project/ray/blob/master/src/ray/core_worker/core_worker.h)）。关键成员：

| 类 | 职责 |
|---|---|
| `CoreWorker` | 中心对象；`SubmitTask`/`CreateActor`/`SubmitActorTask`/`Get`/`Wait`/`Put`/`Pin`/`Push` |
| `TaskManager` | 持有 **`OwnedTasks`**（每个已提交任务的 spec、状态、返回 ref）；worker 失败时重提交 |
| `ReferenceCounter` | **所有权表**：`ObjectID` → borrower 集 / 嵌套 ref / lineage 计数；驱动分布式引用计数与 GC |
| `ObjectRecoveryManager` | 对象丢失时的重建编排 |
| `LeasePolicy` | 选最佳节点（本地/局部性/node affinity） |
| `FutureResolver` / `GeneratorWaiter` | 异步解析 future / 流式生成器 |
| `experimental_mutable_object_manager.h` | **Compiled Graph / mutable-object 通道**钩子 |

子目录：`actor_management/`、`store_provider/`（plasma store provider）、`task_execution/`、`task_submission/`（内部文件名 [verify]）。

### `@ray.remote` → 执行（Python 侧）

1. `remote`（[`_private/worker.py`](https://github.com/ray-project/ray/blob/master/python/ray/_private/worker.py)）判函数/类。
2. 函数 → [`RemoteFunction`](https://github.com/ray-project/ray/blob/master/python/ray/remote_function.py)；`.remote()` 构造 `TaskSpec` → `_submit_task` → 经 `_raylet.pyx` → `CoreWorker::SubmitTask`。
3. 类 → actor 类（[`actor.py`](https://github.com/ray-project/ray/blob/master/python/ray/actor.py)）；`ActorClass._remote()` 走 `CreateActor`；方法调用 = `SubmitActorTask`。

### C++ 侧任务路径

`CoreWorker::SubmitTask` → `TaskManager::AddPendingTask`（在 `ReferenceCounter` 登记所有权 + 返回 ref）→ `LeasePolicy::GetBestNode` → `RayletClient::RequestWorkerLease`（gRPC）→ raylet `ClusterLeaseManager` → `LocalLeaseManager::Dispatch` → `WorkerPool::PopWorker` → worker `CoreWorker::ExecuteTask` → 用户函数 → 返回值经 store provider 序列化进 plasma `CreateObject` → raylet `PinObjectIDs` → ObjectRef 经 `ReferenceCounter` 解析给 borrower。

### `ray.get()` 路径

`ray.get` → CoreWorker `Get` →（未命中）`ReferenceCounter` 知 owner → `OwnershipBasedObjectDirectory` 订阅位置 → `ObjectManager::Pull`（[`PullManager`](https://github.com/ray-project/ray/blob/master/src/ray/object_manager/pull_manager.h) 分块传输 / 从溢写 URL 恢复）→ plasma `GetRequestQueue` 解除阻塞 → `ClientMmapTableEntry` 零拷贝交付。

---

## 6.4 GCS — `src/ray/gcs/`

单一 `GcsServer`（[`gcs_server_main.cc`](https://github.com/ray-project/ray/blob/master/src/ray/gcs/gcs_server_main.cc)）。管理者（`gcs_*_manager.{h,cc}`）：`gcs_node_manager`/`gcs_job_manager`/`gcs_resource_manager`/`gcs_worker_manager`/`gcs_function_manager`/`gcs_placement_group(_manager|_scheduler)`/`gcs_autoscaler_state_manager`/`gcs_health_check_manager`/`gcs_kv_manager`/`gcs_task_manager`（**仅存任务事件/状态，不驱动调度**）。actor 状态在子目录 `gcs/actor/`（`gcs_actor_manager.h` [verify filename]）。

**HA/存储**：默认**内存**（1.11 起 Redisless）；外接 Redis 作可选持久备份；`store_client/` + `gcs_kv_manager` 提供可插拔 KV 抽象（`RedisStoreClient`/`InMemoryStoreClient` [verify]，[issue #53115](https://github.com/ray-project/ray/issues/53115) 让备份 KV 可插拔）。

---

## 6.5 对象存储 / Plasma — `src/ray/object_manager/`

`object_manager/`（顶层）：

| 类 | 职责 |
|---|---|
| `ObjectManager` | 分块 Push/Pull；含 `ObjectBufferPool`、`PullManager`、`PushManager`；gRPC `HandlePush`/`HandlePull` |
| `PullManager` | 拉取编排（本地恢复 vs 跨节点拉） |
| `PushManager` | 每对象并发出站上限 |
| `OwnershipBasedObjectDirectory` | **唯一** `IObjectDirectory` 实现；位置索引基于 owner + pubsub |
| `SpilledObjectReader` | 解析 `path?offset=N&size=M` URL |

`plasma/`：

| 类 | 职责 |
|---|---|
| `PlasmaStore`（单线程） | 创建/密封/删除；OOM 回调溢写 |
| `PlasmaStoreRunner` | 全局单例（Copyright **2025**，dlmalloc 无法隔离） |
| `ObjectStore` | `object_table_`（ObjectID→LocalObject） |
| `ObjectLifecycleManager` | 引用计数；refcount 0 可驱逐 |
| `EvictionPolicy`(LRU) | `RequireSpace`/`ChooseObjectsToEvict` |
| `PlasmaAllocator` | `/dev/shm` mmap + `FallbackAllocate`（OOM 退本地盘） |
| `ClientMmapTableEntry` | 客户端 per-fd mmap（Copyright **2025**） |
| `CreateRequestQueue` | OOM/溢写触发 |

**溢写执行**：Python **IO worker 进程**（`WorkerPool` 的 spill/restore 池）调用 [`python/ray/_private/external_storage.py`](https://github.com/ray-project/ray/blob/master/python/ray/_private/external_storage.py)：`FileSystemStorage`（默认）/`ExternalStorageSmartOpenImpl`（S3/GCS via smart_open）。

---

## 6.6 Ray Serve — `python/ray/serve/`

公共 API（[`serve/__init__.py`](https://github.com/ray-project/ray/blob/master/python/ray/serve/__init__.py)）：`serve.run`/`serve.start`/`serve.deployment`/`serve.batch`。实现（[`serve/_private/`](https://github.com/ray-project/ray/tree/master/python/ray/serve/_private)）：

| 文件 | 角色 |
|---|---|
| `controller.py`（`ServeController`） | 全局控制面 actor；创建/销毁副本与 proxy；**运行 autoscaler**；checkpoint 到 GCS |
| `proxy.py` | HTTP(Uvicorn)/gRPC(grpcio) proxy；新版 `haproxy*.py` router 降延迟 ~88% |
| `replica.py` | `ReplicaActor`；async handler；支持 `@serve.batch` |
| `application_state.py`/`deployment_state.py`/`deployment_scheduler.py`/`deployment_node.py`/`build_app.py` | 部署状态机 + DAG 构建（**旧 DeploymentGraph API 已被 `serve/dag.py` 取代**） |
| `router.py` | 每节点路由 actor；**power-of-two-choices** 选副本 |
| `long_poll.py` | router↔controller 副本列表同步 |
| `autoscaling_state.py`/`gang_scheduling_autoscaling_policy.py` + 公共 `serve/autoscaling_policy.py` | 伸缩策略 |

> **澄清**：没有独立的"Serve v2 controller"产品——controller 始终是 `ServeController`；"v2 风格"工作指 HAProxy router + gRPC ingress。

---

## 6.7 构建系统与语言

- **C++ 构建：Bazel**（每目录 `BUILD.bazel`；仓库根 `MODULE.bazel`，module 模式）。
- **C++/Python 边界：Cython**（[`_raylet.pyx`](https://github.com/ray-project/ray/blob/master/python/ray/_raylet.pyx)），正迁移到 **pybind11**（[issue #46512](https://github.com/ray-project/ray/issues/46512)，降低构建痛感）。`pip install -e .` 的 Python-only 快速开发可跳过 C++ 重编。
- **线格式**：Plasma 用 **FlatBuffers**（`plasma.fbs`），RPC 用 **protobuf/gRPC**。

---

## 6.8 2024–2026 源码级演进

1. **Redis 解除默认依赖**（1.11）：GCS 默认内存；Redis 仅可选 FT 备份（[Redis in Ray](https://www.anyscale.com/blog/redis-in-ray-past-and-future)）；2024–25 让备份 KV **可插拔**（[#53115](https://github.com/ray-project/ray/issues/53115)）。
2. **Compiled Graph（beta）**：静态 DAG 编译，预分配 actor/buffer/通道，多 GPU LLM 推理/训练，报告 GPU 张量传输延迟降最多 **140×**（[docs](https://docs.ray.io/en/latest/ray-core/compiled-graph/ray-compiled-graph.html)、[Anyscale 公告](https://www.anyscale.com/blog/announcing-compiled-graphs)）；钩子 [`experimental_mutable_object_manager.h`](https://github.com/ray-project/ray/blob/master/src/ray/core_worker/experimental_mutable_object_manager.h)。
3. **Ray Direct Transport (RDT)**：RDMA/原生传输层，配合 Compiled Graph。
4. **task → lease 重命名**：`ClusterTaskManager`→`ClusterLeaseManager`、`LocalTaskManager`→`LocalLeaseManager`（调度代码挪到 `raylet/scheduling/`）。
5. **ray_syncer**：gRPC 节点状态同步取代 Redis-pubsub 心跳。
6. **Plasma 重构**：`IAllocator`/`IObjectStore`/`IObjectLifecycleManager` 接口拆分；`ClientMmapTableEntry`、`PlasmaStoreRunner` 为 Copyright 2025 新文件。
7. **Serve HAProxy router + gRPC ingress**：`_private/haproxy*.py`、`node_port_manager.py`、公共 `serve/grpc_util.py`。
8. **新 `python/ray/llm/` 与 `serve/llm/`**：一等公民 LLM 服务构件（目录已核验，内部结构 [verify]）。
9. **RLlib 新 API stack**：`/rllib/` 围绕 `RLModule`/`Learner`/`EnvRunner`/`ConnectorV2` 重组；**PyTorch-only（弃用 TF）**。
10. **Cython → pybind11 迁移**（[#46512](https://github.com/ray-project/ray/issues/46512)）。

---

## 6.9 易错路径纠正（常被误引）

- ❌ `src/ray/plasma/` → ✅ `src/ray/object_manager/plasma/`
- ❌ `src/ray/scheduling/` → ✅ `src/ray/raylet/scheduling/`
- ❌ `src/ray/raylet/raylet.h`、`cluster_task_manager.h`、`local_task_manager.h` → ✅ `node_manager.h`、`cluster_lease_manager.h`、`local_lease_manager.h`
- ❌ `python/ray/_private/remote_function.py` / `actor.py` → ✅ `python/ray/remote_function.py` / `actor.py`（顶层）
- ❌ `python/ray/serve/_private/deployment_graph.py` / `handle.py` / `autoscaling_policy.py` → ✅ `serve/dag.py` + `_private/deployment_node.py`；`serve/handle.py`（公共）；`serve/autoscaling_policy.py`（公共）

---

下一章 [Mini Demo](07-mini-demo) 用可运行代码验证 task/actor 调度与 lineage 重建。

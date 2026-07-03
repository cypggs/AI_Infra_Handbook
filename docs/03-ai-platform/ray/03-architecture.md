# 3. 架构设计：组件分层与控制面/数据面

> 本章画出 Ray 的进程模型与分层架构。内容以 [Ray v2 架构白皮书](https://docs.ray.io/en/latest/ray-contribute/whitepaper.html)（官方明确"取代学术论文"）为准。

---

## 3.1 集群与进程模型

一个 Ray 集群 = **1 个 head 节点 + N 个 worker 节点**（[集群关键概念](https://docs.ray.io/en/latest/cluster/key-concepts.html)）：

```
                ┌──────────────────────── HEAD NODE ────────────────────────┐
                │  GCS Server   Dashboard(:8265)   Autoscaler driver         │
                │  ray_syncer   Raylet   Plasma Store                        │
                └───────────────▲────────────────────────▲───────────────────┘
                                │ gRPC (ray_syncer 心跳/资源) │
        ┌───────────────────────┼──────────────────────────┼──────────────────┐
        │              WORKER NODE 1                WORKER NODE 2  ...        │
        │   Raylet  Plasma Store  Workers     Raylet  Plasma Store  Workers   │
        └─────────────────────────────────────────────────────────────────────┘
```

每个节点（head 与 worker）都跑：

| 进程 | 角色 | 关键职责 |
|---|---|---|
| **GCS Server**（仅 head） | 全局控制面 | 存 actor/job/placement-group/node/resource 元数据；调度协调；autoscaler 状态 |
| **Raylet**（每节点，C++） | 节点调度器 | 调度任务、管 worker 池、对象存储生命周期、溢写编排 |
| **Plasma Store**（每节点） | 数据面 | 共享内存对象存储（mmap `/dev/shm`） |
| **Dashboard Agent**（每节点） | 可观测 | 采集指标、日志，上报 head 的 Dashboard(:8265) |
| **Driver / Worker**（Python） | 用户代码 | Driver 是入口；Worker 执行 task/actor 方法；都内嵌 C++ **CoreWorker** |

> **Raylet 是 C++ 写的**（性能敏感的调度/对象传输），Python 侧通过 **Cython 桥 `_raylet.pyx`** 调用（正迁移到 pybind11，[issue #46512](https://github.com/ray-project/ray/issues/46512)）。

---

## 3.2 控制面 / 数据面

### 控制面（Control Plane）

```
Driver ──(提交 task/actor)──► CoreWorker(owner)
                                   │
                                   │ ① RequestWorkerLease (gRPC)
                                   ▼
                            Raylet(本地) ──spillback──► Raylet(远端)
                                   │                       │
                                   │ ② GCS 注册/查询 actor·job·PG·node
                                   ▼
                                 GCS ──(ray_syncer 每 100ms 广播资源视图)──► 所有 Raylet
```

- **任务不进 GCS**（所有权模型）：任务 spec 在 owner CoreWorker 里（`TaskManager::OwnedTasks`）。GCS 只存 actor/job/PG/node/resource + 任务**事件/状态**（供 State API/Dashboard，不驱动调度）。
- **GCS 资源广播每 100ms 一次**（`ray_syncer`，gRPC，取代旧的 Redis-pubsub 心跳）：GCS 从每节点 raylet 拉资源可用量、聚合、再广播。**最终一致**（某次查询未必反映精确快照）；每节点**自身**资源视图强一致。
- **ray_syncer**（[src/ray/ray_syncer/](https://github.com/ray-project/ray/tree/master/src/ray/ray_syncer)）是关键解耦件：把集群状态同步从 Redis 假设中解放出来，是 1.11 "Redisless by default" 得以实现的前提。

### 数据面（Data Plane）

```
Worker A ──写返回值──► Plasma Store A（本地 mmap）
                            │
        ObjectRef 在 owner 处建引用计数
                            │
Worker B ──ray.get(ref)──► owner 告知位置 ──► ObjectManager.Pull ──► chunk 传输 / 本地命中零拷贝
```

- **ObjectManager**（[src/ray/object_manager/](https://github.com/ray-project/ray/tree/master/src/ray/object_manager)）：分块 Push/Pull 传输，带 `PullManager`（拉取编排）与 `PushManager`（并发出站上限）。
- **OwnershipBasedObjectDirectory**：唯一的对象目录实现——位置索引基于**所有者 CoreWorker + pubsub**，**不集中存于 GCS**。
- **引用计数五元组**（白皮书 "Reference Counting"）：每个被拥有的对象维护
  1. 本地 Python 引用计数
  2. 已提交但未完成的任务数
  3. **borrower**（借走 ref 的 worker）
  4. nested（值里**包含**此 ref 的对象）
  5. lineage 计数
  
  对应 `ray memory` 标签：`LOCAL_REFERENCE` / `PINNED_IN_MEMORY` / `USED_BY_PENDING_TASK` / `CAPTURED_IN_OBJECT` / `ACTOR_HANDLE`。
- **Borrower 协议**：ref 逃出作用域（传给 task、存进别的对象、被返回）时，owner 把它加入本地计数；任务完成时 worker 汇报"哪些 ref 仍被借用"；borrower 形成递归树，**owner 只跟踪直接 borrower**。

---

## 3.3 对象存储分层（Plasma）

Plasma 不是单一类，而是一组协作组件（[src/ray/object_manager/plasma/](https://github.com/ray-project/ray/tree/master/src/ray/object_manager/plasma)）：

| 组件 | 职责 |
|---|---|
| `PlasmaStore`（单线程） | 对象存储主进程；创建/密封/删除对象；OOM 时回调溢写 |
| `ObjectStore` | 持有 `object_table_`（ObjectID → LocalObject）；`CreateObject`/`SealObject` |
| `ObjectLifecycleManager` | **引用计数**（`AddReference`/`RemoveReference`）；refcount 归 0 才可驱逐 |
| `EvictionPolicy`（LRU） | `RequireSpace` → `ChooseObjectsToEvict` |
| `PlasmaAllocator` | 从预 mmap 的 `/dev/shm`（或磁盘）分配；**`FallbackAllocate`** 在 OOM 时退到本地盘 mmap |
| `ClientMmapTableEntry` | 客户端 per-fd mmap 缓存（零拷贝） |
| `CreateRequestQueue` | OOM/溢写触发逻辑 |

### 主副本 vs 可驱逐副本

- **主副本（primary copy）**：由生产任务或 `ray.put` 创建的第一份 plasma 副本，被 raylet **pin**，**只要还有 ref 在作用域内就不会被 LRU 驱逐**。
- **可驱逐副本**：`ray.get`/参数拉取产生的副本，可被 LRU 驱逐。
- **兜底**：超大对象在内存放不下时，raylet 用 `FallbackAllocate` 把它 mmap 到**本地磁盘**；磁盘满 → `OutOfDiskError`。

### 主动溢写（Object Spilling）

冷对象溢写到外部存储（默认 `/tmp`，可配 S3/GCS，但 **S3 后端白皮书标为 experimental**）：

- **触发**：80% 容量时**主动**溢写（`object_spilling_threshold=0.8`，白皮书 "Handling OOM"），不止 OOM 时才溢。
- **执行任务参数上限 70%**：所有在途任务的参数总大小封顶对象存储 70%，留 30% 给任一任务写返回值。
- **对象融合**：< 100MB 的对象**融合进单文件**（避免 inode 耗尽），24 字节头 `addr_len|metadata_len|buf_len`，URL `…/ray_spilled_objects_<nodeid>/<uuid>-multi-<count>?offset=N&size=M`。
- **三层**：检测（`CreateRequestQueue`）→ 编排（raylet 的 `LocalObjectManager`，**真正的"溢写管理器"**，状态机 `Pinned→PendingSpill→Spilled`）→ 执行（Python **IO worker 进程**，spill/restore 两个池，调用 `external_storage.py` 后端：`FileSystemStorage` 默认、`ExternalStorageSmartOpenImpl` 走 S3/GCS）。

---

## 3.4 GCS（Global Control Store）

GCS 是 head 节点上的单一 `GcsServer` actor（[src/ray/gcs/](https://github.com/ray-project/ray/tree/master/src/ray/gcs)），托管控制面状态。关键管理者：

- `gcs_node_manager` / `gcs_job_manager` / `gcs_resource_manager` / `gcs_worker_manager` / `gcs_function_manager`
- `gcs_placement_group(_manager|_scheduler)` —— placement group 两阶段提交
- `gcs_autoscaler_state_manager` / `gcs_health_check_manager`
- `gcs_kv_manager` —— 通用 KV（`ray.kv`、Serve checkpoint）
- `gcs_task_manager` —— **只存任务事件/状态供 State API/Dashboard**，不驱动调度（所有权模型）

### GCS 容错（关键工程约束）

> **默认 GCS 不可容错**：状态全在内存，GCS 挂 = **整个集群挂**。（[GCS FT 文档](https://docs.ray.io/en/latest/ray-core/fault_tolerance/gcs.html) 原文）

- 自 **1.11** 起 GCS 默认存自己的内存结构（**Redis 不再是默认运行时依赖**，[Redis in Ray](https://www.anyscale.com/blog/redis-in-ray-past-and-future)）。
- **可选容错**：外接 **HA Redis**（`RAY_REDIS_ADDRESS`）做**持久备份**，GCS 重启时从中恢复。
- **恢复期间不可用**：actor/PG 的创建/删除/重建、资源管理、worker 节点注册、worker 进程创建。**仍可用**：运行中的 task/actor 继续活、已存在对象仍可访问。
- raylet 重连超时 **60s**（`RAY_gcs_rpc_server_reconnect_timeout_s`）。
- **官方警告**：*"GCS 容错（外接 Redis）只在 KubeRay 上用于 Ray Serve 容错时官方支持；其他情况自担风险。"*
- KubeRay **v1.3.0** 把容错配置收敛为 `spec.gcsFaultToleranceOptions`（`redisAddress`/`redisPassword`），注意多集群 Redis key 冲突（[kuberay#2694](https://github.com/ray-project/ray/issues/2694)）。

---

## 3.5 全栈一张图

```
┌─────────────────────────── 用户 Python ───────────────────────────┐
│  @ray.remote fn/class   ray.get/put/wait   ray.init   serve.run   │
└───────────────────────────────┬───────────────────────────────────┘
                          Cython 桥 _raylet.pyx
┌───────────────────────────────▼───────────────────────────────────┐
│              CoreWorker (C++，每 driver/worker 内嵌)               │
│  TaskManager(OwnedTasks)  ReferenceCounter(所有权表)               │
│  ObjectRecoveryManager  LeasePolicy  FutureResolver                │
└───┬───────────────────────────────────────────────┬───────────────┘
    │ RequestWorkerLease (gRPC)                       │ 对象读/写
    ▼                                                 ▼
┌─────────────────────────────┐               ┌─────────────────────┐
│  Raylet (C++, 每节点)        │               │  Plasma Store       │
│  ClusterLeaseManager         │  pin/溢写编排  │  ObjectStore        │
│  LocalLeaseManager           │◄─────────────►│  LRU/FallbackAlloc  │
│  WorkerPool(含 IO 池)        │               │  ClientMmapTable    │
│  LocalObjectManager(溢写)    │               └──────────▲──────────┘
└───────┬──────────────────────┘                          │ chunk Push/Pull
        │ ray_syncer (gRPC, 100ms)                        │ ObjectManager
        ▼                                                 │
┌──────────────────────────────────────────────────────────┴──────────┐
│   GCS (head): node/job/resource/worker/PG/kv/autoscaler + 任务事件    │
│   ray_syncer 广播 ◄──── 所有 Raylet 资源视图                          │
└──────────────────────────────────────────────────────────────────────┘
```

---

下一章 [执行模型](04-execution-model) 把这张图变成"一个请求的完整生命周期"。

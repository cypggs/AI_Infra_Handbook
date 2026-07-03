# 2. 核心思想：三大原语 + 所有权模型

> 本章拆解 Ray 的设计内核：task / actor / object 三原语、动态任务图、**所有权（ownership）+ 溢回（spillback）调度**如何替代 OSDI'18 论文的全局调度器，以及它与其他系统的边界。

---

## 2.1 三大原语

Ray 把"分布式 Python"浓缩为三个一等公民：

### 原语一：Task（无状态远程函数）

```python
@ray.remote
def square(x):
    return x * x

ref = square.remote(3)   # 立即返回 ObjectRef，不阻塞
print(ray.get(ref))      # 10 —— 此时才真正取回
```

- `@ray.remote` 把普通函数包成**远程函数**；`.remote(...)` **立即返回 `ObjectRef`（future）**，调用方不阻塞。
- 默认资源：**1 CPU**。可声明 `@ray.remote(num_cpus=2, num_gpus=1)`。
- **无状态 + 可重放**：任务失败可被重新调度执行（默认非 actor 任务重试 3 次）。
- 支持生成器返回（`num_returns="streaming"`），用于流式大输出。

### 原语二：Actor（有状态长进程）

```python
@ray.remote
class Counter:
    def __init__(self):
        self.n = 0
    def inc(self):
        self.n += 1
        return self.n

c = Counter.remote()      # 创建 actor（一个独立进程，状态常驻）
print(ray.get(c.inc.remote()))   # 1
print(ray.get(c.inc.remote()))   # 2  —— 状态被保持
```

- `@ray.remote` 作用在**类**上 → actor。actor 是一个**长寿命进程**，方法调用串行（默认）作用于其内部状态。
- 默认：**0 CPU 用于执行、1 CPU 用于放置**（所以 `--num-cpus=0` 的节点会拒绝默认 actor——必须显式声明资源）。
- 可配 `max_restarts`（actor 死后重启几次）、`max_task_retries`（在途方法重试几次）、`max_concurrency`（并发度，默认 **1**，见 [§2.5 坑](#)）。

> **为什么需要 actor？** 这是 Ray 区别于 Spark 的关键。RL 需要"一个仿真器进程、一个环境实例、一个策略服务"这种**可寻址、可变、长寿命**的 worker——纯无状态 task 表达不了。actor 补上了这一刀。

### 原语三：Object（共享内存对象 + ObjectRef）

```python
ref = ray.put(big_array)      # 显式放进 Plasma 对象存储
# 或隐式：task 返回值自动落 Plasma
```

- 每个 `ObjectRef` 指向 **Plasma 对象存储**里的一份对象。Plasma 基于 **Apache Arrow**，**同节点 worker 间零拷贝读**（mmap `/dev/shm`）。
- 大小规则（源码 `ray_constants.py`）：**可用 RAM 的 30%**（`DEFAULT_OBJECT_STORE_MEMORY_PROPORTION=0.30`），Linux/云 **200GB 硬上限**（`DEFAULT_OBJECT_STORE_MAX_MEMORY_BYTES`），**macOS 仅 2GB**（`MAC_DEGRADED_PERF_MMAP_SIZE_LIMIT`，避免性能退化），最小 **75MB**。Linux `/dev/shm`：`min(200GB, 0.95×/dev/shm)`。
- **小对象（≤100 KiB）走 in-band**：`max_direct_call_object_size = 100 KiB`（`ray_config_def.h`），直接内联在任务回复里、存在 **owner 进程内对象存储**，**owner 死则丢失、不可重建**。每个 task 的 RPC 内联上限 10MB（`task_rpc_inlined_bytes_limit`）。

---

## 2.2 动态任务图（Dynamic Task Graph）

Ray 程序在运行时构建一张**动态有向图**：

- 节点 = task / actor 方法调用；边 = 数据依赖（ObjectRef）。
- 图是**运行时生成/修改**的（例如根据 task 返回值决定下一步调谁），不是像 Spark 那样静态定义后再执行。

```python
@ray.remote
def step(x): return x + 1

# fan-out：100 个任务，依赖同一个 ref
refs = [step.remote(ref) for _ in range(100)]
results = ray.get(refs)
```

这与 Spark 的"先 build lineage 再 materialize action"形成对照——Ray 的图可以**边跑边长**，这是 RL/Agent 这种"下一步依赖上一步结果"工作负载的关键。

---

## 2.3 所有权模型：替代论文里的全局调度器

这是理解**现代 Ray**（v2 白皮书）最关键的概念，也是它与 OSDI'18 论文最大的架构差异。

### 论文里的旧设计（2018）

- **全局调度器**（global scheduler，在 GCS 内）+ 每节点**本地调度器**（raylet）。
- GCS 持有**任务表 + lineage 表**，集中调度。

**问题**：GCS 成为吞吐与延迟瓶颈，不符合"亚毫秒派发、百万任务/秒"目标。

### 现代设计：所有权（Ownership）

> 核心转变：**"谁提交任务，谁拥有它"**。任务不再进 GCS，而是由**提交它的 worker（owner）**持有其 spec、返回值引用与 lineage。

- 每个任务/对象有一个**唯一 owner**（提交它的 CoreWorker）。owner 维护该任务的状态、返回值 `ObjectRef` 的引用计数、以及 lineage。
- **所有权不可转移**：`ObjectRef` 终生与 owner 命运绑定——**owner 死，即使物理副本还在，`ray.get` 也会抛 `OwnerDiedError`**。
- 量化（白皮书）：任务提交延迟 **~1 RTT、<200 µs**；单客户端吞吐 **~10k tasks/s**，集群线性到百万级；每个 `ObjectRef` 元数据约 **3 KB**（`CALLER_MEMORY_USAGE_PER_OBJECT_REF=3000`）。
- **Lineage 也不再在 GCS**：每个 worker 自缓存 lineage，上限 `max_lineage_bytes = 1 GiB`。

### 溢回调度（Spillback）

没有全局调度器后，任务如何找到合适的节点？靠**两跳溢回**：

```
owner 的本地 raylet A  →  (A 拒绝本地放行，返回一个更合适的远端 raylet B 的地址)  →  owner 直接向 B 请求 worker
```

- owner 优先选**本地 raylet**（默认）、或**数据局部性最优的节点**（参数对象最多的节点）、或**node affinity** 指定的节点。
- 若该 raylet 当前资源不足，它**不会排队死等**，而是返回一个**溢回提示**——告诉 owner"去 raylet B 试试"。这就是旧"转发给全局调度器"的现代等价物。

### 默认调度策略：HYBRID（不是 SPREAD）

常见误解：Ray 默认把任务摊开（spread）。**错。默认是 HYBRID**（白皮书 "Default Hybrid Policy"）：

1. 在 **top-k 节点组**（默认 **20% 节点**）内，**先偏向已有本任务/actor 的节点**（为局部性打包）；
2. 再偏向**低利用率节点**（负载均衡）；
3. top-k 组内**随机选**。

切换阈值 `RAY_scheduler_spread_threshold = 0.5`：关键资源利用率 < 50% 时倾向打包（局部性），> 50% 时倾向摊开（负载均衡）。([调度文档](https://docs.ray.io/en/latest/ray-core/scheduling/index.html))

> **工程含义**：默认 HYBRID 对"局部性 + 资源均衡"做了平衡；但**对冷启动/缩容不友好**（打包会让部分节点满、部分空）。要友好的缩容，用 placement group 的 `PACK` 策略把活儿压到少数节点（见 [第 8 章 §8.x](08-production-practice)）。

---

## 2.4 资源模型

| 资源 | 粒度 | 说明 |
|---|---|---|
| CPU | 固定点（`kResourceUnitScaling=10000`） | 默认 task=1、actor=0(执行)/1(放置) |
| GPU | 整数 | 分配 GPU **自动设 `CUDA_VISIBLE_DEVICES`** |
| 内存 | 仅准入控制 | **运行时不强制**——超了靠对象存储溢写/killer（见下） |
| 自定义 | 任意键值 | `"GPU": 2`、`"memory": 1e9`、`"node:...": 1` |

- **内存是准入而非执行强制**：Ray 用内存配额做调度准入，但**不在运行时限制进程内存**。这是对象存储 OOM 与 `ray_memory_manager_worker_eviction_total` killer 存在的根本原因（[内存管理文档](https://docs.ray.io/en/latest/ray-core/scheduling/memory-management.html)）。

### Placement Group（放置组）

需要"一组资源原子地放在一起"时（如多 GPU all-reduce），用 placement group：

- **原子创建**：bundles 全部就位才算成功；**任一 bundle 放不下则全部不占资源**（all-or-nothing）。
- **bundle 必须能装进单节点**（不跨节点切分一个 bundle）。
- 四策略：`PACK`（默认，压少数节点）、`STRICT_PACK`（严格同节点）、`SPREAD`（散开）、`STRICT_SPREAD`（每节点最多一个）。
- 创建走 **GCS 协调的两阶段提交**（跨 raylet 预留）。

---

## 2.5 与相邻系统的边界

| 系统 | 模型 | 为何不是 Ray |
|---|---|---|
| **Spark** | 批/微批 RDD、静态 lineage | 无原生 actor；粗粒度；无 sub-ms 延迟；服务是附加（Structured Streaming）非统一 |
| **Dask** | 动态任务图 + pandas/numpy 扩展 | 图相似，但**无原生 actor**、无 Serve/RL/Tune 库 |
| **MPI / PyTorch DDP** | 静态 SPMD，训练专用 | 紧耦合训练强，但无动态图、无服务、无 RL 循环、无长作业容错。**Ray 与 DDP 互补**：Ray Train 包装 DDP/FSDP/DeepSpeed |
| **Kubernetes Jobs** | 容器编排 | **无 ML 语义**：无共享对象存储、无任务图、无 actor 生命周期。KubeRay 把 Ray 跑在 K8s 上 |
| **Modal** | 无服务器 Python（专有云） | 不同抽象（云上函数），厂商锁定；无开源集群运行时 |

Ray 的独特赌注：**一个底座跑训练 + 服务 + 数据 + RL，全部是普通 Python**。

---

## 2.6 容错思想（概览，细节见 [第 8 章](08-production-practice)）

Ray 的容错分五层：**任务、actor、对象、节点、GCS**。核心机制是 **lineage 重建**：

- 对象的 lineage 存在 owner worker；对象丢失时，沿 lineage 重新执行生成它的任务。
- **重建前提**：对象必须由 task 生成、owner 存活、任务可重放。
- **关键例外**：
  - **`ray.put` 的对象不可重建**——它与 owner 命运绑定，owner 死 → `OwnerDiedError`。
  - **小对象（≤100 KiB）随 owner 而亡**（存在 owner 进程内，无物理副本）。
  - 默认**非 actor 任务重试 3 次、actor 任务不可重试**（除非设 `max_task_retries` + `max_restarts`）。
  - actor 任务默认**不可重建**（actor 有状态，重放可能重复副作用）。

这把"哪些可丢、哪些不可丢"讲得非常清楚——是设计分布式 AI 系统时值得借鉴的语义分层。

---

下一章 [架构设计](03-architecture) 画出 Ray 的组件分层与控制面/数据面。

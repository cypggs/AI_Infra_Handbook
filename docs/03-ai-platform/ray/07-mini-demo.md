# 7. 动手：Ray Core 迷你模拟器

> 本章提供一个纯 CPU、单线程、确定性的 Ray Core 迷你实现 `ray-mini`，用于把前几章的抽象机制“跑”一遍。它覆盖：所有权 + ObjectRef 解析、Hybrid 调度、Plasma 式对象存储、血缘重建、自动扩缩容。

---

## 7.1 设计目标与边界

`ray-mini` 不是分布式运行时，而是**可观测机制的教学模型**：

| 机制 | 教学要点 | 与真实 Ray 的差异 |
|---|---|---|
| 所有权 / ObjectRef | `ray.put` 与内联对象随 owner 消亡；任务产出的对象可通过血缘重建 | 真实 CoreWorker 每张表更复杂（borrower、嵌套对象等） |
| Hybrid 调度 | 本地性优先 → top-k → spread threshold | 真实调度是分布式 spillback，非全局分数 |
| 对象存储 | primary / evictable / spilled 三层 + 80% 主动溢写 | 真实 Plasma 按字节管理，有 IO worker 池 |
| 血缘重建 | 任务规格保存在 owner（driver），worker 失效后重放任务 | 真实 Ray 同时依赖 GCS 元数据与引用计数 |
| 自动扩缩容 | pending CPU demand > 可执行空闲 CPU 时扩容；idle timeout 缩容 | 真实 Autoscaler 监控 resource demand、node provider、镜像拉取等 |

---

## 7.2 目录结构

```
docs/03-ai-platform/ray/mini-demo/
├── pyproject.toml
├── README.md
├── ray_mini/
│   ├── __init__.py
│   ├── model.py          # Config / ObjectRef / Task / SimResult / 异常
│   ├── cluster.py        # Node / Cluster 资源会计
│   ├── object_store.py   # 每节点 Plasma 式存储 + 引用计数 + 溢写
│   ├── scheduler.py      # Hybrid 调度策略
│   ├── runtime.py        # MiniRay：submit / get / put / actor / fail_node
│   ├── autoscaler.py     # 需求驱动扩缩容
│   └── demo.py           # 4 个演示场景
└── tests/
    ├── test_model.py
    ├── test_object_store.py
    ├── test_scheduler.py
    ├── test_runtime.py
    ├── test_autoscaler.py
    └── test_demo.py
```

---

## 7.3 运行方式

```bash
cd docs/03-ai-platform/ray/mini-demo
pip install -e ".[dev]"
pytest tests/ -v          # 25 个测试
python -m ray_mini.demo   # 交互式场景输出
```

---

## 7.4 关键代码片段

### 7.4.1 ObjectRef：可重建性由 owner + 任务血缘决定

```python
@dataclass
class ObjectRef:
    id: int
    size: int
    owner_node: int
    generating_task: Optional["Task"] = None
    small_inline: bool = False

    @property
    def is_reconstructable(self) -> bool:
        return self.generating_task is not None and not self.small_inline
```

- `ray.put` 产生的对象 `generating_task=None`，不可重建。
- 大小 ≤ 100 KiB 的返回值被标记为 `small_inline`，随 owner 消亡（`OwnerDiedError`）。
- 只有任务产生且非内联的对象才具备血缘重建资格。

### 7.4.2 对象存储：primary / evictable / spilled

```python
class ObjectStore:
    def put_primary(self, ref: ObjectRef) -> None:
        self.primary[ref.id] = ref.size
        self.used += ref.size
        self.refcount[ref.id] = self.refcount.get(ref.id, 0) + 1
        self._maybe_spill()

    def release(self, ref_id: int) -> None:
        if self.refcount.get(ref_id, 0) <= 0:
            return
        self.refcount[ref_id] -= 1
        if self.refcount[ref_id] == 0:
            if ref_id in self.primary:
                size = self.primary.pop(ref_id)
                self.evictable[ref_id] = size
            del self.refcount[ref_id]

    def _maybe_spill(self) -> None:
        while self.used > self.capacity * self.spill_threshold and self.evictable:
            ref_id, size = self.evictable.popitem(last=False)  # LRU
            self.used -= size
            self.spilled[ref_id] = size
            self.spill_count += 1
```

`primary` 被引用计数钉住；释放后降级为 `evictable`；超过 `spill_threshold`（默认 80%）时把 LRU evictable 推入 `spilled`。

### 7.4.3 Hybrid 调度：本地性 → top-k → spread

```python
class HybridScheduler:
    def choose_node(self, cluster, task, arg_locations, exclude_nodes=None):
        candidates = [n for n in cluster.nodes.values()
                      if n.id not in exclude_nodes and n.cpus_free >= task.num_cpus]

        def locality_score(node_id):
            return sum(1 for arg in task.arg_refs
                       if arg_locations.get(arg.id) == node_id)

        ranked = sorted(candidates,
                        key=lambda n: (-locality_score(n.id), utilization(n.id), n.id))
        k = max(1, int(len(ranked) * self.top_k_fraction))
        top_k = ranked[:k]

        best = top_k[0]
        if utilization(best.id) > self.spread_threshold:
            return min(top_k, key=lambda n: (utilization(n.id), n.id)).id
        return best.id
```

与 Ray 默认策略对应：先按 argument 位置做本地性排序，在 top-k（约 20%）节点里，若最优节点利用率已超 `spread_threshold` 则切换为摊平。

### 7.4.4 运行时的关键路径

```python
class MiniRay:
    def submit(self, fn_name, arg_refs=(), cost=1, result_size=1, num_cpus=1):
        task = Task(...)
        ref = self._new_ref(result_size, generating_task=task,
                            small_inline=(result_size <= INLINE_OBJECT_SIZE_BYTES))
        self._task_result_ref[task.id] = ref.id
        self.cluster.nodes[self._driver_node].store.add_ref(ref.id)
        self._pending.append(task)
        return ref

    def get(self, ref):
        # 1. 若对象在 worker 上，拉取 evictable 副本到 driver
        # 2. 若对象丢失且可重建，触发 _reconstruct 重放生成任务
        # 3. 若 owner 死亡且不可重建，抛 OwnerDiedError
```

所有 ObjectRef 的 owner 被简化为 driver 节点；worker 节点只负责任务执行与对象存储。这样可以用一次显式的 `fail_node(worker)` 展示“worker 挂掉但 owner 还在 → 重建成功”。

### 7.4.5 自动扩缩容

```python
class Autoscaler:
    def _scale_up(self, ray, cluster):
        pending_cpus = sum(t.num_cpus for t in ray._pending)
        executable_free = sum(n.cpus_free for n in cluster.nodes.values()
                              if n.id != ray._driver_node)
        needed = max(0, pending_cpus - executable_free)
        while needed > 0 and len(cluster.nodes) < self.max_nodes:
            ray.scale_up(self._next_node_id(cluster))
            needed -= ray.config.cpus_per_node
```

- 只把 **worker 节点**计入可执行容量；head/driver 节点不跑任务。
- pending demand 超过可执行空闲 CPU 时扩容。
- 空闲超过 `idle_timeout_ticks` 且存在 pending demand 已满足时缩容。

---

## 7.5 四个演示场景

```bash
python -m ray_mini.demo
```

### 场景 1：所有权 + 血缘重建

```python
dataset = ray.put(size=10)
intermediate = ray.submit("preprocess", arg_refs=(dataset,), cost=2, result_size=200_000)
final = ray.submit("train", arg_refs=(intermediate,), cost=3, result_size=200_000)
ray.run_until_done()
ray.fail_node(ray._arg_locations[intermediate.id])  # 模拟 worker 失效
ray.get(final)  # 触发 intermediate 与 final 的重建
```

输出示例：

```
failing worker node 1 which holds intermediate primary copy
final object resolved after reconstruction
tasks reconstructed: 2
```

### 场景 2：Hybrid 调度

先让 `produce` 任务在 worker 1 上生成对象 `a`，再提交 6 个读取 `a` 的任务：

```
object `a` produced on worker node 1
scheduling choices (task_id -> node_id):
  task   0 -> node 1 *   # 本地性打包
  task   1 -> node 1 *
  task   2 -> node 1 *
  task   3 -> node 2     # 超过 spread_threshold 后摊平
  task   4 -> node 3
  task   5 -> node 2
  task   6 -> node 3
```

### 场景 3：自动扩缩容

8 个单 CPU 任务在 1 个 2-CPU 节点上无法同时调度，Autoscaler 自动扩容到 4 个节点；任务完成后缩回。

```
initial nodes: 1
final nodes: 3
nodes added: 3, nodes removed: 1
```

### 场景 4：对象存储溢写

4 个大小为 6 的对象被 `get()` 到容量为 20 的 driver 存储：24 > 20 × 0.8，触发 LRU 溢写。

```
objects spilled: 2, objects evicted: 0
```

---

## 7.6 测试结果

```
============================== 25 passed in 0.02s ==============================
```

覆盖：
- ObjectRef 可重建性判定
- 对象存储的 primary / evictable / spilled 转换与 LRU
- Hybrid 调度的本地性、spread threshold、无合适节点返回 None
- `ray.get` / `ray.put` / 任务依赖 / 血缘重建 / owner 死亡
- Autoscaler 扩缩容与 head 节点保护
- 4 个端到端 demo 场景

---

## 7.7 与生产 Ray 的差异速查

| 维度 | ray-mini | 生产 Ray |
|---|---|---|
| 执行模型 | 单线程同步 tick | 多进程异步 RPC |
| 网络 | 内存拷贝 | gRPC / shared memory / RDMA |
| 对象容量 | 抽象“单位” | 字节（默认 30% RAM，Linux 上限 200 GB） |
| 调度 | 全局分数函数 | 分布式 spillback + 资源反压 |
| 所有权 | driver 统一拥有 | 每个 CoreWorker 独立拥有 |
| Actor | 状态占位 | 完整 worker 池、方法调用、并发模型 |
| 容错检测 | 显式 `fail_node()` | 心跳、GCS 失效检测、lease 超时 |

---

## 7.8 课后练习

1. 修改 `Config.spread_threshold` 与 `top_k_fraction`，观察 Demo 2 的调度选择如何变化。
2. 在 Demo 1 中把 `ray.put` 换成一个任务产生的对象，再 fail 该 worker，看看是否仍能重建。
3. 把 `object_store_capacity` 调小，观察溢写与驱逐的触发顺序。
4. 给 Autoscaler 增加“预热时间”：新节点加入后 N 个 tick 内不可被缩容，避免抖动。

---

## 7.9 延伸阅读

- 本章代码：`docs/03-ai-platform/ray/mini-demo/`
- Ray 真实源码：`src/ray/core_worker/`、`src/ray/raylet/scheduling/`、`src/ray/object_manager/`
- 回读：第 2 章核心思想、第 3 章架构、第 4 章执行模型、第 6 章源码分析

# 8. 企业生产实践

> 本章把 Ray 从“本地 `ray.init()`”推到真实生产环境：部署形态、资源调优、容错配置、可观测性、库的选择与典型踩坑。所有参数均来自 Ray 官方文档/配置；经验数据来自公开用户案例与 release notes。

---

## 8.1 三种典型部署形态

| 形态 | 适用场景 | 关键组件 | 伸缩方式 |
|---|---|---|---|
| **本地 / 单节点** | 开发、调试、CI 小测试 | `ray.init()`、本地 raylet + plasma | 手动 |
| **On-premise / VM 集群** | 已有机器、私有云 | `ray start --head` + `ray start --address=...` | Ray Autoscaler |
| **Kubernetes（KubeRay）** | 云原生生产 | KubeRay Operator、`RayCluster` CR、`RayJob`/`RayService` | HPA / cluster autoscaler + KubeRay |

### 8.1.1 本地开发

```python
import ray
ray.init()  # 自动启动本地 raylet、plasma、调度器
```

注意点：
- macOS 上 object store 默认上限 **2 GB**；Linux 上限 **200 GB** 或 30% RAM。
- 本地调试时 `ray.get` 容易把 future 列表全部展开导致内存爆炸；优先用 `ray.wait` + 流式消费。

### 8.1.2 VM 集群

Head 节点：

```bash
ray start --head --port=6379 --dashboard-host=0.0.0.0
```

Worker 节点：

```bash
ray start --address="<head-ip>:6379" --num-cpus=16 --num-gpus=2
```

带自动扩缩容的 cluster config（YAML）：

```yaml
provider:
  type: aws  # 或 gcp/azure/onprem
  region: us-west-2
available_node_types:
  ray.head.default:
    resources: {CPU: 8}
    node_config: {...}
  ray.worker.default:
    min_workers: 1
    max_workers: 10
    resources: {CPU: 16, GPU: 1}
    node_config: {...}
```

### 8.1.3 KubeRay（生产推荐）

```yaml
apiVersion: ray.io/v1
kind: RayCluster
metadata: {name: example-cluster}
spec:
  headGroupSpec:
    rayStartParams:
      dashboard-host: "0.0.0.0"
    template:
      spec:
        containers:
        - name: ray-head
          image: rayproject/ray:2.55.1-py310
          resources: {limits: {cpu: "8", memory: "32Gi"}}
  workerGroupSpecs:
  - replicas: 2
    minReplicas: 1
    maxReplicas: 10
    rayStartParams: {}
    template:
      spec:
        containers:
        - name: ray-worker
          image: rayproject/ray:2.55.1-py310-gpu
          resources: {limits: {cpu: "16", memory: "128Gi", nvidia.com/gpu: "1"}}
```

- **RayJob**：把作业作为 CR 提交，支持 runtime env、失败重试。
- **RayService**：Ray Serve 的声明式部署，支持滚动升级、多副本、流量切分。
- **FT**：GCS FT 仅在 KubeRay + Redis 场景下被官方支持（Ray Serve 的故障转移）。

---

## 8.2 资源调优

### 8.2.1 Object Store

Ray 的 object store 默认占用 **min(max(30% RAM, 75 MB), 200 GB on Linux / 2 GB on macOS)**。关键环境变量与启动参数：

| 参数 | 含义 | 典型生产设置 |
|---|---|---|
| `--object-store-memory` | 显式指定 plasma 大小 | 根据 workload 数据量，留出 20–30% 余量 |
| `RAY_object_spilling_threshold` | 主动溢写阈值 | 默认 0.8（80%）；大对象/高吞吐可略降 |
| `RAY_object_store_full_max_retries` | OOM 前重试次数 | 默认 6；纯内存型 workload 可调低以快速失败 |
| `RAY_max_direct_call_object_size` | 内联对象大小阈值 | 默认 100 KiB；一般不改 |

生产建议：
- 不要把 object store 当作持久存储；大于内存的数据集应使用 **Ray Data**（流式分块）或外部存储（S3/Cloud Storage + Parquet）。
- 观察 Dashboard 的 **Object Store Memory** 面板；若持续触顶，优先增大节点内存或开启 spilling 到本地 SSD/云盘。
- Spilling 路径默认在 `/tmp/ray/session_*/spills`；生产应挂高速本地盘并定期清理。

### 8.2.2 调度

默认策略是 **HYBRID**（`--scheduler=DEFAULT` 或留空），行为由 `spread_threshold` 控制：

```bash
# 0.0 = 完全摊平；1.0 = 完全打包
ray start --head --scheduler=DEFAULT --spread-threshold=0.5
```

常见场景：
- **GPU 训练**：希望任务/actor 集中在少数节点以利用 NVLink → 用 `PACK` 或降低 `spread_threshold`。
- **推理服务**：希望副本均匀分布以提高可用性 → 用 `SPREAD` 或提高 `spread_threshold`。
- **数据并行训练**：配合 `PlacementGroup` 的 `STRICT_SPREAD` 让每个 worker 各占一台机器。

### 8.2.3 Actor 资源

默认 actor 调度占用 **1 CPU 用于调度、0 CPU 用于执行**，这会导致资源 Accounting 混乱。生产代码务必显式声明：

```python
@ray.remote(num_cpus=2, num_gpus=1)
class MyActor:
    ...
```

异步 actor 提高并发：

```python
@ray.remote(num_cpus=1, max_concurrency=10)
class AsyncActor:
    async def handle(self, req):
        ...
```

---

## 8.3 容错配置

### 8.3.1 默认行为

| 对象/调用 | 默认重试 | 说明 |
|---|---|---|
| 普通 task | `max_retries=3` | 进程崩溃/节点失败触发 |
| Actor | `max_restarts=0`, `max_task_retries=0` | 默认不重启；显式开启 |
| `ray.put` 对象 | 不可重建 | 与 owner fate-share |
| 小内联对象 | 不可重建 | 与 owner fate-share |
| 任务生成的普通对象 | 可重建 | 依赖 owner 存活 |

### 8.3.2 推荐配置

**数据/训练任务**：

```python
@ray.remote(max_retries=5, retry_exceptions=[ValueError])
def robust_task(...):
    ...
```

**有状态 Actor（如 model replica）**：

```python
@ray.remote(max_restarts=3, max_task_retries=3)
class ModelReplica:
    def __init__(self):
        self.model = load_model()  # 重启后重新加载
```

> Actor 重启会丢失内存状态；状态应外置到 Redis/DynamoDB/RDBMS 或从 checkpoint 恢复。

### 8.3.3 GCS 高可用

- 默认 GCS 是**内存存储**（自 Ray 1.11）。
- 可选 Redis 后端持久化，但官方**仅在 KubeRay + Ray Serve FT 场景下支持**。
- 若把 actor/task metadata 大量依赖 GCS，Redis 会成为瓶颈；现代 Ray 已尽量把任务规格下放到 CoreWorker（ownership 模型）。

---

## 8.4 可观测性

### 8.4.1 Ray Dashboard

默认在 head 节点 `8265` 端口。关键视图：

- **Cluster**：节点资源、actor/task 分布、object store 使用。
- **Metrics**：Grafana/Prometheus 集成，包含 `ray_tasks`、`ray_actors`、`ray_object_store_memory`、`ray_scheduler_*`。
- **Jobs**：提交的作业列表与日志。
- **Serve**：部署、副本、QPS、延迟。

### 8.4.2 关键 Prometheus 指标

```promql
# task 排队时间
ray_task_queued_time_ms_bucket

# object store 内存
ray_object_store_memory

# actor 内存
ray_memory_manager_worker_eviction_total

# scheduler 等待资源
ray_scheduler_unscheduleable_tasks

# autoscaler 决策
ray_autoscaler_pending_nodes
ray_autoscaler_failed_create_nodes
```

### 8.4.3 日志与追踪

- `RAY_LOG_TO_STDERR=1` 可让组件日志输出到 stderr，便于 K8s 日志收集。
- Ray 2.x 集成 OpenTelemetry；Serve/Train 支持分布式 tracing。

---

## 8.5 库级别的生产选择

| 库 | 成熟版本 | 典型生产场景 | 注意 |
|---|---|---|---|
| Ray Core | 稳定 | 自定义分布式 Python、Actor 池 | 需自己处理容错与扩缩容 |
| Ray Serve | 稳定 | 在线推理、模型服务 | 用 `RayService` + 多副本；注意 gRPC/HTTP 并发 |
| Ray Serve LLM | 较新 | LLM serving（vLLM 后端） | 2024–2025 快速迭代；需紧跟版本 |
| Ray Data | GA 2.10 | ETL、批量推理、数据集预处理 | 优先于手写 task 做大数据流 |
| Ray Train | GA 2.7 | 分布式训练（PyTorch/TF/Horovod/XGBoost） | Ray Train v2 默认自 2.51 |
| Ray Tune | 稳定 | 超参搜索 | 与 Train 配合；注意 checkpoint 存储 |
| RLlib | 新 API stack | 强化学习 | 仅 PyTorch；旧 API 逐步弃用 |
| Compiled Graph | beta | 静态 DAG 高性能执行 | API 仍在演进 |

### 8.5.1 Ray Serve 生产要点

```python
@serve.deployment(
    num_replicas=4,
    autoscaling_config={"min_replicas": 1, "max_replicas": 20, "target_num_ongoing_requests_per_replica": 5},
    ray_actor_options={"num_cpus": 2, "num_gpus": 0.25},
)
class MyModel:
    ...
```

- 使用 `RayService` CR 做声明式部署与滚动升级。
- 长请求/流式响应用 `DeploymentHandle.options(stream=True)`。
- 2.55 新增 queue-based autoscaling for async inference 与 gang scheduling across deployments。

### 8.5.2 Ray Train/Data 生产要点

- 用 `ScalingConfig` 声明资源；`label_selector`（2.53+）可控制 worker 放置。
- Checkpoint 写到共享存储（S3/GCS/Cloud Storage），不要用本地盘。
- Ray Data 的 V2 autoscaler（`RAY_DATA_CLUSTER_AUTOSCALER=V2`）在 2.53 引入，生产建议开启。

---

## 8.6 常见生产踩坑

### 8.6.1 Object Store OOM

现象：任务报 `ObjectStoreFullError` 或 `OutOfMemoryError`。

排查：
1. Dashboard 查看 object store 曲线是否触顶。
2. 检查是否有 ObjectRef 被无限持有（循环中未释放）。
3. 大数据集改用 Ray Data 流式处理。
4. 增大 `--object-store-memory` 或启用 spilling 到 SSD。

### 8.6.2 调度不均 / 资源碎片

现象：集群有空闲 GPU 但任务排队。

排查：
1. 检查是否有 actor/task 声明了 `num_gpus=1` 但只用了 0.1；考虑 fractional GPU。
2. 使用 Placement Group 做 gang scheduling。
3. 调整 `spread_threshold` 或显式指定 `SPREAD`/`PACK`。

### 8.6.3 Actor 死锁

现象：actor 方法互相等待或等待自己。

排查：
1. 避免在 actor 方法内调用 `ray.get` 等待同一个 actor 的其他方法。
2. 使用 async actor + `await` 提高并发。
3. 设置 `max_concurrency`。

### 8.6.4 依赖环境问题

现象：worker 上缺少包、版本不一致。

解决方案：
1. 用 `runtime_env` 指定 `pip`/`conda`/`working_dir`。
2. 生产推荐预构建 Docker 镜像 + `image_uri`（experimental）。
3. 避免在 `runtime_env` 里装大依赖；镜像化更稳定。

### 8.6.5 GCS 成为瓶颈

现象：大集群下 Dashboard 卡顿、任务提交延迟高。

排查：
1. 减少把大对象/频繁状态写入 GCS（使用 object store 或外部存储）。
2. 对 GCS 使用 Redis 后端（仅 KubeRay Serve FT 官方支持）。
3. 升级到新版 Ray（ownership 模型持续减少 GCS 负载）。

---

## 8.7 公开用户案例参考

| 公司 | 规模 / 效果 | 来源 |
|---|---|---|
| Ant Group | 240k cores，1.37M TPS | Ray Summit |
| Coinbase | 15× 作业数、同成本；50× 数据量 | Anyscale blog |
| Shopify Merlin | 推荐系统 | public tech talk |
| Pinterest | 特征平台 / 训练 | public tech talk |
| Uber Michelangelo | 机器学习平台 | public tech talk |
| Netflix | 个性化推荐 | public tech talk |

---

## 8.8 小结

- **部署**：本地 → VM 集群 → KubeRay；生产首选 KubeRay。
- **资源**：显式声明 actor/task 资源；监控 object store；大数据用 Ray Data。
- **容错**：task 默认 3 次重试；actor 默认不重启；GCS FT 仅限 KubeRay Serve。
- **可观测**：Dashboard + Prometheus/Grafana + OpenTelemetry。
- **库选择**：Serve 做在线、Data 做批量、Train 做训练、Tune 做搜索。
- **踩坑**：OOM、调度碎片、actor 死锁、runtime_env、GCS 瓶颈。

---

## 8.9 课后练习

1. 为一个 4-GPU 训练任务设计 Placement Group，要求 4 个 worker 各占一台机器。
2. 给 Ray Serve 部署写一段 autoscaling 配置，目标每个副本 5 个并发请求。
3. 列出三种减少 object store OOM 的方法，并说明适用场景。
4. 在 KubeRay 中启用 GCS FT 需要哪些条件？

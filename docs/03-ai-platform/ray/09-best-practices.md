# 9. 最佳实践与 Trade-off

> 本章把 Ray 的设计选择、参数调优、代码习惯与成本意识汇总成可落地的建议。没有放之四海而皆准的“最优”，只有对 workload 特征的匹配。

---

## 9.1 何时选择 Ray

### 9.1.1 Ray 适合的场景

- **分布式 Python**：已有 Python 算法，想横向扩展到多机多卡。
- **异构计算图**：任务、Actor、对象之间形成动态 DAG，而非纯数据并行。
- **训练 + 服务一体化**：Ray Train 训练出的模型直接交给 Ray Serve 部署。
- **超参搜索**：Ray Tune 与 Train/Data 原生集成。
- **RL / 模拟**：RLlib 提供大规模 rollout + 训练闭环。

### 9.1.2 不必用 Ray 的场景

| 场景 | 更合适的工具 | 原因 |
|---|---|---|
| 纯 SQL/Spark 批处理 | Spark / DuckDB / BigQuery | 成熟、成本低、生态广 |
| 单一模型静态训练（如大型 LLM pre-train） | Megatron-LM / FSDP / DeepSpeed | 专为 all-reduce 优化 |
| 简单 REST API 包装模型 | FastAPI + Uvicorn / Triton / KServe | 更轻量、运维更简单 |
| 严格低延迟、确定性的微服务 | 专用服务网格 | Ray actor 重启、调度开销不可忽略 |

---

## 9.2 Task vs Actor：选择指南

| 维度 | Task | Actor |
|---|---|---|
| 状态 | 无状态 | 有状态 |
| 生命周期 | 执行完即释放 | 长期存活，需显式删除 |
| 并发 | 天然并行 | 同一 actor 方法串行（除非 async/threaded） |
| 容错 | 默认重试 3 次 | 默认不重启；需显式配置 |
| 典型用例 | ETL、批量推理、训练 step | 模型 replica、参数服务器、缓存、会话 |

**实践**：
- 需要共享状态或长连接 → Actor。
- 一次性计算、数据并行 → Task。
- 小心“把所有东西变成 actor”：actor 是故障域，也是资源碎片来源。

---

## 9.3 对象生命周期管理

### 9.3.1 避免 ObjectRef 泄漏

```python
# 不好：refs 列表一直增长
refs = []
for batch in batches:
    refs.append(process.remote(batch))
results = ray.get(refs)  # 最后一起取，内存可能爆

# 好：流式消费
refs = []
for batch in batches:
    refs.append(process.remote(batch))
    if len(refs) >= max_inflight:
        ready, refs = ray.wait(refs, num_returns=1)
        consume(ready[0])
```

### 9.3.2 谨慎使用 ray.put

- `ray.put` 对象**不可重建**，且与 owner fate-share。
- 大对象尽量由 task 返回（可重建）或使用 Ray Data。
- 多个 task 需要同一份大对象时，用 `ray.put`  broadcast 比每个 task 自己传参数更高效。

### 9.3.3 内联对象阈值

默认 100 KiB 以下的返回值直接内联在 owner 进程。无需调优，但要知道：
- 内联对象不可重建。
- 频繁返回大量小对象会增加 owner 内存与序列化压力；可考虑 batching。

---

## 9.4 调度与资源

### 9.4.1 显式声明资源

永远显式声明 `num_cpus`/`num_gpus`：

```python
@ray.remote(num_cpus=2, num_gpus=1, memory=4*1024*1024*1024)
def train_step(...):
    ...
```

默认 `num_cpus=1` 对 task 合理，但对 actor 默认是“调度 1 CPU、执行 0 CPU”，生产务必重写。

### 9.4.2 本地性 vs 负载均衡

- **数据局部性优先**：让 task 在已持有输入对象的节点上执行，减少网络传输。
- **负载均衡优先**：高并发在线服务用 `SPREAD` 或高 `spread_threshold`。
- 默认 HYBRID 是大多数 batch workload 的甜点。

### 9.4.3 Placement Group 使用原则

```python
pg = placement_group([{"CPU": 4, "GPU": 1}] * 4, strategy="STRICT_SPREAD")
ray.get(pg.ready())
```

- 需要 gang scheduling（如 4-GPU DDP）→ `STRICT_SPREAD`。
- 需要本地 NVLink → `STRICT_PACK`。
- 不要让 PG 长期占用但不使用；任务结束后 `remove_placement_group(pg)`。

---

## 9.5 性能调优

### 9.5.1 减少序列化开销

- 优先传递 NumPy 数组 / Arrow 表（零拷贝）。
- 避免在 task 参数中传大 Python 对象（如大 dict/list）；用 `ray.put` 或 Ray Data。
- 自定义类需可 pickle；必要时实现 `__reduce__`。

### 9.5.2 减少任务粒度

任务提交本身有开销（毫秒级）。

- 粒度过细 → 调度 overhead 占主导。
- 粒度过粗 → 负载不均、恢复代价高。
- 经验：单个 task 执行时间建议在 **100 ms–数秒**；太短的 task 做 batching。

### 9.5.3 Actor 并发

```python
@ray.remote(num_cpus=1, max_concurrency=10)
class AsyncActor:
    async def handle(self, req): ...
```

- IO 密集型 actor（如调用外部服务）用 async actor。
- CPU 密集型 actor 不建议高并发，会 GIL 争用；可用 threaded actor（ experimental）。

### 9.5.4 Object Store 与 Spilling

- 监控 `ray_object_store_memory`；触顶前主动溢写。
- 大 shuffle 场景：Ray Data 的 `map_batches` + `shuffle` 优于手写 task shuffle。
- Spilling 目标盘要够快；云环境用本地 SSD，不要用网络盘。

---

## 9.6 成本意识

### 9.6.1 自动扩缩容参数

```yaml
available_node_types:
  ray.worker.gpu:
    min_workers: 0
    max_workers: 20
    idle_timeout_minutes: 5
```

- `idle_timeout_minutes` 平衡“快速释放成本”与“任务波动导致的反复启动”。
- GPU 节点启动慢，timeout 不要太短（建议 5–15 分钟）。
- CPU-only 节点可更激进。

### 9.6.2 Spot / 抢占式实例

Ray Autoscaler 支持 spot instance；配合 task 重试可容忍中断。

```yaml
node_config:
  InstanceMarketOptions:
    MarketType: spot
```

注意：
- 有状态 actor 不适合 spot。
- checkpoint 频率要匹配 spot 回收时间。

### 9.6.3 镜像与 Runtime Env

- 生产优先用预构建镜像，减少 `runtime_env` 每次安装依赖的开销。
- `runtime_env` 适合快速迭代；缓存默认 10 GB/field。
- 远程 `working_dir` 必须是 zip 且单顶层目录。

---

## 9.7 可维护性

### 9.7.1 版本与升级

- Ray 2.x 持续发布；关注 release notes 中的 breaking changes（如 2.52 结束 Python 3.9 支持，2.56 计划弃用 Pydantic V1）。
- 不要跨小版本混用 head/worker（如 2.54 head + 2.55 worker）。
- KubeRay 版本与 Ray 版本有对应矩阵，需匹配。

### 9.7.2 测试策略

- 本地 `ray.init()` 跑单元测试。
- 用 `ray.cluster_utils.Cluster` 做多节点集成测试（不启动真实进程）。
- 生产变更先在 staging 集群用真实 workload 跑数小时。

### 9.7.3 文档与可观测性

- 为每个 actor/deployment 命名，便于 Dashboard 定位。
- 关键路径记录自定义 metrics（Prometheus）。
- 保留 task/actor 日志；K8s 下集中收集到 ELK/Loki。

---

## 9.8 常见反模式

| 反模式 | 问题 | 改进 |
|---|---|---|
| 在 task 里创建大量子 task 但不等待 | 级联失控 | 用 DAG 或 Ray Data |
| Actor 持有大状态但不 checkpoint | 重启后状态丢失 | 状态外置或定期 checkpoint |
| 全局 `ray.get` 所有 futures | 内存峰值高、延迟高 | `ray.wait` 流式处理 |
| 用 actor 做纯计算 | 增加调度与容错复杂度 | 改用 task |
| 忽略 `max_retries` 默认值 | 意外重试导致副作用翻倍 | 显式设置，幂等设计 |
| 把 GCS 当 KV 存储 | GCS 瓶颈 | 用 Redis/S3/RDBMS |

---

## 9.9 与 Ray 相邻主题的关系

- **[vLLM](/04-llmops/vllm/)** / **[TensorRT-LLM](/04-llmops/tensorrt-llm/)**：Ray Serve LLM 默认 vLLM 后端，可替换为 TRT-LLM。
- **KServe**：可与 Ray Serve 互补，KServe 做网关、Ray Serve 做推理引擎（本手册 LLMOps 篇待补充）。
- **[Kubernetes](/02-cloud-native/)**：KubeRay 是 Ray 在 K8s 上的官方 operator。
- **[Observability](/07-ai-sre/)**：Prometheus/Grafana/OpenTelemetry 是 Ray 生产可观测的基座。

---

## 9.10 小结

- **选 Ray 前先问**：是否需要动态 DAG、异构资源、训练服务一体化？
- **Task/Actor 分清楚**：无状态计算用 task，有状态服务用 actor。
- **对象管理三原则**：避免泄漏、慎用 ray.put、大数据用 Ray Data。
- **资源声明要显式**：actor 尤其不能依赖默认 CPU。
- **成本与性能平衡**：扩缩容 timeout、spot 实例、镜像化依赖。
- **可维护性**：命名、metrics、日志、版本对齐、staging 验证。

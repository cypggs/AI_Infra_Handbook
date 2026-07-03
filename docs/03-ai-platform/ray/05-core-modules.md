# 5. 核心模块速查

> 本章是 Ray 各组件的"参数与边界速查表"。每个模块给一句话定位、关键 API/参数、成熟度、出处。

---

## 5.1 库总览

| 组件 | 定位 | 成熟度 |
|---|---|---|
| [Ray Core](https://docs.ray.io/en/latest/ray-core/index.html) | task/actor/object/placement group 分布式原语 | GA（稳定 API） |
| [Ray Serve](https://docs.ray.io/en/latest/serve/index.html) | 模型服务（HTTP+gRPC）、DAG、自动伸缩 | GA |
| [Ray Serve LLM](https://docs.ray.io/en/latest/serve/llm-serving/index.html)（原 RayLLM/Aviary） | OpenAI 兼容 LLM 服务（默认 vLLM 引擎） | GA（快速演进） |
| [Ray Data](https://docs.ray.io/en/latest/data/key-concepts.html) | 流式数据预处理；`map_batches` | GA（2.10） |
| [Ray Train](https://docs.ray.io/en/latest/train/index.html) | 分布式训练（PyTorch/FSDP/DeepSpeed/HF/XGBoost/JAX） | GA（2.7） |
| [Ray Tune](https://docs.ray.io/en/latest/tune/index.html) | 超参搜索；ASHA/PBO/BOHB；Optuna/HyperOpt/W&B | GA |
| [RLlib](https://docs.ray.io/en/latest/rllib/index.html) | 分布式 RL；新 API stack（PyTorch-only） | GA（API 迁移中） |
| [Ray Workflows](https://docs.ray.io/en/latest/ray-core/workflows/index.html) | 持久、可 checkpoint 的长任务 DAG | **Beta（2025 弃用）** |
| [Compiled Graph](https://docs.ray.io/en/latest/ray-core/compiled-graph/index.html) | 编译静态执行图（紧耦合集合通信） | Beta（2.44 起） |
| [KubeRay](https://docs.ray.io/en/latest/cluster/kubernetes/index.html) | K8s operator + RayCluster/RayJob/RayService CRD | GA |
| [RayDP](https://docs.ray.io/en/latest/ray-more-libs/raydp.html)（Spark on Ray） | 在 Ray 上跑 PySpark | 社区 |
| Dask/Modin/Mars on Ray | 熟悉 dataframe API 跑在 Ray 后端 | 社区/GA |

---

## 5.2 Ray Core 关键参数

### `@ray.remote` 装饰器参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `num_cpus` | task=1 / actor=0(执行)+1(放置) | CPU 资源 |
| `num_gpus` | 0 | GPU 资源；分配即设 `CUDA_VISIBLE_DEVICES` |
| `memory` / `object_store_memory` | — | 内存（**仅准入控制，运行时不强制**） |
| `resources` | — | 自定义资源键值 |
| `max_restarts`（actor） | 0 | actor 死后重启次数 |
| `max_task_retries`（actor） | 0 | 在途方法重试次数 |
| `max_retries`（task） | 3 | 非任务重试次数 |
| `max_concurrency`（actor） | 1 | 并发度（async actor 才有真并行） |
| `runtime_env` | — | 每任务依赖环境 |
| `scheduling_strategy` | DEFAULT(HYBRID) | `SPREAD`/`PACK`/PlacementGroup/NodeAffinity |

### 全局/集群关键常量（源码 `ray_constants.py` / `ray_config_def.h`）

| 常量 | 值 | 含义 |
|---|---|---|
| `DEFAULT_OBJECT_STORE_MEMORY_PROPORTION` | 0.30 | 对象存储 = 30% 可用 RAM |
| `DEFAULT_OBJECT_STORE_MAX_MEMORY_BYTES` | 200 GiB | Linux/云硬上限 |
| `MAC_DEGRADED_PERF_MMAP_SIZE_LIMIT` | 2 GiB | **macOS 上限**（避免性能退化） |
| `OBJECT_STORE_MINIMUM_MEMORY_BYTES` | 75 MiB | 最小 |
| `max_direct_call_object_size` | 100 KiB | in-band 小对象阈值（随 owner 而亡） |
| `task_rpc_inlined_bytes_limit` | 10 MiB | 单 task RPC 内联上限 |
| `object_spilling_threshold` | 0.8 | 主动溢写阈值 |
| `max_lineage_bytes` | 1 GiB | 每 worker lineage 缓存上限 |
| `CALLER_MEMORY_USAGE_PER_OBJECT_REF` | 3000 B | 每 ObjectRef 元数据约 3 KB |
| `RAY_scheduler_spread_threshold` | 0.5 | HYBRID 打包→摊开切换阈值 |
| `RAY_gcs_rpc_server_reconnect_timeout_s` | 60 | raylet 重连 GCS 超时 |
| `RAY_memory_monitor_refresh_ms` | 250 | OOM killer 检查间隔 |
| `RAY_memory_usage_threshold` | 0.95 | OOM killer 触发阈值 |

---

## 5.3 Ray Serve 关键参数

| 概念 | API/参数 | 说明 |
|---|---|---|
| 部署 | `@serve.deployment(num_replicas, ray_actor_options, autoscaling_config)` | 副本数 / actor 资源 / 伸缩 |
| 路由 | `DeploymentHandle` + Router（power-of-two-choices） | 模型组合/DAG |
| 批处理 | `@serve.batch(max_batch_size, batch_wait_timeout_s)` | 动态批 |
| 伸缩 | `autoscaling_config`：`min_replicas`/`max_replicas`/`target_num_ongoing_requests_per_replica`/`upscale_delay_s`/`downscale_delay_s` | **按请求驱动**，与集群 VM autoscaler 独立 |
| Ingress | HTTP（Uvicorn）/ gRPC（grpcio）/ HAProxy router | proxy 每节点一个 |
| 健康 | RayService CRD 滚动更新 + 健康探针 | 零停机升级 |

---

## 5.4 Ray Serve LLM（`ray.serve.llm`）

```python
from ray import serve
from ray.serve.llm import LLMConfig, build_openai_app

cfg = LLMConfig(
    model_loading_config=dict(model_id="qwen", model_source="Qwen/Qwen2.5-0.5B-Instruct"),
    deployment_config=dict(autoscaling_config=dict(min_replicas=1, max_replicas=4)),
    accelerator_type="A10G",
    engine_kwargs=dict(tensor_parallel_size=1, max_model_len=8192),
)
serve.run(build_openai_app({"llm_configs": [cfg]}), blocking=True)
```

- **OpenAI 兼容 API**，与 `vllm serve` 对齐；`engine_kwargs` 大多通用。([vLLM 兼容指南](https://docs.ray.io/en/latest/serve/llm/user-guides/vllm-compatibility.html))
- 能力：chat/completions/embeddings/transcriptions(Whisper)/VLM/结构化输出(JSON+Pydantic)/推理模型(DeepSeek-R1)。
- **`vllm serve` ↔ Ray Serve LLM 无需改代码**，额外获得自动伸缩/多模型/高级路由。
- 高级特性：[跨节点并行](https://docs.ray.io/en/latest/serve/llm/user-guides/cross-node-parallelism.html)、[数据并行 attention](https://docs.ray.io/en/latest/serve/llm/user-guides/data-parallel-attention.html)、[prefill/decode 分离](https://docs.ray.io/en/latest/serve/llm/user-guides/prefill-decode.html)、[KV cache 卸载](https://docs.ray.io/en/latest/serve/llm/user-guides/kv-cache-offloading.html)、[prefix-aware 路由](https://docs.ray.io/en/latest/serve/llm/user-guides/prefix-aware-routing.html)、[多 LoRA](https://docs.ray.io/en/latest/serve/llm/user-guides/multi-lora.html)、[分数 GPU](https://docs.ray.io/en/latest/serve/llm/user-guides/fractional-gpu.html)。
- **连续批处理来自 vLLM 引擎**，Ray 不重造。

---

## 5.5 Ray Train 关键参数

| 概念 | API | 说明 |
|---|---|---|
| 规模 | `ScalingConfig(num_workers, use_gpu, resources_per_worker)` | worker 数与资源 |
| 持久化 | `RunConfig(storage_path=...)` | **2.7 起必需**（trial/checkpoint） |
| Trainer | `TorchTrainer`/`HuggingFaceTrainer`/`XGBoostTrainer`/`LightGBMTrainer`/`JAXTrainer`/`DeepSpeedTrainer`/`HorovodTrainer`/`TensorflowTrainer` | `AccelerateTrainer` 自 2.8 弃用，改用 `HuggingFaceTrainer` |
| 上报 | `session.report(metrics, checkpoint=ray.train.Checkpoint(...))` | 指标 + checkpoint |
| 弹性 | [Elastic training](https://docs.ray.io/en/latest/train/user-guides/elastic-training.html) | worker 加入/离开 |
| 容错 | [Fault tolerance](https://docs.ray.io/en/latest/train/user-guides/fault-tolerance.html) | 重启 + spot + checkpoint |

> `ScalingConfig.trainer_resources` **已弃用**——trainer 资源改由 trainer 构造器传。

---

## 5.6 Ray Data 关键参数

| 概念 | API | 说明 |
|---|---|---|
| 抽象 | `Dataset`（惰性分布式集合）+ `Block`（单分区，Pandas/PyArrow） | 两层 |
| 计划 | 逻辑计划（`ReadOp`/`MapBatches`/`Filter`/`Project`）→ 优化器（`OperatorFusionRule`）→ 物理计划（`TaskPoolMapOperator`/`ActorPoolMapOperator`） | 两阶段 |
| 执行 | **流式**（非 shuffle 算子流水线，不同 stage 独立伸缩并发）；shuffle（`sort`/`groupby`）需物化、中断流式 | — |
| 主变换 | `ds.map_batches(fn, batch_format=, num_cpus=, num_gpus=)` | 核心算子 |
| 连接器 | Parquet/JSON/CSV/text/binary/**HuggingFace**(`read_huggingface`)/**TFRecords**/**WebDataset**/NumPy/pandas/Delta Lake；远端 S3/GCS/Azure/HDFS | — |
| LLM 批推理 | `ray.data.LLM` / `Dataset.map_llm()` | 批推理 API |

---

## 5.7 RLlib（新 API stack，PyTorch-only）

| 新（默认） | 旧（淘汰） |
|---|---|
| `RLModule` | `ModelV2` + `Policy` |
| `Learner` / `LearnerGroup` | `RolloutWorker`（训练侧） |
| `EnvRunner` | `RolloutWorker`（采样侧） |
| `ConnectorV2` | `ViewRequirement` |
| `OfflineData` | Policy 上的离线 API |

- 算法：PPO/IMPALA/APPO/DQN(Rainbow)/SAC/A2C/A3C/PG/MARL(QMIX…)（[Algorithms](https://docs.ray.io/en/latest/rllib/algorithms.html)）。
- **GRPO 不是 RLlib 原生**：走 TRL 的 `GRPOTrainer`，由 Ray Train 的 `TorchTrainer` 包装（`vllm_mode="colocate"`）。
- Ray + vLLM 的 RLHF 框架：[verl](https://docs.ray.io/en/latest/cluster/kubernetes/examples/verl-rlhf-kuberay.html)、[OpenRLHF](https://github.com/OpenRLHF/OpenRLHF)。

---

## 5.8 KubeRay CRD 选型

| CRD | 何时用 |
|---|---|
| **RayCluster** | 声明式集群（head + worker pod 模板 + 集群内 autoscaler） |
| **RayJob** | 提交/跟踪一个 Ray Job（entrypoint、runtime_env、`shutdownAfterJobFinishes`、TTL） |
| **RayService** | 部署 Ray Serve 应用，滚动更新 + 健康探针 + 零停机 + HA |
| **RayCronJob** | 定时任务（2.56 文档 ToC 出现，[细节未完全核验]） |

集成：[Kueue](https://docs.ray.io/en/latest/cluster/kubernetes/doc-source/kuberay/kueue)/[Volcano](https://docs.ray.io/en/latest/cluster/kubernetes/doc-source/kuberay/volcano)/[YuniKorn](https://docs.ray.io/en/latest/cluster/kubernetes/doc-source/kuberay/yunikorn)/[KAI Scheduler](https://docs.ray.io/en/latest/cluster/kubernetes/doc-source/kuberay/kai-scheduler)/[Istio mTLS](https://docs.ray.io/en/latest/cluster/kubernetes/doc-source/kuberay/istio)/[Prometheus+Grafana](https://docs.ray.io/en/latest/cluster/kubernetes/doc-source/kuberay/prometheus-grafana)。

---

## 5.9 可观测工具速查

| 工具 | 用途 |
|---|---|
| Dashboard `:8265` | 集群/actor/task/PG/日志/指标/内存/事件 |
| `ray status` | 集群资源摘要 |
| `ray list actors/tasks/placement-groups/nodes/cluster-events` | 实体列表 |
| `ray get <type> <id>` / `ray summary actors/tasks` | 详情/聚合 |
| `ray memory` | ObjectRef 五类引用诊断 |
| Prometheus metrics | 见 [第 8 章 §8.x](08-production-practice) |
| Task Timeline | chrome://tracing / Perfetto |
| Tracing | OpenTelemetry 导出 |

---

下一章 [源码与生态分析](06-source-analysis) 深入仓库的真实文件与调用链。

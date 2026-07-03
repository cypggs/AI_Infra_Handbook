# 6. 源码与生态分析

本章进入真实代码：用 **MaxText**（Google 最易读的 TPU 训练参考实现）展示"标注即并行"如何在源码里落地，再用 **Pathways / GSPMD / JetStream** 补全运行时与推理侧，最后给出**开源生态状态表**。所有代码片段均取自 `AI-Hypercomputer/maxtext` 的 `main` 分支（2026-07-03 核验），标注文件路径 + GitHub blob URL + 行号区间。

> **仓库结构提示**：MaxText 已迁移到 Python `src/` 布局（2025-07 宣布，2026-02 完成）。旧文档里的 `MaxText/maxtext/transformer_layers.py`、`MaxTextModel.py`、`GlobalMesh.py` **已不存在**，等价物现在 `src/maxtext/` 下。

---

## 6.1 MaxText 仓库结构

MaxText 是纯 Python/JAX 的高性能 LLM 训练库，"几乎免优化（无 C++/CUDA）"，靠 JAX + XLA 拿高 MFU。`src/maxtext/` 下的关键目录：

| 目录 | 职责 |
|---|---|
| `layers/` | Transformer 构件：`attentions.py`、`linears.py`、`decoders.py`、`embeddings.py`、`normalizations.py`、`moe.py`、`pipeline.py`、`quantizations.py` |
| `models/` | 整模型装配：`TransformerLinenPure`/`TransformerLinen`/`Transformer`(NNX) + Zero-1 FSDP 包装 |
| `kernels/` | 专用 kernel（`attention/`：flash/splash/ragged attention） |
| `configs/` | `pyconfig.py`（YAML 驱动的 `HyperParameters` + `logical_axis_rules`/`data_sharding` 合并）+ 各模型 YAML |
| `utils/` | `sharding.py`（PartitionSpec/Mesh/FSDP 辅助）、`maxtext_utils.py`（mesh 创建/`init_state`）、`train_utils.py` |
| `common/` | `checkpointing.py`（Orbax）、`train_state_nnx.py`、`data_loader.py` |
| `trainers/` | `pre_train/train.py`（训练循环、loss、`train_step`/`eval_step`）+ 后训练/RL |
| `checkpoint_conversion/` | HF ↔ MaxText 双向 checkpoint 转换 |

---

## 6.2 真实代码片段

### 6.2.1 注意力层：分片标注如何嵌入模块

`src/maxtext/layers/attentions.py` L102-L161 —— `attention_as_linen` 工厂。注意 `mesh` 参数和一组 `AxisNames` 逻辑分片参数（`KV_BATCH`/`ATTN_LENGTH`/`KV_HEAD`/`KV_HEAD_DIM`...）——这些就是喂给 XLA/GSPMD 的分片标注，告诉编译器如何把 Q/K/V/O 沿 mesh 分片。

```python
def attention_as_linen(
    *,
    config: Config,
    num_query_heads: int,
    num_kv_heads: int,
    head_dim: int,
    max_target_length: int,
    mesh: Mesh,
    attention_kernel: str,
    ...
    # Shard the query activation as the same as the key and value.
    prefill_query_axis_names: AxisNames = (PREFILL_KV_BATCH, PREFILL_LENGTH, KV_HEAD, KV_HEAD_DIM),
    prefill_key_axis_names:   AxisNames = (PREFILL_KV_BATCH, PREFILL_LENGTH, KV_HEAD, KV_HEAD_DIM),
    prefill_value_axis_names: AxisNames = (PREFILL_KV_BATCH, PREFILL_LENGTH, KV_HEAD, KV_HEAD_DIM),
    query_axis_names: AxisNames = (KV_BATCH, ATTN_LENGTH, KV_HEAD, KV_HEAD_DIM),
    key_axis_names:   AxisNames = (KV_BATCH, ATTN_LENGTH, KV_HEAD, KV_HEAD_DIM),
    value_axis_names: AxisNames = (KV_BATCH, ATTN_LENGTH, KV_HEAD, KV_HEAD_DIM),
    ...
):
  """A factory function to create an Attention as a Linen module."""
  return nnx_wrappers.to_linen(Attention, config=config, ...)
```

实际的 softmax/QK matmul 委托给 `kernels/attention/` 下的后端 kernel（`jax_flash_attention.py`/`splash_attention_kernel.py`），由 `attention_kernel` 选择。

> 源：[`src/maxtext/layers/attentions.py#L102-L161`](https://github.com/AI-Hypercomputer/maxtext/blob/main/src/maxtext/layers/attentions.py#L102-L161)

### 6.2.2 Mesh + 带分片 JIT：把设备组织成命名轴网格

`src/maxtext/utils/maxtext_utils.py` L2062-L2069 —— MaxText 在（可能多 slice 的）设备数组上建 JAX `Mesh`，每个轴标 `Explicit` 或 `Auto`：

```python
  devices_array = create_device_mesh(config, devices)

  if config.shard_mode == ShardMode.EXPLICIT:
    axis_types = tuple([AxisType.Explicit] * len(config.mesh_axes))
  else:
    axis_types = tuple([AxisType.Auto] * len(config.mesh_axes))

  return Mesh(devices_array, config.mesh_axes, axis_types=axis_types)
```

`create_device_mesh`（L1809-L1838）让"每个 slice 各自成一个数据并行组"，支持 elastic（在线设备）与多 slice：

```python
def create_device_mesh(config, devices=None):
  """Creates a device mesh with each slice in its own data parallel group."""
  ...
  num_devices = len(devices)
  num_slices = 1 if config.inference_benchmark_test else num_slices
  num_devices_per_slice = num_devices // num_slices
```

> 注：JAX 已把 `pjit` 并入 `jax.jit`（`jit` 现接受 `in_shardings`/`out_shardings`）。MaxText 因此直接用带分片的 `jit`，而非单独的 `pjit`。状态初始化示例（`maxtext_utils.py` L1557）：

```python
  abstract_sharded_state = jax.jit(
      init_state_partial, in_shardings=None, out_shardings=state_mesh_shardings
  ).eval_shape()
```

### 6.2.3 逻辑轴 → PartitionSpec：用户标注层

`src/maxtext/utils/sharding.py` L263-L293 —— 把逻辑轴名映射到 mesh 轴的 PartitionSpec（这是降低到 GSPMD 的用户接口）：

```python
def logical_to_mesh_axes(logical_names, mesh, rules=None):
  """Remove size one mesh axes given logical names."""
  tensor_spec = nn.logical_to_mesh_axes(logical_names, rules=rules)
  return remove_size_one_mesh_axis(tensor_spec, mesh)

def create_sharding(mesh, logical_names, rules=None):
  """Create NamedSharding with given logical names."""
  return NamedSharding(mesh, logical_to_mesh_axes(logical_names, mesh, rules=rules))
```

`maybe_shard_with_name`（L73-L113）在 Auto 模式下作为 GSPMD 提示（`with_sharding_constraint`），Explicit 模式下强制分片：

```python
def maybe_shard_with_name(inputs, named_sharding, shard_mode, ...):
  """In auto shardmode, this function hints inputs follow given named_sharding.
  In explicit shardmode, this function enforces inputs following named_sharding."""
  ...
  if shard_mode == "auto":
      return jax.lax.with_sharding_constraint(inputs, named_sharding)
  return reshard(inputs, named_sharding)
```

### 6.2.4 训练循环 + Orbax checkpoint

`src/maxtext/trainers/pre_train/train.py` L884-L900 —— 外层步循环：

```python
    while python_vars["step"] < immutable_data["steps"]:
      training_loop_iteration(jax_device_state, python_vars, immutable_data)
      python_vars["step"] += 1

    state = jax_device_state["state"]
    if immutable_data["save_checkpoint_on_completion"]:
      checkpointing.maybe_save_checkpoint(checkpoint_manager, state, config, data_iterator)
    if checkpoint_manager is not None:
      checkpoint_manager.wait_until_finished()
```

一步内部（`train.py` L686-L703）—— 在 mesh + 逻辑轴规则下跑编译后的 `p_train_step`，并尝试 checkpoint：

```python
  with jax.profiler.StepTraceAnnotation("train", step_num=step):
    example_batch = data_loader.load_next_batch(rampup_manager=rampup_manager)
    ...
    with maybe_record_goodput(recorder, GoodputEvent.STEP, step):
      with jax.set_mesh(mesh), nn_partitioning.axis_rules(logical_axis_rules):
        if shard_optimizer_over_data and isinstance(model, nn.Module):
          state = sharding.maybe_shard_with_name(state, state_mesh_shardings, shard_mode)
        state, metrics = p_train_step(state, example_batch, *step_rng_args)

  checkpointing.maybe_save_checkpoint(checkpoint_manager, state, config, data_iterator, step)
```

Orbax checkpoint manager（`common/checkpointing.py` L394-L430）—— 默认 OCDBT + Zarr3：

```python
def create_orbax_checkpoint_manager(checkpoint_dir, enable_checkpointing, use_async,
        save_interval_steps, ..., use_ocdbt=True, use_zarr3=True,
        enable_continuous_checkpointing=False, max_num_checkpoints_to_keep=10,
        checkpoint_storage_concurrent_gb=96, ...):
  ...
  item_handlers = {
      "items": PyTreeCheckpointHandler(
          restore_concurrent_gb=checkpoint_storage_concurrent_gb,
          save_concurrent_gb=checkpoint_storage_concurrent_gb,
          use_ocdbt=use_ocdbt, use_zarr3=use_zarr3,
      )
  }
```

### 6.2.5 FSDP：用 `fsdp` mesh 轴 + `remove_fsdp_sharding`

MaxText 用一个名为 `fsdp`（及 `fsdp_transpose`）的 mesh 轴表达 FSDP。`src/maxtext/utils/sharding.py` L822-L849 —— 遍历分片树，把每个 `fsdp`/`fsdp_transpose` PartitionSpec 项替换为 `None`（即复制/all-gather）：

```python
def remove_fsdp_sharding(sharding_tree):
  """Recursively traverses the sharding tree to remove fsdp axes."""
  def _remove_fsdp_from_partition_spec(named_sharding):
    if isinstance(named_sharding, jax.sharding.NamedSharding):
      new_spec = []
      for axis in named_sharding.spec:
        if axis is None:
          new_spec.append(None)
        elif isinstance(axis, str):
          if axis not in ("fsdp", "fsdp_transpose"):
            new_spec.append(axis)
          else:
            new_spec.append(None)   # 复制
        ...
      return jax.sharding.NamedSharding(named_sharding.mesh, jax.sharding.PartitionSpec(*new_spec))
    return named_sharding
  return jax.tree.map(_remove_fsdp_from_partition_spec, sharding_tree)
```

Zero-1 FSDP 包装（`models/models.py` L456-L479）在 apply 前 all-gather 权重、apply 后释放。

> **读码要点**：MaxText 的源码是 Google 栈设计哲学最可读的证明——**写单设备 JAX，用逻辑轴规则 + 少量 `PartitionSpec`/`with_sharding_constraint` 标注，让 XLA/GSPMD 自动发数据/FSDP/张量/流水线并行的 per-device 集合通信**。你建的 `Mesh` 与 JAX 分布式数组文档描述的是同一抽象；在 Pod 规模下 gang-schedule 这些编译函数、跨 island 流水线化的运行时是 Pathways。

---

## 6.3 Pathways：单控制器异步分片数据流

Pathways 是内部系统（**未开源**，协调底座 PLAQUE 在论文中明确称"closed-source"），但其架构（arXiv:2203.12533）值得理解，因为它是"一个程序跨数千 TPU"在控制面上可扩展的关键。

**设计动机**：SPMD/MPI 的 lockstep 同步在 Pod 内尚可，但跨 Pod、跨异构、跨稀疏（MoE/流水线）模型力不从心——"单一并行策略被迫套到整个程序上"，且同步 barrier 浪费资源；把大规模同质"岛"独占给单用户程序"既贵又浪费"。

**架构**：client-server，单控制器。组件：Client、Resource Manager（全局）、Scheduler（每 island，gang scheduler）、Executor（每设备）、XLA 后端。"我们采用单控制器模型，因为它比多控制器有更好的机会……不同之处在于它用**异步派发**追平多控制器性能，支持集中式资源管理与 gang 调度，并用**分片数据流系统**高效协调。"

**异步派发**："parallel asynchronous dispatch……利用编译函数静态已知的资源占用，把一个计算节点的大部分主机端工作**并行**而非串行地派发。"

**成组派发**："当一个子图可静态调度，程序向 scheduler 发**单条消息**（描述整个子图），scheduler 把所有 active shard 串起来执行。"

**分片数据流**：每个节点是一个已分片的编译 XLA 函数，边是 future；"每个分片计算一个节点"的紧凑表示避免 M×N 边爆炸（"A↔B 两段 N-shard 计算只有 4 个节点：Arg→Compute(A)→Compute(B)→Result，与 N 无关"）。

**headline**：2048 TPU 上 SPMD 约 100% 利用率；跨 16 级流水线或跨两 island Transformer 吞吐与 SPMD 相当。

---

## 6.4 GSPMD：标注即并行的编译器 pass

GSPMD（arXiv:2105.04663）是 XLA 的分片 pass。核心命题（论文摘要）："允许用户像单设备一样写程序，再通过少数标注给出如何分布张量的提示，GSPMD 据此并行化计算。其分片表示简单而通用，能在多种模型上表达不同或混合并行范式。"

- **标注而非改写**：用户标注少数张量，GSPMD 的"sharding propagation"逐算子推断其余分片。
- **混合范式**：数据/张量/流水线（经"manual"轴）/FSDP 在同一图里混合。
- **为何自动化重要**：万亿参数规模下，为每种并行组合逐算子手写集合通信不可行。
- **指标**：2048 个 TPUv3 核心上，万亿参数模型 50%–62% 利用率。

JAX 通过 `Mesh` + `PartitionSpec` + `with_sharding_constraint` 暴露 GSPMD；三种可混合的并行风格（编译器自动分片 / 显式分片+自动分区 / 手写 per-device 通信）都降低到 GSPMD。

---

## 6.5 JetStream / tpu-inference：推理侧

JetStream（→`tpu-inference`）是 XLA/TPU 推理引擎，README 自述"a throughput and memory optimized engine for LLM inference on XLA devices, starting with TPUs"。与 vLLM/TRT-LLM（GPU/CUDA 优先）的区别：**TPU 原生 + XLA 编译**。权重分片三轴（`ici_fsdp_parallelism`/`ici_autoregressive_parallelism`/`ici_tensor_parallelism`）+ 连续批处理 + HBM KV cache（可 int8）。**归档状态**：核心功能迁至 `tpu-inference`（`tpu.vllm.ai`），JetStream 本体 2026-02-01 起只读。

---

## 6.6 开源生态状态表

2026-07-03 经 GitHub API 核验（`archived`/`pushed_at`/stars）：

| 项目 | 仓库 | 状态 |
|---|---|---|
| **JAX** | [`jax-ml/jax`](https://github.com/jax-ml/jax) | 活跃，未归档；2026-07-03 push；~36k stars（已从 `google/jax` 迁至 `jax-ml/jax`） |
| **XLA / OpenXLA** | [`openxla/xla`](https://github.com/openxla/xla) | 活跃；~4.4k stars；steward = OpenXLA Foundation |
| **MaxText** | [`AI-Hypercomputer/maxtext`](https://github.com/AI-Hypercomputer/maxtext) | 活跃；Apache-2.0；PyPI 可装 |
| **MaxDiffusion**（扩散兄弟） | [`AI-Hypercomputer/maxdiffusion`](https://github.com/AI-Hypercomputer/maxdiffusion) | 活跃 |
| **JetStream** | [`AI-Hypercomputer/JetStream`](https://github.com/AI-Hypercomputer/JetStream) | 挂归档通知，迁至 `tpu-inference` |
| **Gemma** | HF `google/gemma-3` / `ai.google.dev/gemma` | 开放权重（Gemma Terms of Use） |
| **Pax / Paxml** | [`google/paxml`](https://github.com/google/paxml) | 维护/参考角色（新 LLM 工作转向 MaxText） |
| **T5X** | [`google-research/t5x`](https://github.com/google-research/t5x) | 长期维护 |
| **Lingvo** | [`tensorflow/lingvo`](https://github.com/tensorflow/lingvo) | 遗留（TF 时代，已被 JAX 栈取代） |
| **Pathways 运行时** | — | **未开源**（内部系统，PLAQUE 闭源） |
| Orbax/Optax/Flax/Grain/Tunix | `google/orbax` 等 | 活跃依赖库，MaxText 组合使用 |

**2026 年的开放可复现路径**：`JAX + Flax/Orbax/Optax/Grain + MaxText`，由 `XLA/OpenXLA`（含 GSPMD pass）做自动分片，跑在 Cloud TPU 上。Pathways 是闭源内部运行时；Paxml/T5X/Lingvo 是可读参考而非推荐起点。

---

## 6.7 源码 ↔ 架构的对应

| 架构层 | 源码体现 |
|---|---|
| 标注（JAX/Mesh） | MaxText `sharding.py`、`maxtext_utils.py` 的 Mesh/PartitionSpec |
| 分片（XLA/GSPMD） | `with_sharding_constraint` → 编译器插集合通信 |
| FSDP | `fsdp` mesh 轴 + `remove_fsdp_sharding`/Zero-1 包装 |
| 训练循环 | `trainers/pre_train/train.py` 的步循环 + `p_train_step` |
| checkpoint | `common/checkpointing.py` 的 Orbax manager |
| Pod 编排 | Pathways（闭源，但架构见论文） |
| 推理 | JetStream/`tpu-inference` 的权重分片三轴 |

下一章 [Mini Demo](07-mini-demo) 用可运行代码验证两个核心机制：3D-torus 分维 AllReduce 的延迟优势，与 NSDI'24 双路径恢复的权衡。

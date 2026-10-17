# 5. 核心模块

TensorRT-LLM 的功能由多个核心模块协作完成。本章按数据流从“输入 → 构建 → 执行 → 服务”拆解每个模块的职责、关键类与配置。

## 模块总览

```mermaid
flowchart LR
    subgraph Input
        Tokenizer[TokenizerManager]
        Quant[Quantization Toolkit]
    end

    subgraph Build
        LLM[LLM API]
        Builder[Builder / Converter]
        Plugin[Plugin Registry]
    end

    subgraph Plan
        Engine[Engine / PyTorchModelEngine]
        Config[BuildConfig / KvCacheConfig]
    end

    subgraph Runtime
        Executor[PyExecutor]
        Scheduler[CapacityScheduler<br/>MicroBatchScheduler]
        KV[KVCacheManager]
        Decoder[Decoder]
    end

    subgraph Serving
        Triton[Triton Backend]
        Bench[trtllm-bench]
    end

    Input --> Build --> Plan --> Runtime --> Serving
```

## 1. LLM API（Python 入口）

`tensorrt_llm.LLM` 是最常用的 Python 入口，封装了构建、加载、生成全流程。

```python
from tensorrt_llm import LLM, SamplingParams

llm = LLM(model="TinyLlama/TinyLlama-1.1B-Chat-v1.0")
outputs = llm.generate("Hello, my name is", SamplingParams(max_tokens=32))
```

关键职责：

- 解析模型路径、trust_remote_code、tokenizer
- 根据 `BuildConfig` 与 `SamplingParams` 初始化后端
- 管理 tokenization / detokenization
- 提供 `generate()` / `save()` / `shutdown()` 等接口

主要配置类：

| 类 | 作用 |
|---|---|
| `BuildConfig` | max_batch_size、max_seq_len、precision、parallelism 等 |
| `KvCacheConfig` | KV cache dtype、enable_block_reuse、paged/cache_size 等 |
| `SamplingParams` | temperature、top_k、top_p、max_tokens、beam_width 等 |

## 2. Builder / Model Converter

Builder 负责把外部 checkpoint 转换为 TRT-LLM 内部可执行表示。

### TensorRT 后端时代（1.2 之前）

- `tensorrt_llm.Builder()`：创建 builder 与 network
- `trtllm-build` CLI：生成 `.engine` 文件
- 输出序列化的 TensorRT engine / plan

### PyTorch 后端时代（1.2+）

- `LLM(model=...)` 隐式完成权重加载与转换
- 模型定义位于 `tensorrt_llm/_torch/models/`
- 通过 `torch.compile`、CUDA Graph、custom kernel 做运行时优化

核心概念保留：

- 构建期完成算子选择、融合、量化、并行策略配置
- 运行期加载执行计划，避免重复解析模型结构

## 3. Engine / PyTorchModelEngine

Engine 是“执行计划”的载体。

### TensorRT Engine（历史）

- 二进制序列化文件，包含 CUDA kernel 选择、张量布局、融合图
- 通过 `runtime.Session` 加载
- 强绑定 GPU SKU 与 build 参数

### PyTorchModelEngine（当前）

- 位置：`tensorrt_llm/_torch/pyexecutor/model_engine.py`
- 持有 PyTorch 模型权重与计算图
- 关键方法：`forward(scheduler_output) → logits`
- 支持 CUDA Graph 重放、piecewise CUDA Graph、`torch.compile`

Engine 层的优化手段：

| 优化 | 作用 |
|---|---|
| CUDA Graph | 减少 kernel launch CPU overhead |
| torch.compile | 图级优化、kernel 融合 |
| Piecewise CUDA Graph | 对不同 shape 分段捕获 graph |
| Custom Triton Kernel | 替换标准 PyTorch op，提升特定 kernel 性能 |

## 4. Plugin Registry（插件注册表）

Plugin 机制允许注入自定义 CUDA kernel 或 PyTorch custom op。

### 自定义 Plugin 示例

```python
import tensorrt_llm as trtllm
from tensorrt_llm.plugin import PluginBase

@trtllm.plugin("TritonLookUp")
class LookUpPlugin(PluginBase):
    def shape_dtype_inference(self, inputs):
        ...

    def forward(self, inputs, outputs):
        ...
```

### 内置 Plugin（历史与现状）

| Plugin | 作用 |
|---|---|
| `gpt_attention_plugin` | 融合 masked / flash / paged attention |
| `gemm_plugin` | 融合 GEMM + bias + activation |
| `nccl_plugin` | 多 GPU 通信算子 |
| `rmsnorm_plugin` | 融合 RMSNorm |

PyTorch 后端下，这些能力更多以 custom op / Triton kernel 形式存在，但 plugin 注册与替换的思想仍然适用。

## 5. Executor（执行器）

Executor 是服务阶段的核心，负责持续调度与执行。

### PyExecutor

- 每个 rank 一个 `PyExecutor(Worker)`
- 连续后台循环：fetch → schedule → forward → decode → update
- 通过 `ExecutorConfig` 配置：
  - `max_batch_size`
  - `max_num_tokens`
  - `scheduler_config`
  - `kv_cache_config`

### C++ Executor

- 提供更低的调度延迟
- 1.3 起 KVCacheManager V2 提供 C++ 实现（1.4 移除其 Python 后端）
- OpenEngine gRPC server（1.3+）直接架在 Executor 之上，供 Dynamo sidecar 调用

## 6. Scheduler（调度器）

TRT-LLM 的 Scheduler 由两层组成：

### CapacityScheduler

检查当前资源是否能容纳新请求：

- KV cache 是否足够
- batch size 是否未超上限
- token budget 是否足够

### MicroBatchScheduler

从 waiting/running 队列中选出当前 step 的 micro-batch：

- 优先 generation-phase 请求
- 剩余 budget 分配给 context-phase
- 支持 chunked prefill

调度器配置：

```python
from tensorrt_llm.executor import SchedulerConfig

scheduler_config = SchedulerConfig(
    capacity_scheduler_policy=...,  # 容量调度策略
    scheduler_policy=...,            # 调度策略
)
```

## 7. KVCacheManager

KV Cache 管理器负责显存分配与复用。支持两种模式：

### Contiguous KV Cache

- 单一大张量：`[max_batch_size * beam_width, 2, num_heads, max_seq_len, head_size]`
- 实现简单，但存在内部碎片

### Paged KV Cache

- 按 block 分配，block 大小通常为 64/128 tokens
- 每个 sequence 维护 block table
- 支持 block reuse / prefix caching
- 与 chunked prefill 配合良好

```python
from tensorrt_llm.llmapi import KvCacheConfig

kv_cache_config = KvCacheConfig(
    dtype='fp8',
    enable_block_reuse=True,
)
```

### KVCacheManager V2（1.3 默认）

1.3 起 KVCM2 成为主流模型默认实现，核心改进：

- **分层显存池**：热数据在 GPU，冷页可压缩后落到 CPU 内存，缓解长上下文显存压力
- **分布式池再均衡**：多实例间迁移 KV block
- **流水线化传输**：与分离式服务配合，传输与计算重叠
- **Mamba / 线性注意力状态快照**：统一缓存管理
- **C++ 实现**：降低 Python 调度开销（1.4 起移除 Python 后端）

V1 已进入弃用期，迁移时需注意 `block_reuse_policy` 等配置项已迁移到 `block_reuse_config.policy`。

## 8. Decoder（采样器）

Decoder 从 logits 生成下一个 token。

支持策略：

- greedy
- top-k、top-p、temperature
- beam search
- repetition penalty、frequency/presence penalty
- guided decoding / structured generation

```python
from tensorrt_llm import SamplingParams

SamplingParams(
    temperature=0.8,
    top_k=50,
    top_p=0.9,
    max_tokens=128,
)
```

## 9. 投机解码（Speculative Decoding）

1.x 周期内投机解码是 TRT-LLM 投入最大的特性之一，核心变化是 **1.2 移除了双引擎方案**——draft 与 target 合并为单模型实现（Eagle3、MTP-Eagle、Draft-Target 均如此），降低显存与调度复杂度。1.3 RC 周期又引入了一批新算法与 kernel：

| 机制 | 说明 |
|---|---|
| Eagle3 / MTP-Eagle | 单模型多步草稿，支持多层 draft head |
| DSpark / DFlash | 面向 Blackwell 的 draft/verify kernel，扩展到 RoPE、滑窗、结构化输出 |
| Helix | FP8 / FP4 MLA 场景的投机验证 |
| GVR（top-K） | 基于树的投机采样，支持自采样 prefill |

调度侧支持 **dynamic speculation**（按负载动态调整每步草稿长度）与投机 + 引导解码组合，并可在指标中按请求统计接受率（1.4.0rc0）。

## 10. Quantization Toolkit（量化工具链）

TRT-LLM 支持多种量化方案：

| 方案 | 精度 | 适用硬件 |
|---|---|---|
| FP8 | Hopper / Blackwell 首选 | H100/H200/B200/GB200 |
| FP4 / NVFP4 | Blackwell 专属 | B200/GB300，消费级 SM120（W4A16 NVFP4） |
| MXFP4 | Blackwell 微缩放 FP4 | B200/GB300、DGX Spark |
| Marlin NVFP4 | 高吞吐 NVFP4 kernel | Ada（SM89）/Blackwell |
| AWQ / GPTQ | W4A16 / W4A8 | 多代 GPU |
| INT8 | 传统方案 | 多代 GPU |

2025 下半年以来的 kernel 进展：1.1 引入基于 CuTe DSL 的 Blackwell NVFP4 grouped GEMM 与 DeepEP FP4 MoE 通信；1.3 周期加入 Marlin NVFP4（Ada 也有）、MegaMoE CuTe DSL（替代弃用的 WIDEEP）、CUTLASS MoE 的 FP8 block-scale 路径（TRITON MoE 后端已弃用）；KV cache 侧支持 NVFP4（如 MiniMax-M3）。

量化流程：

1. 选择量化 recipe（FP8 / FP4 / AWQ / GPTQ）
2. 使用 NVIDIA ModelOpt 离线校准
3. 生成量化 checkpoint
4. TRT-LLM 加载并按 recipe 选择 kernel

## 11. TokenizerManager

负责 prompt 的 tokenization 与生成 token 的 detokenization。

- 通常使用 HuggingFace Transformers tokenizer
- 支持 chat template、special tokens
- Triton backend 中由 `preprocessing` / `postprocessing` ensemble 处理

## 12. 服务化模块：trtllm-serve / OpenEngine / Triton

1.0 之后服务化入口有三条路径：

### trtllm-serve（推荐起点）

OpenAI 兼容服务，直接从模型引用启动：

```bash
trtllm-serve --model meta-llama/Llama-3.1-8B-Instruct --port 8000
```

1.3 起补齐 `/v1/responses` 与 Anthropic Messages API，支持多模态与流式输出。

### OpenEngine + NVIDIA Dynamo（分离式推荐）

[OpenEngine](https://github.com/ai-dynamo/openengine) 是 vendor-neutral 的 gRPC 契约，定义引擎角色（aggregated / prefill / decode）与容量元数据。TRT-LLM 1.3 起内置可选的 OpenEngine gRPC server，作为 sidecar 接入 [Dynamo](https://github.com/ai-dynamo/dynamo) 编排层：

- Dynamo Planner：按 SLA 自动伸缩 prefill / decode 实例
- KV 感知路由：按前缀命中把请求路由到持有 KV 的实例
- KV Block Manager（KVBM）：GPU → CPU → SSD 分层卸载
- NIXL：GPU 间 RDMA / NVLink 的 KV 零拷贝传输

### Triton backend（弃用中，存量维护）

经典模型仓库结构：

```
models/
├── ensemble/
├── preprocessing/
├── tensorrt_llm/
├── postprocessing/
└── tensorrt_llm_bls/
```

关键配置：

- `batching_strategy: inflight_fused_batching`
- `triton_max_batch_size`
- `max_queue_delay_microseconds`
- `decoupled_mode`

注意：NVIDIA 已于 2026 年将 `*-trtllm-python-py3` 容器标记弃用（PB 5.9 为最后版本，见 [EOL Notices](https://docs.nvidia.com/ai-enterprise/lifecycle/latest/eol-notices.html)），新部署不建议再选此路径。

## 13. trtllm-bench

TRT-LLM 自带的 benchmark 工具，用于测量：

- throughput（token/s）
- TTFT（time to first token）
- TPOT（time per output token）
- 不同 batch size / sequence length 下的性能

```bash
trtllm-bench --model <model> --mode <static> --batch_size <bs> --input_len <in> --output_len <out>
```

## 模块协作示例

一个 `generate()` 调用在模块间的流转：

```
LLM.generate(prompt)
  → TokenizerManager.encode(prompt)
  → Executor.submit(Request)
  → Scheduler.step() 选择 batch
  → KVCacheManager.prepare_resources()
  → ModelEngine.forward()
  → Decoder.step(logits)
  → KVCacheManager.update_resources()
  → Request.update()
  → 若完成 → TokenizerManager.decode(tokens)
  → 返回 Response
```

## 本章小结

TensorRT-LLM 的模块划分清晰：LLM API 做封装，Builder/Engine 做编译与执行计划，Executor/Scheduler/KVCacheManager（1.3 起 V2）做运行时调度，Decoder 与投机解码模块做采样加速，量化工具链覆盖 FP8/FP4/NVFP4/MXFP4，服务层以 `trtllm-serve` 与 OpenEngine/Dynamo 为主、Triton 进入维护期。1.2 后 TensorRT 后端被移除，PyTorchModelEngine 接管执行，但模块职责与交互关系保持稳定。

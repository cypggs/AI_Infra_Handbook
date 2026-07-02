# 2. 核心思想

## 一句话理解

> Triton 把“模型仓库 + 配置文件 + 后端抽象 + 调度器”拼成一条流水线：业务请求进来，先被路由到某个模型，再被调度器拼成 batch，最后交给对应 backend 执行并返回。

这条流水线有四个核心抽象：

1. **Model Repository（模型仓库）**：所有模型以固定目录结构存放，Triton 启动时自动扫描加载。
2. **`config.pbtxt`**：每个模型的“声明式配置”，定义输入输出、backend、instance group、调度策略等。
3. **Backend（后端）**：把请求真正翻译成模型推理的插件，Triton 支持 TensorRT、ONNX Runtime、PyTorch、Python、vLLM 等。
4. **Scheduler（调度器）**：决定如何把多个请求组合成 batch，包括 Dynamic Batching、Sequence Batching、Ensemble。

## Model Repository

Triton 对模型目录有严格的约定：

```text
model_repository/
├── classify/
│   ├── config.pbtxt
│   └── 1/
│       └── model.onnx
├── generate/
│   ├── config.pbtxt
│   └── 1/
│       └── model.plan
└── pipeline/
    └── config.pbtxt          # ensemble 模型可以只有配置
```

- 每个模型一个子目录。
- 子目录下必须包含 `config.pbtxt`。
- 数值模型通常还有一个版本子目录（如 `1/`），里面放真实的模型文件。
- Ensemble 模型可以没有版本目录，因为它只是对其他模型的编排。

这种结构让 Triton 可以在启动时自动发现模型，并按版本进行管理、加载和回滚。

## `config.pbtxt`

`config.pbtxt` 是 Triton 的核心配置入口，采用 Protocol Buffers 文本格式。一个典型配置如下：

```protobuf
name: "classify"
platform: "onnxruntime_onnx"
max_batch_size: 8
input [
  {
    name: "image"
    data_type: TYPE_FP32
    dims: [3, 224, 224]
  }
]
output [
  {
    name: "class"
    data_type: TYPE_INT64
    dims: [1]
  }
]
instance_group [
  {
    count: 2
    kind: KIND_GPU
    gpus: [0, 1]
  }
]
dynamic_batching {
  preferred_batch_size: [4]
  max_queue_delay_microseconds: 10000
}
```

关键字段的含义：

| 字段 | 作用 |
|---|---|
| `name` | 模型名，与目录名一致 |
| `platform` / `backend` | 指定后端类型，例如 `onnxruntime_onnx`、`tensorrt_plan`、`python`、`vllm` |
| `max_batch_size` | 该模型单次推理能接受的最大 batch size；`0` 表示不支持动态 batch |
| `input` / `output` | 输入输出张量的名称、数据类型、形状 |
| `instance_group` | 该模型启动几个实例、跑在 CPU 还是 GPU、绑定哪些 GPU |
| `dynamic_batching` | 开启动态 batching，设置 preferred batch size 与最大等待时间 |
| `sequence_batching` | 开启序列 batching，用于有状态模型（如对话） |
| `ensemble_scheduling` | 定义 ensemble 的执行步骤与输入输出映射 |
| `parameters` | 后端特定参数，例如 Python backend 的 `EXECUTION_ENV_PATH` |

## Backend 抽象

Backend 是 Triton 与具体推理引擎之间的接口。Triton 会把调度后的 batch 交给 backend，backend 负责把张量传给真实的 runtime 并取回结果。

常见 backend：

| Backend | 适用场景 |
|---|---|
| **TensorRT** | 极致性能的 CNN/Transformer，需要提前编译成 plan |
| **TensorRT-LLM** | NVIDIA GPU 上的大语言模型推理 |
| **ONNX Runtime** | 跨框架模型，支持 CPU/GPU |
| **PyTorch (LibTorch)** | TorchScript 模型 |
| **Python** | 自定义前后处理、embedding、reranker、实验模型 |
| **vLLM** | 通过 vLLM backend 把 vLLM 接入 Triton |
| **OpenVINO / TensorFlow / DALI** | 其他生态 |

Backend 的接口对上层调度器是透明的：调度器只关心“把输入张量传下去、把输出张量拿回来”。

## 调度器

Triton 提供三种主要调度策略：

### Dynamic Batching（动态批处理）

把短时间内到达的独立请求拼成一个 batch，以提高吞吐。关键参数：

- `preferred_batch_size`：希望组成的 batch size，可设置多个。
- `max_queue_delay_microseconds`：最大等待时间，超时即使没有凑够 batch 也会发出去。
- `preserve_ordering`：是否保证请求返回顺序与到达顺序一致。

适用于无状态的分类、embedding、OCR 等模型。

### Sequence Batching（序列批处理）

用于有状态模型，例如多轮对话。同一个 `correlation_id` 的多个请求必须按顺序交给同一个模型实例，模型内部维护 KV Cache 等状态。

关键参数：

- `correlation_id`：标识一个序列。
- `CONTROL_SEQUENCE_*`：控制序列的开始、结束、就绪。

### Ensemble（模型编排）

把多个模型按依赖图串联起来，例如：

```text
raw image -> preprocess -> inference -> postprocess -> final result
```

Ensemble 模型本身不执行 kernel，只负责张量在不同子模型之间的路由。它的 `config.pbtxt` 用 `ensemble_scheduling.step` 定义执行链。

## Business Logic Scripting（BLS）

BLS 允许 Python backend 在运行时调用其他模型。与 Ensemble 的区别：

- **Ensemble**：静态依赖图，在 `config.pbtxt` 里写死，适合固定流水线。
- **BLS**：动态逻辑，可以在 Python backend 中根据输入决定调用哪些模型、调用几次，适合条件分支、循环、重排序等。

## Metrics

Triton 原生输出 Prometheus 格式的指标，包括：

- `nv_inference_count`：请求总数。
- `nv_inference_latency`：端到端延迟。
- `nv_inference_compute_input` / `compute_infer` / `compute_output`：各阶段延迟。
- `nv_gpu_memory_used_bytes`：GPU 显存使用。
- `nv_queue_size`：动态 batcher 队列长度。

这些指标是生产监控、告警和自动扩缩的基础。

## 本章小结

Triton 的核心思想可以概括为：**用 model repository 解决“模型放哪里”，用 `config.pbtxt` 解决“怎么配置”，用 backend 解决“用什么引擎跑”，用 scheduler 解决“怎么拼 batch”**。四个抽象彼此解耦，使得同一个服务进程可以承载多种模型、多种框架、多种调度策略。

**参考来源**

- [Triton User Guide — Model Configuration](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/model_configuration.html)
- [Triton User Guide — Model Repository](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/model_repository.html)
- [Triton User Guide — Dynamic Batching](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/model_configuration.html#dynamic-batcher)
- [Triton User Guide — Business Logic Scripting](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/business_logic_scripting.html)
- [Triton User Guide — Metrics](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/metrics.html)

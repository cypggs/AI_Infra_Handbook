# 7. 工程实践：Mini Triton

本章实现一个纯 Python 的 Mini Triton Inference Server，用于理解 **Model Repository → `config.pbtxt` → Backend → Scheduler → HTTP 服务** 的完整链路。

## 为什么用纯 Python 模拟？

真实的 Triton 需要：

- `tritonserver` C++ 二进制。
- GPU backend 共享库（TensorRT、ONNX Runtime CUDA、vLLM 等）。
- Linux 环境（macOS 上无法直接运行）。

当前环境是 macOS / CPU，因此 Mini Demo 用纯 Python + NumPy 模拟服务层核心逻辑。它不依赖 `tritonserver`，但保留了真实的模块划分与接口命名。

## 设计目标

- 不依赖 GPU，CPU 即可运行。
- 代码控制在 1000~1500 行。
- 展示模型仓库加载、`config.pbtxt` 解析、backend 注册表、dynamic batching、ensemble 调度、HTTP 入口、Prometheus 风格指标。
- 通过 pytest 验证核心逻辑。

## 目录结构

```
mini-demo/
├── README.md
├── pyproject.toml
├── triton_mini/
│   ├── __init__.py
│   ├── model_repository.py   # 模型仓库加载
│   ├── config_parser.py      # config.pbtxt 简化解析器
│   ├── backend.py            # Backend 注册表与 mock backend
│   ├── scheduler.py          # Dynamic Batcher / Default Scheduler
│   ├── ensemble.py           # Ensemble 执行链
│   ├── server.py             # HTTP/gRPC 服务入口模拟
│   ├── metrics.py            # Prometheus 风格指标
│   └── demo.py               # 入口演示
└── tests/
    ├── test_config_parser.py
    ├── test_dynamic_batching.py
    └── test_ensemble.py
```

## 核心设计

### 1. 模型仓库加载

`ModelRepository.load()` 扫描目录，对每个包含 `config.pbtxt` 的子目录：

1. 用 `ConfigParser` 解析配置。
2. 根据 `backend` / `platform` 从 `BackendRegistry` 创建 backend。
3. 根据 `dynamic_batching` / `ensemble_scheduling` 创建 scheduler。

### 2. Config Parser

实现了一个简化版 `config.pbtxt` 解析器，支持：

- 标量字段：`name: "classify"`、`max_batch_size: 8`
- 列表字段：`dims: [-1, 3, 224, 224]`
- 消息字段：`dynamic_batching { ... }`
- 重复消息块：`input [ { ... }, { ... } ]`
- 映射字段：`input_map { key: "raw" value: "raw" }`

### 3. Backend 注册表

内置 mock backend：

| Backend | 作用 |
|---|---|
| `IdentityBackend` | 用于 ensemble 中的前后处理步骤 |
| `ClassificationBackend` | 模拟分类模型，输出 class 与 logits |
| `LLMBackend` | 模拟 vLLM / TensorRT-LLM，输出 next token |
| `ONNXRuntimeBackend` | 模拟线性投影 |

Backend 对上层完全透明：`execute(inputs, config) -> outputs`。

### 4. Dynamic Batcher

`DynamicBatcher.schedule(requests)` 把请求按以下规则分组：

- 优先满足 `preferred_batch_size`。
- 不超过 `max_batch_size`。
- 只把输入形状兼容的请求放进同一个 batch。
- 超过 `max_queue_delay_microseconds` 的请求会被强制 flush。

### 5. Ensemble Scheduler

`EnsembleScheduler` 维护一个张量池：

1. 用请求输入初始化张量池。
2. 按 `ensemble_scheduling.step` 依次执行子模型。
3. 用 `input_map` / `output_map` 在张量池与子模型之间搬运张量。
4. 最终从张量池提取 ensemble 的输出。

### 6. HTTP 入口

`TritonServer` 提供：

- `infer(model_name, inputs)`：单个请求推理。
- `infer_batch(model_name, inputs_list)`：批量请求推理，演示 dynamic batching。
- `serve_http()`：基于 `http.server` 的 `/v2/models/{name}/infer` 与 `/metrics` 端点。

### 7. Metrics

`MetricsCollector` 记录：

- `triton_mini_inference_count`：请求总数。
- `triton_mini_inference_latency_microseconds`：延迟直方图。
- `triton_mini_batch_size`：batch size 分布。

输出格式与 Prometheus 兼容。

## 运行方式

```bash
cd docs/04-llmops/triton/mini-demo
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m triton_mini.demo
pytest tests/
```

## 预期输出

```text
Built temporary model repository at: /tmp/triton_mini_repo_xxx
Loaded models: ['classify', 'generate', 'pipeline', 'postprocess', 'tokenize']

=== Demo 1: Dynamic Batching on classify ===
Sent 5 individual requests
  Request 0: class=0
  Request 1: class=0
  Request 2: class=0
  Request 3: class=0
  Request 4: class=0

=== Demo 2: Dynamic Batching on generate (vLLM backend) ===
Sent 6 prompts
  Prompt 0: next_token=60
  Prompt 1: next_token=44
  ...

=== Demo 3: Ensemble pipeline (tokenize -> generate -> postprocess) ===
  Ensemble output: final=53

=== Metrics ===
# HELP triton_mini_inference_count ...
...
```

## 与真实 Triton 的差异

| 维度 | Mini Demo | 真实 Triton Inference Server |
|---|---|---|
| 核心语言 | Python | C++ |
| Backend | mock Python 函数 | TensorRT、ONNX、PyTorch、Python、vLLM 等共享库 |
| 网络协议 | 模拟 HTTP/JSON | HTTP/REST、gRPC、C API |
| 调度 | 单线程教学级 | 多线程、多实例、Rate Limiter |
| 显存管理 | 无 | CUDA / pinned / shared memory 池 |
| 生产特性 | 无 | Model Analyzer、Tracing、热更新、Warmup |

## 完整代码

完整代码与运行说明见 [mini-demo/README.md](./mini-demo/README.md)。

## 本章小结

Mini Demo 的价值不在于性能，而在于把 Triton 的“仓库-配置-后端-调度”四层抽象用可运行的代码展现出来。通过 `ConfigParser`、`BackendRegistry`、`DynamicBatcher`、`EnsembleScheduler` 与 `TritonServer`，读者可以直观理解 Triton 的核心设计思想。

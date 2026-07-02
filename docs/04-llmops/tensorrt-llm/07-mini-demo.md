# 7. 工程实践：Mini TensorRT-LLM

本章实现一个纯 Python 的 Mini TensorRT-LLM，用于理解 **Builder → Engine → Runtime → Executor** 的完整链路，以及 **In-flight Batching** 的调度思想。

## 为什么用纯 Python 模拟？

真实的 TensorRT-LLM 需要：

- NVIDIA GPU
- TensorRT / PyTorch with CUDA
- 大量 CUDA kernel 与编译依赖

当前环境是 macOS / CPU，因此 Mini Demo 用纯 Python + NumPy 模拟核心流程。它不 import `tensorrt` 或 `tensorrt_llm`，但保留了真实 TRT-LLM 的模块划分与接口命名。

## 设计目标

- 不依赖 GPU，CPU 即可运行
- 代码控制在 800~1500 行
- 展示模型定义、Builder 编译、Engine 序列化、Runtime 单请求推理、Executor 多请求 IFB 调度
- 展示 Plugin 注册与替换、Quantization 配置
- 通过 pytest 验证核心逻辑

## 目录结构

```
mini-demo/
├── README.md
├── pyproject.toml
├── tensorrt_llm_mini/
│   ├── __init__.py
│   ├── model.py          # 简化 Module / Linear / Attention / GPT
│   ├── builder.py        # Builder：编译模型 + 量化 + plugin 替换
│   ├── engine.py         # Engine：可序列化的执行计划
│   ├── plugin.py         # PluginBase + 注册表 + mock plugin
│   ├── quantization.py   # QuantConfig / fake quantize
│   ├── runtime.py        # Runtime：单请求 prefill/decode
│   ├── executor.py       # Executor + Scheduler + IFB
│   ├── dummy_backend.py  # NumPy CPU 后端
│   └── demo.py           # 入口演示
└── tests/
    ├── test_builder.py
    ├── test_executor.py
    └── test_plugin.py
```

## 核心设计

### 1. Model API

用极小的维度定义一个玩具 GPT：

```python
class Linear(Module):
    def __init__(self, in_features, out_features):
        self.weight = np.random.randn(out_features, in_features).astype(np.float32) * 0.01
        self.bias = np.zeros(out_features, dtype=np.float32)
```

`Attention` 用简单的点积 attention + 缓存，`TransformerBlock` 堆叠 attention 与 FFN。

### 2. Plugin 机制

定义 `PluginBase` 与 `@trtllm_plugin(name)` 装饰器。Builder 在遍历模型时，如果匹配到可替换的子图，就用注册 plugin 替换原 op。Demo 中提供两个 mock plugin：

- `GELUPlugin`：替换 FFN 中的 GELU 激活
- `LookupPlugin`：替换 embedding lookup

### 3. Builder

`Builder.build(model, build_config)` 返回 `Engine`：

1. 遍历模型模块，建立执行图
2. 根据 `quant_config` 对权重做 fake quantize
3. 根据 `plugin_registry` 替换匹配子图
4. 将图、权重、plugin map、配置打包进 `Engine`

### 4. Engine

`Engine` 是可序列化的 dataclass：

```python
@dataclass
class Engine:
    graph: List[Op]
    weights: Dict[str, np.ndarray]
    plugin_map: Dict[str, PluginBase]
    quant_config: QuantConfig
    build_config: BuildConfig
```

支持 `serialize()` / `deserialize()`。

### 5. Runtime

`Runtime.generate(prompt_ids, max_tokens)`：

1. prefill：对 prompt 做一次完整 forward，得到第一个 token
2. decode：循环 forward，每次生成一个新 token，直到满足停止条件

### 6. Executor + IFB Scheduler

`Executor` 维护三个队列：waiting / running / finished。

每轮 `step()`：

1. `Scheduler.schedule()` 优先选 generation-phase 请求，再填 context-phase
2. `ModelEngine.forward()` 执行当前 batch
3. `Decoder` 采样
4. 更新请求状态，完成的移入 finished

### 7. Dummy Backend

使用 NumPy 实现线性、softmax、attention 等基础算子。权重随机但固定 seed，保证可复现。

## 运行方式

```bash
cd docs/04-llmops/tensorrt-llm/mini-demo
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m tensorrt_llm_mini.demo
pytest tests/
```

## 预期输出

```
=== Demo 1: Build Engine and Single Request ===
Building tiny GPT engine ...
Plugin replaced: GELUPlugin at block.0.ffn.gelu
Prompt: The capital of France is
Generated: The capital of France is ...

=== Demo 2: Executor with In-flight Batching ===
[Step 0] context=[req-A(10), req-B(5)], generation=[]
[Step 1] context=[req-C(8)], generation=[req-A, req-B]
[Step 2] context=[], generation=[req-A, req-B, req-C]
...
[Done] 3 requests finished
```

## 与真实 TensorRT-LLM 的差异

| 维度 | Mini Demo | 真实 TRT-LLM |
|---|---|---|
| 后端 | NumPy CPU | CUDA / TensorRT / PyTorch |
| 模型规模 | 玩具维度 | 数十亿参数 |
| attention | 简单点积 | FlashAttention / paged attention |
| 量化 | fake quantize | FP8/FP4 kernel、校准 |
| plugin | mock Python 函数 | CUDA / Triton kernel |
| IFB | 单线程调度 | 多 rank / 异步执行 |

## 完整代码

完整代码详见 [mini-demo/README.md](./mini-demo/README.md)。

## 本章小结

Mini Demo 的价值不在于性能，而在于把 TensorRT-LLM 的“构建-执行-调度”三层抽象用可运行的代码展现出来。通过 Builder、Engine、Runtime、Executor 四个类，读者可以直观理解 TRT-LLM 的核心设计思想。

# 6. 源码分析

本章梳理 TensorRT-LLM 的 GitHub 仓库目录结构与关键调用链，帮助读者在需要深入源码时快速定位。

## 仓库概览

```
TensorRT-LLM/
├── tensorrt_llm/            # Python 包
│   ├── __init__.py          # LLM, SamplingParams 等入口
│   ├── llmapi/              # LLM API、BuildConfig、SamplingParams
│   ├── _torch/              # PyTorch 后端（1.0+ 默认）
│   │   ├── models/          # 各模型定义（Llama、Qwen、DeepSeek 等）
│   │   ├── pyexecutor/      # PyExecutor、ModelEngine、Scheduler
│   │   ├── attention/       # Attention backend
│   │   ├── custom_ops/      # PyTorch custom ops / Triton kernels
│   │   └── deployment/      # 部署相关工具
│   ├── executor.py          # C++ Executor Python binding
│   ├── runtime/             # 历史 Runtime Session（TensorRT 时代）
│   ├── plugin.py            # Plugin 注册基类
│   ├── quantization/        # 量化工具
│   └── mapping.py           # TP/PP 映射
├── cpp/                     # C++ / CUDA 核心
│   └── tensorrt_llm/
│       ├── executor/        # C++ Executor 实现
│       ├── kernels/         # CUDA kernels
│       ├── layers/          # 层实现
│       └── runtime/         # 历史 TensorRT runtime
├── examples/                # 使用示例
├── tests/                   # 测试
├── triton_backend/          # Triton Inference Server backend
├── benchmarks/              # benchmark 脚本
└── docs/                    # 文档源码
```

## Python 侧关键调用链

### 1. `LLM.generate()` 入口

```
tensorrt_llm/__init__.py
  LLM 类导出
    → tensorrt_llm/llmapi/llm.py
      LLM.__init__()
        → _build_engine() / _load_engine()
        → 初始化 PyExecutor / TokenizerManager
      LLM.generate(prompts, sampling_params)
        → _generate_async() / _generate_sync()
          → executor.submit(requests)
          → 等待 responses
```

### 2. PyExecutor 主循环

```
tensorrt_llm/_torch/pyexecutor/py_executor.py
  PyExecutor.__init__()
    → 创建 ModelEngine、Scheduler、KVCacheManager、Decoder
  PyExecutor.start()
    → 启动后台线程 / 进程
  PyExecutor._run_loop()
    → fetch_requests()
    → scheduler.step()
    → model_engine.forward(scheduler_output)
    → decoder.step(model_output)
    → update_requests()
```

### 3. Scheduler

```
tensorrt_llm/_torch/pyexecutor/scheduler.py
  CapacityScheduler.step()
    → 检查 KV cache、batch size、token budget
  MicroBatchScheduler.step()
    → 优先 generation-phase
    → 填充 context-phase（含 chunked prefill）
```

### 4. ModelEngine Forward

```
tensorrt_llm/_torch/pyexecutor/model_engine.py
  PyTorchModelEngine.__init__()
    → 加载模型权重
    → 应用 torch.compile / CUDA Graph
  PyTorchModelEngine.forward(scheduler_output)
    → prepare_inputs()
    → model(**inputs)
    → 返回 logits
```

### 5. Decoder

```
tensorrt_llm/_torch/pyexecutor/decoder.py
  Decoder.__init__()
    → 根据 SamplingParams 选择采样策略
  Decoder.step(logits)
    → 应用 temperature / top-k / top-p
    → 输出下一个 token id
```

### 6. KVCacheManager

```
tensorrt_llm/_torch/pyexecutor/kv_cache_manager.py
  KVCacheManager.prepare_resources()
    → 分配 / 复用 KV cache block
  KVCacheManager.update_resources()
    → 更新 block table
  KVCacheManager.free_resources()
    → 释放完成请求的 block
```

## C++ 侧关键目录

### `cpp/tensorrt_llm/executor/`

C++ Executor 是 Triton backend 与高性能 Python binding 的底层：

| 文件 | 作用 |
|---|---|
| `executor.cpp` | `Executor` 类接口 |
| `executorImpl.cpp` | 实现细节：请求队列、调度、执行 |
| `schedulerConfig.cpp` | 调度器配置 |
| `kvCacheConfig.cpp` | KV cache 配置 |
| `samplingConfig.cpp` | 采样配置 |
| `request.cpp` / `response.cpp` | 请求/响应数据结构 |
| `cache_transmission/` | 分离式服务 KV 传输 |

### `cpp/tensorrt_llm/kernels/`

自定义 CUDA kernel，包括：

- `decoderMaskedMultiheadAttention/`：解码期 attention
- `flashForward/`: FlashAttention 相关
- `mixtureOfExperts/`: MoE kernel
- `quantization/`: 量化/反量化 kernel

## 历史 TensorRT 后端源码路径（1.2 之前）

虽然 1.2 已移除 TensorRT 后端，但了解历史路径有助于理解设计：

```
tensorrt_llm/
├── builder.py              # Builder API
├── runtime/                # Runtime Session
│   ├── generation_session.py
│   └── model_runner.py
├── models/                 # 模型定义（Llama、GPT 等）
│   └── llama/
│       └── model.py
└── plugin/                 # Plugin 注册
```

关键历史调用链：

```
Builder().create_network()
  → model = LlamaForCausalLM(config)
  → model.forward(...)  # 构建 TensorRT network
  → builder.build_engine(network, builder_config)
  → 序列化 .engine 文件

Runtime.Session(engine_file)
  → session.run(inputs)
```

## 源码阅读建议

1. **先读 `tensorrt_llm/llmapi/llm.py`**：理解用户入口与生命周期。
2. **再读 `tensorrt_llm/_torch/pyexecutor/py_executor.py`**：理解 Executor 主循环。
3. **深入 `model_engine.py`、`scheduler.py`、`kv_cache_manager.py`**：理解执行、调度、显存管理。
4. **按需查看 `cpp/tensorrt_llm/executor/`**：理解 C++ 侧调度与高性能路径。
5. **参考 `examples/`**：学习真实模型 build 与 serving 写法。

## 本章小结

TensorRT-LLM 的源码结构清晰：Python 侧提供易用 API，`_torch` 目录承载 PyTorch 后端核心，`cpp/executor` 提供高性能 C++ 执行层。理解 `LLM → PyExecutor → Scheduler → ModelEngine → Decoder → KVCacheManager` 的调用链，就能快速定位大多数问题。

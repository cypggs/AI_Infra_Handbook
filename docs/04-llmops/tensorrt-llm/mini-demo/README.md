# Mini TensorRT-LLM

一个纯 Python 的 TensorRT-LLM 教学模拟，用于理解 **Builder → Engine → Runtime → Executor** 的完整链路，以及 **In-flight Batching（IFB）** 的调度思想。

## 环境要求

- Python >= 3.10
- NumPy
- 无需 NVIDIA GPU，无需安装 `tensorrt` 或 `tensorrt_llm`

## 安装

```bash
cd docs/04-llmops/tensorrt-llm/mini-demo
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## 运行 Demo

```bash
python -m tensorrt_llm_mini.demo
```

预期输出：

```
Building tiny GPT engine ...
Engine summary: {...}

=== Demo 1: Runtime single-request generation ===
Prompt ids:   [1, 2, 3, 4, 5]
Generated ids: [...]

=== Demo 2: Executor with In-flight Batching ===
[Step 01] context=[req-A,req-B,req-C], generation=[-], scheduled=3
[Step 02] context=[], generation=[req-A,req-B,req-C], scheduled=3
...
Finished responses:
  req-A: [...]
```

## 运行测试

```bash
pytest tests/
```

## 模块说明

| 文件 | 作用 |
|---|---|
| `model.py` | 玩具 GPT 模型定义，生成符号执行图 |
| `builder.py` | Builder：编译模型、量化、plugin 替换 |
| `engine.py` | 可序列化的 Engine（plan） |
| `plugin.py` | PluginBase、注册表、mock plugin |
| `quantization.py` | QuantConfig、fake quantize |
| `runtime.py` | Runtime：单请求 prefill/decode |
| `executor.py` | Executor + IFB Scheduler |
| `dummy_backend.py` | NumPy CPU 算子后端 |
| `demo.py` | 入口演示 |

## 与真实 TensorRT-LLM 的区别

- 本 Demo 使用 NumPy CPU 后端，真实 TRT-LLM 使用 CUDA / TensorRT / PyTorch GPU。
- attention、layer norm 等做了极大简化，仅保留概念。
- 量化使用 fake quantize，真实 TRT-LLM 使用 FP8/FP4 kernel 与校准。
- Plugin 是 Python 函数，真实 TRT-LLM 的 plugin 是 CUDA / Triton kernel。
- Executor 是单线程模拟，真实 TRT-LLM 是多 rank 异步执行。

## 许可证

与主项目一致：CC-BY-SA-4.0

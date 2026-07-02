# Mini Triton Inference Server

一个纯 Python 的 Triton Inference Server 教学实现，**不依赖 `tritonserver` 二进制或 GPU**，可在 macOS / CPU 上直接运行。

## 覆盖的核心概念

- **Model Repository**：目录结构与模型加载
- **`config.pbtxt` 解析**：`max_batch_size`、`input/output`、`instance_group`、`dynamic_batching`、`ensemble_scheduling`、`parameters`
- **Backend 抽象**：Python / ONNX Runtime / TensorRT-LLM / vLLM 的 mock backend
- **调度器**：
  - Dynamic Batching：按 `preferred_batch_size` 和 `max_queue_delay_microseconds` 组 batch
  - Ensemble Scheduling：按依赖图串联 preprocessing → inference → postprocessing
- **HTTP 服务入口**：模拟 Triton 的 `/v2/models/{name}/infer`
- **Metrics**：Prometheus 风格的请求数、延迟、batch size 直方图

## 运行方式

```bash
cd docs/04-llmops/triton/mini-demo
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m triton_mini.demo
pytest tests/
```

## 与真实 Triton 的差异

| 维度 | Mini Demo | 真实 Triton Inference Server |
|---|---|---|
| 运行方式 | 纯 Python | C++ core + backend shared libraries |
| Backend | mock Python 函数 | TensorRT、ONNX Runtime、PyTorch、Python 等 |
| 网络协议 | 模拟 HTTP/JSON | HTTP/REST、gRPC、C API |
| 调度 | 单线程、教学级 | 多线程、多实例、序列 batching、Rate Limiter |
| 显存管理 | 无 | CUDA / shared memory / system memory 池 |
| 生产功能 | 无 | Model Analyzer、Metrics、Tracing、Warmup、模型热更新 |

本 Demo 的价值在于把 Triton 的“仓库-配置-后端-调度”四层抽象用可运行代码展现出来，便于理解其设计思想。

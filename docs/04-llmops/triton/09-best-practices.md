# 9. 最佳实践

## 什么时候选 Triton？

| 场景 | 推荐方案 |
|---|---|
| 单一 LLM 模型，快速上线，团队规模小 | 裸部署 vLLM / SGLang，或 Triton vLLM backend |
| 多模型、多框架、需要统一入口与监控 | **Triton Inference Server** |
| 极致 NVIDIA GPU 性能，模型固定 | TensorRT-LLM backend |
| 强 Kubernetes 生态，需要自动扩缩与 A/B 测试 | KServe + Triton runtime |
| 高度自定义路由、计费、权限 | 自研网关 + Triton 作为 backend 层 |

## Backend 选择

| Backend | 延迟 | 吞吐 | 灵活性 | 适用模型 |
|---|---|---|---|---|
| TensorRT / TensorRT-LLM | 最低 | 最高 | 低 | 已优化的 CNN / Transformer / LLM |
| ONNX Runtime | 低 | 高 | 中 | 跨框架导出的模型 |
| PyTorch (LibTorch) | 中 | 中 | 高 | TorchScript 模型 |
| Python | 中-高 | 中 | 最高 | 前后处理、embedding、reranker、实验模型 |
| vLLM | 低 | 高 | 高 | 通用 LLM |

建议：

- 性能核心路径优先用 TensorRT-LLM / TensorRT。
- 快速迭代与实验模型用 vLLM 或 Python backend。
- 前后处理、embedding、reranker 用 Python backend。
- 跨团队共享模型时，用 ONNX Runtime 降低框架依赖。

## Instance Group 配置

```protobuf
instance_group [
  {
    count: 2
    kind: KIND_GPU
    gpus: [0]
  }
]
```

- **count 不是越大越好**：每个实例都占用一份模型权重显存，LLM 模型复制两份会显著增加 OOM 风险。
- **多卡场景**：用 `gpus` 指定实例分布在哪些 GPU 上，避免所有实例挤在一张卡。
- **CPU backend**：`kind: KIND_CPU`，适合小模型或前后处理。
- **结合 Model Analyzer**：通过自动搜索确定最优 count。

## Dynamic Batching 调优

关键参数：

- `preferred_batch_size`：通常设置为能使 GPU 饱和的最小 batch。
- `max_queue_delay_microseconds`：在线服务建议 100us~10ms；离线批量可以更大。
- `max_batch_size`：不能超过 backend 与 GPU 显存能承受的上限。

调优步骤：

1. 先跑单请求测延迟基线。
2. 逐步提高 `preferred_batch_size`，观察吞吐提升与延迟增长。
3. 当延迟超过 SLA 时，停止增加 batch size。
4. 用 `max_queue_delay_microseconds` 控制最大等待时间，避免小流量时延迟抖动。

**注意**：vLLM / TensorRT-LLM backend 内部已有 batching，Triton 层通常关闭 dynamic batching。

## 显存与内存管理

- **预留余量**：不要把 `gpu_memory_utilization` 设到 1.0，建议 0.85~0.9。
- **KV Cache 控制**：LLM 的 KV cache 是显存大户，通过 backend 参数限制最大 token 数。
- **Pinned Memory**：为 CPU ↔ GPU 传输配置足够的锁页内存。
- **Shared Memory**：同一节点上的客户端与 Triton 进程可通过 shared memory 零拷贝传输大张量。

## 模型版本管理

- 使用显式版本目录（`1/`、`2/`），避免用 `latest` 链接。
- 生产环境使用 `--model-control-mode=explicit`，通过 CI/CD 调用 load/unload API。
- 旧版本保留一段时间，便于快速回滚。

## 可观测性

- 必须接入 Prometheus + Grafana。
- 关注 `nv_inference_queue_duration_us`：queue 时间长说明 batch 没凑够或实例不足。
- 关注 `nv_inference_compute_infer`：这是 backend 真实推理耗时。
- 对 LLM 服务，额外关注 **TTFT（首 token 延迟）** 与 **TPOT（逐 token 延迟）**。

## 安全与隔离

- 使用 Docker / Kubernetes 资源限制防止一个模型拖垮整台机器。
- 对多租户场景，考虑按业务拆分 Triton 实例，避免共享显存导致的信息泄露。
- HTTP/gRPC 入口前置 API Gateway，统一做认证、限流、审计。

## 典型 LLM 生产配置示例

```protobuf
name: "llama3-8b"
backend: "vllm"
max_batch_size: 0          # vLLM 内部已有 batching
input [
  {
    name: "text_input"
    data_type: TYPE_STRING
    dims: [-1]
  }
]
output [
  {
    name: "text_output"
    data_type: TYPE_STRING
    dims: [-1]
  }
]
instance_group [
  {
    count: 1
    kind: KIND_GPU
    gpus: [0]
  }
]
parameters: {
  key: "model"
  value: { string_value: "meta-llama/Meta-Llama-3-8B-Instruct" }
}
parameters: {
  key: "gpu_memory_utilization"
  value: { string_value: "0.9" }
}
parameters: {
  key: "max_model_len"
  value: { string_value: "8192" }
}
```

## 本章小结

Triton 的最佳实践围绕**选择合适的 backend、合理配置 instance group 与 batching、严格控制显存、做好可观测性**展开。它不是一个“开箱即用”的系统，而是一个需要结合业务负载、GPU 容量、延迟 SLA 进行调优的服务平台。

**参考来源**

- [Triton Model Analyzer](https://github.com/triton-inference-server/model_analyzer)
- [Triton Performance Tuning](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/optimization.html)
- [Triton Model Configuration](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/model_configuration.html)
- [Triton Dynamic Batcher](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/model_configuration.html#dynamic-batcher)

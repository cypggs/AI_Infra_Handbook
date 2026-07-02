# 8. 企业生产实践

## Docker 部署

NVIDIA 提供官方 NGC 镜像，是生产部署的首选：

```bash
docker run --gpus all --rm -p 8000:8000 -p 8001:8001 -p 8002:8002 \
  -v $(pwd)/model_repository:/models:ro \
  nvcr.io/nvidia/tritonserver:24.05-py3 \
  tritonserver --model-repository=/models
```

端口说明：

- `8000`：HTTP/REST。
- `8001`：gRPC。
- `8002`：Metrics（Prometheus）。

对于 LLM 场景，通常使用带 backend 的专用镜像：

- `nvcr.io/nvidia/tritonserver:24.05-trtllm-python-py3`：含 TensorRT-LLM backend。
- `nvcr.io/nvidia/tritonserver:24.05-vllm-python-py3`：含 vLLM backend。

## Kubernetes / KServe 集成

KServe 把 Triton 作为 runtime 之一，通过 `InferenceService` 直接部署：

```yaml
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: my-model
spec:
  predictor:
    triton:
      storageUri: s3://my-bucket/model-repository
      runtime: kserve-tritonserver
      env:
        - name: OMP_NUM_THREADS
          value: "1"
```

生产建议：

- 使用 KServe 的 `storageUri` 把模型仓库放在 S3 / GCS，Triton 启动时自动拉取。
- 配置 HPA 基于 GPU 利用率或自定义 metrics（如 queue size）自动扩缩。
- 为 Triton 容器配置 `resources.limits.nvidia.com/gpu`。
- 使用 `readinessProbe` 与 `livenessProbe` 检查 `/v2/health/ready`。

## TensorRT-LLM Backend 配置要点

TensorRT-LLM backend 的 model repository 通常包含：

```text
tensorrt_llm/
├── config.pbtxt
└── 1/
    └── config.json          # 构建期生成的引擎配置
```

关键 `config.pbtxt` 参数：

```protobuf
backend: "tensorrtllm"
max_batch_size: 64
input [
  { name: "input_ids" data_type: TYPE_INT32 dims: [-1] }
]
output [
  { name: "output_ids" data_type: TYPE_INT32 dims: [-1] }
]
parameters: {
  key: "max_beam_width"
  value: { string_value: "1" }
}
parameters: {
  key: "max_tokens_in_paged_kv_cache"
  value: { string_value: "8192" }
}
```

注意事项：

- 引擎文件需要在相同 GPU 架构上构建。
- TensorRT-LLM backend 内部已经实现了 In-flight Batching，因此 Triton 层通常**不需要再开 dynamic batching**。
- 通过 `parameters` 控制 KV cache 大小、beam width、end id 等。

## vLLM Backend 配置要点

vLLM backend 把 vLLM 的 `LLMEngine` 封装为 Triton backend：

```protobuf
backend: "vllm"
max_batch_size: 64
input [
  { name: "text_input" data_type: TYPE_STRING dims: [-1] }
]
output [
  { name: "text_output" data_type: TYPE_STRING dims: [-1] }
]
parameters: {
  key: "model"
  value: { string_value: "meta-llama/Meta-Llama-3-8B-Instruct" }
}
parameters: {
  key: "gpu_memory_utilization"
  value: { string_value: "0.9" }
}
```

vLLM backend 与 TensorRT-LLM backend 的关键区别：

| 维度 | TensorRT-LLM backend | vLLM backend |
|---|---|---|
| 构建方式 | 需要提前 build engine | 直接加载 HuggingFace checkpoint |
| 性能 | NVIDIA GPU 上通常更优 | 通用场景高吞吐 |
| 灵活性 | 受支持的模型/算子约束 | 更高，支持新模型更快 |
| 适用场景 | 性能敏感、模型固定的生产环境 | 快速上线、模型迭代频繁 |

## 多模型并发与资源隔离

在一张 GPU 上同时部署多个模型时，需要注意：

- **显存预算**：LLM 模型会占用大量显存，给其他模型预留空间。
- **Instance Group**：为每个模型设置合理的实例数，避免互相抢占。
- **Rate Limiter**：限制每个模型占用的资源配额，防止一个模型把 GPU 占满。
- **MPS（Multi-Process Service）**：在 A100/H100 上可以通过 MPS 提高多模型并发效率。

## 模型热更新

Triton 支持两种热更新模式：

1. **Poll 模式**：

   ```bash
   tritonserver --model-repository=/models --model-control-mode=poll --repository-poll-secs=30
   ```

   Triton 每 30 秒扫描一次仓库，自动加载新模型、卸载删除的模型、更新修改的版本。

2. **Explicit 模式**：

   ```bash
   tritonserver --model-repository=/models --model-control-mode=explicit
   ```

   通过 HTTP/gRPC API 显式加载/卸载：

   ```bash
   curl -X POST http://localhost:8000/v2/repository/models/my_model/load
   curl -X POST http://localhost:8000/v2/repository/models/my_model/unload
   ```

生产推荐 explicit 模式，避免 poll 带来的意外变更。

## A/B 测试与金丝雀

Triton 通过**版本控制**支持简单的 A/B 测试：

```text
my_model/
├── config.pbtxt
├── 1/          # 旧版本
└── 2/          # 新版本
```

- 默认流量到最新版本（2）。
- 通过 `/v2/models/my_model/versions/1/infer` 保留旧版本入口。

更复杂的金丝雀需要在 Triton 前置一个网关（如 Nginx、Envoy、KServe Transformer）按权重分发流量。

## 监控与告警

### Prometheus 抓取

```yaml
scrape_configs:
  - job_name: triton
    static_configs:
      - targets: ["triton:8002"]
```

### 关键告警规则

| 指标 | 告警条件 |
|---|---|
| `nv_inference_queue_duration_us` > 100ms | batch 没凑够或实例不足 |
| `nv_gpu_memory_used_bytes / nv_gpu_memory_total_bytes` > 0.9 | 显存不足 |
| `nv_inference_compute_infer` P99 > SLA | 推理延迟超标 |
| `nv_inference_count` 突降 | 流量异常或模型失败 |
| `rate(nv_inference_exec_count[5m]) == 0` | 某个模型无请求，可能配置错误 |

### Grafana Dashboard

NVIDIA 提供官方 Triton Grafana dashboard 模板，可直接导入。

## 常见踩坑

1. **输入 shape 不匹配**：
   - 客户端发送的 shape 必须与 `config.pbtxt` 一致，包括 batch 维度。
   - 使用 `-1` 表示可变维度时，仍需保证同一个 batch 内 shape 兼容。

2. **Backend 共享库缺失**：
   - 启动时报 `unable to load backend`，通常是镜像未包含对应 backend。
   - LLM 场景务必使用 `trtllm` 或 `vllm` 专用镜像。

3. **显存 OOM**：
   - LLM 的 KV cache 会随 batch size 与序列长度增长，需要预留足够余量。
   - 通过 `gpu_memory_utilization`（vLLM）或 `max_tokens_in_paged_kv_cache`（TRT-LLM）控制。

4. **Dynamic Batching 与 LLM backend 冲突**：
   - vLLM / TensorRT-LLM backend 内部已经有 continuous/in-flight batching。
   - 在 Triton 层再开 dynamic batching 可能导致 batch 被错误拆分，通常建议 `max_batch_size: 0` 或关闭 dynamic batching。

5. **模型版本未更新**：
   - 新模型放入 `2/` 目录后，Triton 不会自动切换，除非启用 poll 或调用 load API。

6. **Python backend 依赖冲突**：
   - Python backend 运行在独立子进程中，依赖通过 `parameters: { key: "EXECUTION_ENV_PATH" value: { string_value: "/path/to/env.tar.gz" } }` 指定。

## 本章小结

生产部署 Triton 的核心是：**选对镜像、写好 `config.pbtxt`、合理配置 instance group 与调度策略、做好监控与热更新**。对于 LLM 场景，特别要注意 LLM backend 内部已经有 batching，不要在 Triton 层重复启用 dynamic batching，同时要严格控制显存预算。

**参考来源**

- [Triton NGC Container](https://catalog.ngc.nvidia.com/orgs/nvidia/containers/tritonserver)
- [Triton User Guide — Deploying on Kubernetes](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/kubernetes_deploy.html)
- [Triton TensorRT-LLM Backend](https://github.com/triton-inference-server/tensorrtllm_backend)
- [Triton vLLM Backend](https://github.com/triton-inference-server/vllm_backend)
- [KServe Triton Runtime](https://kserve.github.io/website/latest/modelserving/v1beta1/triton/)
- [Triton Metrics](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/metrics.html)

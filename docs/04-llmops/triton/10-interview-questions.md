# 10. 面试题

## 初级

### Q1：Triton Inference Server 的核心定位是什么？它与 vLLM、TensorRT-LLM 有什么区别？

**参考答案**：

Triton 是多框架推理服务的统一入口，负责模型管理、请求路由、调度、协议转换和可观测性。vLLM、TensorRT-LLM 是具体的推理引擎，解决“单个模型怎么跑得快”；Triton 可以把它们作为 backend 接入，解决“多个模型怎么稳定地对外服务”。

### Q2：`config.pbtxt` 中 `platform` 和 `backend` 有什么区别？

**参考答案**：

- `platform` 是早期 Triton 用来指定模型格式的方式，例如 `onnxruntime_onnx`、`tensorrt_plan`。
- `backend` 是更现代的方式，直接指定 backend 名，例如 `onnxruntime`、`tensorrt_llm`、`vllm`、`python`。
- 两者一般只设一个；如果同时存在，`backend` 优先级更高。

### Q3：Dynamic Batching 的核心参数有哪些？

**参考答案**：

- `preferred_batch_size`：希望组成的 batch size。
- `max_queue_delay_microseconds`：请求最大等待时间。
- `max_batch_size`：单次推理最大 batch size。
- `preserve_ordering`：是否保证返回顺序。

## 中级

### Q4：Dynamic Batching、Sequence Batching、Ensemble 分别适合什么场景？

**参考答案**：

- **Dynamic Batching**：无状态模型，如分类、OCR、embedding，通过合并请求提高吞吐。
- **Sequence Batching**：有状态模型，如多轮对话，需要保证同一序列按顺序执行并维护状态。
- **Ensemble**：多模型流水线，如 preprocess → inference → postprocess，通过 `input_map` / `output_map` 编排。

### Q5：为什么 LLM 场景下 Triton 层的 dynamic batching 通常要关闭？

**参考答案**：

因为 vLLM / TensorRT-LLM backend 内部已经实现了 Continuous Batching 或 In-flight Batching。Triton 层再开 dynamic batching 会把请求拆成静态 batch 发给 backend，反而破坏了 LLM backend 内部的动态调度，可能导致延迟增加或 batch 利用率下降。

### Q6：Triton 的 Backend API 中，`TRITONBACKEND_ModelExecute` 的作用是什么？

**参考答案**：

它是 backend 执行推理的核心回调。Triton core 把一组 `TRITONBACKEND_Request`（已拼好的 batch）传给 backend，backend 负责把输入张量传给底层 runtime、执行推理、把输出写回请求，然后返回。

### Q7：模型热更新有哪两种模式？生产推荐哪种？

**参考答案**：

- **Poll 模式**：Triton 周期性扫描仓库，自动加载/卸载/更新。
- **Explicit 模式**：通过 API 显式控制 load/unload。
- 生产推荐 explicit 模式，避免 poll 带来的意外变更。

## 高级

### Q8：设计一个高可用、低延迟的 LLM 服务架构，Triton 应该放在什么位置？

**参考答案**：

典型架构：

```text
Client -> API Gateway（认证/限流/A-B）-> Triton Inference Server -> TensorRT-LLM / vLLM backend
                                      -> Python backend（pre/post processing）
```

Triton 作为统一服务层，承接上游请求并分发到不同 backend。关键点：

- LLM backend 内部已有 batching，Triton 层 `max_batch_size: 0`。
- 通过 instance group 控制每卡实例数，避免 OOM。
- Prometheus 监控 queue duration、compute infer、显存。
- KServe 做 Kubernetes 层面的自动扩缩与蓝绿发布。

### Q9：Triton 的 Python backend 是如何避免 GIL 影响 core 并发的？

**参考答案**：

Python backend 把 Python 执行逻辑放到独立的子进程中，Triton core 通过 shared memory + socket 与子进程通信。这样 Python 的 GIL 只影响子进程内部，不会阻塞 C++ core 的网络、调度与其他 backend。

### Q10：如何定位 Triton 服务延迟高的问题？

**参考答案**：

按延迟分解排查：

1. 看 `nv_inference_queue_duration_us`：如果 queue 时间长，说明 batch 没凑够或实例不足，可调整 `preferred_batch_size`、`max_queue_delay_microseconds`、instance count。
2. 看 `nv_inference_compute_input` 与 `nv_inference_compute_output`：如果高，可能是前后处理或数据传输瓶颈。
3. 看 `nv_inference_compute_infer`：如果高，是 backend 推理本身慢，需要优化模型、启用 TensorRT-LLM、调整 KV cache。
4. 看 `nv_gpu_memory_used_bytes` 是否接近上限：显存紧张会触发 swapping 或 OOM。
5. 开启 tracing，定位具体请求在各阶段的耗时。

## 本章小结

面试中关于 Triton 的问题通常集中在四个方向：**`config.pbtxt` 配置**、**调度策略对比**、**backend 架构与生命周期**、**生产部署与调优**。掌握本章问题，基本可以覆盖大部分 Triton 相关面试场景。

**参考来源**

- [Triton User Guide — Architecture](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/architecture.html)
- [Triton Backend API](https://github.com/triton-inference-server/backend/blob/main/README.md)
- [Triton Model Management](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/model_management.html)

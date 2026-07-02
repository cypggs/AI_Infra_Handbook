# 10. 面试题

本章按难度分级，覆盖 TensorRT-LLM 的核心概念、源码与生产实践。

## Level 1：概念理解

### 1. 一句话解释 TensorRT-LLM 的核心价值？

**参考答案**：TensorRT-LLM 先把 LLM 编译/优化成针对 NVIDIA GPU 的执行计划，再用 In-flight Batching 持续动态调度请求，从而在 NVIDIA 硬件上获得极致推理性能。

### 2. Builder / Engine / Runtime / Executor 分别做什么？

**参考答案**：

- Builder：把模型 checkpoint 转换成优化执行计划
- Engine：可序列化的执行计划（historically TensorRT engine；现在 PyTorchModelEngine）
- Runtime：执行 Engine 的环境
- Executor：面向服务的调度与执行入口，持续做 IFB

### 3. 什么是 In-flight Batching？

**参考答案**：在同一个 batch 中交错执行 context-phase（prefill）与 generation-phase（decode）请求，优先调度 decode，再填 prefill，从而提高 GPU 利用率。

## Level 2：原理与实现

### 4. TensorRT-LLM 的 Scheduler 为什么优先调度 generation-phase 请求？

**参考答案**：decode 请求每步只产生少量新 token，但数量多、计算量小；如果让长 prefill 阻塞 decode，会显著增加已生成部分请求的 inter-token latency。优先 decode 可以保障流式体验。

### 5. Paged KV Cache 与 Contiguous KV Cache 的区别？

**参考答案**：

- Contiguous：每个请求预留连续最大长度空间，内部碎片多
- Paged：按 block 分配，动态回收复用，支持 prefix/block reuse，适合 IFB 与 chunked prefill

### 6. TensorRT 后端被移除后，TRT-LLM 用什么替代执行优化？

**参考答案**：PyTorch 后端通过 `torch.compile`、CUDA Graph、custom Triton kernel、PyTorch custom op 等方式，继续实现算子融合与硬件级优化。

## Level 3：源码与架构

### 7. 描述一个请求在 PyTorch 后端中的完整调用链。

**参考答案**：

```
LLM.generate()
  → Executor.submit(Request)
  → CapacityScheduler 检查资源
  → MicroBatchScheduler 选 batch
  → KVCacheManager.prepare_resources()
  → PyTorchModelEngine.forward()
  → Decoder.step()
  → KVCacheManager.update_resources()
  → Request 更新状态 / 完成返回
```

### 8. Plugin 机制在 TRT-LLM 中如何工作？

**参考答案**：开发者继承 `PluginBase`，实现 `shape_dtype_inference` 与 `forward`，用 `@trtllm_plugin("Name")` 注册。Builder 在构建网络时，可以用 plugin 替换标准 op，注入自定义 kernel。

### 9. PyExecutor 与 C++ Executor 有什么区别？

**参考答案**：PyExecutor 是 Python 后端的执行循环，便于开发与自定义；C++ Executor 延迟更低，Triton backend 默认使用 C++ Executor 路径。

## Level 4：生产与调优

### 10. 如何为线上服务选择 `max_batch_size` 与 `max_num_tokens`？

**参考答案**：

- `max_batch_size`：构建时设足够大（如 64/128），运行时再根据延迟约束调整
- `max_num_tokens`：根据线上 prompt 长度 P95 设置，过大挤占 KV cache，过小 batch 不满
- 两者共同决定每步 GPU 负载与显存分配

### 11. FP8 与 FP4 在生产中如何选择？

**参考答案**：

- FP8：Hopper/Blackwell 通用，精度损失小，首选
- FP4：Blackwell 专属，显存减半，但需要充分校准，适合对显存极度敏感且可接受一定精度损失的场景

### 12. Triton backend 启用 IFB 的关键配置是什么？

**参考答案**：在 `tensorrt_llm/config.pbtxt` 中设置 `batching_strategy:inflight_fused_batching`，并合理配置 `triton_max_batch_size` 与 `max_queue_delay_microseconds`。

## Level 5：综合设计与对比

### 13. 设计一个基于 TRT-LLM 的高可用推理服务，需要考虑哪些因素？

**参考答案要点**：

- 多副本 Triton + 负载均衡
- TP/PP/CP/EP 并行策略选择
- 量化方案与精度评估
- IFB 参数调优
- KV cache 显存管理
- 可观测性（TTFT/TPOT/吞吐/显存）
- 版本管理与回滚
- fallback 到 vLLM/SGLang 的能力

### 14. TensorRT-LLM、vLLM、SGLang 分别适合什么场景？

**参考答案**：

- TRT-LLM：NVIDIA 硬件、模型稳定、追求极限性能
- vLLM：通用在线推理、跨硬件、生态开放
- SGLang：LLM 程序、多轮/Agent、结构化生成、共享前缀多的场景

### 15. 如果 TRT-LLM 上线后发现 TTFT 过高，你会如何排查？

**参考答案要点**：

1. 检查是否有长 prefill 独占 batch → 启用 chunked prefill
2. 检查 `max_num_tokens` 是否过小 → 调大
3. 检查 generation-phase 是否过多挤占 token budget → 平衡调度
4. 检查是否启用 CUDA Graph / 并行策略是否匹配
5. 使用 Nsight / trtllm-bench 定位瓶颈 kernel

## 本章小结

面试题覆盖了从概念到源码、从调优到架构设计的完整维度。核心考点包括：Builder/Engine/Runtime/Executor 的职责、IFB 调度原理、PyTorch 后端调用链、Paged KV Cache、量化选型、Triton 部署与参数调优。

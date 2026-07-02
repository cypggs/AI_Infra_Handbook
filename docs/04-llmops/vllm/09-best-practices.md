# 9. 最佳实践

本章总结 vLLM 的使用建议、常见陷阱与 Trade-off。

## 什么时候使用 vLLM？

vLLM 适合以下场景：

- 需要高吞吐、低成本的在线 LLM 推理服务
- 请求长度差异大，需要动态批处理
- 希望使用开源方案，避免被特定云厂商绑定
- 需要 OpenAI 兼容 API，快速接入现有生态
- 需要快速试验新模型、新特性

## 什么时候不使用 vLLM？

以下场景可能需要考虑其他方案：

- **极致延迟要求**：TensorRT-LLM 或 SGLang 可能更优
- **完全离线批处理**：可能不需要 vLLM 的在线调度开销
- **超大规模模型且已有 NVIDIA 全栈**：TensorRT-LLM 的定制 kernel 可能更快
- **需要复杂 Agent 工作流**：考虑 SGLang 的编程模型

## vLLM vs 其他方案

| 场景 | 推荐方案 | 理由 |
|---|---|---|
| 通用在线推理 | vLLM | 生态最好，易用性高 |
| 极致吞吐/延迟 | TensorRT-LLM | 深度优化的 NVIDIA kernel |
| 复杂程序式 Agent | SGLang | 原生支持结构化生成、多轮交互 |
| 快速原型/小规模 | HuggingFace Transformers | 最简单 |
| 企业级模型服务 | Triton + vLLM / TensorRT-LLM | 成熟的 serving 框架 |

## 关键参数调优

### `gpu_memory_utilization`

- 默认值 0.9，表示允许 vLLM 使用 90% 的 GPU 显存
- 如果系统上还有其他进程（如监控 agent、Ray worker），需要降低此值
- 注意：这是 vLLM 可用于 KV cache + 模型权重的总预算，不是单一项

### `max_num_seqs`

- 最大并发 Sequence 数
- 越大吞吐越高，但会增加调度复杂度和显存压力
- 建议从默认值开始，根据 TTFT / TPOT 指标逐步调整

### `max_model_len`

- 模型支持的最大序列长度
- 根据实际业务设置，避免为不存在的超长序列预留资源
- 设置过大可能导致 KV cache 预分配过多而 OOM

### `block_size`

- Block 大小，常见 16
- 太小会增加 Block Table 开销，太大会增加内部碎片
- V1 引擎支持 hybrid blocks（内存分配块大小与 kernel 块大小不同），由系统根据 attention backend 自动选择

### `enable_chunked_prefill`

- 把长 prefill 拆分成多个 chunk，与 decode 交错执行
- 可降低 TTFT，提高整体吞吐
- 在 V1 引擎中，prefill 与 decode 已统一调度，chunked prefill 是默认行为的一部分

### `enable_prefix_caching`

- 启用前缀缓存，对共享系统 prompt 或长前缀的请求收益巨大
- V1 引擎中 prefix caching 已功能完整

### 量化选项

当前 vLLM 支持的量化方式包括：

- **FP8**：在 H100/H200 等支持 FP8 的硬件上性能最好，可使用 `llm-compressor` 进行校准
- **AWQ / GPTQ**：4-bit 权重量化，显著降低显存占用
- **INT8 / INT4 / GGUF / compressed-tensors**：更多量化后端

选择建议：

| 目标 | 推荐量化 |
|---|---|
| 最高吞吐 + 支持 FP8 硬件 | FP8（权重 + KV cache） |
| 极致显存压缩 | AWQ / GPTQ 4-bit |
| 快速部署预量化模型 | GGUF / compressed-tensors |

## 常见陷阱

1. **默认参数不适合所有模型**：不同模型的显存占用差异很大，需要实测调整。
2. **忽略 prefix caching**：长系统 prompt 场景下收益巨大。
3. **过度依赖量化**：量化虽降低显存，但可能损害模型能力；需评估 perplexity 和业务指标。
4. **不做监控**：没有 TTFT/TPOT 指标，就无法优化。
5. **单实例部署**：生产环境应使用 LLM Gateway + 多实例。
6. **混淆 V0 与 V1 引擎**：V1 引擎调度器与 V0 不同，部分参数和行为有差异；升级前阅读 [V1 Guide](https://docs.vllm.ai/en/stable/usage/v1_guide)。

## Trade-off 总结

| 优化方向 | 收益 | 代价 |
|---|---|---|
| 增大 batch size | 更高吞吐 | 更高延迟 |
| 量化 | 更低显存、更高吞吐 | 可能精度下降 |
| TP/PP | 支持更大模型 | 通信 overhead |
| Prefix Caching | 降低重复计算 | 增加显存管理复杂度 |
| Speculative Decoding | 降低 TPOT | 需要额外 draft model |

## 本章小结

vLLM 是一个强大的默认选择，但不是银弹。理解它的 Trade-off，根据业务场景选择合适的参数与架构，才能真正发挥价值。

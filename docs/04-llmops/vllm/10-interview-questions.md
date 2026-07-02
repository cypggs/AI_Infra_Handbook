# 10. 面试题

## 初级

### Q1: 什么是 KV Cache？为什么在 LLM 推理中很重要？

**参考答案：**

KV Cache 是 Transformer 在 decode 阶段保存的历史 Key 和 Value 张量。每次生成新 token 时，模型需要与之前所有 token 的 Key、Value 计算注意力。把这些历史 KV 缓存起来，可以避免重复计算，显著加速 decode。

---

### Q2: vLLM 最核心的两个优化是什么？

**参考答案：**

1. **PagedAttention**：把 KV Cache 按 Block 分页管理，按需动态分配，减少显存浪费。
2. **Continuous Batching**：在每个 iteration 边界动态调整 batch 内容，提高 GPU 利用率。

---

### Q3: 解释 prefill 和 decode 阶段的区别。

**参考答案：**

- **Prefill**：处理输入 prompt 的所有 token，计算它们的 KV Cache 并生成第一个输出 token。计算密集。
- **Decode**：每次只处理一个新 token，生成下一个 token。受内存带宽限制。

---

## 中级

### Q4: PagedAttention 如何解决显存碎片问题？

**参考答案：**

传统方法为每个请求预先分配一段连续的显存。PagedAttention 把 KV Cache 切分为固定大小的 Block，每个 Sequence 的 Block 可以离散分布在物理显存中，通过 Block Table 维护映射关系。这样只需要为实际生成的 token 分配 Block，避免了内部碎片和预分配浪费。

---

### Q5: vLLM 的 Scheduler 维护哪几个队列？分别代表什么状态？

**参考答案：**

- **Waiting**：新到达、尚未开始执行的请求
- **Running**：正在 decode 的请求
- **Swapped**：因显存不足被 swap 到 CPU 的请求

---

### Q6: 什么是 Continuous Batching？它相比静态批处理有什么优势？

**参考答案：**

Continuous Batching（也称 iteration-level scheduling）允许在每个 iteration 结束时动态加入新请求、移除已完成请求。相比静态批处理，它可以减少 GPU 空闲等待时间，提高吞吐，降低尾部延迟。

---

## 高级

### Q7: 描述一条请求在 vLLM 中的完整生命周期。

**参考答案：**

1. 客户端请求到达 API Server
2. API Server 调用 Tokenizer 编码 prompt
3. 创建 SequenceGroup，调用 `LLMEngine.add_request()` 加入 Waiting 队列
4. `Scheduler.schedule()` 在每轮 iteration 中选择可执行请求
5. `BlockManager` 分配 KV Cache Block
6. `Worker.execute_model()` 执行 prefill 或 decode
7. `ModelRunner` 调用 Attention Backend 和 Sampler 生成新 token
8. 更新 Sequence 状态，返回 token 给客户端
9. 请求完成或达到 max_tokens 后释放资源

---

### Q8: vLLM 支持哪些分布式并行策略？各自的适用场景是什么？

**参考答案：**

- **Tensor Parallelism（TP）**：把模型层的计算切分到多个 GPU，适合单节点多 GPU。通信密集，但延迟较低。
- **Pipeline Parallelism（PP）**：把模型按层切分到多个 GPU，适合跨节点大模型。会有 pipeline bubble。

---

### Q9: Prefix Caching 在 vLLM 中如何实现？有什么好处？

**参考答案：**

Prefix Caching 缓存共享前缀（如系统 prompt）的 KV Cache。当多个请求前缀相同时，可以直接复用已计算的 KV，避免重复 prefill。实现上需要 BlockManager 支持 Block 级别的哈希索引和引用计数。

---

## Staff

### Q10: 如果你要在生产环境中部署一个支持 1000 QPS 的 vLLM 服务，你会如何设计？

**参考答案：**

- 使用 LLM Gateway 做负载均衡、限流、配额、缓存
- 多 vLLM 实例部署，根据模型大小选择 TP/PP
- 根据请求长度分布调优 `max_num_seqs`、`block_size`、`gpu_memory_utilization`
- 启用 prefix caching 和 chunked prefill
- 配置完善的监控：TTFT、TPOT、throughput、KV Cache 利用率、GPU 利用率
- 根据延迟/成本要求选择是否量化
- 设置自动扩缩容策略

---

### Q11: 你如何排查 vLLM 的 CUDA OOM 问题？

**参考答案：**

1. 检查 `gpu_memory_utilization` 和 `max_model_len` 是否合理
2. 监控 KV Cache 增长趋势，确认是否有长序列请求
3. 调低 `max_num_seqs` 限制并发
4. 检查是否启用了 swap，以及 swap 空间是否足够
5. 查看是否有显存泄漏（如 Block 未正确回收）
6. 必要时启用 quantization 降低权重显存占用

---

## Architect

### Q12: 设计一个面向多租户的 LLM 推理平台，vLLM 在其中扮演什么角色？你会如何与调度、配额、计费系统结合？

**参考答案：**

- vLLM 作为底层推理引擎，负责单实例内的高吞吐调度
- 上层需要 LLM Gateway / Router：负责租户路由、限流、配额、A/B 测试、缓存
- 调度系统根据租户优先级、成本、SLA 决定请求发往哪个实例
- 计费系统基于 token 数、GPU 时间、延迟等指标计费
- 可观测系统统一采集日志、指标、trace
- 安全层面需要模型隔离、请求审计、输出过滤

---

### Q13: 比较 vLLM、TensorRT-LLM、SGLang 的设计哲学差异，并说明在什么情况下你会选择哪一个。

**参考答案：**

- **vLLM**：开源、易用、生态最大，适合大多数在线推理场景。设计哲学是通用性和社区驱动。
- **TensorRT-LLM**：NVIDIA 专有，极致性能，适合有 NVIDIA 全栈支持、对延迟/吞吐要求极高的场景。
- **SGLang**：强调结构化生成和编程式交互，适合复杂 Agent、多轮对话、需要控制流的场景。

选择时会综合考虑：性能要求、团队能力、模型支持、生态锁定、部署复杂度。

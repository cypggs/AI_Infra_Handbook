# 10. 面试题

## 初级

### Q1: 什么是 RadixAttention？它和 vLLM 的 Prefix Caching 有什么区别？

**参考答案：**

RadixAttention 是 SGLang 提出的 KV Cache 管理机制，使用 Radix Tree（基数树）自动复用不同请求之间的公共前缀。vLLM 的 Prefix Caching 基于 Block-level hash，需要显式配置；RadixAttention 对用户透明，可以复用任意 token 边界的前缀，并且天然支持 `fork` 产生的多分支共享。

---

### Q2: SGLang 的核心抽象有哪些？

**参考答案：**

1. **LLM Program**：`gen`、`select`、`fork`、`run` 等原语。
2. **RadixAttention**：Radix Tree 前缀缓存。
3. **Structured Generation**：regex / JSON Schema / EBNF 约束输出。
4. **Compiler + Runtime**：把程序编译成执行图并调度执行。

---

### Q3: 结构化生成相比“生成后再校验”有什么优势？

**参考答案：**

结构化生成在采样阶段就限制只能生成合法 token，因此：

- 避免生成无效输出后重试，降低延迟和成本。
- 保证输出 100% 符合约束（只要约束编译正确）。
- 提高复杂 schema 下的成功率。

---

## 中级

### Q4: 描述 SGLang 中一条 LLM Program 的完整执行流程。

**参考答案：**

1. Python API 构建 LLM Program。
2. Language Frontend 解析为 IR。
3. Compiler 优化 IR 并生成 Schedule Plan。
4. Runtime 调用 Scheduler，对每轮待计算 token 做 Radix Tree 前缀匹配。
5. Worker 执行 forward，Constrained Sampler 施加结构化约束。
6. 新 token 的 KV 插入 Radix Tree。
7. Detokenizer 输出文本，流式或非流式返回。

---

### Q5: Radix Tree 如何实现写时复制（Copy-on-Write）？

**参考答案：**

当多个请求或分支共享同一个前缀节点时，节点引用计数大于 1。如果某个分支需要在该前缀之后生成新 token，只需要从共享节点分叉出新边，不需要复制整个前缀。只有当节点需要被修改时（实际中主要是新增边），才进行复制或新建分支，实现高效的写时复制。

---

### Q6: SGLang 的 Scheduler 与 vLLM V1 的 Scheduler 有什么异同？

**参考答案：**

相同点：都使用统一调度视角处理 prefill / decode，都根据 token budget 决定每轮计算量。

不同点：SGLang 的 Scheduler 需要与 RadixCache 紧密交互，只计算未缓存的 suffix；同时要考虑 LLM Program 中多个调用之间的依赖和合并。

---

## 高级

### Q7: 如何把 JSON Schema 转换为约束采样可用的形式？

**参考答案：**

通常有两种路径：

1. **FSM 路径**：把 JSON Schema 编译成上下文无关文法或正则表达式，再转换为 FSM。每步采样时根据 FSM 状态生成合法 token mask。
2. **Grammar 路径**：SGLang 的 XGrammar-2 直接把 JSON Schema / EBNF 编译成 grammar，采样时按 grammar 的合法展开选择 token。

实际中 Grammar 路径更通用，能处理嵌套对象、数组、递归结构。

---

### Q8: SGLang 支持哪些分布式并行策略？各自的适用场景是什么？

**参考答案：**

- **Tensor Parallelism（TP）**：层内切分，适合单节点多 GPU。
- **Pipeline Parallelism（PP）**：层间切分，适合跨节点大模型。
- **Data Parallelism（DP）**：模型副本并行服务不同请求。
- **PD 分离**：prefill 与 decode 分别部署，分别优化计算与带宽。

---

### Q9: 结构化生成可能带来哪些性能开销？如何优化？

**参考答案：**

开销来源：

- 约束编译（regex/schema → FSM/grammar）。
- 每步生成合法 token mask。
- FSM 状态集合可能很大。

优化手段：

- 使用 XGrammar-2 等高效后端。
- 预编译或缓存常用约束。
- 简化 schema，避免深层嵌套。
- 对热约束使用增量编译。

---

## Staff

### Q10: 如果你要在生产环境中部署一个支持 1000 QPS 的 SGLang 服务，你会如何设计？

**参考答案：**

- 使用 LLM Gateway 做负载均衡、限流、缓存、A/B。
- 多 SGLang 实例部署，根据模型大小选择 TP/PP/DP。
- 对通用请求可路由到 vLLM，对结构化/多轮请求路由到 SGLang。
- 启用 RadixAttention，统一 system prompt 模板以提升命中率。
- 配置监控：TTFT、TPOT、Radix Tree 命中率、约束编译耗时、吞吐。
- 根据场景选择量化（FP8/NVFP4 on Blackwell）。
- 设置自动扩缩容和降级策略。

---

### Q11: 你如何排查 SGLang 的首 token 延迟高问题？

**参考答案：**

1. 检查是否是结构化约束编译耗时高，考虑预编译。
2. 检查 Radix Tree 命中率，确认 system prompt 是否稳定。
3. 检查 chunked_prefill_size 是否合理。
4. 监控 TP 通信和 GPU 利用率。
5. 检查是否因 batch 过大导致排队。
6. 必要时使用 PD 分离把 prefill 单独部署。

---

## Architect

### Q12: 设计一个面向 Agent 平台的多引擎推理架构，SGLang 和 vLLM 如何分工？

**参考答案：**

- **vLLM**：处理通用单次/短多轮 chat completion，追求高吞吐。
- **SGLang**：处理 Agent 的复杂程序（多分支、结构化输出、函数调用）。
- **LLM Gateway**：根据请求特征（是否有 `response_format`、是否多轮、是否 Agent 会话）动态路由。
- **共享缓存层**：在网关层维护 session context，对热 system prompt 做提示缓存。
- **可观测**：统一采集两个引擎的指标、日志、trace。
- **成本优化**：对 SGLang 侧启用 RadixAttention 和结构化约束缓存；对 vLLM 侧启用 prefix caching 和 chunked prefill。

---

### Q13: 比较 SGLang、vLLM、TensorRT-LLM 的设计哲学差异，并说明选择策略。

**参考答案：**

- **SGLang**：程序式 LLM 执行 + 自动前缀复用 + 原生结构化生成。适合复杂 Agent、多轮、结构化输出。
- **vLLM**：通用高吞吐推理 + PagedAttention + 大规模生态。适合大多数在线推理场景。
- **TensorRT-LLM**：NVIDIA 专有、极致性能。适合 NVIDIA 全栈、对延迟/吞吐要求极高、模型固定的场景。

选择策略：先按场景初选，再实测业务指标（TTFT、TPOT、格式正确率、成本），避免单纯看 benchmark。

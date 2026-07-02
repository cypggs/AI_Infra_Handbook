# 9. 最佳实践

本章总结 SGLang 的使用建议、常见陷阱与 Trade-off。

## 什么时候使用 SGLang？

SGLang 适合以下场景：

- 需要复杂的 LLM 程序（多轮、分支、结构化、Agent）。
- 多轮对话中长 system prompt 或历史上下文复用率高。
- 需要原生、高性能的结构化输出（JSON Schema、Function Calling、EBNF）。
- 希望用统一的 Python API 表达控制流，而不是手写多次 HTTP 调用。
- 愿意接受较快的版本迭代，以换取新特性。

## 什么时候不使用 SGLang？

以下场景可能更适合其他方案：

- **通用单次补全 / 高吞吐在线推理**：vLLM 生态更成熟、社区更大。
- **完全 NVIDIA 封闭环境且对延迟极致敏感**：TensorRT-LLM 可能更快。
- **团队不想维护快速迭代的依赖**：SGLang 版本更新快，API 可能变化。
- **简单的聊天机器人，没有结构化或多轮复用需求**：vLLM 足够。

## SGLang vs 其他方案

| 场景 | 推荐方案 | 理由 |
|---|---|---|
| 通用在线推理 | vLLM | 生态最好，通用吞吐领先 |
| Agent / 多轮 / 结构化 | SGLang | 原生 LLM Program + RadixAttention + XGrammar-2 |
| 极致延迟/吞吐 + NVIDIA 全栈 | TensorRT-LLM | 深度优化的 CUDA kernel |
| 企业级模型网关 | Triton + vLLM / SGLang backend | 成熟的 serving 框架 |
| 复杂程序式 Agent | SGLang / SGLang + LangGraph | 控制流表达力强 |

## 关键参数调优

### `mem_fraction_static`

- 控制静态显存分配比例。
- 如果系统上还有其他进程，需要降低此值。

### `chunked_prefill_size`

- 长 prefill 拆成 chunk，与 decode 交错执行。
- 根据 prompt 长度和 TTFT 要求调整。

### `max_running_requests`

- 最大并发请求数。
- 过大可能增加调度复杂度和显存压力；过小可能浪费吞吐。

### `max_num_seqs`

- 与 vLLM 类似，控制 batch 中最大序列数。

### 缓存相关

- 启用 RadixAttention（默认开启）。
- 根据 prompt 长度分布调整 Radix Tree 容量。
- 使用 HiCache / UnifiedRadixTree 时配置 SSD offload。

### 结构化生成

- 优先 XGrammar-2 后端。
- JSON schema 尽量扁平，避免深层嵌套。
- 对复杂 schema 做预编译或缓存编译结果。

### 量化

- Blackwell（GB200/GB300）：优先 FP8 / NVFP4。
- 旧架构：AWQ / GPTQ 降低显存。
- 结构化输出场景量化后需重点验证格式正确率。

## 常见陷阱

1. **默认参数不一定最优**：SGLang 参数与 vLLM 不完全相同，迁移时需实测。
2. **结构化约束编译慢**：复杂 EBNF 或 JSON schema 可能显著增加首 token 延迟。
3. **Radix Tree 命中率被低估**：system prompt 不稳定或模板太多会大幅降低收益。
4. **版本升级带来 API 变化**：建议锁定 minor 版本，升级前阅读 Release Notes。
5. **与 vLLM 混合部署时的请求路由**：应根据请求特征（是否结构化、是否多轮）动态路由。
6. **忽略约束输出正确率评估**：结构化生成不仅要快，还要保证格式合法、字段正确。

## Trade-off 总结

| 优化方向 | 收益 | 代价 |
|---|---|---|
| RadixAttention | 降低重复 prefill | 树结构维护复杂 |
| 结构化生成 | 输出可控 | 约束编译与 mask 计算开销 |
| 投机解码 | 降低 TPOT | 需要 draft model / 额外显存 |
| 量化 | 降低显存、提升吞吐 | 可能损失精度/格式正确率 |
| PD 分离 | 分别优化 prefill 与 decode | 增加系统复杂度 |

## 本章小结

SGLang 是复杂 LLM 程序场景的强力工具，但不是所有场景都优于 vLLM。理解它的设计边界，根据 workload 选择合适的引擎和参数，才能真正发挥价值。

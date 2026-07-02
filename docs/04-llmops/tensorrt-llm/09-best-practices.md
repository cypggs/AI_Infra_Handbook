# 9. 最佳实践

本章回答三个关键问题：什么时候选 TensorRT-LLM？如何调优？如何管理版本与风险？

## 1. 选型：TensorRT-LLM vs vLLM vs SGLang

| 场景 | 推荐 |
|---|---|
| 已锁定 NVIDIA GPU，追求极限吞吐/延迟 | **TensorRT-LLM** |
| 模型频繁变化，需要快速试错 | **vLLM** / **SGLang** |
| 多轮对话 / Agent / 结构化生成 | **SGLang** |
| 通用在线推理，跨硬件部署 | **vLLM** |
| 需要与 NVIDIA Triton / Dynamo 深度集成 | **TensorRT-LLM** |
| 超长上下文（>200k）且预算充足 | **SGLang** / **TensorRT-LLM + CP** |

一句话总结：

> 如果你的基础设施已经 NVIDIA 化，且模型相对固定、性能敏感，TensorRT-LLM 通常是吞吐与延迟的最优解；如果你更看重灵活性和生态开放性，vLLM / SGLang 更合适。

## 2. 构建期调优

### 合理设置 `max_batch_size`

- 构建时设得足够大（如 64 或 128），避免运行时成为瓶颈
- 实际运行时通过调度器控制并发，不必满载

### `max_num_tokens` 调优

- 过小：batch 不满，GPU 利用率低
- 过大：workspace 占用多，KV cache 空间被挤占
- 建议根据线上 prompt 长度 P95 设置

### 精度选择

| 精度 | 显存 | 速度 | 精度损失 | 推荐硬件 |
|---|---|---|---|---|
| BF16 | 基准 | 基准 | 无 | 通用 |
| FP8 | 50% | 1.3-1.5x | 小 | Hopper/Blackwell |
| FP4/NVFP4 | 25% | 显著 | 中 | Blackwell |
| AWQ/GPTQ W4A16 | 25% | 1.5-2.0x | 中 | 多代 GPU |

### 启用 CUDA Graph

- 低 batch size 时收益明显
- 需要捕获常用 batch size 的 graph
- 注意与动态 shape 的权衡

## 3. 运行期调优

### In-flight Batching 参数

- `max_queue_delay_microseconds`：平衡排队延迟与 batch 满载
- `max_batch_size`：运行时并发上限
- `max_num_tokens`：每步最大 token 数

### KV Cache 配置

```python
from tensorrt_llm.llmapi import KvCacheConfig

KvCacheConfig(
    dtype='fp8',
    enable_block_reuse=True,
    free_gpu_memory_fraction=0.9,
)
```

- `enable_block_reuse=True`：启用 block 级复用
- `free_gpu_memory_fraction`：控制 KV cache 占用的显存比例

### 调度策略

- 优先保证 decode 不被饿死
- 长 prefill 使用 chunked prefill 拆分
- 关注 generation / context 比例，避免某类请求垄断 token budget

## 4. 量化最佳实践

1. **先用 FP8**：在 Hopper/Blackwell 上，FP8 是精度与速度的最佳平衡点。
2. **再用 ModelOpt 离线校准**：不要依赖动态量化。
3. **评估业务指标**：PPL 好不代表下游任务好。
4. **保留 BF16 fallback**：对精度敏感场景保留非量化版本。
5. **FP4 需要充分校准**：建议 1024+ 样本，并重点关注代码/数学任务。

## 5. Engine 版本管理

- 将 build 产物按模型版本、精度、GPU SKU、TRT-LLM 版本命名
- 例如：`llama-3.1-8b-fp8-h100-trtllm-1.2/`
- 在 CI/CD 中自动化 build 与回归测试
- 记录 build config 与 benchmark 结果

## 6. License 与生态锁定

TensorRT-LLM 的优势与风险都来自于 NVIDIA 生态：

- **优势**：深度优化、与 Triton/Dynamo 集成、官方支持
- **风险**：硬件锁定、版本迭代快、部分组件专有

建议：

- 同时维护一套 vLLM / SGLang 的 fallback 部署能力
- 关键业务避免深度依赖单个专有 feature
- 跟踪 Release Notes，提前评估版本迁移成本

## 7. 版本升级策略

- 关注 Release Notes 中的 breaking changes（如 1.2 移除 TensorRT 后端）
- 在新版本发布后在 staging 环境 rebuild engine
- 对比 benchmark 后再推全量
- 保留可回滚的 engine 目录

## 8. 监控清单

上线后重点监控：

- TTFT / TPOT P99
- throughput per GPU
- KV cache 使用率
- batch size 分布
- GPU 利用率与显存占用
- 请求失败率、超时率
- 量化模型的业务指标漂移

## 9. 常见反模式

| 反模式 | 后果 |
|---|---|
| 不对齐 build 与线上 GPU SKU | 性能下降或无法加载 |
| `max_num_tokens` 盲目设大 | KV cache 不足 |
| 忽略 IFB 配置 | 吞吐大幅损失 |
| 只看吞吐不看 TTFT/TPOT | 用户体验差 |
| 量化后不评估业务指标 | 精度劣化 |
| 单点部署无 fallback | 故障时无退路 |

## 本章小结

TensorRT-LLM 的最佳实践核心在于：**在 NVIDIA 生态内把“构建期优化”做足，在运行期通过合理的 IFB、KV Cache、量化与并行策略榨取硬件性能，同时保留灵活 fallback 以应对锁定风险**。选型时不要把 TRT-LLM 当成唯一答案，而要把它当成性能敏感、模型稳定场景下的强力工具。

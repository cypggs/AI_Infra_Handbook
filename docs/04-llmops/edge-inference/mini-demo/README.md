# 端侧与边缘推理基础设施 Mini Demo

纯 Python（仅依赖 numpy，无 GPU）模拟端侧/边缘 LLM 推理基础设施的七个核心机制：

| 模块 | 模拟对象 | 对应真实系统 |
|---|---|---|
| `edge_inference_mini/clock.py` | 离散事件伪时钟（FakeClock） | OS 调度器/硬件计时器的可步进抽象 |
| `edge_inference_mini/memory.py` | 带宽受限 decode 吞吐模型；GQA 下 KV cache 每 token 字节数与上下文容量规划 | llama.cpp/MLX 的带宽账、KV 预算管理 |
| `edge_inference_mini/hetero.py` | NPU/GPU/CPU 能力表 + roofline 单算子时延 + 回退链与传输税 | ExecuTorch delegate / ORT ExecutionProvider / ggml backend 抽象的调度层 |
| `edge_inference_mini/streaming.py` | 闪存/磁盘 mmap 流式加载：缺页、预取窗口（readahead）、热子集工作集 | llama.cpp mmap + `--mlock`、MLC 分页加载、LLM-in-a-flash |
| `edge_inference_mini/lora.py` | LoRA 热切换（低秩增量）vs 权重合并（dense 副本）的内存/时延权衡 | llama.cpp `--lora` / PEFT 端侧多 adapter 管理 |
| `edge_inference_mini/speculative.py` | 投机解码/MTP 接受率-加速比解析模型 | llama.cpp draft 模型、GLM/DeepSeek MTP 头的端侧评估 |
| `edge_inference_mini/routing.py` | 端-云混合路由：隐私分级硬约束 + 延迟 SLO + 热节流降额 + 成本 | Apple Intelligence 端侧优先/PCC 兜底、AICore 调度 |
| `edge_inference_mini/demo.py` | 6 个端到端场景 | — |

## 快速开始

```bash
cd docs/04-llmops/edge-inference/mini-demo
pip install -e ".[dev]"
pytest tests/ -v
python -m edge_inference_mini.demo
```

## 场景说明

1. **bandwidth_decode**：8B 模型（GQA 8 KV 头）在 68 GB/s 统一内存上，Q4_K_M 与 FP16 权重的 decode 吞吐上限（11.15 vs 3.61 tok/s），叠加 MTP 投机解码（α=0.75, γ=4）后的 21.26 tok/s。
2. **kv_capacity**：8 GiB 设备扣掉保留与权重后的 KV 预算，FP16/INT8/INT4 KV 三档对应的上下文上限（19,431 / 38,863 / 77,726 tokens）。
3. **hetero_fallback**：seq=512 单层 prefill 的 8 个算子在 NPU 优先策略下的放置表：softmax/norm 回退 GPU，回退传输税占 16.8%。
4. **mmap_streaming**：5.18 GB 模型文件（316,407 页）的全量预载 0.076 s、按需缺页 7.986 s、预取窗口 32 页 0.323 s、30% 热子集 + 预取 0.097 s。
5. **lora_switch**：rank=16 全层 adapter 56.0 MiB vs 合并副本 12.06 GiB；热切换一次 1,977.1 µs；热切换内存仅为合并的 0.45%，8 GiB 设备可驻留 42 个 adapter。
6. **edge_cloud_route**：机密/公开/内部三类隐私 × 长短请求在隐私硬约束、SLO 与热节流降额下的端/云决策表。

## 运行测试

```bash
pytest tests/ -v
```

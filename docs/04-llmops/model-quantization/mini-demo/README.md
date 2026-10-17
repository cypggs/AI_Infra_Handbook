# 模型量化与压缩基础设施 Mini Demo

纯 Python（仅依赖 numpy，无 GPU）模拟 LLM 量化工具链与算法基础设施层的四个核心机制：

| 模块 | 模拟对象 | 对应真实系统 |
|---|---|---|
| `model_quantization_mini/quantize.py` | 对称/非对称、per-tensor/per-channel/group-wise 整数量化；FP8/FP4 浮点格式与 NVFP4/MXFP4 block-float 模拟；误差度量 | 各类量化器的基础设施（scale/zero-point 管理、等效位宽核算） |
| `model_quantization_mini/gptq_like.py` | 简化 OBS/GPTQ 逐列误差补偿：Hessian → Cholesky → 逐列量化+补偿 | GPTQ / llm-compressor GPTQ recipe |
| `model_quantization_mini/smooth.py` | SmoothQuant 难度迁移：逐通道缩放平衡权重/激活量化难度 | SmoothQuant / Quark / llm-compressor smoothquant recipe |
| `model_quantization_mini/kv_quant.py` | KV cache 分组量化（K 按通道、V 按 token）与注意力误差随上下文长度的传播 | KIVI、vLLM/TRT-LLM FP8 KV cache |
| `model_quantization_mini/demo.py` | 6 个端到端场景 | — |

## 快速开始

```bash
cd docs/04-llmops/model-quantization/mini-demo
pip install -e ".[dev]"
pytest tests/ -v
python -m model_quantization_mini.demo
```

## 场景说明

1. **linear_quant**：同一 256×512 权重在 per-tensor / per-channel / group-wise(g=128/32) × INT8/INT4 下的相对 L2 误差对比。
2. **group_tradeoff**：INT4 group size 从 32 到 per-channel 的误差-等效位宽权衡（4+16/g bits/weight）。
3. **smooth_quant**：含 30× 离群通道的激活，per-tensor INT8 W8A8 在 α 扫描下的输出误差与最优迁移比例。
4. **gptq_vs_rtn**：低秩相关校准特征下，GPTQ 误差补偿 vs RTN 的权重/输出误差（INT4/INT8）。
5. **kv_long_context**：K 含通道离群时，K 按通道 vs 按 token 量化在 128→512 上下文的注意力余弦相似度。
6. **fp4_fp8_formats**：NVFP4(blk16,E4M3 scale) vs MXFP4(blk32,E8M0 scale) vs 裸 E2M1；FP8 E4M3 vs E5M2 的范围-精度取舍。

## 运行测试

```bash
pytest tests/ -v
```

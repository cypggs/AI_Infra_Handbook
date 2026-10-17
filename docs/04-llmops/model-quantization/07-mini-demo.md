# 7. 工程实践：Mini Demo

> 一句话理解：这个 Mini Demo 用纯 Python（仅依赖 numpy、无 GPU）模拟量化工具链的四类核心机制——整数量化与误差度量（per-tensor/per-channel/group-wise）、GPTQ 风格误差补偿、SmoothQuant 难度迁移、KV cache 分组量化与注意力误差传播，外加 NVFP4/MXFP4/FP8 浮点格式模拟，全部数字确定性可复现。

## 7.1 Demo 设计

真实系统的对应关系：

| Demo 模块 | 模拟对象 | 真实系统 |
|---|---|---|
| `model_quantization_mini/quantize.py` | 对称/非对称量化、三种粒度、FP8/FP4 浮点格式与 block-float、误差度量 | 量化器基础设施（scale/zero-point 管理、等效位宽核算） |
| `model_quantization_mini/gptq_like.py` | Hessian → Cholesky → 逐列量化+误差补偿 | GPTQ / llm-compressor GPTQ recipe |
| `model_quantization_mini/smooth.py` | 逐通道缩放难度迁移 + α 扫描 | SmoothQuant / Quark smoothquant |
| `model_quantization_mini/kv_quant.py` | K/V 分组量化粒度选择与注意力误差随长度传播 | KIVI、vLLM/TRT-LLM FP8 KV cache |
| `model_quantization_mini/demo.py` | 6 个端到端场景 | — |

## 7.2 目录结构

```text
docs/04-llmops/model-quantization/mini-demo/
├── README.md
├── pyproject.toml
├── model_quantization_mini/
│   ├── __init__.py
│   ├── quantize.py      # 整数量化/反量化、误差度量、FP8/FP4 与 block-float 模拟
│   ├── gptq_like.py     # Hessian + OBS/GPTQ 风格逐列误差补偿
│   ├── smooth.py        # SmoothQuant 难度迁移与 α 扫描
│   ├── kv_quant.py      # KV 分组量化 + 注意力误差传播
│   └── demo.py          # 6 个端到端场景
└── tests/
    ├── conftest.py
    ├── test_quantize.py    # 16 个用例
    ├── test_gptq_like.py   # 7 个用例
    ├── test_smooth.py      # 7 个用例
    ├── test_kv_quant.py    # 8 个用例
    └── test_demo.py        # 7 个用例
```

## 7.3 快速运行

```bash
cd docs/04-llmops/model-quantization/mini-demo
pip install -e ".[dev]"
pytest tests/ -v
python -m model_quantization_mini.demo
```

## 7.4 六个场景与实测输出

### 场景 1：线性层量化误差对比

同一 256×512 权重，对称量化，相对 L2 误差：

```text
   int8_per_tensor: 0.010762
  int8_per_channel: 0.007500
     int8_group128: 0.006484
      int8_group32: 0.005355
   int4_per_tensor: 0.194726
  int4_per_channel: 0.135814
     int4_group128: 0.117969
      int4_group32: 0.097576
```

读法：INT8 下粒度细化收益温和（1.5-2×）；INT4 下 per-tensor 误差近 20% 完全不可用，group-wise 是刚需——这正是 AWQ/GPTQ 论文全部使用 g=128/64 的原因。

### 场景 2：INT4 group size 权衡

```text
 group   rel_l2_err  bits/weight
    32     0.097576       4.5000
    64     0.108250       4.2500
   128     0.117969       4.1250
   256     0.127411       4.0625
per-channel     0.135814       4.0000
```

读法：g 从 128 缩到 32，误差降 17%，等效位宽从 4.125 涨到 4.5——group size 是「误差 vs 显存」的直接旋钮，g=128 是常见的甜点。

### 场景 3：SmoothQuant 难度迁移

激活含 4 个 30× 离群通道，per-tensor INT8 W8A8 输出相对误差：

```text
 alpha     baseline     smoothed  reduction
  0.00     0.066425     0.078573      0.85x
  0.25     0.066425     0.032899      2.02x
  0.50     0.066425     0.019833      3.35x
  0.75     0.066425     0.028811      2.31x
  1.00     0.066425     0.067077      0.99x
最优 alpha=0.5，误差降低 3.3x
```

读法：迁移方向 matters——α=0（难度全推给权重）比不迁移还差（0.85×）；α=0.5 均衡最优，误差降 3.35×。

### 场景 4：GPTQ vs RTN

校准特征为低秩相关（rank 16），W 64×128：

```text
            方案     权重rel_l2     输出rel_l2
RTN  INT4 g=64     0.108396     0.105888
GPTQ INT4 g=64     0.158272     0.037161
RTN  INT8 g=128     0.006542     0.006230
GPTQ INT8 g=128     0.009525     0.002258
INT4 输出误差改善: 2.85x，INT8: 2.76x
```

读法：GPTQ 把校准集输出误差压低 2.85×，但**权重本身的 rel L2 反而更大**——补偿扰动刻意落在校准数据的零空间里。评判量化算法看输出误差，不看权重范数。

### 场景 5：KV 量化对长上下文的影响

K 含通道离群（×20），d=64，平均余弦相似度：

```text
 length    int8_channel    int4_channel      int4_token
    128        0.999895        0.964978        0.945355
    256        0.999800        0.976906        0.932374
    384        0.999935        0.990474        0.850511
    512        0.999888        0.975306        0.844447
```

读法：K 按通道分组（int4_channel）在 512 token 下仍保持 ~0.98；按 token 分组（int4_token）被离群通道拖垮且随长度劣化（0.945→0.844）——验证了 KIVI 的核心观察：**K 的离群在通道维，量化粒度必须沿 token 轴切**。

### 场景 6：FP4/FP8 格式模拟

权重（128×512）上三种 FP4 方案的对比，及激活上 FP8 两格式的取舍：

```text
NVFP4(blk16,E4M3scale): err=0.102930  bits/elem=4.500
MXFP4(blk32,E8M0scale): err=0.117200  bits/elem=4.250
裸 E2M1（无 block scale）: err=1.000000  bits/elem=4.000
=== FP8 格式对比（激活, 离群通道 ×2000 vs 无离群, rel L2）===
有离群(×2000): E4M3=0.827787  E5M2=0.052476
无离群        : E4M3=0.026553  E5M2=0.052885
```

读法：裸 E2M1 对 0.02 量级的权重完全失效（误差 100%）——block scale 不是优化而是 FP4 的生命线；NVFP4 用更细的 E4M3 scale 换取比 MXFP4 更高的精度。FP8 一侧，E4M3 精度高但范围小（±448），大离群下被饱和拖垮；E5M2 范围大（±57344）对离群鲁棒——按数据特性分域选择。

## 7.5 可做的扩展练习

1. 给 `quantize.py` 的 INT4 加非对称 group-wise（带 zero_point），对比同位宽下对称/非对称误差；
2. 在 `gptq_like.py` 里实现 act-order（按对角元从大到小决定量化顺序），观察输出误差变化；
3. 把 `smooth.py` 的逐通道迁移与 `gptq_like.py` 的补偿叠加（先迁移再 GPTQ），验证正交性；
4. 在 `kv_quant.py` 中给 K 加「残差流式」量化（新 token 先 FP 缓存，攒够一组再量化），模拟 KIVI 的 streaming 设计；
5. 用 `float_quantize` 实现 NF4（正态分布分位数量化），对比均匀 INT4 的权重误差。

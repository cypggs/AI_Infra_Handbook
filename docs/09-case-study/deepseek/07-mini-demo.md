# 7. Mini Demo：DeepSeek 训练系统核心机制模拟器

配套 Mini Demo 位于本主题的 `mini-demo/` 目录（代码路径：`docs/09-case-study/deepseek/mini-demo/`），纯 Python + numpy，CPU 可运行，全部随机性走固定 seed，共 **97 个确定性测试**。它把前四章的四本"账"变成了可执行、可篡改、可复算的代码。

## 7.1 模块与机制的对应

| 模块 | 复现对象 | 核心函数 |
|---|---|---|
| `pipeline.py` | DualPipe vs 1F1B（技术报告 Table 2） | `bubble_1f1b` / `bubble_dualpipe` / `simulate_pipeline` / `ascii_timeline` |
| `fp8.py` | E4M3 量化与累加精度（§3.3 + 附录 B） | `quantize_e4m3` / `quantize_tile_wise` / `fp8_gemm_simulate` / `bulk_signal_error` |
| `ep.py` | EP all-to-all 通信量（§3.2.2） | `dispatch_bytes_per_gpu` / `inter_node_fraction` / `all_to_all_time` / `routing_imbalance` |
| `mla.py` | MLA 低秩 KV 压缩（§2.1.1 + V3.2 §2.1） | `kv_compression_ratio` / `latent_reconstruction_error` / `lightning_index_scores` / `select_top_k` |
| `demo.py` | 5 个端到端场景 | `scenario_pipeline` ~ `scenario_step_budget` |

## 7.2 运行方式

```bash
cd docs/09-case-study/deepseek/mini-demo
pip install -e ".[dev]"
pytest tests/ -v        # 97 passed
python -m deepseek_case_mini.demo
```

## 7.3 实测输出（确定性）

### 场景 1：DualPipe vs 1F1B 流水线气泡

```text
========================================================================
场景 1：DualPipe vs 1F1B 流水线气泡（PP=16, F=1, B=2, W=0.2）
========================================================================
1F1B   气泡（Table 2 闭式）: 45.0 时间单位
DualPipe 气泡（Table 2 闭式）: 16.8 时间单位
气泡缩减比: 62.7%
列表调度器复现 1F1B：makespan=117.0, 数值气泡=45.0

stage |    0   19   39   58   78   97
   0  |########...............o#oo#oo#oo#oo.oooo.oo.oo.oo.oo.oo.ooo
   1  |########..............o#oo#oo#oo#oo#oo.o.oo.oo.oo.oo.oo.oo..
   2  |.#######.............o#oo#oo#oo#oo#oo.o.oo.oo.oo.oo.oo.oo...
   3  |.#######............o#oo#oo#oo#oo#oo#oooo.oo.oo.oo.oo.oo....
   4  |..######...........o#oo#oo#oo#oo#oo#oo.o.oo.oo.oo.oo.oo.....
   5  |..######..........o#oo#oo#oo#oo#oo#oo#o.oo.oo.oo.oo.oo......
   6  |...#####.........oooo#oo#oo#oo#oo#oo#oooo.oo.oo.oo.oo.......
   7  |...#####........oo#o#oo#oo#oo#oo#oo#oo#o.oo.oo.oo.oo........
   8  |....####.......oo#o#oo#oo#oo#oo#oo#oo#o#oo.oo.oo.oo.........
   9  |....####......oo#oooo#oo#oo#oo#oo#oo#oooo.oo.oo.oo..........
  10  |.....###.....oo#oo#o#oo#oo#oo#oo#oo#oo#o#oo.oo.oo...........
  11  |.....###....oo#oo#o#oo#oo#oo#oo#oo#oo#o#oo.oo.oo............
  12  |......##...oo#oo#oooo#oo#oo#oo#oo#oo#oooo#oo.oo.............
  13  |......##..oo#oo#oo#o#oo#oo#oo#oo#oo#oo#o#oo.oo..............
  14  |.......#.oo#oo#oo#o#oo#oo#oo#oo#oo#oo#o#oo#oo...............
  15  |.......#oo#oo#oo#oooo#oo#oo#oo#oo#oo#oooo#oo................
legend: # = forward(F), o = backward(B), . = bubble/idle
```

读图：对角线左上是填充段（stage s 等前 s 个前向传完）；稳态区"F/B 交替"之间的空隙就是气泡。调度器（列表调度 + 1F1B 在途窗口约束 `pp-s`）数值复现了 Table 2 闭式气泡 45.0，与 `bubble_1f1b(16,1,2)` 精确一致（测试 `test_simulator_1f1b_matches_closed_form` 断言到 1e-9）。

### 场景 2：FP8 精度账（动态范围扫描 + 累加策略）

```text
========================================================================
场景 2：FP8 精度账（动态范围扫描 + 累加策略）
========================================================================
主体信号保真度扫描（剔除离群通道后的相对量化误差）:
      离群 std |  tensor-wise | 1x128 tile-wise
           1 |        2.64% |           2.57%
        1000 |        2.66% |           2.62%
       30000 |       12.68% |           4.01%
      100000 |       42.26% |          11.63%
高斯数据单次量化误差 floor: tile-wise 3.64%, tensor-wise 3.76%（同为 E4M3 格式属性）
FP16 直接累加的额外误差（对照 FP32 提升）: 0.0841%
注：V3 附录 B 的 <0.25% 是 FP8 vs BF16 的端到端【损失误差】口径。
```

三个正确口径的分离是本场景最重要的教学点：

1. **动态范围扫描**：E4M3 的舍入相对误差在正规区间是尺度不变的，所以中等离群幅度下两者无差异；只有当离群通道把全局 amax 推到主体信号跌出正规区间（次正规悬崖）时，tensor-wise 才崩溃（42.26%），tile-wise 把损伤隔离在离群通道所在组（11.63%，仍有组内泄漏）。
2. **量化 floor**：3.64% 是 3 位尾数的格式属性——这就是为什么附录 B 的"低于 0.25%"必须是端到端损失误差口径（误差近似无偏、被训练过程平均），不能误读成单次 GEMM 误差。
3. **累加策略**：FP16 直接累加的额外误差 0.0841% 小于量化 floor——V3 的 FP32 提升累加把"可避免误差"压到了格式固有误差之下，精度预算没有内耗。

### 场景 3：EP64 all-to-all 通信账

```text
========================================================================
场景 3：EP64 all-to-all 通信账（V3 风格：8192 tokens/GPU, top-8, hidden 7168）
========================================================================
dispatch 总量: 939.5 MB/GPU
  其中 NVLink（组内 8 卡）: 587.2 MB
  其中 IB（跨节点）:       352.3 MB
节点受限路由(M=4)通信时间: 18.42 ms
不限节点(M=8)通信时间:     36.20 ms
节点受限带来的加速: 1.97x
```

对应公式：`dispatch = tokens × topk × hidden × 2B = 8192 × 8 × 7168 × 2 ≈ 939.5 MB`；跨节点占比从 M=8 的 7/8 压到 M=4 的 `(3/7)×(7/8) = 3/8`。带宽取值 NVLink 400 GB/s、IB 50 GB/s（量级示意；含 seeded 路由不均因子）。

### 场景 4：MLA 压缩比 + DSA 稀疏注意力

```text
========================================================================
场景 4：MLA 压缩比 + DSA 稀疏注意力（V3/V3.2 真实维度）
========================================================================
V3 MHA 假设下 KV/token/层: 64.0 KiB
V3 MLA 实际 KV/token/层:   1.12 KiB
压缩比: 56.9x
潜空间重建误差（无噪声）: 1.01e-15
潜空间重建误差（5% 噪声）: 4.99e-02
V3.2 DSA 主注意力 FLOPs 比例 (k/L=2048/128K): 0.0156
```

`32768 / 576 = 56.9×`（MHA 2×128×128 元素 vs MLA 512+64 元素，BF16）。重建误差 1e-15 量级（浮点往返）演示了"对潜空间内数据无损"；5% 满秩噪声下误差 4.99e-02 演示低秩外成分的代价有界。DSA 的 k/L = 2048/131072 = 1/64。

### 场景 5：一个优化器 step 的时间账

```text
========================================================================
场景 5：一个优化器 step 的时间账（为什么不用 TP、EP 敢跨节点）
========================================================================
单卡 micro-batch 计算时间: 5308 ms（8192 tokens × 0.648 ms/token 官方口径）
all-to-all 每 token 通信时间: 0.0045 ms（dispatch+combine）
计算/通信比: 144x
32-micro-batch step：1F1B 气泡 79.6 s（占 31.9%）
32-micro-batch step：DualPipe 气泡 29.7 s（占 14.9%）
DualPipe 每 step 省下的时间: 49.9 s

核心结论：通信可以被计算完全盖住 ⇒ 省掉 TP、EP 跨节点、气泡近零。
```

0.648 ms/token 来自官方口径（180K H800 GPU 小时 / 1T tokens）。计算通信比 ~144× 是"all-to-all 可隐藏"的定量表达；气泡账则回答了"为什么非 DualPipe 不可"——32 个 micro-batch 的 step，1F1B 光气泡就空转 79.6 秒（31.9%），DualPipe 砍掉 49.9 秒。

## 7.4 核心代码片段

`pipeline.py` 的闭式气泡（与技术报告 Table 2 逐字符对应）：

```python
def bubble_1f1b(pp: int, f: float, b: float) -> float:
    if pp < 2:
        return 0.0
    return (pp - 1) * (f + b)

def bubble_dualpipe(pp: int, f: float, b: float, w: float) -> float:
    if pp < 4:
        return 0.0
    if pp % 2 != 0:
        raise ValueError("DualPipe 要求 PP 为偶数（每个设备承载两个虚拟 stage）")
    inner = max(f + b - 3.0 * w, 0.0)
    return (pp // 2 - 1) * inner
```

`ep.py` 的通信量与节点受限路由：

```python
def dispatch_bytes_per_gpu(tokens_per_gpu: int, cfg: EpConfig) -> float:
    return float(tokens_per_gpu * cfg.topk * cfg.hidden * cfg.dtype_bytes)

def inter_node_fraction(cfg: EpConfig) -> float:
    n = cfg.num_nodes
    m = cfg.nodes_limited if cfg.nodes_limited is not None else n
    base = (cfg.node_size - 1) / cfg.node_size  # 不限节点时的跨节点占比
    return (m - 1) / (n - 1) * base if n > 1 else 0.0
```

`mla.py` 的压缩比（V3 真实维度，验证 56.9×）：

```python
def v3_reference_config() -> MlaConfig:
    return MlaConfig(n_heads=128, d_head=128, n_latent=512, n_rope=64)

def kv_compression_ratio(cfg: MlaConfig) -> float:
    return kv_elements_mha(cfg) / kv_elements_mla(cfg)  # 32768 / 576 ≈ 56.9
```

## 7.5 测试一览

```text
tests/test_pipeline.py  闭式公式、奇数 PP 报错、调度器复现闭式（1e-9）、
                        GPipe/1F1B 同气泡、甘特图形状、确定性
tests/test_fp8.py       E4M3 网格（饱和/次正规/RNE）、缩放因子形状、
                        动态范围扫描三断言、累加对比、量化 floor 口径
tests/test_ep.py        字节公式、FP8 dispatch 减半、节点受限分数 (3/7)×(7/8)、
                        不均因子范围与放大效应、step 时间量级
tests/test_mla.py       V3 压缩比精确值、重建误差（无损/有界）、
                        indexer 打分与 top-K 选择正确性
tests/test_demo.py      5 个场景的结构、量级、排序与确定性
────────────────────────────────────────────────
97 passed in ~22s
```

## 7.6 动手建议

1. 把场景 1 的 `W` 从 0.2 调到 1.5（超过 `(F+B)/3`），观察 `dualpipe_exposed_comm` 生效、优势缩水——理解"DualPipe 的前提是通信盖得住"。
2. 把场景 3 的 `nodes_limited` 改成 `None`，再改成 `1`——跨节点流量占比从 3/8 → 7/8 → 0，时间差近 2 倍。
3. 把 `fp8_gemm_simulate` 的 `promote_every` 从 128 提到 512——累加误差上升，体会 N_C=128 这个"最小显著提升精度"的取值。

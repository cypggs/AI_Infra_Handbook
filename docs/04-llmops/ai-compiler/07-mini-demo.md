# 7. 工程实践：Mini Demo

> 一句话理解：**`ai_compiler_mini` 用纯 Python + numpy（约 400 行）重建了 AI 编译器的四个核心机制**——graph IR、算子融合 pass、auto-tune cost model、Triton-like tile kernel 模拟器。没有 GPU、没有 CUDA，但编译链路的每一环语义都可运行、可对拍。

## 7.1 为什么需要这个 Mini Demo

AI 编译器的真实系统（PyTorch + Inductor + Triton）动辄数十万行代码，编译一次要几分钟，调试还要真 GPU。Mini Demo 把链路压缩到 CPU 可运行的规模，让你可以：

- 单步跟踪"Python 计算 → IR → 融合 → 调优 → kernel 模拟执行"的完整编译流程。
- 用 numpy 参考执行对拍每一步的正确性（误差 < 1e-9）。
- 亲手改融合规则 / cost model 参数，观察输出变化——这是理解真实编译器 pass 的最短路径。
- 作为阅读 Triton / Inductor 源码前的"可运行草图"。

## 7.2 快速开始

```bash
cd docs/04-llmops/ai-compiler/mini-demo
pip install -e ".[dev]"               # 依赖 numpy + pytest
pytest tests/ -v                      # 45 个测试全部通过
python -m ai_compiler_mini.demo       # 跑六个端到端场景
```

## 7.3 模块与真实系统的映射

```
ai_compiler_mini/
├── graph.py        # 计算图 IR：Node/OpKind/Graph，shape 推导 + numpy 参考执行
├── fusion.py       # 算子融合 pass：结构规则 + 单消费者合法性检查 + 诊断
├── tune.py         # 朴素 auto-tuner：配置空间 + 启发式 cost model（确定性打分）
└── triton_like.py  # Triton-like tile kernel 模拟器：launch/program/tile 语义 + 访存统计
```

| Mini Demo | 真实系统 |
|---|---|
| `Graph`（IR + 参考执行） | torch.fx / XLA HLO / TVM Relax |
| `fuse()`（融合 pass） | Inductor scheduler / XLA HloPass / TVM FuseOps |
| `autotune()`（cost model） | Triton `@autotune` / Inductor max-autotune / Ansor |
| `run_tiled_matmul()`（tile 语义） | Triton kernel → TTIR/TTGIR → PTX → SASS |
| `KernelStats`（访存统计） | Nsight Compute 的 memory throughput 面板 |

## 7.4 六个端到端场景

### 场景 1：Graph Capture

把 `y = relu(x @ W + bias).sum(axis=1)` 捕获成文本形式 IR（输出节选）：

```text
graph {
  %x = input() : (64, 48)
  %W = const() : (48, 32)
  %bias = const() : (32,)
  %mm = matmul(%x, %W) : (64, 32)
  %bias_add = add(%mm, %bias) : (64, 32)
  %relu = relu(%bias_add) : (64, 32)
  %rowsum = sum(%relu) : (64, 1) axis=1 keepdims=True
}
节点数: 7，其中 placeholder=1, constant=2
```

对应 `torch.fx` 的 `GraphModule` 或 MLIR 的文本形式：每个节点有算子名、输入边（SSA 形式）、推导出的 shape。

### 场景 2：算子融合 pass

对同一张图跑 `fuse()`：

```text
融合结果（每组 = 一个 kernel）：
  kernel0 [matmul_epilogue] %mm -> %bias_add -> %relu -> %rowsum

原始计算节点 4 个 -> 融合后 1 个 kernel
```

`matmul → add(bias) → relu → sum` 四节点合成一个 kernel：GEMM 的 epilogue 融合 + elementwise 链融合 + 归约融合全部命中。融合规则与本主题 2.2 节一致——单消费者才融、结构规则限定可融组合；对不满足条件的边，`explain_non_fusion()` 会逐条给出原因（如"有 2 个消费者，融合会导致重复计算"）。

### 场景 3：Auto-tuner

M=N=K=256 的 GEMM，config space 生成 576 个候选配置，启发式 cost model 打分输出 Top-3（实测输出）：

```text
问题规模 M=256 N=256 K=256，候选配置 576 个

Top-3 配置（score = 预估毫秒，越低越好）：
  #1 BM=128 BN=128 BK= 16 warps=4 stages=3  score=0.0324 ms
      分解: mem=0.0002 comp=0.0322 launch=0.0000 waste=0.0000 (padding 浪费 0.0%)
  #2 BM=128 BN=128 BK= 16 warps=4 stages=4  score=0.0324 ms
      分解: mem=0.0002 comp=0.0322 launch=0.0000 waste=0.0000 (padding 浪费 0.0%)
  #3 BM=128 BN=128 BK= 32 warps=4 stages=3  score=0.0324 ms
      分解: mem=0.0002 comp=0.0322 launch=0.0000 waste=0.0000 (padding 浪费 0.0%)
```

打分是纯解析的（带宽/峰值算力/launch 开销/padding 浪费四项分解），不依赖 wall-clock，因此结果完全确定。大 tile 胜出正是因为 2.3 节的算术强度逻辑：BM=BN=128 时 A/B 的重复读取次数最少。这是 Triton autotune 与 Inductor max-autotune 的"教学版同构"。

### 场景 4：Triton-like tile 语义模拟 GEMM

在 M=100、K=60、N=84（均不被 32 整除，存在边界 tile）上模拟分块 GEMM：

```text
grid = (4, 3)，共 12 个 program
全局读 305.3 KB，写 67.2 KB
与 numpy 参考的最大误差: 1.78e-14 -> PASS
```

`run_tiled_matmul` 复刻了 Triton 的 program 语义：每个 program 用 `pid` 定位自己负责的 tile，K 维在 program 内部按 BLOCK_K 循环累加，边界 tile 自动截断。`KernelStats` 统计的全局内存流量同时验证了 tiling 直觉——BLOCK 越小，A/B 被重复读得越多（`test_smaller_blocks_repeat_traffic` 专门断言了这一点）。

### 场景 5：融合 vs 未融合的内存流量对比

对 `relu(x).sum(axis=1)`（x 形状 128x96）分别模拟融合 kernel 与 eager 逐算子执行：

```text
未融合（eager）：295.9 KB 全局流量
融合 kernel  ：99.3 KB 全局流量
流量下降 66.4%（中间结果不再往返 HBM）
结果一致: True
```

这正是 2.2 节融合思想的量化演示：eager 版每个中间张量都要写回再读回（多 2 次 x 大小的往返），融合版每行只读一次、写一次。

### 场景 6：端到端 mini 编译流程

把前五个场景串成一次完整"编译"（实测输出）：

```text
[1] graph capture
    7 个 IR 节点
[2] fusion pass
    kernel0 [matmul_epilogue] <- mm, bias_add, relu, rowsum
[3] autotune (matmul 组)
    选中 BM=64 BN=32 BK=16 warps=4 stages=3
[4] codegen + 模拟执行
    生成 1 个 GEMM kernel：1 programs，53.2 KB 流量，误差 1.07e-14
[5] 正确性对拍
    eager 后端 rowsum = [[ 99.6757]
 [ 80.2185]
 [101.2184]
 [124.6992]] ...

端到端 PASS：graph -> fusion -> tuning -> simulated codegen 全链路一致
```

## 7.5 测试

`tests/` 下 45 个确定性测试，不依赖 wall-clock（打分走解析 cost model，正确性走 numpy 对拍）：

| 文件 | 数量 | 覆盖 |
|---|---|---|
| `test_graph.py` | 14 | IR 构造、shape 推导（广播/归约/错误路径）、参考执行 |
| `test_fusion.py` | 12 | 链式融合、GEMM epilogue、单消费者规则、归约边界、诊断输出 |
| `test_triton_like.py` | 9 | tile 执行正确性（含边界 tile）、访存统计、融合流量对比 |
| `test_tune.py` | 9 | 配置空间、打分确定性、padding 惩罚、tile 大小与流量关系 |
| `test_demo.py` | 1 | 六个场景端到端可运行且正确性检查全部 PASS |

## 7.6 练习建议

1. 在 `fusion.py` 里加一条规则"matmul → reduce 允许融合"，观察场景 2/6 输出变化，并思考真实编译器为什么默认不这么做。
2. 把 `heuristic_cost` 里的 `HBM_BW_GBS` 改成 8 TB/s（Rubin 量级），看最优 tile 是否变化。
3. 给 `triton_like.py` 加一个 softmax 融合 kernel（max、sub、exp、sum、div 一次完成），对比未融合版本的流量。

## 本章小结

- Mini Demo 用 400 行 Python 复刻了编译链路四环：graph IR → 融合 → autotune → tile kernel 模拟执行。
- 45 个确定性测试全部通过；六个场景输出与文档记录完全一致。
- 每个模块都能对应到真实系统（fx/Inductor/Triton/NCU），是读真实源码前的理想草图。

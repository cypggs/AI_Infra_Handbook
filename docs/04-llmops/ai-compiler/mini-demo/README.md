# AI 编译器 Mini Demo

用纯 Python + numpy 实现的微型 AI 编译器教学模拟器，演示 **graph IR / 算子融合 / auto-tune cost model / Triton-like tile kernel 语义** 四个核心机制。全部 CPU 可运行，无任何 GPU 依赖。

## 快速开始

```bash
pip install -e ".[dev]"
pytest tests/ -v
python -m ai_compiler_mini.demo
```

## 六个场景

1. **Graph Capture**：把 `y = relu(x @ W + bias).sum(axis=1)` 捕获成文本形式 IR（类比 torch.fx / MLIR）
2. **算子融合 pass**：GEMM + bias + relu + rowsum 四个节点融合成 1 个 kernel（类比 Inductor / XLA fusion）
3. **Auto-tuner**：576 个 tile 配置经启发式 cost model 打分，输出 Top-3（类比 Triton autotune / max-autotune）
4. **Triton-like tile 语义模拟 GEMM**：在边界 tile（不整除）下与 numpy 参考对拍，误差 < 1e-9
5. **融合 vs 未融合**：行归约 kernel 融合后全局内存流量下降约 66%（中间结果不再往返 HBM）
6. **端到端 mini 编译流程**：graph -> fusion -> tuning -> simulated codegen，全链路一致性校验

## 模块

```
ai_compiler_mini/
├── graph.py        # 计算图 IR：Node/OpKind/Graph，shape 推导 + numpy 参考执行
├── fusion.py       # 算子融合 pass：结构规则 + 单消费者合法性检查 + 诊断输出
├── tune.py         # 朴素 auto-tuner：配置空间 + 启发式 cost model（确定性打分）
├── triton_like.py  # Triton-like tile kernel 模拟器：launch/program/tile 语义 + 访存统计
└── demo.py         # 六个端到端场景
```

## 与真实系统的映射

| Mini Demo | 真实系统 |
|---|---|
| `Graph`（IR + 参考执行） | torch.fx / XLA HLO / TVM Relax |
| `fuse()`（融合 pass） | Inductor fusion / XLA HloPass / TVM FuseOps |
| `autotune()`（cost model） | Triton @autotune / Inductor max-autotune / Ansor |
| `run_tiled_matmul()`（tile 语义） | Triton kernel -> PTX -> SASS |
| `KernelStats`（访存统计） | NCU / profiler 的 memory throughput |
| `heuristic_cost()`（打分） | roofline model / analytical cost model |

## 测试

`tests/` 下 45 个确定性测试（不依赖 wall-clock，全部基于解析 cost model 与 numpy 对拍）：

- `test_graph.py`：IR 构造、shape 推导（广播/归约）、参考执行
- `test_fusion.py`：链式融合、GEMM epilogue、单消费者规则、归约边界
- `test_tune.py`：配置空间、打分确定性、padding 惩罚、tile 大小与流量关系
- `test_triton_like.py`：tile 执行正确性（含边界 tile）、访存统计、融合流量对比
- `test_demo.py`：六个场景端到端可运行且正确性检查全部 PASS

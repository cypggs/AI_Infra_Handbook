# 7. 工程实践：CPU 可运行的 GPU 执行模型模拟器

真实 GPU/CUDA 开发需要 NVIDIA 硬件、nvcc 编译器和 Nsight 性能分析工具。但为了让大家在没有 GPU 的情况下也能理解核心概念，我们写了一个纯 Python 模拟器。

## 7.1 设计目标

这个 Mini Demo 模拟：

1. **Grid/Block/Warp/Thread 层级**；
2. **Global memory 合并访问 vs 跨步访问**；
3. **Shared memory bank conflict**；
4. **Naive vs Tiled 矩阵乘法的 global memory 事务数**；
5. **SM Occupancy 计算**。

它**不模拟真实性能、不执行真实矩阵运算、不涉及时钟周期**，只把注意力集中在“概念是否被正确体现”上。

## 7.2 目录结构

```
mini-demo/
├── README.md
├── pyproject.toml
├── gpu_cuda_mini/
│   ├── __init__.py
│   ├── arch.py          # Grid/Block/Warp/Thread 模拟
│   ├── memory.py        # Global / Shared Memory 模拟
│   ├── kernel.py        # Kernel 执行与统计
│   ├── occupancy.py     # Occupancy 计算
│   └── demo.py          # 入口脚本
└── tests/
    ├── __init__.py
    ├── test_arch.py
    ├── test_memory.py
    ├── test_kernel.py
    └── test_occupancy.py
```

## 7.3 运行方式

```bash
cd docs/01-foundation/gpu-cuda/mini-demo
pip install -e ".[dev]"
pytest tests/ -v
python -m gpu_cuda_mini.demo
```

## 7.4 关键代码片段

### Grid / Block / Warp 拆分

```python
grid = build_grid(grid_dim=(2, 2), block_dim=(4, 4))
# 64 个线程，分成 4 个 Block，每个 Block 16 线程 = 1 个 Warp
```

### 合并访问 vs 跨步访问

```python
def coalesced(t):
    return t.global_idx[0] * 4  # 线程 i 访问连续地址

def strided(t):
    return t.global_idx[0] * 4 * 32  # 线程 i 跨 32 个元素
```

测试结果：128 线程下，合并访问只需 4 次 transaction，跨步访问需要 128 次。

### Shared memory bank conflict

```python
# 行优先：32 个线程访问 32 个不同 bank，无冲突
addr = (0 * 32 + thread_idx) * 4

# 列优先：32 个线程都访问同一个 bank，严重冲突
addr = (thread_idx * 32 + 0) * 4
```

### Tiled 矩阵乘

```python
# Naive：每个线程读一整行 A 和一整列 B
# Tiled：每个 Block 协作加载 A/B 的一个 tile 到 shared memory，再复用
```

对 $N=64$、tile=8 的模拟结果：

| 版本 | Global Memory Transactions | Element Accesses |
|---|---|---|
| Naive | 270,336 | 524,288 |
| Tiled | 8,192 | 65,536 |
| 降低 | **97.0%** | **87.5%** |

### Occupancy 计算

```python
cfg = BlockResourceUsage(
    threads_per_block=256,
    registers_per_thread=128,
    shared_memory_per_block=0,
)
ratio, warps, limit = occupancy(cfg)
# ratio=50%, warps=16, limit=registers
```

## 7.5 测试结果示例

```text
$ pytest tests/ -v
============================= test session starts ==============================
tests/test_arch.py::test_grid_dimensions PASSED
tests/test_arch.py::test_warp_count PASSED
tests/test_arch.py::test_total_threads PASSED
tests/test_kernel.py::test_tiled_reduces_transactions PASSED
tests/test_kernel.py::test_larger_tile_fewer_transactions PASSED
tests/test_memory.py::test_coalesced_vs_strided PASSED
tests/test_memory.py::test_shared_bank_conflict PASSED
tests/test_memory.py::test_bank_function PASSED
tests/test_occupancy.py::test_occupancy_basic PASSED
tests/test_occupancy.py::test_register_limited PASSED
tests/test_occupancy.py::test_shared_memory_limited PASSED
============================== 11 passed in 0.11s ==============================
```

## 7.6 模拟器与真实 GPU 的差异

| 维度 | 模拟器 | 真实 GPU |
|---|---|---|
| 执行 | Python 循环 | 硬件 SIMD/SIMT |
| 时间 | 不计时 | 精确的时钟周期、流水线、缓存 |
| 内存延迟 | 抽象为 transaction 数 | 真实的 cache hit/miss、bank conflict 时序 |
| 精度 | 只统计访问模式 | 实际 FLOPs、数值误差、Tensor Core 行为 |
| 占用面积 | 简化的资源限制 | 复杂的 register allocation、spilling、scheduler |
| 用途 | 教学理解 | 生产性能优化 |

## 7.7 本节小结

这个 Mini Demo 的价值在于：

1. **把不可见的 GPU 内部行为变成可统计的数字**；
2. **用实验证明 coalescing、tiling、bank conflict 为什么重要**；
3. **为后续学习真实 CUDA / Nsight 建立直觉**。

如果你想继续深入，下一节会进入真实生产环境：GPU 选型、虚拟化、监控与故障排查。

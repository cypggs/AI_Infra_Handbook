# GPU/CUDA Mini Demo

This is a self-contained, **CPU-runnable** mini demo for the AI Infra Handbook
theme **"GPU 架构与 CUDA 基础"**. It simulates key GPU execution concepts
using pure Python, so you can explore them without an NVIDIA GPU.

## What it demonstrates

1. **Grid / Block / Warp / Thread hierarchy** — `arch.py`
2. **Global memory coalescing** — `memory.py` + `kernel.py`
3. **Shared memory bank conflict** — `memory.py`
4. **Naive vs tiled matrix multiplication** — `kernel.py`
5. **SM occupancy calculation** — `occupancy.py`

## Install

```bash
cd docs/01-foundation/gpu-cuda/mini-demo
pip install -e ".[dev]"
```

No GPU, no CUDA toolkit, no PyTorch required.

## Run tests

```bash
pytest tests/ -v
```

The tests verify:

- Grid/block/warp layout correctness;
- Coalesced access produces far fewer transactions than strided access;
- Row-major shared memory access has no bank conflict while column-major does;
- Tiled matrix multiplication reduces global memory transactions;
- Occupancy is limited by registers, shared memory or warp count as expected.

## Run the demo

```bash
python -m gpu_cuda_mini.demo
```

Example output:

```text
=== Warp / Block / Grid layout ===
Grid dim: (2, 2), Block dim: (4, 4)
Total threads: 128
Threads per block: 16
Warps per block: 1
  Warp 0: [(0, 0), (0, 1), ...]

=== Global Memory Coalescing ===
Coalesced access: 4 transactions for 128 threads
Strided access:   128 transactions for 128 threads
Coalescing reduces transactions by 96.9%

=== Shared Memory Bank Conflict ===
Row-major access: max conflict=1, total conflicts=0
Column-major access: max conflict=32, total conflicts=31

=== Naive vs Tiled MatMul Global Memory Transactions ===
Naive: A=... tx, B=... tx, total=... tx, ... element accesses
Tiled: total=... tx, ... element accesses
Tiling reduces global transactions by ...%

=== Occupancy Calculation ===
threads=256, regs/thread=32, smem=0KB -> occupancy=100%, active_warps=32, limited_by=warps
...
```

## Educational goals

- See how a Grid/Block is split into warps of 32 threads.
- Understand why coalesced memory access matters.
- Feel the difference between naive and tiled matrix multiplication at the
  memory-transaction level.
- Learn that occupancy is constrained by multiple resources, not just thread count.

## Difference from real GPU/CUDA

This simulator intentionally abstracts away timing, actual FLOPs, cache eviction,
scheduling policies and many micro-architectural details. It is designed to make
**concepts** tangible. For real performance work, you still need an NVIDIA GPU,
`nvcc`, `ncu` (Nsight Compute) and `nsys` (Nsight Systems).

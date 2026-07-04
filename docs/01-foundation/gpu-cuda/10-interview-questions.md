# 10. 面试题

面试 GPU/CUDA，通常会问三个层次：概念理解、编程能力、生产经验。下面是按难度分层的题目与参考答案要点。

## 10.1 初级

### Q1：CPU 和 GPU 的主要区别是什么？

**要点**：

- CPU 核心少、单核强、擅长城控制分支和低延迟任务；
- GPU 核心多、单核简单、擅长高并行吞吐任务；
- GPU 有高带宽显存（HBM），适合数据并行计算。

### Q2：什么是 CUDA 中的 Thread、Block、Grid、Warp？

**要点**：

- Thread：最小执行单元；
- Block：由多个 Thread 组成，可共享 shared memory 和同步；
- Grid：一次 kernel 启动的所有 Block；
- Warp：32 个 Thread，硬件调度单位。

### Q3：什么是 warp divergence？怎么避免？

**要点**：

- 同一个 warp 内线程走不同分支，导致串行执行；
- 避免方法：让分支发生在 warp 之间，而非 warp 内部；基于 block/warp ID 做分支。

### Q4：什么是内存合并访问（coalesced access）？

**要点**：

- 一个 warp 的线程访问连续的内存地址，合并成少量 transaction；
- 行优先访问矩阵是合并访问，列优先通常不是。

## 10.2 中级

### Q5：解释 SIMT 和 SIMD 的区别。

**要点**：

- SIMD：同一指令同时处理多个数据，控制流统一；
- SIMT：多个线程执行同一指令，但每个线程有自己的程序计数器和寄存器，支持更灵活的分支（虽然 warp divergence 会降速）。

### Q6：什么是 occupancy？哪些因素会影响 occupancy？

**要点**：

- Occupancy = 实际驻留 warp 数 / SM 最大 warp 数；
- 影响因素：block size、每个线程寄存器数、shared memory 用量、warp scheduler 限制；
- 高 occupancy 有助于 hiding 延迟，但不是性能唯一指标。

### Q7：Shared memory 的 bank conflict 是什么？怎么解决？

**要点**：

- Shared memory 分成 32 个 bank，warp 内多个线程同时访问同一 bank 会串行化；
- 解决方法：调整数据布局、加 padding，让线程访问不同 bank。

### Q8：解释 Roofline Model。

**要点**：

- 横轴：计算密度（FLOPs/byte）；
- 纵轴：实际性能；
- 斜线：内存带宽限制；平顶：峰值算力限制；
- 用于判断 kernel 是计算瓶颈还是内存瓶颈。

### Q9：H100 相比 A100 的主要提升有哪些？

**要点**：

- FP8 Tensor Core 与 Transformer Engine；
- NVLink 4（900 GB/s 双向 vs A100 600 GB/s）；
- HBM3 更高带宽（3.35 TB/s vs 2 TB/s）；
- 新指令如 TMA（Tensor Memory Accelerator）。

## 10.3 高级

### Q10：Flash Attention 为什么比标准 Attention 快？

**要点**：

- 标准 Attention 把中间矩阵 S、P 写回 HBM，读写量大；
- Flash Attention 用 tiling 把 Q/K/V 分块，在 SRAM/shared memory 内完成 softmax 和矩阵乘；
- online softmax 避免存储完整 S 矩阵；
- 反向时重计算，用算力换显存。

### Q11：CUDA 程序的编译链路是什么？

**要点**：

- CUDA C/C++ → nvcc 前端分离主机代码和设备代码；
- 设备代码 → PTX（虚拟 ISA）→ SASS（特定架构机器码）；
- PTX 支持 JIT，保证向前兼容；
- 运行时 driver 加载 cubin 并执行。

### Q12：PyTorch 调用 `.cuda()` 后，底层发生了什么？

**要点**：

- Python 层 → ATen 算子实现；
- c10 CUDA stream/allocator 管理异步执行和显存；
- 底层调用 cuBLAS/cuDNN/CUDA driver API；
- Kernel 在 GPU 上异步执行，结果通过 stream 同步返回。

### Q13：多卡训练中 NCCL all-reduce 的瓶颈可能在哪里？

**要点**：

- NVLink/IB 带宽不足；
- 拓扑不优（跨 switch、跨机柜）；
- 消息太小，启动开销占比高；
- 慢节点拖累整体（straggler）；
- NCCL 算法选择不当（Ring vs Tree vs NVLink-SHARP）。

### Q14：你怎么排查一个 CUDA OOM？

**要点**：

- 区分 allocated、reserved、`nvidia-smi` 显示值；
- 检查 batch size、序列长度、KV Cache；
- 检查 activation checkpointing 和 gradient accumulation；
- 查看是否有其他进程占用显存；
- 用 `torch.cuda.memory_summary()` 分析峰值和碎片。

### Q15：MIG、MPS、Time-slicing 怎么选？

**要点**：

- MIG：硬件隔离，适合生产多租户；
- MPS：进程级共享，适合同一信任域内多服务；
- Time-slicing：时间片轮转，适合开发测试；
- 选择依据：隔离性要求、开销、成本。

## 10.4 本节小结

GPU/CUDA 面试的核心考察点：

1. **基础概念**：SIMT、Warp、内存层次、合并访问；
2. **编程能力**：能分析 kernel 性能瓶颈、知道怎么优化；
3. **架构理解**：Tensor Core、NVLink、HBM、架构演进；
4. **生产经验**：OOM、NCCL、Xid、MIG/MPS、监控。

建议面试前结合 Mini Demo 和 Nsight Compute 实际跑几个 kernel，把概念落到数字上。

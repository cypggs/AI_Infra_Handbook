# 9. 最佳实践

这一节把前面所有内容凝结成可执行的原则。无论你是写 CUDA kernel、调推理引擎，还是做 GPU 集群调度，这些原则都适用。

## 9.1 内存访问优先于计算优化

GPU 的峰值算力很高，但内存带宽相对有限。很多时候 kernel 慢不是因为算得慢，而是因为等数据。

**原则**：

- 先优化 global memory 访问模式（合并访问、减少读写）；
- 再用 shared memory 做 tiling 复用数据；
- 最后才考虑指令级优化。

## 9.2 合理选择 block size

Block size 影响 warp 数量、occupancy 和 shared memory 使用。

常见选择：

- **128、256、512**：通用矩阵乘、卷积；
- **1024**：需要大量线程协作的场景，但可能降低并发 block 数。

选择原则：

- 尽量是 warp size（32）的倍数；
- 能让 SM 上同时驻留多个 block；
- 不超过 shared memory 和寄存器限制。

## 9.3 避免 warp divergence

同一个 warp 内出现分支会导致串行执行。

**避免方法**：

- 让分支基于 `threadIdx.x / 32` 或 block-level 索引，而不是 `threadIdx.x % 2`；
- 把需要分支的逻辑放到 warp 之间，而不是 warp 内部。

## 9.4 平衡 occupancy 与寄存器使用

高 occupancy 有助于 hiding 延迟，但：

- 每个线程用太多寄存器，会减少可同时驻留的 warp 数；
- 寄存器 spill 到 local memory 会严重降速。

**原则**：

- 用 `launch_bounds` 或编译器提示限制寄存器；
- 通过 Nsight Compute 查看 register usage；
- 不要为了 occupancy 无限压缩寄存器，关键是**有效计算吞吐**。

## 9.5 Kernel Fusion：减少内存往返

把多个小 kernel 合并成一个，避免中间结果写回 HBM。

典型例子：

- Flash Attention 把 attention 的多个步骤融合；
- LayerNorm + Activation + Gemm 融合成一个 kernel。

PyTorch 2.0 的 `torch.compile` 会自动做大量 fusion，底层通过 Triton 生成 kernel。

## 9.6 混合精度：FP16/BF16/FP8/FP4

| 精度 | 建议 |
|---|---|
| FP32 | 对数值敏感的部分（如 loss scaling、部分 norm） |
| BF16 | 训练首选，动态范围大，稳定性好 |
| FP16 | 推理、混合精度训练 |
| FP8 | H100+ 推理，部分训练（需 Transformer Engine） |
| FP4 | B200+ 推理量化 |

**原则**：

- 训练优先保证稳定，再追求速度；
- 推理可以更大胆地量化；
- 始终用 loss scaling 或梯度缩放防止 FP16 下溢。

## 9.7 使用成熟的库，避免重复造轮子

| 场景 | 推荐 |
|---|---|
| 矩阵乘 | cuBLAS、CUTLASS |
| 卷积/Attention | cuDNN、Flash Attention |
| 多卡通信 | NCCL |
| 通用并行算法 | Thrust |
| 自定义融合算子 | Triton、CUTLASS |

**原则**：手写 CUDA kernel 是最后手段。先确认 cuBLAS/cuDNN 没有满足需求的实现。

## 9.8 Profile 驱动优化

不要猜测瓶颈，要测量。

工具链：

- `nvidia-smi dmon`：快速看利用率；
- `nsys`：系统级时间线；
- `ncu`：kernel 级深度分析；
- `DCGM`：生产监控。

关注指标：

- **Memory throughput / peak bandwidth ratio**：接近 1 说明内存瓶颈；
- **Tensor Core utilization**：低说明没用到 Tensor Core；
- **Occupancy**：低说明并发 warp 不够；
- **Warp stall reason**：看是等待内存、等待指令还是同步。

## 9.9 Kubernetes 调度层面的最佳实践

详细内容参见 [Kubernetes GPU 调度](/02-cloud-native/kubernetes/)，这里列出关键原则：

- 训练任务优先使用整卡或 MIG 实例，避免 MPS 的资源争抢；
- 推理任务按延迟要求选择 MIG/MPS/整卡；
- 启用 GPU 拓扑感知调度，让需要 NCCL 的 Pod 落在 NVLink 全互联节点；
- 监控 DCGM 指标，设置 Xid、温度、功耗告警；
- 定期做显存碎片整理和节点轮换。

## 9.10 本节小结

高效 GPU 使用的十条原则：

1. 内存访问比计算更重要；
2. Block size 选 128/256/512 的常见值；
3. 避免 warp divergence；
4. 平衡 occupancy 与寄存器使用；
5. 能 fusion 就 fusion；
6. 混合精度按场景选择；
7. 优先用成熟库，不轻易手写 kernel；
8. 用 Nsight / DCGM 驱动优化；
9. 多租户环境按隔离性选 MIG/MPS；
10. 监控比调参更重要。

下一节是面试题，检验你是否真正掌握了这些概念。

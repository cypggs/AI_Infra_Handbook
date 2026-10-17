# 10. 面试题

## Q1：torch.compile 之后程序变快，底层发生了什么？

**参考答案**：Dynamo 在字节码层把 forward 捕获成 FX 图（带 guard 校验）；AOTAutograd 补出反向图；Inductor 做 lowering（aten → 原语）、融合（垂直/水平/模板融合）、调度（buffer 复用），为每个融合组生成 Triton 源码；Triton 编译器把 kernel 编译成 cubin；wrapper 代码负责启动，可选 CPP wrapper 与 CUDA graphs。收益主要来自：融合消除 HBM 往返与 launch 开销、自动调优选更优 tile、CUDA graphs 消除残余 launch 开销。

## Q2：什么是算子融合？什么条件下两个算子不能融合？

**参考答案**：融合是把多个算子的计算合并进一个 kernel，中间结果留在片上（寄存器/shared memory），从而省掉 HBM 往返和 launch 开销。不能融合的典型情况：中间值有多个消费者（融合导致重复计算，除非它是组输出）；并行结构不兼容（如行归约与列归约无法共享 tile）；结构规则不允许的组合（mini 模型里 GEMM→归约不融，真实编译器视模板支持而定）。融合本质是带合法性约束的图划分问题。

## Q3：为什么 GEMM 的 tile 越大性能越好？有没有上限？

**参考答案**：算术强度 = FLOPs / 访存字节。tile 越大，每个从 HBM 读入的字节被复用的次数越多（A 的条带被 BN 个列块复用），算术强度上升，更接近算力上限。上限来自片上容量：BM×BK 与 BK×BN 的操作数要同时放进 shared memory，累加器要放进寄存器/TMEM；超过容量就溢出到本地内存，性能崩溃。所以最优 tile 由"容量约束 + autotune 实测"共同决定。

## Q4：Triton 相比手写 CUDA 的核心抽象差异是什么？

**参考答案**：CUDA 以线程为基本单元（每个线程算几个标量），程序员手动管理 block/warp、shared memory、bank conflict、指令流水线；Triton 以 program（处理一个 tile 的"虚拟处理器"）为基本单元，程序员用 tl.load/tl.dot/tl.store 写 tile 级代码，布局、线程映射、寄存器分配、mma 指令选择由编译器完成。代价是失去指令级控制权，遇到编译器表达不了的优化（复杂 warp specialization、TMEM 精细管理）需要 Gluon 或回到 CUDA。

## Q5：什么是 warp specialization？Triton 为什么把它做成自动的？

**参考答案**：Hopper/Blackwell 上 GEMM/attention 的最优执行需要把 warp 分组：producer warp 专职用 TMA 异步搬数，consumer warp 专职喂 Tensor Core，通过 mbarrier 同步重叠通信与计算。手写 CUDA 中这是一套易错的状态机（环形缓冲、相位管理）。Triton 3.4 起在 TTGIR 上分析依赖图自动完成划分与同步插入，让普通 kernel 免费获得流水线收益；3.5-3.7 持续加固，AMD gfx1250 路径也已支持。

## Q6：解释 num_warps 与 num_stages 对 kernel 性能的影响。

**参考答案**：num_warps 决定每个 program 的 warp 数：太少则并行度不足、Tensor Core 喂不饱；太多则同步开销与寄存器压力上升。num_stages 是软件流水线的级数：K 循环被展开成多级缓冲，load(k+n) 与 compute(k) 重叠；太少则访存延迟暴露，太多则 shared memory 被 buffer 占满反而限制 tile 大小。两者与 BLOCK 尺寸耦合，实践中交给 autotune 搜索。

## Q7：auto-tune 的 cost model 与实测 benchmark 各有什么优缺点？

**参考答案**：解析 cost model 快、确定性、可解释，适合粗筛大量候选，但精度有限（难以建模缓存、争用、编译器变换的实际效果）；实测 benchmark 准确，但每个候选要真编译真跑，成本高（几十秒到几分钟/候选），且受机器状态噪声影响。生产系统是混合制：cost model 粗筛到前 10-20 个，实测决选，结果写缓存复用。学习型 cost model（Ansor/Helion 路线）试图兼得两者，代价是冷启动需要数据。

## Q8：Inductor 生成的 kernel 与手写 Triton kernel 有什么区别？

**参考答案**：Inductor 是模板化生成：每个融合组套固定模板，tile 配置进 autotune 空间，风格统一、覆盖广、上限中等；手写 Triton 可以表达任意结构（persistent kernel、复杂 warp 分工、跨算子融合），上限更高但要人肉维护每个变体。工程上通用算子（norm/elementwise）交给 Inductor，性能敏感且形状稳定的算子（attention、MoE grouped GEMM、量化 GEMM）手写。

## Q9：cuTile 与 Triton 的抽象有何异同？为什么 NVIDIA 要推 cuTile？

**参考答案**：同为 tile 级抽象，都用 Python 写 kernel、编译到 MLIR 再到 SASS。差异：cuTile 把内存层级做成类型系统的一部分（tile 类型携带层级信息，load/mma/store 的层级下降由类型驱动），且深度绑定 TMA/tcgen05，目前限定 Blackwell；Triton 的抽象更偏"分布式张量操作"，硬件无关层更厚，可移植到 AMD/CPU。NVIDIA 推 cuTile 的原因：把程序员锁进自家最优指令路径（TMA/tcgen05 的用法被类型系统强制正确），同时降低 Blackwell 编程门槛。

## Q10：CUDA graphs 与编译器是什么关系？

**参考答案**：两者解决不同问题：编译器优化单个/多个 kernel 的质量与数量，CUDA graphs 消除 launch 开销（一次提交整段执行序列）。但互相塑造：CUDA graphs 要求固定地址与形状，促使引擎做 batch 分桶、KV cache 池化、静态 shape 编译；Inductor 2.8 的 graph partitioning 又把"围绕不可捕获算子拆分 CUDA graph"自动化。生产上二者搭配使用（torch.compile mode="reduce-overhead" 即此组合）。

## Q11：graph break 是什么，为什么它有害，怎么治理？

**参考答案**：Dynamo 遇到无法捕获进图的 Python 代码（动态控制流、第三方库调用、不支持的 C 扩展）时，把函数在该点切成两个子图，断点前后回到 eager。危害：子图间无法融合、Python 开销回归、guard 校验叠加。治理：用 `torch._dynamo.explain` 定位断点；把 host 逻辑移出热点函数；对确实需要的动态行为用 `torch.cond`/`torch.while_loop`（2.14 已支持 CUDA-graph 捕获）表达。

## Q12：MLIR 的 dialect 思想如何体现在 AI 编译器中？

**参考答案**：MLIR 允许每套算子集定义自己的 dialect（op 集合 + 类型 + 约束），不同抽象层用不同 dialect，层间用 lowering pass 连接。AI 编译器中：Triton 用 TTIR（语义层）→ TTGIR（GPU 布局层）→ LLVM/NVVM；cuTile 用 Tile IR → cuda_tile → nv_tileaa/nv_tileas → NVVM；StableHLO 是跨框架的图级 dialect。收益是多层级 IR 有工程载体，pass 与基础设施（pattern rewrite、pass 管理）可复用。

## Q13：TileLang 与 Triton 的定位差异是什么？

**参考答案**：Triton 是 OpenAI 主导的通用 kernel 语言，主打 NVIDIA/AMD 双栈与生态成熟；TileLang 构建在 Apache TVM 的 IR/pass 设施上，主打多后端（NVIDIA SM70-SM120、AMD ROCm、华为昇腾 950、Apple Metal、实验性 CPU/WebGPU/CuTe DSL），并配套 LSP、pass visualizer、并行 autotuner 等完整工具链。对芯片厂商与新硬件团队，TileLang 的"一套 DSL 多后端"更有吸引力；对通用 kernel 工程师，Triton 的生态与资料更丰富。

## Q14：什么是 megakernel？它为什么可能改变推理引擎的架构？

**参考答案**：megakernel 把整个模型（或推理 step）编译成单个 persistent kernel：所有层、所有通信在 kernel 内完成，用 task graph 与 GPU 内调度器（MPK 的 local/remote scheduler）替代 CPU 侧调度，消灭跨 kernel 的 launch、同步与显存往返。OSDI'26 的 MPK 报告 LLM 推理端到端 1.2-6.7 倍延迟下降。若成为主流，推理引擎的核心将从"调度算法 + kernel 库"转向"编译器 + 轻量 runtime"，引擎间差异更多地由编译产物质量决定。

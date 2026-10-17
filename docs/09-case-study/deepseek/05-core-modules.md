# 5. 核心模块

本章逐个拆解 DeepSeek 基础设施中最具辨识度的模块。每个模块按"动机 → 机制 → 关键数字"组织。

## 5.1 DualPipe：双向流水线调度

**动机。** 16 路 PP 的朴素代价是惨重的：1F1B 的流水线气泡为 `(PP-1)(F+B)`，PP=16 时相当于 45 个单位时间（取 F=1、B=2）白白空转。而跨节点 EP 又让每个 stage 之间多了 all-to-all 通信，不藏住就等于雪上加霜。

**机制。** DualPipe 的三个招式（技术报告 §3.2.1 + 开源仓库）：

1. **反向拆分**：把反向像 ZeroBubble 一样拆成"输入梯度 B_in"与"权重梯度 B_w"两块；
2. **前向反向配对重叠**：一对前向/反向 chunk 内部重新排布组件，手动调节通信与计算各占的 SM 比例，让 all-to-all 与 PP 通信在执行期间被完全盖住（论文原话：both all-to-all and PP communication can be fully hidden during execution）；
3. **双向注入**：micro-batch 从流水线两端同时进，互为填充——稳态下每个设备承载两个虚拟 stage（一个正向、一个反向）。

**关键数字（技术报告 Table 2）**：

| 方法 | 气泡 | 参数显存 | 激活显存 |
|---|---|---|---|
| 1F1B | (PP−1)(F+B) | 1× | PP |
| ZB1P | (PP−1)(F+B−2W) | 1× | PP |
| **DualPipe** | **(PP/2−1)(F&B+B−3W)** | **2×** | **PP+1** |

两点解读：第一，气泡从 O(PP) 降到 O(PP/2)，PP=16、F=1、B=2、W=0.2 时从 45 降到 16.8（缩减 62.7%，[Mini Demo 场景 1](07-mini-demo) 可复算）；第二，**2× 参数与 PP+1 激活的代价几乎免费**——EP64 把每卡专家参数切到 1/64，双拷贝摊到可以忽略；激活只比 1F1B 多 1/PP。前提条件同样重要：W 必须能被盖住，3W 超过 F+B 的部分会暴露回关键路径。

## 5.2 细粒度专家并行：把 all-to-all 藏进计算

**动机。** 671B 参数、37B 激活的 MoE（每层 256 个路由专家 + 1 个共享专家，每 token 选 top-8），单卡 80GB 显存装不下全部专家，专家必须跨卡切分——专家并行的 all-to-all 由此成为每层的固定开销。

**机制四件套**：

1. **通信量公式**：每 token dispatch 负载 = topk × hidden × 字节数（V3：8 × 7168 × 2B ≈ 114 KB），combine 对称。计算通信比 ≈ 140×（[Mini Demo 场景 3/5](07-mini-demo)）——这就是"能藏住"的定量底气；
2. **节点受限路由（node-limited routing）**：每个 token 的 8 个专家最多分布在 M=4 个节点上（技术报告：按节点亲和分 top-4 选），把跨节点（IB）流量占比从 7/8 压到 3/8；配合 DualPipe，all-to-all 与计算全重叠；
3. **无辅助损失负载均衡（aux-loss-free load balancing）**：传统做法加辅助损失防路由坍塌，但辅助损失会损害模型质量；V2/V3 改为给 router 的亲和分加**可学习的 bias 项**做均衡——负载均衡与模型质量解耦；
4. **配套开源件**：**EPLB**（Expert-Parallel Load Balancer，开源周 Day-4）在部署侧做专家放置优化；推理侧用**冗余专家**（prefill 每卡 8+1）吸收热点。

**DeepEP** 把上述机制落成内核（详见 [第 6 章](06-source-analysis)）：dispatch/combine 双模式（训练高通量 / 推理低延迟）、NVLink+RDMA 两级流水、FP8 dispatch、SM 资源可按调用控制以便与计算重叠。

## 5.3 FP8 混合精度训练：精度预算管理

**动机。** H800 的 FP8 峰值算力是 BF16 的 2 倍，不用等于一半预算打水漂。但 FP8（E4M3，3 位尾数）的固有量化误差是百分量级，2019 年以来"FP8 训练大规模模型"多次被尝试、从未在万亿参数级验证过。

**机制（技术报告 §3.3 四决策）**：

1. **全 E4M3（mantissa over exponents）**：前向、反向梯度统一 E4M3，不用 E4M3/E5M2 混合——靠细粒度缩放换取动态范围，把宝贵的尾数位留给精度；
2. **细粒度缩放（fine-grained quantization）**：前向激活按 **1×128**（每 128 元素一组）、反向按 **128×1** 分组，每组独立 amax 缩放——离群通道只伤害所在组，主体信号不被全局 amax 压入次正规区（[Mini Demo 场景 2](07-mini-demo) 的动态范围扫描直观展示）；
3. **高精度累加（increasing accumulation precision）**：H800 张量核的 FP8 MMA 内部累加精度不足，于是**每 N_C=128 个元素（4 条 WGMMA）把部分和提升到 CUDA Core FP32 累加**——代价是 WGMMA 发射率下降，但 H800 上两个 warpgroup 常驻、提升与 MMA 互相掩盖，张量核利用率不降；
4. **在线量化**：量化融入前序 kernel，不引入独立的转换 kernel 与额外显存往返；优化器状态与激活通信也用低精度（敏感部分保留 BF16）。

**关键数字**：在 16B 与 230B 两个 MoE 基线上各训约 1T tokens 验证，FP8 训练相对 BF16 基线的**损失误差始终低于 0.25%**（附录 B）——落在训练随机性可接受范围内。注意口径：这是端到端 loss 误差，不是单次 GEMM 误差；E4M3 单次量化的 GEMM 误差在百分量级是格式属性，靠误差近似无偏 + 训练过程平均来消化。

## 5.4 MLA：低秩 KV 压缩

**动机。** 长上下文推理的成本核心是 KV cache：标准 MHA 每 token 每层要存 `2 × 头数 × 头维度` 个元素。V3 的 128 头 × 128 维假设下是 64 KiB/token/层——128K 上下文就是单序列 8 GiB/层的怪物，带宽与容量都顶不住。

**机制（技术报告 §2.1.1）**：

1. **低秩压缩**：不为每头存 K/V，而是把每 token 的 KV 压到一个 **512 维共享潜向量 c_t**（降维投影 W_DKV），需要时对各头在线展开（升维投影）；
2. **解耦 RoPE**：位置编码不进潜向量，单独保留一个 **64 维的 k_R**——因为 RoPE 的相对位置旋转会破坏低秩性，混进去会让压缩失效；
3. **MQA 式索引友好**：潜向量维度低（576 元素/token/层 vs MHA 32768），使打分、检索、稀疏选择（DSA）的代价都可承受。

**关键数字**：V3 配置下 KV cache 每 token 每层 **576 元素 = 1.12 KiB**（BF16），相对 MHA **压缩 56.9×**（[Mini Demo 场景 4](07-mini-demo)）；对潜空间内的数据该压缩是**无损**的（低秩世界重建误差为 0），压缩的是存储与带宽，不是模型表达能力。DeepSeek 自 V2（2024-05）起用 MLA，V3/V3.2/R1/V4 一脉相承——V4 的百万 token 上下文若没有 MLA+稀疏化是不可能服务的。

## 5.5 DeepEP / DeepGEMM / FlashMLA：三个内核的分工

| 模块 | 解决什么 | 一句话机制 | 标志性数字 |
|---|---|---|---|
| **DeepEP** | EP all-to-all 的吞吐与延迟 | NVLink+RDMA 两级流水 kernel，SM 可配，计算通信重叠 | 首个开源 EP 通信库；支持 FP8 dispatch；2026 年 V2.5 加入 PP/DP/CP 原语与 Ascend 950 后端 |
| **DeepGEMM** | FP8 GEMM 的性能与可读性 | ~300 行核心代码 + JIT 编译（DeepJIT），tile-wise 缩放布局原生支持 | Hopper 上 1350+ FP8 TFLOPS（官方开源周口径，后续迭代至 1550）；V3.2 起含 lightning indexer 的 MQA 打分 kernel；2026 年加入 FP4、Mega MoE |
| **FlashMLA** | MLA 注意力（及 DSA 稀疏注意力）的推理 kernel | 面向 MLA 潜向量结构的分页注意力（Hopper 时代），DSA 时代做 token 级稀疏 prefill/decode | Hopper BF16 稠密 580→660 TFLOPS；DSA kernel prefill 640 / decode 410 TFLOPS（2025-09 版）；昇腾 950 上 prefill 410 TFLOPS（95% 硬件峰值） |

三者关系：DeepEP 管"token 怎么流动"，DeepGEMM 管"专家怎么算"，FlashMLA 管"历史怎么读"。源码结构见 [第 6 章](06-source-analysis)。

## 5.6 3FS：数据与 KV 的底座

机制要点见 [3.4 节](03-architecture)；本节补充两个工程视角：

- **CRAQ 的读写折中**：链式复制保证写强一致，读由链上多节点分摊（apportioned queries）——相比朴素 chain replication 读只打头节点，CRAQ 把读吞吐放大了链长倍，这正是 KVCache 读能到 40+ GiB/s 的结构性原因（对照 [存储系统](/01-foundation/storage-systems/) 主题的复制协议讨论）；
- **USRBIO 用户态旁路**：客户端经用户态 I/O 路径直打 RDMA 与 NVMe，绕开内核页缓存——AI 负载的访问模式（大块、随机、可重建）不需要通用文件系统的缓存语义，把每一层软件税都剥掉。

## 5.7 DSA：稀疏注意力的完整闭环

**机制（V3.2 报告 §2.1）**：

```mermaid
flowchart LR
    Q[query h_t] --> I[lightning indexer<br/>低维潜向量打分<br/>I = relu(q·k)·w_t]
    KV[全部历史 KV 潜向量] --> I
    I --> TOPK[每 query 选 top-2048]
    TOPK --> ATT[主注意力<br/>只对选中 KV 计算]
    ATT --> O[输出]
```

- **indexer 的代价**：打分本身仍是 O(L²)，但用低维潜向量做类 MQA 单头打分，每对 token 的计算量是稠密注意力的 d_latent/d_model 分之一——"贵的计算稀疏化，便宜的计算全量化"；
- **损失的解耦**：indexer 只拿索引损失训练，主模型只拿语言模型损失训练，两者互不干扰；
- **端到端收益**：主注意力 O(L²) → O(L·k)（k=2048、L=128K 时为 1/64）；KV cache 读量同步下降——长上下文 prefill/decode 成本曲线在论文 Figure 3 给出（H800 实测口径）。

这是 MLA 伏笔的兑现：没有低维潜向量，indexer 的打分就贵到失去意义；没有细粒度 top-K（token 级而非块级），质量就保不住。DSA 与 MLA 再次验证了"算法—系统协同"的主线。

## 5.8 模块总表

| 模块 | 类别 | 一句话价值 | 开源 |
|---|---|---|---|
| DualPipe | 调度 | 气泡 O(PP)→O(PP/2)，通信全隐藏 | ✅（开源周 Day-4） |
| 细粒度 EP + 节点受限路由 | 并行 | EP 跨节点且通信近零 ⇒ 无 TP | ✅（含 EPLB） |
| FP8 混合精度 | 数值 | 算力 ×2，损失误差 低于 0.25% | ✅（DeepGEMM） |
| MLA | 架构 | KV cache 压缩 56.9×，无损 | ✅（FlashMLA） |
| DeepEP | 通信 | EP all-to-all 生产级内核 | ✅ |
| 3FS | 存储 | 6.6 TiB/s + 强一致 + KV 卸载 | ✅ |
| DSA | 架构 | 长上下文注意力 1/64 计算 | ✅（FlashMLA/DeepGEMM kernel） |

下一章 [源码与实现分析](06-source-analysis) 打开这些仓库看代码结构。

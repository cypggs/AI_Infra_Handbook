# 6. 源码与实现分析

DeepSeek 的开源仓库是研究 AI 基础设施的"活教材"——生产验证过的代码，且刻意保持可读性（DeepGEMM README 原话："as clean as a tutorial"）。本章按仓库拆解代码结构与关键实现概念（截至 2026-10 的仓库状态）。

## 6.1 开源周全景（Open Source Week，2025-02-24 ~ 02-28）

先回顾这套组合拳的完整清单（来源：官方 `open-infra-index` 仓库）：

| 日期 | 仓库 | 内容 | 当时披露的性能 |
|---|---|---|---|
| Day 1（02-24） | **FlashMLA** | Hopper GPU 的高效 MLA 解码 kernel，支持变长序列 | 3000 GB/s（访存瓶颈）/ BF16 580 TFLOPS（计算瓶颈）@H800 |
| Day 2（02-25） | **DeepEP** | 首个开源 EP 通信库（MoE dispatch/combine） | NVLink+RDMA 全支持、FP8 dispatch、推理低延迟模式 |
| Day 3（02-26） | **DeepGEMM** | FP8 GEMM 库（dense + MoE grouped） | Hopper 上 1350+ FP8 TFLOPS；核心逻辑 ~300 行 |
| Day 4（02-27） | **DualPipe + EPLB + profile-data** | 双向流水线算法、EP 负载均衡器、V3/R1 计算通信重叠 profiling 数据 | 论文 Table 2 的实现与实测数据 |
| Day 5（02-28） | **3FS + smallpond** | 并行文件系统 + 基于 DuckDB 的 PB 级数据处理框架 | 6.6 TiB/s 读；GraySort 3.66 TiB/min |
| Day 6（加更） | 推理系统概览 | V3/R1 在线服务架构文档 | 73.7K/14.8K tokens/s/H800 节点；理论利润率 545% |

2025-04 官方还发布了《The Path to Open-Sourcing the DeepSeek Inference Engine》（推理引擎开源路径文档），说明推理栈的逐步开放计划。

## 6.2 DeepEP：EP 通信库的代码结构

**仓库**：`deepseek-ai/DeepEP`（MIT）。README 开宗明义：DeepEP 是为 ML 训练与推理打造的高吞吐、低延迟 **EP all-to-all** GPU kernel 库，覆盖 MoE dispatch/combine（含 FP8 dispatch）以及冗余专家的 NVLink 权重/梯度交换；通信 kernel 由 **DeepJIT 运行时编译**。

核心 API 概念（代码级）：

- **`EPBuffer`**（V2 重构后的统一接口）：一个 EP 组的通信缓冲。初始化时给定 `num_max_tokens_per_rank / hidden / num_topk / num_experts / use_fp8_dispatch`，SM 与 QP 数量**按拓扑与通信量解析公式直接算出**（`get_theoretical_num_sms`），不再需要自动调参——这是"通信模型可解析"的工程宣言；
- **dispatch / combine 对**：`dispatch_forward` 返回 `EventOverlap`（事件句柄），框架可继续排队后续 kernel 再等事件——重叠的编程接口化。`do_cpu_sync=True` 用于训练/prefill（精确计数），`False` 配合 GPU 侧计数用于 decode（CUDA graph 友好）；
- **训练高通量与推理低延迟双模式**：同一 `EPBuffer` 接口，内部按场景选 kernel；
- **V2.5 的扩展**（2026）：把 `ElasticBuffer` 拆分为 `EPBuffer / EngramBuffer / PPBuffer / BucketBuffer`；`EPBuffer.lb_prefetch_weights / lb_reduce_grads` 支持**动态冗余专家**——经 NVLink 预取专家权重与量化 scale、反向时把冗余专家的 FP32 梯度归并回原专家（README 明确点名与 Moonshot MoonEP、UltraEP 的专家复制路线互通）；新增 PP/CP/DP 的 bucket 集合通信原语与实验性 **Engram**（RDMA 远程内存访问）。

工程细节值得学：**kernel 运行时编译**（DeepJIT，安装期不需要 GPU）、NCCL Gin 轻量设备端通信后端（复用已有 NCCL communicator）、对 SM 占用的精细控制（通信 kernel 吃多少 SM 由调用方按 overlap 需求指定）。

## 6.3 DeepGEMM：300 行核心的 FP8 GEMM

**仓库**：`deepseek-ai/DeepGEMM`（MIT）。README 的自我定位：统一的高性能张量核 kernel 库（FP8/FP4/BF16 GEMM、融合 MoE、lightning indexer MQA 打分、HyperConnection），借鉴 CUTLASS/CuTe 的概念但**不依赖其模板体系**，核心函数少而精，"性能匹敌甚至超过专家调优库"。

代码级要点：

- **JIT 编译**：所有 kernel 经 DeepJIT 运行时编译，安装零编译负担；SM90（Hopper）与 SM100（Blackwell）双架构；
- **缩放因子布局即协议**：SM90 要求 FP32 格式的缩放因子，SM100 用打包的 UE8M0（4 个 scale 打包进一个 int）——**缩放因子的内存布局本身就是 kernel ABI 的一部分**（TMA 对齐 + 转置），这与 5.3 节的细粒度量化方案严格对应；量化/转置不代劳，留给前序 kernel 融合（库只做 GEMM 本身）；
- **MoE 的两种分组布局**：训练/prefill 用 **contiguous layout**（各专家 token 拼接，M 轴分组，段对齐 `get_mk_alignment_for_contiguous_layout()`）；decode 用 **masked layout**（CPU 不知道各专家收到多少 token 时按 mask 计算有效部分，配合 DeepEP 低延迟输出）——外加 K 轴分组的权重反向 kernel；
- **V3.2 起加入 indexer kernel**：`fp8_fp4_mqa_logits` 家族（非分页 prefill / 分页 decode），向量化实现 `score = relu(q·kv) * w` 再按头求和——DSA 的打分就是这个小 kernel 反复跑；
- **Mega MoE**（2026-04 起）：把 EP dispatch、linear1/linear2、SwiGLU、combine 融合成一个 mega-kernel，NVLink 通信与张量核计算重叠（对称内存 + 多进程启动）；
- **性能轨迹**（README News）：开源周 1350+ TFLOPS（Hopper）→ 2025-04 在 H800 上 1550 TFLOPS → 2026 年迭代 FP4、Sparse Indexer、Mega MoE，并发布 **DeepGEMM-Ascend**（昇腾 950）。

## 6.4 FlashMLA：从 MLA 解码到 DSA 稀疏注意力

**仓库**：`deepseek-ai/FlashMLA`（MIT）。README 2026-09 版本已转向 V4.1（并在 2026-09-30  breaking change 中移除 Hopper/旧模型支持，旧版本锁 commit 可溯）。

代码级要点：

- **API 形态**：`get_mla_metadata()`（decode 循环前取一次 tile 调度元数据）+ `flash_mla_with_kvcache()`（每步调用）——两函数接口，分页 KV cache（块大小 64）；
- **Hopper 时代**（2025）：为 MLA 潜向量结构优化的变长解码 kernel，开源即 580 TFLOPS / 3000 GB/s @H800，2025-04 版提升到 660 TFLOPS（compute-bound 场景 +5~15%），并发布 kernel 深度解析文档（`docs/20250422-new-kernel-deep-dive.md`）；
- **DSA 时代**（2025-09 起）：发布 token 级稀疏注意力 prefill/decode kernel（prefill 640 TFLOPS / decode 410 TFLOPS @Hopper），配套 FP8 稀疏 decode 深度文档；V4/V4.1 时代加入**融合 kernel**：Q-norm + Q-RoPE + 注意力 + O-RoPE（共轭）+ FP8 cast 融合为一次 kernel 调用（B200 上 prefill 1460 / decode 950 TFLOPS）；
- **多后端**（2026）：CUDA（SM100/SM103）与**华为昇腾 950**（CANN 9.2 + bisheng 编译器）双后端；昇腾稀疏 kernel prefill 410 TFLOPS（**95% 硬件峰值**）/ decode 360 TFLOPS（83%），并发布昇腾 prefill 深度技术报告——kernel 移植的"教科书级"公开。

## 6.5 3FS：并行文件系统的组件解剖

**仓库**：`deepseek-ai/3fs`（MIT）。设计文档（`docs/design_notes.md`）+ 部署指南 + USRBIO API 文档齐全。组件视图：

| 组件 | 职责 | 实现要点 |
|---|---|---|
| **Chunk Engine** | 数据面：chunk 的读写与复制 | NVMe SSD + RDMA 全用户态直通 |
| **Meta Service** | 控制面：命名空间与元数据 | **无状态**，事务型 KV（FoundationDB）兜底 |
| **Client（USRBIO）** | 应用侧 API | 用户态旁路 I/O（绕开内核），fio 有专用 engine 压测 |
| **CRAQ 复制** | 强一致 + 分摊读 | 链式写、链上多节点分摊读 |
| **smallpond** | 数据处理框架 | DuckDB 执行层 + 3FS 存储层，GraySort 验证 |

构建细节也透着工程味：编译时需显式指定 `-DSHUFFLE_METHOD`（g++10/g++11）以锁定历史 `std::shuffle` 实现的二进制兼容——生产系统跨编译器升级的真实痛点，被写进了 README 的注意事项。

## 6.6 开源状态总表（截至 2026-10）

| 资产 | 状态 | 许可 | 备注 |
|---|---|---|---|
| V3 / R1 / V3.1 / V3.2 / V4 权重 | 公开 | MIT | Hugging Face `deepseek-ai` |
| DeepEP / DeepGEMM / FlashMLA / 3FS / DualPipe / EPLB / smallpond / profile-data | 持续维护 | MIT | 均演化出 Ascend 后端或衍生生态 |
| 训练框架 HAI-LLM | **未开源** | — | 开源周仅公开 DualPipe 算法与 profile-data |
| 推理引擎 | 部分（内核级） | MIT | 推理系统概览文档 + FlashMLA/DeepGEMM/DeepEP |
| 技术报告（V3/R1/V3.2/V4/Fire-Flyer/ISCA'25） | 公开 | arXiv | 含并行配置、气泡公式、硬件建议 |

**学什么**：DeepEP 学"通信如何成为可调度的资源"，DeepGEMM 学"数值格式如何固化进 kernel ABI"，FlashMLA 学"为模型结构定制 kernel 的收益曲线"，3FS 学"复制协议与负载特征的匹配"。四者共同的工程价值观：**少抽象、零魔法、数字可复现**。

下一章 [Mini Demo](07-mini-demo) 把本章与 [第 5 章](05-core-modules) 的公式跑成可执行的数字。

# DeepSeek 案例研究

如果说 OpenAI 的故事是"把规模做到极致并产品化"、Google 的故事是"为 ML 自研一整台垂直整合的超算"、Meta 的故事是"开放权重 + 硬件协同设计"，那么 DeepSeek 的故事代表了 2025 年之后最重要的第五条范式：**一家没有云业务、没有万亿市值、在出口管制下只能买到"残血版"GPU 的中国量化基金公司，靠算法—系统协同设计（algorithm-system co-design），用 2048 张 H800、557.6 万美元训出了与前沿闭源模型同台竞技的 V3/R1——然后把几乎所有关键基础设施都开源了**。

研究 DeepSeek，是在四个海外案例之外补齐"**用工程换算力**"这条主线：MLA 压缩 KV cache 是给推理带宽做的算法，FP8 训练是为被削减的硬件榨取算力，DualPipe 与细粒度 EP 是在受限互联上把通信藏进计算，3FS 与错峰定价是存储与商业侧的系统性抠成本。它的技术报告罕见地公开了流水线气泡公式、并行配置、GPU 小时账和硬件设计建议——这是主流实验室里独一份的一手工程资料密度。

## 一句话理解

> DeepSeek 的基础设施故事，是用 **算法—系统协同设计（MLA + FP8 + DualPipe + 细粒度 EP）+ 自研轻量训练框架（HAI-LLM）+ 全链路开源（权重 MIT + DeepEP/DeepGEMM/FlashMLA/3FS）+ 极限成本工程（557.6 万美元训完 V3、错峰定价、545% 理论推理利润率）**，在受限硬件上把"每一美元算力"压榨到极限的工程实践史。

## 学习目标

读完本主题后，你应该能够：

- 复述 DeepSeek 的跃迁时间线：从幻方量化的 fire-Flyer 超算（SC'24 论文，1 万 PCIe A100），到 V2 的 MLA 首秀（2024-05）、V3 的 557.6 万美元训练（2024-12）、R1 的"斯普特尼克时刻"（2025-01）、开源周（2025-02）、DSA 稀疏注意力（V3.2-Exp，2025-09）、V3.2-Speciale 的 IMO/IOI 金牌（2025-12）、百万 token 上下文的 V4 系列（2026-04 起）。
- 解释 **MLA（Multi-head Latent Attention）** 的低秩 KV 压缩原理：V3 配置下每 token 每层 KV cache 从 MHA 的 64 KiB 压到 1.12 KiB（约 56.9×），且对潜空间内数据是无损表示。
- 解释 **FP8 混合精度训练** 的三个精度决策：全 E4M3、1x128/128x1 细粒度缩放、每 128 元素提升 CUDA Core FP32 累加；以及附录 B"端到端损失误差低于 0.25%"的正确口径。
- 推导 **DualPipe** 的流水线气泡公式 `(PP/2-1)(F+B-3W)`，对照 1F1B 的 `(PP-1)(F+B)`，说明双向调度与计算—通信重叠的前提（恒定计算通信比）。
- 说明 **细粒度专家并行（EP64 跨 8 节点）** 的通信账：all-to-all 通信量公式、节点受限路由（每 token 最多 4 节点）、无辅助损失负载均衡与 EPLB，以及为什么"通信可以被完全盖住 ⇒ 不需要张量并行（TP）"。
- 描述 **DeepEP / DeepGEMM / FlashMLA / 3FS** 四个开源组件的分工与关键性能数字（如 3FS 180 节点 6.6 TiB/s 读、FlashMLA DSA kernel 640/410 TFLOPS、DeepGEMM ~300 行核心代码）。
- 理解 **DeepSeek Sparse Attention（DSA）**：lightning indexer + 细粒度 top-K 选择，把主注意力复杂度从 O(L²) 降到 O(L·k)（128K 上下文选 2048，1/64）。
- 用 2025-2026 的算力约束时间线（H800→H20 限制→Ascend 950 适配）说明"硬件受限下的设计哲学"，并区分公开报道与传闻。
- 对照 OpenAI/Google/Meta 的算力路线，总结"小力出奇迹"方法论中哪些可迁移、哪些不可迁移。

## 与相邻主题的关系

| 相邻主题 | 与 DeepSeek 案例的关系 |
|---|---|
| [OpenAI 案例研究](/09-case-study/openai/) | 对照"闭源规模 + 通用 GPU + 巨额资本"与"开源权重 + 受限硬件 + 算法系统协同"。R1 发布的 2025-01 被视为两者的分水岭。 |
| [Google 案例研究](/09-case-study/google/) | 对照"自研 TPU 垂直整合"与"用别人（受限版）的 GPU + 自研训练框架/内核库"。两者都证明了框架层（HAI-LLM vs XLA/Pathways）的战略价值。 |
| [Meta 案例研究](/09-case-study/meta/) | 对照两条开放路线：Meta 开放权重 + OCP 硬件设计，DeepSeek 开放权重（MIT）+ 推理/训练基础设施全开源。 |
| [分布式系统基础](/01-foundation/distributed-systems/) | DualPipe 流水线、EP all-to-all、ZeRO-1、CRAQ 链式复制都是并行与分布式系统的经典机制的生产级案例。 |
| [存储系统](/01-foundation/storage-systems/) | 3FS（CRAQ 强一致、FoundationDB 元数据、6.6 TiB/s）是并行文件系统与分离式存储架构的经典案例。 |
| [计算机网络](/01-foundation/computer-networks/) | NVLink vs IB 的两级带宽体系、多平面网络拓扑（ISCA'25 论文建议）、节点受限路由是数据中心网络的典型案例。 |
| [GPU 与 CUDA](/01-foundation/gpu-cuda/) | FP8 WGMMA、SM 分配、CUDA Core 提升累加、TileLang/DeepJIT 运行时编译都建立在 GPU 架构主题之上。 |
| [推理服务（vLLM / SGLang）](/04-llmops/) | PD 分离部署、冗余专家、分页 KV cache、错峰定价是推理服务工程的直接对照；SGLang 已集成 3FS 作为 KV cache 后端。 |
| [AI 编译器与 Kernel 生成](/04-llmops/ai-compiler/) | DeepGEMM/FlashMLA 的 JIT 编译（DeepJIT）、TileLang 可读 kernel 与主题中的 kernel 生成互为印证。 |
| [AI SRE](/07-ai-sre/) | V3 训练全程零不可恢复 loss spike、零回滚；冗余专家部署、故障下的推理降级是可靠性工程案例。 |
| [AI 安全](/08-security/) | 开源权重的双刃剑效应、蒸馏生态与模型许可（MIT vs Llama 社区许可）是 AI 治理的鲜活案例。 |

## 章节导航

1. [背景](01-background) — 幻方量化与 fire-Flyer 超算、出口管制下的硬件现实、从 V2 到 V4 的跃迁时间线。
2. [核心思想](02-core-ideas) — 算法—系统协同设计、用工程换算力、开源作为战略、硬件受限下的设计哲学。
3. [架构设计](03-architecture) — 训练系统全景（HAI-LLM + 3FS + DeepEP + 2048 H800）与推理系统（PD 分离 + 冗余专家）。
4. [训练与推理工作流程](04-training-and-inference) — 一次 V3 训练的完整链路、R1 的多阶段 RL、V3.2 的稀疏注意力训练流程。
5. [核心模块](05-core-modules) — DualPipe、细粒度 EP、FP8 累加策略、MLA、DeepEP、DeepGEMM、FlashMLA、3FS、EPLB、DSA。
6. [源码与实现分析](06-source-analysis) — DeepEP / DeepGEMM / FlashMLA / 3FS 仓库结构解读与开源状态表（截至 2026-10）。
7. [Mini Demo](07-mini-demo) — DualPipe 气泡模拟 + FP8 精度账 + EP 通信量 + MLA 压缩比，97 个确定性测试。
8. [企业生产实践](08-production-practice) — R1 现象、推理扩容与 545% 理论利润率、定价策略、H20 限制与 Ascend 适配、传闻与事实。
9. [最佳实践](09-best-practices) — 从 DeepSeek 学到的可迁移经验与检查清单。
10. [面试题](10-interview-questions) — 初/中/高级 DeepSeek 基础设施面试题。
11. [延伸阅读](11-further-reading) — 论文、仓库、官方公告与手册内交叉引用。

## 一句话总结

DeepSeek 证明了在算力受限、资本受限的条件下，**把算法和系统当成一个整体来设计**可以换算力：MLA 用低秩投影把 KV cache 砍掉 98%，FP8 用细粒度缩放和 CUDA Core 提升累加把 H800 的算力榨到 BF16 的 2 倍，DualPipe 与细粒度 EP 把跨节点通信藏进计算让流水线气泡近零、张量并行出局，3FS 与错峰定价把存储和商业侧的成本抠到极致——然后把这些全部开源，用 557.6 万美元的训练成本和 R1 的 MIT 许可，改写了全球 AI 基础设施的叙事。

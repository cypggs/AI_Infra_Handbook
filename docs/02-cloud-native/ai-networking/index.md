# AI 集群网络总览

> 一句话理解：**AI 集群网络是为"成千上万颗加速器在同步屏障内同时说话"而设计的专用 fabric——scale-up 域（NVLink/UALink）负责机柜内的内存语义互联，scale-out 域（InfiniBand/RoCE/UEC 以太网）负责机柜间的大象流与 all-to-all，两者的带宽、时延、无损语义与故障域设计完全不同，不能用传统云网络的思想硬套。**

## 为什么 AI 平台工程师必须懂 AI 集群网络

不懂 AI 集群网络的工程师，很容易把集群建成"单卡 benchmark 很好看、一上分布式就翻车"的状态。典型场景：

- 128 卡训练的 NCCL all-reduce 实测带宽只有标称的 60%，换块光纤就好了——这是 **光模块/FEC 误码**导致的链路降速，监控里早就报了计数。
- 千卡训练每隔几小时随机挂一个 rank，NCCL timeout——这是 **PFC 风暴 + ECN 参数不当**造成的无损域失稳，不是 GPU 坏了。
- MoE 模型一打开专家并行，网络吞吐打满、step 时间翻倍——这是 **all-to-all 流量的 incast**没有被自适应路由和拥塞控制兜住。
- 采购了 800G 交换机，实测却只有 400G 的有效吞吐——这是 **ECMP 哈希极化**：大象流数量太少，哈希把多条流钉在了同一条上联上。
- 集群从 4k 卡扩到 24k 卡，不改动任何配置，性能从 90%+ 掉到 10–90% 不等——这是 Meta 2024 年真实踩过的坑：**规模本身会暴露拓扑感知调度、路由、集合通信算法三层问题**。

这些都不是"买更快的交换机"能解决的。AI workload 对网络的需求（同步屏障、尾部延迟、大象流、无损语义）与传统云网络（多租户、南北向、尽力而为）几乎是反着的——理解 scale-up/scale-out 的二分、带宽时延比、incast 与拥塞控制、拓扑与故障域，是设计生产级 AI 集群的必修课。

## 与「计算机网络」主题的分工

本手册 [计算机网络](/01-foundation/computer-networks/) 主题已经讲了通用网络原理：OSI/TCP 分层、TCP 拥塞控制、RDMA/RoCE/InfiniBand 的基本概念、数据中心拓扑（Spine-Leaf/Clos/fat-tree/OCS）的通识。**本主题不重复这些内容**，聚焦 AI 集群专用的网络工程：

| 维度 | 计算机网络（通用原理） | 本主题（AI 集群专用工程） |
|---|---|---|
| 视角 | 协议与分层：TCP/RDMA 怎么工作 | 系统与取舍：训练/推理 workload 如何重塑 fabric 设计 |
| 范围 | 通用数据中心 + 云网络 | GPU 集群的 scale-up 域与 scale-out 域 |
| 重点 | 可靠性、通用性、多租户 | 尾部延迟、incast、无损语义、网内计算、故障域 |
| 案例 | 通用云场景 | Meta/xAI/阿里/腾讯/Google/OpenAI 的量化实践 |

## 学习目标

阅读完本主题后，你应该能够：

1. 解释 scale-up 与 scale-out 的划分依据，说出 NVLink 5（1.8 TB/s）、InfiniBand NDR/XDR（400G/800G）、RoCE 在带宽、时延、语义上的数量级差异。
2. 从并行策略（TP/DP/EP/PP）推导一次训练 step 的流量矩阵：谁是大象流、谁是 incast、谁必须留在 scale-up 域。
3. 画出典型 AI 集群网络全景：NVLink 域 → 节点 NIC → leaf-spine fabric → super spine，以及前端网、存储网、带外管理网的位置。
4. 比较 InfiniBand、RoCEv2（PFC/ECN/DCQCN）、Spectrum-X、UEC 的技术路线：无损怎么实现、拥塞控制谁来做、网内计算有没有。
5. 读懂 ring/tree all-reduce 与 all-to-all 的步数和字节数模型，用 α-β 模型解释"小消息 tree 胜、大消息 ring 胜"。
6. 在生产中排查典型故障：all-reduce 掉带宽、NCCL timeout、PFC 死锁、哈希极化、光模块误码。
7. 跟踪 2025–2026 的格局变化：UEC 1.x 规范、UALink 1.0、NVLink Fusion、Spectrum-X Photonics/CPO、OpenAI MRC。
8. 回答初 / 中 / 高级 AI 集群网络面试题，把流量模型、拓扑与故障排查联系起来。

## 本主题与其他主题的关系

| 主题 | 解决的核心问题 | 与本主题的关系 |
|---|---|---|
| [计算机网络](/01-foundation/computer-networks/) | 通用网络原理：TCP/RDMA/拓扑/OSI | 本主题的底层原理；RDMA/RoCE/IB/fat-tree 的通用概念在那里 |
| [分布式系统基础](/01-foundation/distributed-systems/) | 并行计算模型、同步与一致性 | 数据并行/流水并行的语义来源；本主题讲这些语义如何落到网络上 |
| [GPU 架构与 CUDA](/01-foundation/gpu-cuda/) | GPU 硬件、CUDA 编程模型 | NVLink/NVSwitch 的硬件载体；GPUDirect RDMA 的起点 |
| [CNI / CSI 深度](/02-cloud-native/cni-csi/) | K8s 网络与存储插件 | 集群内 Pod 网络、多网卡接入、RDMA 设备插件化 |
| [GPU 调度与资源管理](/02-cloud-native/gpu-scheduling/) | GPU 如何被调度与治理 | 拓扑感知调度决定训练 Job 落在哪些 NVLink 域/轨（rail）上 |
| [vLLM](/04-llmops/vllm/) / [SGLang](/04-llmops/sglang/) | 单实例推理引擎 | PD 分离、多机 TP 推理的通信模式复用本主题的流量模型 |
| [AI SRE](/07-ai-sre/) | 可观测性与 SLO | 网络 SLI（带宽达标率、PFC pause、FEC 误码）是 AI SRE 的核心指标 |
| [xAI 案例](/09-case-study/xai/) | Spectrum-X 的规模化验证 | 95% 实测吞吐 vs 传统以太网 60% 的对照口径来源 |
| [DeepSeek 案例](/09-case-study/deepseek/) | 训练效率极限优化 | 多平面网络拓扑、节点受限路由的设计动机 |
| [Google 案例](/09-case-study/google/) | TPU 集群与 OCS | Falcon 传输、Jupiter OCS、ICI 拓扑与故障恢复 |
| [OpenAI 案例](/09-case-study/openai/) | Stargate 多园区架构 | MRC 开放协议与超大规模 scale-out fabric |

## 本章结构

1. [背景](01-background) — AI workload 的流量特征与传统云网络的本质区别：同步屏障、大象流、incast、尾部延迟。
2. [核心思想](02-core-ideas) — scale-up/scale-out 二分、带宽时延比、无阻塞与收敛、rail-optimized、有损/无损/第三种路线。
3. [架构设计](03-architecture) — 典型 AI 集群网络全景：从 GPU 到 super spine 的四层 fabric 与拓扑选型决策树。
4. [工作流程](04-workflow) — 一次大规模训练的网络流量生命周期：从 NCCL 初始化到 step 内通信时序再到 checkpoint。
5. [核心模块](05-core-modules) — NVSwitch、IB 子网管理器、拥塞控制（PFC/ECN/DCQCN/自适应路由）、SHARP 网内计算、遥测与故障域。
6. [生态与源码分析](06-source-analysis) — InfiniBand vs RoCE vs UEC 对比表；NCCL 源码结构、UEC 规范与 Google Falcon 设计剖析。
7. [工程实践](07-mini-demo) — 纯 Python 可运行的 AI 集群网络模拟器（拓扑、流量矩阵、incast/DCQCN、PFC 死锁、集合通信模型）。
8. [企业生产实践](08-production-practice) — 选型决策、Meta/阿里/腾讯/xAI 量化实践、排障 playbook、扩展路径。
9. [最佳实践](09-best-practices) — fabric 设计检查清单、PFC/ECN 参数模板、NCCL 环境变量与验收标准。
10. [面试题](10-interview-questions) — 初 / 中 / 高级 AI 集群网络面试题。
11. [延伸阅读](11-further-reading) — 官方文档、论文、一手发布与手册内回链。

## 一句话总结

AI 集群网络的精髓在于**"把同步的集合通信当作一等公民来设计 fabric"**：scale-up 域用内存语义的专用互联（NVLink/UALink）换取微秒级时延，scale-out 域在无阻塞拓扑（fat-tree/rail-optimized）上以太网化（RoCE/Spectrum-X/UEC）换取开放与规模；对 AI 平台而言，选对协议路线决定生态与成本，调对拥塞控制决定利用率，管好光纤与故障域决定有效训练时间——三者共同决定一张昂贵的 GPU 集群能不能把理论算力变成模型训练进度。

**参考来源**

- [Meta Engineering：Building Meta's GenAI Infrastructure](https://engineering.fb.com/2024/03/12/data-infrastructure/building-metas-genai-infrastructure/)（2024-03）
- [NVIDIA Newsroom：Spectrum-X Ethernet Networking Accelerates xAI Colossus](https://nvidianews.nvidia.com/news/spectrum-x-ethernet-networking-xai-colossus)（2024-10）
- [Ultra Ethernet Consortium 规范历史](https://ultraethernet.org/specification/)（UEC 1.0：2025-06-11；1.1：2026-10-12）
- [UALink Consortium 发布 UALink 200G 1.0 规范](https://www.businesswire.com/news/home/20250408050548/en/UALink-Consortium-Releases-the-Ultra-Accelerator-Link-200G-1.0-Specification)（2025-04-08）

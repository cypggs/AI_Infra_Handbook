# 11. 延伸阅读

> 按"先官方、再论文、后报道"的顺序读；带 [未完全验证] 标记的条目以官方仓库/后续披露为准。

## 官方文档与规范

**NVIDIA**

- [NVIDIA Networking 产品总览](https://www.nvidia.com/en-us/networking/)（Spectrum-X / Spectrum-XGS / Photonics、Quantum InfiniBand 的定位）
- [Quantum-X800 XDR 集群文档](https://networking-docs.nvidia.com/nvidia-quantum-x800-xdr-clusters)（QM3400/Q3200、ConnectX-8、SHARP v4、两层 fat-tree 10,368 端点）
- [Q32xx/Q34xx XDR 交换机规格](https://networking-docs.nvidia.com/xdrswitcheshw/specifications)
- [NVIDIA NCCL 文档与源码](https://github.com/NVIDIA/nccl)（环境变量、transport、拓扑搜索）

**开放规范**

- [Ultra Ethernet Consortium](https://ultraethernet.org/) 与[规范历史](https://ultraethernet.org/specification/)（1.0：2025-06-11；1.0.2：2026-01-28；1.0.3：2026-07-16；1.1：2026-10-12）
- [UALink Consortium](https://www.ualink.org/)；[UALink 200G 1.0 发布稿](https://www.businesswire.com/news/home/20250408050548/en/UALink-Consortium-Releases-the-Ultra-Accelerator-Link-200G-1.0-Specification)（2025-04-08）；[2026-04 四规范更新（The Register）](https://www.theregister.com/2026/04/07/ualink_2_specs/)
- [OCP Falcon 传输仓库](https://github.com/opencomputeproject/OCP-NET-Falcon)
- [IEEE 802.3 以太网标准族](https://www.ieee802.org/3/)（802.3df 800G；802.3dj 1.6T/200G-per-lane 时代）

## 论文（按主题）

**流量与并行策略**

- [DCQCN: Congestion Control for Large-Scale RDMA Deployments（SIGCOMM'15）](https://www.microsoft.com/en-us/research/publication/dcqcn-congestion-control-for-large-scale-rdma-deployments/)
- [Rail-only: A Low-Cost High-Performance Network for Training LLMs（arXiv 2307.12169）](https://arxiv.org/abs/2307.12169)（38–77% 成本节省）
- [Characterization of Large Language Model Development in the Datacenter（arXiv 2403.07648，Meta Acme 集群 trace）](https://arxiv.org/abs/2403.07648)

**拓扑与生产 fabric**

- [Alibaba HPN（SIGCOMM'24）](https://ennanzhai.github.io/pub/sigcomm24-hpn.pdf)（15,072 GPU/POD 双平面两层、双 ToR、+14.9%）
- [Alibaba Stellar: A New Generation RDMA Network for Cloud AI（SIGCOMM'25）](https://dl.acm.org/doi/10.1145/3718958.3750539)
- [TPU v4: An Optically Reconfigurable Supercomputer（ISCA'23，含 OCS/3D-torus）](https://arxiv.org/abs/2304.01433)；[NSDI'24 TPU 可靠性（PDF）](https://www.usenix.org/system/files/nsdi24-zu.pdf)（0.08%/0.005%/0.04% 日故障率）

**传输层新路线**

- [Falcon: A Reliable, Low Latency Hardware Transport（SIGCOMM'25）](https://dl.acm.org/doi/10.1145/3718958.3754353)
- [Deadlocks in Datacenter Networks: Why Do They Form, and How to Avoid Them（SIGCOMM'16）](https://dl.acm.org/doi/10.1145/2934872.2905803)（PFC 死锁理论）

## 一手发布与工程博客

- [Meta：Building Meta's GenAI Infrastructure（2024-03）](https://engineering.fb.com/2024/03/12/data-infrastructure/building-metas-genai-infrastructure/)（24k 双集群、10–90% → 90%+）
- [Meta：Training large language models at scale（2024-06）](https://engineering.fb.com/2024/06/12/data-infrastructure/training-large-language-models-at-scale-meta/)
- [NVIDIA Newsroom：Spectrum-X × xAI Colossus（2024-10）](https://nvidianews.nvidia.com/news/spectrum-x-ethernet-networking-xai-colossus)（100k→200k H100、95% 吞吐）
- [腾讯星脉 2.0 发布（C114，2024-07）](https://www.c114.com.cn/ai/5339/a1267376.html)（51.2T 自研交换、400G 硅光、TiTa 2.0、灵境）
- [Broadcom Tomahawk 6 发布（2025-06）](https://www.morningstar.com/news/globe-newswire/9462115/broadcom-ships-tomahawk-6-worlds-first-1024-tbps-switch)
- [NVIDIA GTC 2025 要点（SemiAnalysis）](https://newsletter.semianalysis.com/p/nvidia-gtc-2025-built-for-reasoning-vera-rubin-kyber-cpo-dynamo-inference-jensen-math-feynman)（NVL144/Rubin、CPO、NVLink Fusion）
- [OpenAI MRC 协议报道（PANews）](https://www.panewslab.com/en/articles/019dfd99-8e7f-764d-a73c-95d8b72fa38f) [公开报道口径，细节以 OCP 为准]

## 手册内回链

**基础原理（建议先读）**

- [计算机网络](/01-foundation/computer-networks/)——RDMA/RoCE/IB/fat-tree/OCS 的通用原理与本主题的分工
- [分布式系统基础](/01-foundation/distributed-systems/)——并行策略与同步屏障的语义来源
- [GPU 架构与 CUDA](/01-foundation/gpu-cuda/)——NVLink/NVSwitch 的硬件载体、GPUDirect 的前提

**云原生相邻主题**

- [GPU 调度与资源管理](/02-cloud-native/gpu-scheduling/)——拓扑感知调度、Gang 与"轨"选择
- [CNI / CSI 深度](/02-cloud-native/cni-csi/)——K8s 多网卡、RDMA 设备插件化
- [Kubernetes](/02-cloud-native/kubernetes/)——控制面与多租户隔离

**上下游主题**

- [vLLM](/04-llmops/vllm/) / [SGLang](/04-llmops/sglang/)——多机 TP/PD 分离的通信模式
- [AI SRE](/07-ai-sre/)——网络 SLI、灰度故障与 MTTR 的观测闭环

**案例研究（量化实践）**

- [xAI](/09-case-study/xai/)——Spectrum-X 95% 吞吐的对照口径与建设速度
- [Google](/09-case-study/google/)——Falcon/Jupiter OCS、ICI 拓扑、Virgo 网络
- [DeepSeek](/09-case-study/deepseek/)——多平面拓扑与节点受限路由的训练效率动机
- [OpenAI](/09-case-study/openai/)——Stargate 多园区与 MRC 协议
- [Meta](/09-case-study/meta/)——双织物集群与 Llama 训练基础设施

## 学习路径建议

1. **第一遍**：[计算机网络](/01-foundation/computer-networks/) 的 RDMA 与拓扑章节 → 本主题第 1、2 章 → Mini Demo 全部场景。
2. **第二遍**：第 3–6 章 + NCCL 源码（`src/graph/` 与 `src/transport/`）+ UEC 1.0 白皮书。
3. **第三遍**：第 8 章量化案例逐一手读原文（Meta 两篇博客、HPN 论文、星脉发布、NVIDIA Newsroom），把每个数字标注来源与口径。
4. **面试准备**：第 10 章全部 14 题能脱稿讲 5 分钟，其中 Q6/Q12 要求能画出排查流程图。

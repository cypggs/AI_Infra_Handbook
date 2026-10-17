# 6. 生态与源码分析

> 一句话理解：**InfiniBand 是"物理层就无损 + 集中管控 + 网内计算"的封闭全栈；RoCEv2 是"以太网上打无损补丁"的开放妥协；UEC/Falcon 是"把可靠性交还端侧、让以太网回归简单"的第三条路——三条路线的所有差异都可以从"可靠与有序放在哪一层"这一个问题上推导出来。**

## 6.1 三条路线对比表

| 维度 | InfiniBand (NDR/XDR) | RoCEv2 + PFC/ECN | Spectrum-X（增强以太网） | UEC 以太网 | Falcon（Google 私有） |
|---|---|---|---|---|---|
| 无损实现 | credit 流控，物理层天然无损 | PFC 打补丁（逻辑无损） | PFC + 增强 ECN | 不要求无损（支持丢包重传） | 不要求无损（硬件重传） |
| 拥塞控制 | 链路 credit + 可选 CC | DCQCN/RTTCC（ECN 驱动） | 时延/拥塞感知 + 自适应路由 | UEC CMS（新算法族） | 时延 CC（高精度时间戳） |
| 乱序/多路径 | 按序交付；自适应路由需交换机排序 | ECMP 按流哈希（极化问题） | 自适应路由 + 端侧乱序处理 | **报文 spraying + 乱序交付** | multipath LB + 端侧处理 |
| 网内计算 | SHARP v4（约 14.4 TFLOPS） | 无（标准 NIC） | 无（靠端侧与拓扑） | 规范预留 in-network 能力 | 无 |
| 控制面 | SM/UFM 集中式 | BGP/EVPN + 分散配置 | 以太网 + NVIDIA 管控 | 以太网标准 | 私有 SDN（与 Jupiter 共生） |
| 开放性 | 封闭（NVIDIA 主导） | 开放多厂商 | 半开放（NVIDIA 栈） | 开放（Linux 基金会 JDF） | 协议开源 OCP，实现私有 |
| 代表用户 | 顶级超算、Oracle 131k、Stargate 部分 | 自建集群、传统云 | xAI Colossus、CoreWeave 等 | 生态成型中（2026 首批产品） | Google 全数据中心 |
| 主要风险 | 成本、锁定 | PFC 死锁/风暴、调优门槛 | 绑定 NVIDIA 栈 | 规范与产品仍在成熟 | 仅自用 |

选型直觉：**要"开箱即用的确定性"选 IB；要"以太网生态 + 厂商增强"选 Spectrum-X 类；要"开放、长期、愿意共同演进"看 UEC；有 Google 级自研能力就造 Falcon。** 现实中的 2026 年答案往往是混合：Meta 同时建 IB 与 RoCE 集群做对照，OpenAI 在 OCP 开源 MRC 但 Stargate 也大量采购 IB。

## 6.2 源码分析一：NCCL 的传输与拓扑层

NCCL 是 AI 集群网络事实上的"应用层"。读它的源码（github.com/NVIDIA/nccl）抓住三条主线：

**1. 传输抽象（`src/transport/`）**：每种互联一个 transport——`p2p.c`（NVLink/PCIe 的 P2P 读写）、`net_ib.c`/`net_socket.c`（IB/RoCE verbs 与 socket 回退）、`collnet_sharp.c`（SHARP 卸载）。统一接口是 `setup/connect/send/recv`：setup 阶段交换 buffer 地址与 GPU 映射，connect 阶段建立 QP（net transport 下就是 verbs 的 QP 创建 + RTS），之后数据面只由 GPU kernel（`ncclDevKernel`）驱动 doorbell，零 CPU 参与。

**2. 拓扑感知（`src/graph/`）**：`topo.cc` 读取 NVML/PCI 信息构建节点内拓扑（NVLink 域、PCIe switch、NUMA），`search.cc` 在这个图上搜索 channel 到 GPU/NIC 的绑定方案——这就是"拓扑感知 all-reduce"的实现处：同一个 NVLink 域内的 GPU 走 P2P 链，跨机部分按 rail 绑定 NIC。固件升级后拓扑变化（如 NVL72 的新 tray 结构）必须等新版本 NCCL 的拓扑表更新，否则 search 会给出次优绑定——第 4 章"版本必须配套"的出处。

**3. 通道并行（channel）**：NCCL 把通信切成 C 个 channel（典型 2–8 个）并行跑在不同 ring/tree 上，用满多轨 NIC 与多 QP。channel 数、每 channel 的算法（ring/tree）、是否与计算 overlap，由 `ncclParam*` 环境变量体系控制——第 9 章的最佳实践会给出生产上常用的调参清单。

顺带理解三个核心数据结构，读源码时就不会迷路：

| 结构 | 角色 | 关键字段/行为 |
|---|---|---|
| `ncclComm` | 一次通信的上下文 | rank 数、channel 数组、拓扑（`ncclTopoSystem`）、transport 列表 |
| `ncclChannel` | 一条并行通信流水 | 绑定的 GPU 集合、peer 连接（`ncclConnector`）、ring/tree 顺序 |
| `ncclConnector` | 一条单向发送/接收通道 | transport 指针（p2p/net/collnet）、共享 buffer、FIFO 位置 |

数据面的同步也值得一说：NCCL 的 LL（low-latency）协议把 8B flag 与 payload 融合传输，接收端 spin-wait 检测 flag——**集合通信的"消息边界"是内存可见性而不是报文边界**，这让协议能在 RDMA 写之上保持低开销，也是它与普通 RPC 框架的本质区别。

## 6.3 源码分析二：UEC 规范的设计取舍

UEC（Ultra Ethernet Consortium，Linux 基金会 JDF 项目）的规范是"以太网为 AI 重新设计"的蓝图。以 1.0（2025-06-11 发布）与 1.1（2026-10-12 发布）为准，其传输层相对 RoCEv2 的核心变更：

1. **报文喷洒（packet spraying）**：同一"连接"的报文走多条路径，不再按流哈希——从根上消除极化，但要求接收端处理乱序。UEC 的解决方案是**乱序交付语义**：上层（集合通信）本来就以 chunk 为幂等单位，乱序在端侧重组。
2. **新拥塞控制（UEC CMS）**：1.0.2 版本修订了 CMS（Congestion Management Signaling）算法族、RCCC（基于接收端）算法——从"交换机打标、发送端反应"扩展出更多端侧可计算的拥塞信号（时延、ACK 流）。
3. **多路径 + 快速恢复**：允许 fabric 内丢包，配合 NIC 的选择性重传，把 PFC 从"必需品"降级为"可选兼容项"。
4. **规模目标**：官方口径对标"AI at scale"——数十万端点的 fabric。

和 Falcon 对照看（6.4），两者哲学一致（端侧可靠性 + 多路径 + 时延 CC），区别是 Falcon 是 Google 的垂直私有实现（已跑满全数据中心），UEC 是开放规范（Broadcom Tomahawk 6、思科/Arista 等已宣布 UEC 兼容产品）。

## 6.4 源码分析三：Google Falcon 的硬件传输

Falcon（SIGCOMM'25 最佳论文）值得单列，因为它回答了"如果从头为 AI 设计一个传输层，会长什么样"：

- **位置**：实现在 200G NIC 硬件里，对上同时服务 RDMA、NVMe 等多种 ULP（上层协议），对下只要求通用有损以太网——**不需要 PFC、不需要特殊交换机支持**。
- **可靠性**：硬件重传 + 基于高精度时间戳的时延感知拥塞控制 + multipath 负载均衡。官方数据：在高利用率下完成时间比 ConnectX-7 的 RoCE 低最多 8 倍，且能在有损链路上同时做到近最优时延与吞吐（ACM 版本标题即"A Reliable, Low Latency Hardware Transport"）。
- **生态**：Falcon 传输协议规范已捐给 OCP（github.com/opencomputeproject/OCP-NET-Falcon）。它的部署前提是 Google 级 SDN（Jupiter 的 OCS/SDN 体系，见 [Google 案例](/09-case-study/google/)）——这也是"第三条路"的真实门槛：**协议可以开源，但它依赖的 fabric 运维能力很难开源**。

## 6.5 格局演进（2025–2026）

```text
Scale-Up：   NVLink4 → NVLink5(NVL72) → NVLink6(NVL144, [2026H2 规划])
            ├─ NVLink Fusion(2025-03)：授权第三方 CPU/加速器接入 NVLink 域
            └─ UALink 200G 1.0(2025-04) → 1.0.3/2.0(2026)：规范先行，芯片 2027
Scale-Out：  IB NDR → XDR 800G（Quantum-X800, SHARP v4）
            ├─ RoCE：普通 → Spectrum-X（AR/增强ECN）→ Spectrum-X Photonics(CPO)
            ├─ UEC 1.0(2025-06) → 1.1(2026-10)：生态产品 2026 起上市
            ├─ 开放协议：Falcon(OCP) / OpenAI MRC(OCP, 多路径可靠连接)
            └─ 芯片：Tomahawk 6 102.4T(2025-06) / Spectrum-6 / 1.6T 端口时代
光互联：     800G 光模块放量 → CPO 硅光交换机量产(2026) → 1.6T [802.3dj 时代]
```

值得记住的三个"未证实/进行中"标注：UALink 量产芯片（官方口径 2026 下半年进实验室、2027 年产品）；OpenAI MRC 的细节以 OCP 仓库为准，公开报道中的部署规模口径未经独立验证；Rubin NVL144 的交付时间以 NVIDIA 官方路线图为准。

## 6.6 本章小结

| 问题 | IB 的答案 | RoCE 的答案 | UEC/Falcon 的答案 |
|---|---|---|---|
| 可靠放哪层 | 物理层 credit | 链路层 PFC | 传输层重传 |
| 有序怎么保证 | 交换机/子网保证 | 按流哈希天然有序 | 端侧容忍乱序 |
| 多路径怎么开 | 自适应路由（交换机排序） | 开不了（极化） | spraying 原生支持 |
| 拥塞信号 | credit + CC | ECN(CNP) | 时延/ACK/CMS 多样信号 |
| 生态位 | 封闭全栈、确定性 | 开放、需工程纪律 | 开放、面向 AI 原生 |

下一章用一个纯 Python Mini Demo 把前面所有概念变成可运行的模型。

**参考来源**

- [UEC 规范历史（1.0 2025-06-11；1.1 2026-10-12）](https://ultraethernet.org/specification/)
- [UALink 200G 1.0 规范发布（Business Wire，2025-04-08）](https://www.businesswire.com/news/home/20250408050548/en/UALink-Consortium-Releases-the-Ultra-Accelerator-Link-200G-1.0-Specification)
- [Falcon：A Reliable, Low Latency Hardware Transport（SIGCOMM'25）](https://dl.acm.org/doi/10.1145/3718958.3754353)；[OCP Falcon 仓库](https://github.com/opencomputeproject/OCP-NET-Falcon)
- [Broadcom Tomahawk 6 发布（2025-06）](https://www.morningstar.com/news/globe-newswire/9462115/broadcom-ships-tomahawk-6-worlds-first-1024-tbps-switch)
- [NVIDIA Spectrum-X 产品页](https://www.nvidia.com/en-us/networking/)（Spectrum-X / Spectrum-XGS / Photonics 定位）
- [NVIDIA NCCL 源码](https://github.com/NVIDIA/nccl)

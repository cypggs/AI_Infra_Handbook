# 3. 架构设计

本章从**全局分层**视角拆解 Meta 的 GenAI 集群架构。一个 Meta 训练集群不是"一堆 GPU + 交换机"，而是一套从芯片到数据中心的五层协同系统：**计算 → 网络 → 存储 → 软件 → 数据中心设施**。每一层都为"同步训练"这一个核心约束做了专门设计。

## 3.1 集群全栈分层

```mermaid
flowchart TB
    subgraph DC["数据中心设施层"]
        direction LR
        AALC["AALC 风液混合冷却<br/>(Catalina 140kW/pod)"]
        POWER["Open Rack 供电"]
        BUILD["多栋建筑 / 托管<br/>(Prometheus/Hyperion)"]
    end
    subgraph SW["软件层"]
        direction LR
        PYT["PyTorch / FSDP / torch.compile"]
        TRI["Triton kernel"]
        NCCL["NCCL / HCCL 通信"]
        TWIN["Twine 集群管理 + MAST 调度"]
    end
    subgraph STO["存储层"]
        direction LR
        TEC["Tectonic 分布式 FS<br/>(Flash 优化, EB 级)"]
        HAM["Hammerspace 并行 NFS<br/>(交互式调试)"]
        SIERRA["YV3 Sierra Point<br/>+ E1.S SSD"]
    end
    subgraph NET["网络层"]
        direction LR
        ROCE["RoCE 织物<br/>Arista 7800 / Wedge400 / Minipack2"]
        IB["InfiniBand 织物<br/>NVIDIA Quantum-2"]
        TOPO["rail-optimized fat-tree<br/>+ 拓扑感知调度"]
        MR["MetaRoCE 自研传输层<br/>有损以太网设计"]
        FPF["FPF 8 平面 fabric<br/>3 层 Clos → 2 层"]
    end
    subgraph COMP["计算层"]
        direction LR
        H100["H100 (24k 集群)"]
        BW["Blackwell GB200 (Catalina)"]
        MI300["AMD MI300"]
        MTIA["MTIA 300–500"]
    end
    COMP --> NET --> STO --> SW --> DC
```

五层之间不是松耦合，而是**为同一目标（大规模同步训练）紧耦合**的。例如网络层的 fat-tree 拓扑要与软件层的拓扑感知调度配合，才能把 AllGather 利用率推到 90%+；存储层的 Tectonic 要与软件层的 checkpoint 流程配合，才能在数百毫秒内跨数千 rank 存取。

## 3.2 计算层：异构硅组合

Meta 的计算层是**多供应商 + 自研**的异构组合，这是它与单一供应商策略的核心区别。

| 硬件 | 角色 | 关键参数 |
|---|---|---|
| **NVIDIA H100** | 2024 GenAI 集群主力 | 24,576 / 集群，FP8 训练 |
| **NVIDIA Blackwell GB200/GB300** | Catalina 机柜 | 72 GPU / 6-rack pod，~140 kW，360 PFLOPS FP16；GB300 2026 年起进入部署 |
| **AMD MI300/MI350** | 异构推理/训练 | 与 NVIDIA 形成供应链备份；Muse Spark Open 官方 AMD 优化目标 |
| **MTIA 300** | ranking/recommendation 训练 | 内置 12×800G NIC + 16 message engine；2026 年初已量产上线（ISCA'26 论文） |
| **MTIA 400/450/500** | 推理为主（含 LLM） | FP8/MX4/MX8，硬件加速 attention/FlashAttention |

异构策略的工程意义：**不把鸡蛋放在一个篮子里**。当 NVIDIA 产能受限或价格波动时，AMD 与自研 MTIA 提供缓冲；同时异构负载（推荐 vs LLM）可以用最合适的硅，提升整体 ROI。

### 整机柜集成：Grand Teton 与 Catalina

单台服务器优化在大规模上边际收益递减，Meta 选择**整机柜协同设计**：

- **Grand Teton**：OCP 开放 GPU 平台，把 GPU、CPU、电源、控制、网络织物集成进单体机柜。优势：减少机柜内线缆、简化供电与远程管理、可规模化复制。
- **Catalina（GB200）**：6-rack pod 结构——中间 2 个机柜装 72 个 Blackwell GPU，4 个 AALC 冷却机柜提供风液混合散热。140 kW/pod 的功耗密度远超传统风冷机柜，必须上液冷。

## 3.3 网络层：双织物与 fat-tree 拓扑

网络是同步训练最关键的瓶颈层。Meta 的设计有三个要点。

### 双织物并行

如 [第 2 章](02-core-ideas) 所述，Meta 同时部署 RoCE 与 InfiniBand 两套 400 Gbps 织物。关键工程点在于：**两者都能支撑超大规模训练**，前提是做好拓扑与路由协同优化。

### rail-optimized fat-tree 拓扑

Meta 采用 **fat-tree（胖树）** 拓扑而非 3D-torus（后者是 Google TPU pod 的特征）。fat-tree 的核心思想是：**上层链路总带宽 ≥ 下层链路总带宽之和**，从而保证任意两个叶子节点之间都有无阻塞的全带宽路径。

"rail-optimized" 进一步指：把每个 GPU 节点的多条上行链路（rail）分配到不同的 spine 交换机域，使得 AllReduce/AllGather 的通信模式能在多个等价路径间均衡，避免拥塞热点。

> ⚠️ **易错点**：fat-tree / rail-optimized 是 Meta H100 集群的特征；3D-torus 与 ICI 光互连是 Google TPU pod 的特征。不要混淆。

### 拓扑感知调度 + NCCL 协同优化

仅有好的物理拓扑不够。Meta 还做了：

1. **拓扑感知作业调度（topology-aware job scheduling）**：把训练任务调度到网络距离最近的 GPU 子集，减少跨域通信。
2. **NCCL 路由优化**：与 NVIDIA 合作改造 NCCL（NVIDIA 集体通信库），让 collective 通信感知底层拓扑，选择最优路径。

两者配合的成果：**大规模集群的 AllGather 带宽利用率从优化前的 10%–90%（剧烈波动）提升并稳定到 90%+**。

### MetaRoCE：为有损以太网重新设计的 RDMA 传输层（2026）

2026-08-24 Meta 公开了自研 RDMA 传输层 **MetaRoCE**（engineering.fb.com；OCP 2026 上宣布开源规范与参考实现）。它的设计哲学与 RoCEv2 根本不同——**假设以太网是有损的，把可靠性全部搬到 NIC 端点**：

| 设计点 | RoCEv2 的传统做法 | MetaRoCE 的做法 |
|---|---|---|
| 丢包假设 | 依赖 PFC 构建"无损"以太网（PFC 本身会引入队头阻塞与拥塞扩散） | 容忍丢包，**取消 PFC 依赖** |
| 路径利用 | 单流绑定单路径，易在 fat-tree 上产生哈希极化 | NIC 把报文**喷洒到多条路径**（UDP 源端口作 ECMP 熵），乱序到达后直接写入最终内存地址，无重排缓冲、无队头阻塞 |
| 拥塞控制 | 单一拥塞窗口 | **逐路径状态**（RTT / ECN / cwnd 独立跟踪）+ 发送端 ECN-AIMD 与接收端公平份额提示的双侧控制；incast 一至两个 RTT 内消解 |
| 丢包恢复 | go-back-N 类重传 | **256-bit 选择性确认位图**，只重传丢失报文 |
| 交换机要求 | 无损队列管理 | 只需标准 ECMP + ECN，可跨 fat-tree / 多平面 / 深浅缓冲交换机和云厂商网络 |

验证数据：在 AMD Pensando 可编程 NIC + AMD GPU 集群（RCCL collective）上，吞吐与流完成时间全面优于 RoCEv2；**1% 丢包下保持约 86% 吞吐**，10% 丢包下仍可用；4/8 平面拓扑线性扩展至 4,000 并发连接；模拟平面故障可自治恢复。对交换机的要求降到"标准以太网"，这正是它能进 OCP 成为开放标准的原因。

### FPF 多平面 fabric 与"三层网络"框架（OCP 2026）

OCP Summit 2026（2026-10-12）上，Meta 把 AI 网络明确分成三层并各给出一套开放方案：

| 层 | 范围 | Meta 方案 |
|---|---|---|
| **Scale-Up** | 机柜/节点内加速器互连 | MTIA 300 用 **Tahan** 以太网交换机（51.2T，4 台组 16 加速器无阻塞域）；下一代 102.4T 刀片预览支持单机柜 72 加速器；**ESUN 1.0** 规范（与 AMD、Arista、ARM、Broadcom、Cisco、HPE、Marvell、Microsoft、NVIDIA 共同推进）统一 scale-up 数据面 |
| **Scale-Out** | 数据中心内 GPU 互连 | **Flattened Planar Fabric（FPF）**：每 GPU 8 条独立 100G 链路接入 8 个独立平面，NIC 硬件喷洒 + 交换机/主机联合控制面（主机可绕开故障平面），把 3 层 Clos 压成 2 层，降低跳数/时延/成本；配套 **IceCube** 102.4T 交换刀片（Tomahawk6C / Spectrum-6 两版，跑开源 FBOSS）与首个液冷网络机柜 **IcePack**；**OSPA** 规范（Meta/Microsoft/Alibaba 共导）标准化交换机平台层 |
| **Scale-Across** | 跨建筑/园区/区域 | **BAG**（backend aggregation）petabit 级 super-spine，把多个 spine 织成一个跨园区 mega-cluster（Inter-BAG 容量达数十 Pbps），支撑 Prometheus（~1GW）与 Hyperion（→5GW）；SRv6 区域骨干跑在 Cisco SiliconOne 浅缓冲交换机 + FBOSS 上，可桥接云容量 |

这套框架的意义：网络从"集群的内部细节"升级为"跨数据中心的体系结构"，且每一层都以开放规范（OCP/ESUN/OSPA）形式发布——与 Meta 的开放哲学一脉相承。

## 3.4 存储层：训练数据的吞吐保证

训练集群每秒要喂给数千 GPU 海量数据，checkpoint 又要在故障时快速存取。Meta 的存储栈：

| 组件 | 作用 |
|---|---|
| **Tectonic** | 数据中心级分布式文件系统，针对 Flash 介质优化，EB 级容量，承载训练数据与 checkpoint。 |
| **FUSE API** | Meta 自研的 Linux FUSE 接口，跑在 Tectonic 之上，给训练任务提供文件系统语义。 |
| **Hammerspace** | 并行 NFS，主要用于**交互式调试与数据探索**（交互式 vs 批量训练两种访问模式并存）。 |
| **YV3 Sierra Point + E1.S SSD** | 存储服务器硬件平台与 EDSFF 外形 SSD，高密度闪存。 |

存储层的关键 SLA 是 **checkpoint 的存取延迟**——见 [第 4 章](04-training-and-inference) 的 checkpoint/恢复流程。

### 2026：AI 存储蓝图——从文件语义到 BLOB 数据湖

2026-07-01 Meta 发表《Meta's AI Storage Blueprint at Scale》（engineering.fb.com），披露存储栈的一次大重构。动机很直白：**AI 算力每两年约翻三倍，存储与互连增速跟不上，存储已成为 GPU stall 的主因之一**。要点：

- **Tectonic 重新定位**：从"分布式文件系统"底座升级为**区域级多租户块存储 fabric**（纠删码、HDD/Flash 分层、热温冷数据智能放置），Meta 在其上运行数百个 EB 级存储集群。
- **训练访问路径从 NFS 式接口迁到 BLOB API**：早期 Llama 训练通过 NFS 式接口跑在 Tectonic 上；新栈把 BLOB 存储直接部署到每个 AI 区域、与 GPU 共置，元数据从多层查找（namelayer/volumeslayer/containerlayer，延迟最高数百毫秒）收敛为 ZippyDB 上的**扁平统一 schema，O(1) 路径解析**，读路径改为 fat-client SDK 直接从 Tectonic 服务器拉块（省掉数据面代理，吞吐/时延/功耗三赢）。
- **分层缓存体系**（借鉴 OS 页缓存）：**L1/L2 = GPU 宿主机内存 + 本地 Flash；L3 = 区域 Flash BLOB fabric；真相源 = 全球 HDD BLOB fabric**。分布式数据缓存复用 Meta 的 **Owl** 子系统组件、放进 SDK 并利用 GPU 宿主机的闲置内存，平均命中率约 **80%**；辅以 hedged reads（对冲慢节点）与客户端动态并发控制（平滑 checkpoint 写出尖峰）。
- **研究速度（research velocity）成为一等指标**：dataloader 预取 + 显式 prefetch() API（深度预取 + 元数据预热 + TTL/LRU 生命周期管理），消除了过去数小时的跨区数据导入作业。

存储设计的重心从"容量 EB 级"转向"**别拖 GPU 的后腿 + 别拖研究员的迭代**"，这是 2026 年之后 AI 存储的主线。

## 3.5 软件层：从 PyTorch 到集群管理

软件层横跨"模型代码"到"集群运维"：

- **训练框架**：PyTorch + FSDP/FSDP2（分片数据并行）+ torch.compile（图编译）+ Triton（kernel 生成）。
- **通信**：NCCL（NVIDIA）/ HCCL（MTIA，Hoot Collective Communications Library）。
- **集群管理**：**Twine**（把整个数据中心抽象成资源池，从推荐系统时代延续而来）。
- **作业调度**：**MAST**（训练/通用调度器，在 2025-09-29 文章中提到支撑 Prometheus 的长距离地理分布式训练）。
- **可靠性工具**：desync debug、distributed collective flight recorder、SDC 检测三件套（[第 5 章](05-core-modules)）；性能与故障分析平台 **Zoomer**（2025-11）与根因分析平台 **DrP**（2025-12）。

> ⚠️ **澄清**：Meta 公开资料中**没有**名为"Titanium"的调度器；集群管理用 **Twine**，训练调度用 **MAST**。本手册以官方命名为准。

## 3.6 数据中心设施层：电力、冷却、选址

当集群规模到 1 GW 量级，数据中心设施本身成为主约束：

- **冷却**：Catalina 的 140 kW/pod 功耗密度远超风冷能力，必须用 **AALC（Air-Assisted Liquid Cooling）**——风液混合，用液体带走大部分热，残余热量用风辅助。
- **供电**：Open Rack 标准化供电与配电。
- **选址与电力**：**Prometheus（~1 GW）**跨多栋建筑、甚至防风雨帐篷与托管（colocation）场地——因为单一数据中心无法容纳 1 GW；2026 年内上线，成为业界首个 1GW+ 超集群。**Hyperion（路易斯安那）2026-07 宣布从 2GW 扩至 5GW**（Reuters，2026-07-13；投资从 ~$27B 增至 $50B+），初期 2GW 计划 2030 年上线。
- **电力获取**：GW 级用电本身就是选址与电网协调难题。2026-01 Meta 宣布三笔核电协议（Forbes，2026-01-09）——Vistra 20 年购电 >2.1 GW、Oklo 1.2 GW 核电园区、TerraPower 两座 Natrium 电站（最高 690 MW），2035 年合计最高约 6.6 GW，外加 $21B 级的外部算力采购（CoreWeave，2026-04）作弹性缓冲。电力已取代土地成为第一约束。
- **长距离训练**：当集群跨建筑/园区，Twine + MAST 需要支撑**地理分布式同步训练**（长距离光纤互连下的带宽与延迟管理）——这正是 Scale-Across 层（BAG super-spine）要解决的问题。

## 3.7 控制面与数据面

从职责划分看，Meta 的架构遵循清晰的**控制面 / 数据面**分离：

| 平面 | 职责 | 典型组件 |
|---|---|---|
| **数据面** | 训练 step 的实际计算与通信：前向/反向、AllReduce/AllGather、checkpoint 存取 | GPU、网络织物、Tectonic、NCCL/HCCL |
| **控制面** | 作业调度、故障检测、健康检查、自动恢复、SDC 扫描 | Twine、MAST、Fleetscanner/Ripple/Hardware Sentinel、auto-restart 控制器 |

这种分离让数据面保持极简（专注于低延迟通信），控制面可以独立演进（例如新增一种 SDC 检测机制，不影响训练 step 路径）。

## 小结

Meta 的架构设计可以浓缩为一个原则：**每一层都为"大规模同步训练"这一个核心约束做了专门优化，并通过开放标准（OCP / PyTorch）让优化可复用**。计算层用异构硅 + 整机柜协同设计换供应链韧性；网络层用双织物 + fat-tree + 拓扑感知调度换 AllGather 带宽；存储层用 Tectonic + Hammerspace 换训练数据吞吐与 checkpoint 延迟；软件层用 PyTorch 原生栈换跨硬件一致性；设施层用 AALC + 多栋建筑换 GW 级供电散热。后续章节将分别拆解训练流程、核心模块与源码实现。

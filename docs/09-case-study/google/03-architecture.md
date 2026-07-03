# 3. 架构设计

本章给出 Google TPU 基础设施的**分层架构总览**，从一颗芯片内部的数据通路，一直讲到跨数据中心的训练网络和软件栈。每一层都针对 ML 的计算特征做了协同设计——理解这套分层，是理解后续章节（训练/推理流程、核心模块、源码）的地图。

## 3.1 分层架构总览

```
┌─────────────────────────────────────────────────────────────────────┐
│  软件栈        JAX (jax.numpy / jit / vmap / grad)                    │
│                ↓ 追踪为 HLO                                            │
│                XLA + GSPMD (分片标注传播 → 插入集合通信)                 │
│                ↓ 已分片的 per-device 程序                              │
│                Pathways (单控制器 / 异步分片数据流 / 成组派发)           │
│                + Multislice (跨 Pod: ICI 内归约 → DCN 归约)            │
├─────────────────────────────────────────────────────────────────────┤
│  调度与管理    Borg (集群管理: 作业/任务/alloc, 优先级/抢占/装箱)         │
│                Borgmaster(Paxos×5) + borglet + healthd + Pod Manager  │
│                datacenter model DB = Borg 与 Pod Manager 的共同真相源   │
├─────────────────────────────────────────────────────────────────────┤
│  主机传输      Falcon (NIC 硬件传输: 200 Gbps / 120 Mops, Swift 拥塞,   │
│                硬件重传, RDMA/NVMe ULP, 多路径 + PSP 加密)              │
├─────────────────────────────────────────────────────────────────────┤
│  跨 Pod 网络   DC-GN / Jupiter (数据中心织物; Multislice 跨 slice 通信)  │
├─────────────────────────────────────────────────────────────────────┤
│  Pod 内光路    OCS (Palomar MEMS 光路交换; 48×128端口/Pod; 按需重配拓扑) │
├─────────────────────────────────────────────────────────────────────┤
│  Pod 内电气    ICI (3D-torus; 每链路 50 GBps 单向; 一个 ICI 域可达 4096) │
├─────────────────────────────────────────────────────────────────────┤
│  芯片         TPU ASIC = MXU(稠密) + SparseCore(稀疏) + HBM + ICI 端口  │
└─────────────────────────────────────────────────────────────────────┘
```

下面自底向上逐层展开。

## 3.2 芯片层：MXU + SparseCore + HBM + ICI

一颗 TPU ASIC 内部的核心数据通路：

- **MXU（Matrix Multiply Unit）**：权重驻留脉动阵列，做稠密矩阵乘。矩阵乘期间不访存（见 [第 2 章](02-core-ideas)）。不同代次规模不同（v1 是 256×256 INT8；后续代次支持 BF16/FP8，且 v4 起每芯片多个 MXU）。
- **SparseCore**（v4 起）：面向稀疏嵌入/动态路由的数据流处理器，"5% 面积/功耗换 5×–7× 嵌入加速"。
- **HBM（高带宽显存）**：存放权重、激活、优化器状态、KV cache。Ironwood 达 192GB / 7.37 TB/s。
- **ICI 端口**：6 个（±x ±y ±z），每端口 50 GBps 单向，连向 3D-torus 的 6 个最近邻。
- **统一缓冲 / 标量/向量单元**：MXU 之外的片上存储与控制流单元。

一颗芯片是"稠密计算（MXU）+ 稀疏计算（SparseCore）+ 高带宽存储（HBM）+ 专用互联（ICI）"的协同样本。

## 3.3 Pod 内电气层：ICI 与 3D-torus

**ICI（Inter-Chip Interconnect）** 是 TPU 专用的芯片间互联，构成 **3D-torus**：

- 每颗芯片 6 条单向 ICI 链路，每条 **50 GBps**。
- 一个 TPUv4 Pod 是**一个 ICI 域**：任意两颗 TPU 可 RDMA 互达（NSDI'24："A TPUv4 pod is one ICI domain, where any pair of TPUs can RDMA to each other"）。
- 拓扑是 3D-torus（带回绕的 3D mesh），把 4096 颗芯片组织成 64 个 cube（每个 cube 4×4×4 = 64 芯片）。
- 作业对其使用的 ICI 链路有**独占所有权**（"each job has exclusive ownership of all the links it uses"）——没有跨作业共享来吸收 straggler，这强化了"一颗坏芯片毒化整个同步作业"的压力，也是可靠性设计的驱动力（见 [第 8 章](08-production-practice)）。

**为什么是 torus 而非 fat-tree**：torus 把一次 AllReduce 沿三个维度拆成短 ring，延迟项 = 2·Σ(dᵢ−1)（按边长线性增长），远低于单一大环的 2·(N−1)（按芯片总数指数增长）。对 16×16×16：90 vs 8190。详见 [Mini Demo](07-mini-demo) 的定量验证。

## 3.4 Pod 内光路层：OCS（可重配拓扑）

**OCS（Optical Circuit Switch）** 是 Google 在 v4 引入的光电重配层，是整套可调度/可容错设计的物理基础：

- 每个 Pod 配 **48 台 128 端口的 Palomar MEMS 光路交换机**，Pod 内共 **6144 条光 ICI 链路**。
- OCS 在光层把 cube 交叉连接成作业想要的 torus / 扭曲 torus 形状——**逻辑拓扑与物理放置解耦**。
- 代价极低：OCS + 光纤 < 一台 v4 Pod 总资本成本的 5%，功耗 < 3%，"远低于用 InfiniBand 等包交换扩展的方案"（NSDI'24）。
- 运行时频繁重配：v4 Pod 每天"每 Pod 数万次 OCS 交叉连接变更"仍可靠运行。

OCS 让拓扑成为"可调度资源"：Borg 不必担心 TPU 资源的物理连续性，"任意一组空闲 cube 都能通过 OCS 交叉连接给某个作业"（NSDI'24）。这也是 cube（64 芯片）成为**故障域 blast radius** 的原因——16 机的粒度被选为"在部署便利与小 blast radius 之间取衡"。

## 3.5 跨 Pod 网络层：DC-GN / Jupiter

单个 Pod（ICI 域）受限于物理规模（v4 = 4096 芯片）。要训练更大模型，需要跨 Pod：

- **DC-GN（Data Center Network）/ Jupiter**：Google 的数据中心织物，把多个 slice/Pod 串起来。Jupiter 相对前代"流完成时间降 10%、吞吐升 30%、功耗降 40%、capex 降 30%、停机降 50×"（Multislice 博客引内部数据）。
- **Multislice**：在 DC-GN 之上，让一个训练 run 跨多个 slice。并行模型是分层的——**激活走 ICI，梯度走 DCN 归约**；XLA 编译器自动把一个 all-reduce 分解为"ICI 内 → DCN 跨 slice → ICI 内"的层次集合通信；引入"跨 DCN 的新分片维度"，支持 FSDP/模型/流水线并行。在 TPUv4 上对几十亿参数模型达到 **58.9% MFU**，且"多 slice 的 MFU 与单 slice 相当"。

跨 Pod 时 ICI 不再可达，所以集合通信要跨"ICI 域 → DCN"两层，这是 Multislice 的核心工程点。

## 3.6 主机传输层：Falcon

**Falcon** 是 Google 自研的主机 NIC 硬件传输（SIGCOMM'25 最佳论文），定位是"在有丢包、无需特殊交换机支持的通用以太网数据中心里，第一个支持多种上层协议（ULP）与异构 workload 的硬件传输"：

- **性能**：峰值 200 Gbps、120 Mops（百万消息操作/秒）。
- **拥塞控制**：基于延迟（Swift 血缘）+ 多路径负载均衡（PLB 血缘）。
- **可靠性**：硬件重传与错误处理；不依赖 PFC（不像 RoCE），在有丢包以太网上仍可靠。
- **ULP**：RDMA（IB Verbs）与 NVMe，"开箱即用兼容"。
- **指标**：在网络拥塞下完成时间比 CX-7 RoCE 低最多 8×；有丢包条件下 goodput 高最多 65%。
- **血缘**：Carousel（流量整形, SIGCOMM'17）、Snap（主机网络微内核, SOSP'19）、Swift（延迟拥塞控制, SIGCOMM'20）、PLB（拥塞信号负载均衡, SIGCOMM'22）、CSIG（拥塞信令）、PSP（加密）。通过 OCP 开放。
- **为何自研**：Google 想要一个横跨存储 + AI/ML + HPC、跑在通用有损以太网上的单一传输；现有硬件传输（RoCE、TTPoE）都不满足"多 ULP / 多 workload"的要求。首发于 Intel IPU E2000 系列。

Falcon 是 DC-GN 流量与存储 ULP 之下的可靠主机侧传输。

## 3.7 调度与管理层：Borg

**Borg**（EuroSys'15）是 Google 的集群管理器，"管理着横跨多个集群、每集群上万台机器的数十万作业"：

- **作业/任务/alloc**：一个 job 含多个跑同一二进制的 task；alloc 是机器上预留的资源槽。
- **优先级与抢占**：非重叠优先级带（监控 > 生产 > 批 > 尽力而为）；资源不足时从低到高抢占；生产带内禁止互相抢占以防级联。
- **配额与准入**：配额是资源向量（CPU/RAM/磁盘...）按优先级表达，配额不足的作业提交时即被拒。
- **装箱/评分**：可行性检查 + 混合评分（介于 worst-fit 与 best-fit 之间，比 best-fit 好 3–5% 装箱效率），配合评分缓存、等价类、随机化机器顺序 + 早停。
- **架构**：Borgmaster（逻辑单进程，实际 5 副本 + Paxos）+ 独立 scheduler + 每机 borglet；Borgmaster 实测 **99.99% 可用**；已在运行的 task 在 master/borglet 宕机时仍继续跑。
- **TPU 扩展**：NSDI'24 披露 TPUv4 在 Borg 之上加了 **Borg Prime**（带优先级调度 + 为反碎片化而抢占/迁移）+ **borglet**（每机代理，跑 `healthd`）+ **Pod Manager**（管 OCS）+ **libtpunet**（设 ICI 网络）。一个 **datacenter model DB** 是 Borg 与 Pod Manager 的共同真相源，"为 cube 部署、作业调度、OCS 交叉连接、网络设置、健康检查设定意图"。

**为什么是 Borg 而非 vanilla K8s**：Borg 是成熟的高可用内部集群管理器（生产十年+，99.99% Borgmaster 可用，优先级/配额/抢占，与物理库存绑定的容量规划），Kubernetes 是它的开源后裔，但开箱即用缺乏 TPUv4 所依赖的 cube/OCS/ICI 协同调度、配额即容量规划、cell 级 gang/抢占语义。

## 3.8 软件栈层：JAX → XLA/GSPMD → Pathways

软件栈自上而下：

1. **JAX**：`jax.numpy` 前端 + 变换（`jit`/`vmap`/`pmap`/带分片的 `jit`/`grad`/`shard_map`）。函数式、可追踪——这是 GSPMD 自动分片的前提。
2. **XLA + GSPMD**：JAX 追踪为 HLO；GSPMD 是 XLA 的分片 pass，从少量用户标注（`PartitionSpec`/`with_sharding_constraint`）传播分片到每个算子，插入集合通信，生成 per-device 程序。
3. **Pathways**：把已分片的 XLA 函数 gang-schedule 到数千 TPU，用单控制器 + 异步分片数据流（futures）+ 成组派发，跨 island 流水线化。Pathways 依赖 PLAQUE（内部闭源分片数据流引擎）做跨主机协调。

三层映射清晰：**JAX/Mesh（标注）→ XLA/GSPMD（分片）→ Pathways（Pod 级编排）**。详见 [第 6 章 源码分析](06-source-analysis)。

## 3.9 一张图的完整链路：一个训练步如何流过这套架构

一个跨 Pod 的训练步，数据/控制流大致是：

1. **JAX 程序**经 XLA/GSPMD 编译为一组分片的 per-device HLO，集合通信已插入（数据/FSDP/张量/流水线混合并行）。
2. **Pathways** 把这些函数 gang-schedule 到各 slice 的 TPU；跨 slice 的梯度归约经 Multislice 分解为 ICI 内 + DCN 两层。
3. **Borg** 已在调度时避开已知坏芯片（datacenter model DB + `healthd` 信号 + preflight 检查）；作业对其 ICI 链路独占。
4. 每颗 **TPU** 上：稠密矩阵乘走 MXU（不访存），稀疏嵌入走 SparseCore，权重/激活/KV 在 HBM，片间通信走 6 条 ICI 链路（3D-torus）。
5. **ICI** 在 Pod 内完成同步集合通信；**OCS** 保证拓扑健康（坏 cube 已被绕过/替换）。
6. 跨 slice 的梯度经 **DC-GN/Jupiter** 归约，主机侧由 **Falcon** 可靠传输。
7. 若某颗芯片故障：`healthd`/preflight 发现 → Borg 标记不可用 → 按 NSDI'24 双路径恢复（reconfigure 迁移，或 reroute 容错路由）→ 从 checkpoint 恢复或原地继续。
8. 进度周期性写入 **Orbax** checkpoint（OCDBT + Zarr3，异步）。

这条链路上每一层都不可替代：抽掉 OCS，拓扑不可重配、容错退化为"等修好"；抽掉 GSPMD，并行退化回手写集合通信；抽掉 Pathways，跨 Pod 单控制器编排失去性能。这正是 Google 垂直整合的价值。

下一章 [训练与推理](04-training-and-inference) 将聚焦这条链路上训练与推理两条 workload 的具体流程。

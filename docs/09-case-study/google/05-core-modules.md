# 5. 核心模块

本章逐个剖析 Google TPU 基础设施的关键模块，每个模块给出**职责、关键参数/事实、设计要点**。这些模块对应 [第 3 章](03-architecture) 分层架构里的具体组件，也是面试与工程借鉴时最常被问到的对象。

---

## 5.1 计算类模块

### 5.1.1 MXU（Matrix Multiply Unit）—— 稠密矩阵乘引擎

- **职责**：TPU 的计算核心，做稠密矩阵乘（GEMM）。
- **原理**：权重驻留（weight-stationary）脉动阵列。权重预载入每个 MAC 单元并固定，激活沿阵列流入，部分和沿另一方向流动，矩阵乘期间**不访存**。
- **规模**：v1 = 256×256 INT8（65536 个 8-bit MAC）；后续代次支持 BF16/FP8，v4 起每芯片多个 MXU。
- **设计要点**：把"访存"从 GEMM 热路径删除，是 TPU 能效（v1 相对当代 GPU/CPU 快 15–30×、TOPS/W 高 30–80×）的根因。推理时验证成本由权重加载主导（见 [4.2.2](04-training-and-inference#422-投机解码dflash-与-3-加速)），是投机解码"宽验证免费"的物理基础。

### 5.1.2 SparseCore —— 稀疏嵌入数据流处理器

- **职责**：加速稀疏计算（嵌入查表、动态稀疏路由、大规模 embedding）。
- **事实**（v4 论文）："用 5% 的晶圆面积和功耗，把依赖嵌入的模型加速 5×–7×"。
- **代次差异**：v5p/Ironwood 每芯片 4 个，v6e 每芯片 2 个。
- **设计要点**：让稠密（MXU）与稀疏（SparseCore）走两条数据通路，避免稀疏访存拖慢脉动阵列。对推荐系统、RAG 检索、MoE 这类"稠密 + 稀疏"混合 workload 尤为关键。

### 5.1.3 HBM（高带宽显存）

- **职责**：存放权重、激活、优化器状态、KV cache。
- **规模**：Ironwood 达 192GB / 7.37 TB/s。
- **设计要点**：大容量高带宽 HBM 是"权重驻留 + 激活流过"脉动阵列的存储后盾，也是推理时 KV cache 容量（决定可服务并发/上下文长度）的硬约束。JetStream 用 int8 KV cache 量化来压缩 cache 进 HBM。

---

## 5.2 互联与拓扑类模块

### 5.2.1 ICI（Inter-Chip Interconnect）—— Pod 内专用互联

- **职责**：TPU 专用芯片间互联，承载 Pod 内同步集合通信（激活、张量/模型并行、权重归约）。
- **关键参数**：每链路 50 GBps 单向；每芯片 6 条（±x ±y ±z）。
- **设计要点**：一个 TPUv4 Pod 是**一个 ICI 域**，任意两颗 TPU 可 RDMA 互达；作业对其链路**独占**（无跨作业共享吸收 straggler）。这是"一颗坏芯片毒化整个同步作业"的结构性原因，也是可靠性设计的驱动力。

### 5.2.2 3D-torus —— Pod 电气拓扑

- **职责**：把 4096 颗芯片组织成带回绕的 3D mesh（64 个 4×4×4 cube）。
- **关键性质**：把一次 AllReduce 沿三维拆成短 ring，延迟项 = **2·Σ(dᵢ−1)**（按边长线性），远低于单一大环的 2·(N−1)（按芯片总数指数）。16×16×16：90 vs 8190。
- **设计要点**：torus 让布线/交换数随规模近似线性增长（而非 fat-tree 的更陡），是 Google 拓扑选择的数学根因。详见 [Mini Demo](07-mini-demo)。

### 5.2.3 OCS（Optical Circuit Switch）—— 可重配光路层

- **职责**：在光层按需把 cube 交叉连接成作业想要的 torus/扭曲 torus 形状，解耦逻辑拓扑与物理放置。
- **关键参数**：每 Pod 48 台 128 端口 Palomar MEMS OCS；6144 条光 ICI 链路；OCS + 光纤 < Pod 总资本成本 5%、功耗 < 3%。
- **运行事实**：每 Pod 每天"数万次 OCS 交叉连接变更"仍可靠运行。
- **设计要点**：OCS 让拓扑成为"可调度资源"——Borg 不必担心物理连续性；同时让 cube（64 芯片）成为故障域 blast radius（16 机粒度，"部署便利与小 blast radius 之间取衡"）。OCS 故障 blast radius 大（可影响 Pod 所有 cube），故走 reroute 而非 reconfigure。

### 5.2.4 DC-GN / Jupiter —— 跨 Pod 数据中心织物

- **职责**：把多个 slice/Pod 串起来，承载 Multislice 跨 slice 通信。
- **关键参数**：Jupiter 相对前代"流完成时间 −10%、吞吐 +30%、功耗 −40%、capex −30%、停机 −50×"（Multislice 博客引内部数据）。
- **设计要点**：跨 slice 时 ICI 不可达，集合通信分两层（ICI 内 + DCN）；XLA 自动把 all-reduce 分解为层次集合通信。

### 5.2.5 Falcon —— 主机 NIC 硬件传输

- **职责**：在有丢包、无需特殊交换机的通用以太网上，提供可靠、低延迟、多 ULP 的主机侧传输。
- **关键参数**：200 Gbps / 120 Mops；Swift 血缘的延迟拥塞控制 + PLB 多路径；硬件重传；RDMA/NVMe ULP；PSP 加密。
- **指标**：拥塞下完成时间比 CX-7 RoCE 低最多 8×；有丢笔下 goodput 高最多 65%。
- **设计要点**：不依赖 PFC（不像 RoCE），首发 Intel IPU E2000，经 OCP 开放。是 DC-GN 流量与存储 ULP 之下的可靠主机侧传输。

---

## 5.3 调度与管理类模块

### 5.3.1 Borg —— 集群管理器

- **职责**：准入、调度、启动、重启、监控全量应用；TPUv4 作业的集群管理层（NSDI'24："Borg: a cluster management service that admits, schedules and manages TPUv4 jobs"）。
- **核心机制**：作业/任务/alloc；优先级带（监控 > 生产 > 批 > 尽力而为）+ 抢占；配额即容量规划；混合装箱评分（比 best-fit 好 3–5%）；Borgmaster（5 副本 + Paxos）+ scheduler + borglet。
- **可用性**：Borgmaster 99.99%；已在运行 task 在 master/borglet 宕机时仍继续。

### 5.3.2 Borg Prime + borglet + Pod Manager + healthd —— TPU 专用扩展

- **Borg Prime**：带优先级调度 + 为反碎片化而抢占/迁移（如把多个 sub-cube 作业重定位以腾出连续 cube，或把多 cube 作业迁到别的 Pod 以容纳超大作业）。
- **borglet**：每机代理，跑 `healthd`，向 Borg 报告状态。
- **Pod Manager**：管 OCS。
- **healthd**：每台 TPUv4 机器上的守护进程，实时监控 24 条单向 ICI 链路 + 4 颗 TPU ASIC + PCIe；按临界度排序症状，严重症状触发 Borg 驱逐并重调度。
- **datacenter model DB**：Borg 与 Pod Manager 的共同真相源，"为 cube 部署、调度、OCS 交叉连接、网络设置、健康检查设定意图"。

### 5.3.3 libtpunet —— ICI 网络设置与容错路由

- **职责**：为作业设置 ICI 网络；加载容错路由表。
- **容错路由**：reroute 路径下，libtpunet 加载预计算的 **wild-first routing（WFR）** 表——"每维最多一次 wild hop 后回到 DOR"，配 sandwich 规则 + 双虚信道（如 `xyZYX`）保证无死锁；路径由整数线性规划（ILP）离线优化 all-to-all 吞吐后缓存。

---

## 5.4 软件栈类模块

### 5.4.1 JAX —— 函数式、可追踪的前端

- **职责**：NumPy 式前端 + 变换（`jit`/`vmap`/`pmap`/带分片 `jit`/`grad`/`shard_map`）。
- **设计要点**：函数式、可追踪——程序是数组纯函数、无隐藏副作用，是 GSPMD 自动分片的前提。

### 5.4.2 XLA + GSPMD —— 编译器与分片 pass

- **XLA**：把 HLO 降低为优化的 CPU/GPU/TPU 代码。
- **GSPMD**：XLA 的分片 pass，从少量用户标注（`PartitionSpec`/`with_sharding_constraint`）传播分片到每个算子，插入集合通信，生成 per-device 程序。覆盖数据/FSDP/张量/流水线混合并行。
- **指标**：2048 个 TPUv3 核心上，万亿参数模型 50%–62% 利用率。

### 5.4.3 JAX Mesh + PartitionSpec —— 用户标注层

- **Mesh**：带命名轴的设备网格（如 `data`/`fsdp`/`tensor`/`pipeline`）。
- **PartitionSpec**：把张量轴绑定到 mesh 轴的标注。
- **with_sharding_constraint**：在 Auto 模式下作为 GSPMD 提示，Explicit 模式下强制分片。

### 5.4.4 Pathways —— 跨 Pod 单控制器运行时

- **职责**：把已分片的 XLA 函数 gang-schedule 到数千 TPU，跨 island 流水线化。
- **核心机制**：单控制器 + 异步分片数据流（sharded dataflow of futures）+ 成组派发（grouped dispatch）；依赖 PLAQUE（内部闭源分片数据流引擎）做跨主机协调。
- **指标**：2048 TPU 上 SPMD 约 100% 利用率；跨 16 级流水线或跨两 island 的 Transformer 吞吐与 SPMD 相当。

### 5.4.5 Orbax —— checkpoint

- **职责**：训练进度的周期性持久化。
- **机制**：`CheckpointManager`（同步/异步）+ `PyTreeCheckpointHandler`（默认 OCDBT + Zarr3）；保留最近 N 个 checkpoint；按 `save_interval_steps` 决定落盘。
- **设计要点**：checkpoint 间隔直接决定 reconfigure 路径的回滚损失（见 [Mini Demo](07-mini-demo)）。

### 5.4.6 JetStream / tpu-inference —— TPU 原生推理引擎

- **职责**：XLA/TPU 上吞吐与内存优化的 LLM 推理。
- **机制**：权重分片三轴（FSDP/自回归/张量）+ 连续批处理 + HBM KV cache（可 int8 量化）+ XLA 编译量化。
- **生态**：核心功能已迁移到 `tpu-inference`（`tpu.vllm.ai`），JetStream 本体归档。

---

## 5.5 模块速查表

| 模块 | 层 | 一句话职责 |
|---|---|---|
| MXU | 芯片 | 权重驻留脉动阵列，矩阵乘不访存 |
| SparseCore | 芯片 | 稀疏嵌入数据流处理器（5% 面积换 5×–7×） |
| HBM | 芯片 | 权重/激活/KV 的高带宽存储（Ironwood 192GB） |
| ICI | Pod 电气 | 50 GBps/链路 3D-torus，一个 ICI 域 4096 芯片 |
| OCS | Pod 光路 | 48×128 端口 Palomar，按需重配拓扑（<5% 成本） |
| Jupiter/DC-GN | 跨 Pod | 数据中心织物，Multislice 跨 slice 通信 |
| Falcon | 主机传输 | 200 Gbps/120 Mops 硬件传输，Swift 拥塞，不依赖 PFC |
| Borg | 调度 | 集群管理，优先级/抢占/装箱，99.99% Borgmaster |
| healthd | 调度 | 每机守护，监控 ICI/ASIC/PCIe，触发驱逐 |
| libtpunet | 调度 | 设 ICI 网络，加载 wild-first 容错路由表 |
| JAX | 软件 | 函数式可追踪前端 |
| XLA/GSPMD | 软件 | 编译器分片 pass，标注即并行 |
| Pathways | 软件 | 单控制器跨 Pod gang-schedule 运行时 |
| Orbax | 软件 | OCDBT+Zarr3 checkpoint |
| JetStream/tpu-inference | 软件 | TPU 原生推理引擎（权重分片+连续批处理） |

下一章 [源码与生态分析](06-source-analysis) 将进入 MaxText / Pathways / GSPMD 的真实代码。

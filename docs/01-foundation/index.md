# 基础篇

本章节覆盖 AI 基础设施工程师必须掌握的底层基础。

## 已上线主题

- [大模型从 0 到 1：训练与推理全链路之旅](./llm-from-zero/) — 用通俗易懂的方式走完数据 → Tokenizer → Transformer → 预训练 → 后训练 → 推理服务 → 优化加速的完整旅程，穿插真实模型案例与 2025-2026 前沿动态
- [GPU 架构与 CUDA 基础](./gpu-cuda/) — 从 SIMT/Warp/SM 到 CUDA 编程模型，从 Fermi 到 Blackwell 架构演进，从 cuBLAS/NCCL 到 DCGM 生产监控，建立 AI Infra 的底层硬件与软件栈直觉（内容更新至 2026-07-04）
- [Linux 系统与性能调优](./linux-systems/) — 从 Kernel/User Space、系统调用到 CFS 调度器、虚拟内存/TLB/HugePages/NUMA、VFS/I/O 调度、网络协议栈、cgroup v2/namespace，配合 CPU 可运行 Mini Demo（CFS、LRU page cache、OOM、I/O 调度、cgroup 限制），覆盖 AI 训练/推理场景的 Linux 调优与性能分析（内容更新至 2026-07-04）
- [计算机网络](./computer-networks/) — 从 OSI/TCP-IP 分层、分组交换、可靠传输与拥塞控制，到数据中心 Spine-Leaf/fat-tree/3D-torus、InfiniBand/RoCE/RDMA、Kubernetes CNI/Service/DNS/LB，配合 CPU 可运行 Mini Demo（LPM 路由、滑动窗口、CUBIC-like 拥塞控制、ring/tree all-reduce、DNS/LB），覆盖 AI 训练与推理的网络底座（内容更新至 2026-07-04）
- [存储系统](./storage-systems/) — 从块/文件/对象三种存储语义、一致性、复制与纠删码，到 DAS/NAS/SAN/对象存储/并行文件系统、Kubernetes PV/PVC/StorageClass/CSI、PyTorch Distributed Checkpoint，配合 CPU 可运行 Mini Demo（块分配、inode 文件系统、对象存储/版本/multipart/最终一致性、三副本/XOR 纠删码、热/暖分层缓存、AI checkpoint 保存/加载），覆盖 AI 训练 checkpoint 与推理模型加载的存储底座（内容更新至 2026-07-04）

- [分布式系统基础](./distributed-systems/) — 从故障模型、CAP/PACELC、一致性谱系、复制/分区/quorum/共识，到分布式事务、分布式锁、幂等、逻辑时钟/向量时钟，配合 CPU 可运行 Mini Demo（Lamport/Vector Clock、Raft、2PC、Quorum），建立 AI 集群协调、K8s 控制面、对象存储一致性与分布式训练通信的底层直觉（内容更新至 2026-07-04）

## 计划中主题

- 基础篇阶段性补完，后续将进入进阶专题更新。

## 一句话理解

> 没有扎实的 Linux、网络、存储、GPU 和分布式基础，任何上层 AI 平台都建不稳。

本章节正在建设中，敬请期待。

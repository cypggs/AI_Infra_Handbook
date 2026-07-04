# 存储系统

> 一句话理解：**存储系统是 AI 基础设施的“仓库与血脉”——模型权重、训练数据、checkpoint、artifact 都存放在这里，并通过网络流入 GPU；仓库设计不好，算力再强也会挨饿。**

如果你已经理解了 Linux 系统调优和计算机网络，下一步就该把目光投向存储。AI 平台上的大量性能问题，最终都会追溯到存储：

- 分布式训练 checkpoint 保存一次要几分钟，可能是本地 NVMe 吞吐不足、对象存储 multipart 并发不够，或 page cache 回写策略不当；
- 模型服务冷启动慢，可能是模型权重文件太大、对象存储下载带宽受限、或本地缓存未命中；
- Kubernetes Pod 一直 `ContainerCreating`，可能是 CSI 卷 provision/attach 慢、PVC 绑定失败、StorageClass 配置错误；
- 对象存储账单暴涨，可能是生命周期策略没配、海量小对象未合并、或低频数据未转冷存。

本章面向的是**已经会用 Linux、Kubernetes 和对象存储，但想理解存储系统为什么这样设计**的工程师。

## 学习目标

读完本章，你将能够：

1. 解释块、文件、对象三种存储语义，以及它们各自的优缺点和适用场景；
2. 理解存储抽象栈（应用 → 文件系统 → 卷 → 块 → 设备）与 DAS/NAS/SAN/对象存储/并行文件系统分类；
3. 理解一致性模型（强一致、最终一致、读写一致）和耐久性机制（复制 vs 纠删码）；
4. 理解 AI 工作负载的存储特征：突发大写、TB 级顺序文件、海量小对象、热/温/冷分层；
5. 理解 Kubernetes 存储抽象 PV/PVC/StorageClass/CSI 背后的原理与选型逻辑；
6. 理解 AI 训练 checkpoint、模型权重、artifact 的存储最佳实践；
7. 掌握基础存储性能工具：fio、dd、iostat、s3 benchmark、Lustre/WEKA 监控；
8. 与 Linux 系统调优、Kubernetes、案例研究、AI 平台主题形成知识闭环。

## 本章与手册其他主题的关系

| 主题 | 关系 | 本章会讲到的交叉点 |
|---|---|---|
| [Linux 系统与性能调优](/01-foundation/linux-systems/) | 下层实现 vs 上层抽象 | Linux 系统调优讲“VFS、ext4/xfs、块层、I/O 调度器、page cache 如何实现”，本章讲“存储系统概念、选型与 AI 场景”。 |
| [计算机网络](/01-foundation/computer-networks/) | 网络 vs 存储 | 网络存储（NAS/SAN/对象存储/并行文件系统）依赖网络；本章解释数据如何通过网络从存储到达 GPU。 |
| [分布式系统基础](/01-foundation/distributed-systems/) | 分布式一致性 vs 存储语义 | 分布式系统基础讲 CAP、复制、quorum、共识；本章讲这些理论在块/文件/对象存储与 AI checkpoint 中的落地。 |
| [容器运行时](/02-cloud-native/container-runtime/) | 容器隔离 vs 存储挂载 | 容器运行时讲“怎么用 overlayfs/镜像分层”，本章讲“持久化存储、卷、CSI 挂载”。 |
| [Kubernetes](/02-cloud-native/kubernetes/) | 编排层 vs 存储层 | Kubernetes 主题讲“PV/PVC/StorageClass/CSI 怎么用”，本章讲“它们背后的存储原理与选型”。 |
| [MLflow / Kubeflow / KServe / Ray / Airflow](/03-ai-platform/) | AI 平台 vs 存储底座 | Artifact Store、模型仓库、checkpoint 路径、数据集来源都依赖存储；本章提供底层视角。 |
| [Meta / Google / OpenAI / Anthropic 案例研究](/09-case-study/) | 超大规模集群 vs 存储设计 | 这些案例研究详细讲 Tectonic、Orbax/Zarr3、TB 级 checkpoint；本章提供理论基础。 |

## 本章结构

按手册统一结构，本章包含 11 节：

1. [背景](01-background) — 为什么 AI Infra 工程师必须懂存储
2. [核心思想](02-core-ideas) — 块/文件/对象、一致性、耐久性、延迟/吞吐/IOPS
3. [架构设计](03-architecture) — DAS/NAS/SAN/对象存储/并行文件系统/K8s 存储架构
4. [存储数据流](04-storage-workflow) — checkpoint、模型加载、CSI 挂卷三条链路
5. [核心模块](05-core-modules) — 本地/网络/对象/并行文件系统、K8s CSI、缓存分层、数据管理
6. [源码分析](06-source-analysis) — PyTorch Distributed Checkpoint 或 EBS CSI driver 链路
7. [工程实践](07-mini-demo) — CPU 可运行存储机制模拟器
8. [企业生产实践](08-production-practice) — AI 集群存储选型、checkpoint 策略、K8s 存储
9. [最佳实践](09-best-practices) — AI 存储设计检查清单与性能基准
10. [面试题](10-interview-questions) — 初/中/高级存储面试题
11. [延伸阅读](11-further-reading) — 书籍、论文、官方文档与交叉引用

## 一句话总结

> **存储系统不是“能 mount 就行”的磁盘，而是决定 AI 训练/推理效率、成本和稳定性的关键基础设施。理解它，才能解释为什么同样的模型和代码，在不同存储环境下会有完全不同的表现。**

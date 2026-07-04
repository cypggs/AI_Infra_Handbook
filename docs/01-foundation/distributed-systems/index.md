# 分布式系统基础

> 一句话理解：**分布式系统不是“把多台机器连起来”，而是在“网络一定会分区、节点一定会故障、消息一定会延迟”的前提下，仍然让整体表现得像一台可靠计算机”的工程实践。**

如果你已经掌握了 Linux、网络和存储，下一步就必须理解分布式系统——因为现代 AI 基础设施几乎没有不是分布式的：

- 万卡训练集群：数千个 GPU 需要协同完成一次前向/反向传播，任何节点掉队或网络抖动都会影响整个任务；
- 模型推理服务：多副本部署在多个节点上，负载均衡、状态同步、故障转移都依赖分布式协议；
- Kubernetes：etcd 用 Raft 维护集群状态，apiserver 通过 watch 机制把状态变更推送给所有组件；
- 对象存储与并行文件系统：数据被复制到多个节点/机架/可用区，一致性与可用性的 trade-off 每天都在发生。

本章面向的是**已经会用 Kubernetes / 跑过分布式训练，但想理解底层协议为什么这样设计**的工程师。

## 学习目标

读完本章，你将能够：

1. 解释分布式系统的核心挑战：网络分区、节点故障、消息延迟、时钟不一致；
2. 区分故障模型（fail-stop / crash-recovery / Byzantine）并选择合适的容错策略；
3. 理解 CAP / PACELC 定理，并能在 AI Infra 场景中做出一致性 vs 可用性的 trade-off；
4. 掌握一致性谱系：线性一致性、顺序一致性、因果一致性、最终一致性；
5. 理解复制、分区、quorum、共识算法（Raft / Paxos）的基本原理；
6. 理解分布式事务（2PC / 3PC）、分布式锁、幂等性与去重；
7. 理解分布式系统中的时间、顺序与因果（逻辑时钟、向量时钟）；
8. 与 Kubernetes、Ray、存储系统、案例研究形成知识闭环。

## 本章与手册其他主题的关系

| 主题 | 关系 | 本章会讲到的交叉点 |
|---|---|---|
| [Linux 系统与性能调优](/01-foundation/linux-systems/) | 单机 OS 底座 vs 分布式系统 | Linux 讲进程/网络/存储在单机内如何工作；本章讲多台机器如何协作、容错与一致性。 |
| [计算机网络](/01-foundation/computer-networks/) | 网络通信底座 | 网络讲协议/拓扑/RDMA；本章讲网络分区、RPC、消息传递语义、超时与重试。 |
| [存储系统](/01-foundation/storage-systems/) | 数据持久化 vs 分布式一致性 | 存储讲块/文件/对象；本章讲 CAP、复制、quorum、共识、最终一致性。 |
| [Kubernetes](/02-cloud-native/kubernetes/) | 编排层 vs 分布式协调 | K8s 用 etcd/Raft、controller 控制循环、watch；本章讲它们背后的分布式原理。 |
| [Ray](/03-ai-platform/ray/) | 分布式运行时 | Ray 的 ownership、GCS、对象存储、lineage 重建都是分布式系统问题。 |
| [案例研究](/09-case-study/) | 超大规模实践 | Google Borg/Paxos、Meta ZippyDB/Paxos、Pathways 单控制器都是分布式系统经典案例。 |

## 本章结构

按手册统一结构，本章包含 11 节：

1. [背景](01-background) — 为什么 AI Infra 工程师必须懂分布式系统
2. [核心思想](02-core-ideas) — 故障模型、CAP、一致性谱系、复制、分区、共识
3. [架构设计](03-architecture) — 分层架构、Leader-Follower、分片、复制拓扑、故障域
4. [分布式工作流程](04-distributed-workflow) — 一次分布式 AI 训练 job 的完整链路
5. [核心模块](05-core-modules) — RPC、成员发现、失败检测、领导者选举、复制日志、分布式事务
6. [源码分析](06-source-analysis) — etcd Raft 核心调用链
7. [工程实践](07-mini-demo) — CPU 可运行的分布式机制模拟器
8. [企业生产实践](08-production-practice) — AI 集群中的分布式系统实践
9. [最佳实践](09-best-practices) — 设计检查清单与 CAP 决策树
10. [面试题](10-interview-questions) — 初/中/高级分布式系统面试题
11. [延伸阅读](11-further-reading) — 书籍、论文、官方文档与交叉引用

## 一句话总结

> **分布式系统是 AI Infra 的“粘合剂”：它让 Linux、网络、存储、GPU 在多台机器上协同工作，并在故障与分区中保持可用和一致。**

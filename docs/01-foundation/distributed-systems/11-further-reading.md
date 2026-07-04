# 11. 延伸阅读与总结

> 一句话理解：分布式系统是 AI Infra 的底层语言；想要深入，必读《Designing Data-Intensive Applications》、Lamport 的时钟与 Paxos 论文、Raft 论文，以及 etcd/Ray/PyTorch Distributed 的官方文档。

## 11.1 必读书籍

| 书籍 | 作者 | 看点 |
|---|---|---|
| *Designing Data-Intensive Applications* | Martin Kleppmann | 复制、分区、事务、一致性与共识的系统化讲解 |
| *Distributed Systems*（在线版） | Maarten van Steen & Andrew Tanenbaum | 从基础概念到一致性协议 |
| *The Datacenter as a Computer* | Luiz André Barroso 等 | 数据中心 scale、故障域、能耗 |

## 11.2 经典论文

| 论文 | 作者 | 看点 |
|---|---|---|
| *Time, Clocks, and the Ordering of Events in a Distributed System* | Leslie Lamport, 1978 | 逻辑时钟、happens-before |
| *Paxos Made Simple* | Leslie Lamport, 2001 | Paxos 的最清晰入门 |
| *In Search of an Understandable Consensus Algorithm (Raft)* | Ongaro & Ousterhout, ATC'14 | 现代工程共识算法首选 |
| *Viewstamped Replication Revisited* | Barbara Liskov & James Cowling | 另一种复制状态机视角 |
| *Dynamo: Amazon's Highly Available Key-value Store* | DeCandia et al., SOSP'07 | Leaderless + Quorum + Gossip |
| *Bigtable: A Distributed Storage System for Structured Data* | Chang et al., OSDI'06 | 分片 + SSTable + 分布式协调 |
| *Spanner: Google's Globally-Distributed Database* | Corbett et al., OSDI'12 | TrueTime + 外部一致性 |
| *The Google File System* | Ghemawat et al., SOSP'03 | 大规模分布式文件系统 |
| *MapReduce: Simplified Data Processing on Large Clusters* | Dean & Ghemawat, OSDI'04 | 分布式计算编程模型 |
| *ZooKeeper: Wait-free coordination for Internet-scale systems* | Hunt et al., ATC'10 | 分布式协调服务 |
| *Large-scale cluster management at Google with Borg* | Verma et al., EuroSys'15 | 超大规模调度与状态管理 |
| *Ray: A Distributed Framework for Emerging AI Applications* | Moritz et al., OSDI'18 | AI 场景分布式运行时 |
| *Falcon: Replacing Fragmented Datasets with Distributed Shared Memory* | Kim et al., NSDI'24 | AI 训练中的分布式共享内存 |

## 11.3 官方文档与源码

| 资源 | 说明 |
|---|---|
| [etcd 官方文档](https://etcd.io/docs/) | Raft 实现与运维必读 |
| [etcd Raft 源码](https://github.com/etcd-io/etcd/tree/main/raft) | 生产级 Raft 实现 |
| [Ray 官方文档](https://docs.ray.io/) | ownership、GCS、fault tolerance |
| [PyTorch Distributed](https://pytorch.org/tutorials/beginner/dist_overview.html) | DDP/FSDP/c10d/Elastic |
| [Kubernetes 官方文档](https://kubernetes.io/docs/home/) | etcd、controller、scheduler 设计 |
| [NCCL 文档](https://docs.nvidia.com/deeplearning/nccl/) | GPU 集合通信 |
| [MLflow Tracking Server](https://mlflow.org/docs/latest/tracking/server.html) | 分布式实验追踪 |

## 11.4 相邻主题交叉引用

| 主题 | 关系 | 链接 |
|---|---|---|
| Linux 系统与性能调优 | 单机 OS 底座 | [总览](../linux-systems/index.md) |
| 计算机网络 | 网络分区、RPC、消息传递 | [总览](../computer-networks/index.md) |
| 存储系统 | CAP、复制、一致性、对象存储 | [总览](../storage-systems/index.md) |
| Kubernetes | etcd/Raft、controller、watch | [总览](../../02-cloud-native/kubernetes/index.md) |
| Ray | ownership、GCS、对象存储、lineage | [总览](../../03-ai-platform/ray/index.md) |
| Google 案例研究 | Borgmaster/Paxos、GFS/Bigtable | [总览](../../09-case-study/google/index.md) |
| Meta 案例研究 | ZippyDB/Paxos、Twine 调度 | [总览](../../09-case-study/meta/index.md) |

## 11.5 推荐学习路径

1. **第 1 周**：精读本章 01-05 节，理解 CAP、一致性谱系、Raft、quorum、2PC。
2. **第 2 周**：读 06 源码分析 + 07 Mini Demo；本地运行分布式系统模拟器。
3. **第 3 周**：读 08-09 生产实践与最佳实践；结合你所在的 K8s / 训练 / 推理平台做 CAP 决策树练习。
4. **第 4 周**：读 10 面试题；挑 3-5 题用白板或文档写出完整答案；阅读 DDIA 相关章节和 Raft 论文。

## 11.6 一句话总结

> **分布式系统是 AI Infra 的“操作系统”：它把不可靠的网络、节点、时钟组织成可靠的计算、存储、协调能力。掌握它，才能真正理解 Kubernetes、Ray、FSDP、对象存储和超大规模训练平台为什么这样设计。**

## 本章小结

- 经典书籍和论文是深入理解分布式系统的不二法门。
- etcd Raft 源码、Ray 文档、PyTorch Distributed 文档是 AI Infra 工程师的实战参考。
- 本主题与 Linux、网络、存储、Kubernetes、Ray、案例研究形成完整知识闭环。

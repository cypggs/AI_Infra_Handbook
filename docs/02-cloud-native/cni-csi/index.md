# CNI / CSI 深度

> 一句话理解：**CNI 与 CSI 是 Kubernetes 把"网络"和"存储"这两件最脏、最硬件相关的事，从核心代码里踢出去，变成可插拔插件的两根柱子**——CNI 让任意 Pod 在创建瞬间拿到 IP 并连入集群网络，CSI 让任意卷从声明到挂载到扩容都通过 gRPC 接口由外部驱动完成；二者共同撑起了 K8s 对异构基础设施的包容性，也是 AI 平台高性能网络（RDMA/GPU Direct）与大规模存储（并行文件系统 / 本地 SSD / 对象存储）落地的关键接口。

## 为什么 AI 平台工程师必须懂 CNI / CSI

Kubernetes 主题讲透了"编排"，但 K8s 自己**不实现网络，也不实现存储**——它只定义接口，把具体实现交给插件生态。当你：

- 分布式训练 Job 出现 NCCL 通信 hang，需要判断是 CNI 的 VXLAN 性能瓶颈、MTU 问题，还是 RDMA 网卡没有正确透传；
- 大模型 checkpoint 写入慢到拖垮训练，需要选择本地 NVMe / Lustre / WEKA / Ceph RBD 哪一种 CSI 方案；
- Pod 卡在 `ContainerCreating`，`kubectl describe` 报 `FailedCreatePodSandBox` 或 `VolumeAttachment` 卡住，需要定位是 CNI 配置冲突还是 CSI 驱动没响应；
- 多租户推理集群要隔离南北向与东西向流量，同时让训练 Pod 访问高速存储，需要设计 NetworkPolicy + 多网卡（Multus）+ 存储类的组合；

——这些都落在 CNI / CSI 的范畴里。网络决定 AI 负载的通信效率，存储决定数据吞吐与 checkpoint 可靠性；不理解接口边界、生命周期与排障方法，就无法设计生产级 AI 基础设施。

## 学习目标

阅读完本主题后，你应该能够：

1. 解释 CNI 与 CSI 的设计动机：为什么 K8s 要把网络和存储从 in-tree 插件迁到 out-of-tree。
2. 画出 CNI 的调用链：kubelet / CRI → CNI 可执行文件 → plugin chain → IPAM → netns，理解 ADD / DEL / CHECK / GC / STATUS 的语义。
3. 画出 CSI 的调用链：PVC → external-provisioner → Controller CreateVolume → PV → external-attacher → NodeStageVolume → NodePublishVolume → mount，理解 Controller / Node / Identity 三面的 gRPC 接口。
4. 对比主流 CNI：Flannel、Calico、Cilium、Weave、Multus、SR-IOV CNI，能在 AI 场景下做选型。
5. 对比主流 CSI 驱动与存储后端：EBS / GCE PD / Ceph RBD / Lustre / WEKA / NFS / S3 CSI / local PV / TopoLVM，理解 RWO / RWX / ROX、文件系统 vs 块设备、拓扑与快照。
6. 读懂 CNI 参考插件（bridge / host-local IPAM）与 CSI 侧车（external-provisioner / external-attacher / external-resizer / external-snapshotter / node-driver-registrar）的核心源码入口。
7. 在生产中排查典型故障：IP 池耗尽、CNI 配置冲突、MTU / conntrack 问题、NetworkPolicy 误拦截、VolumeAttachment 残留、attach limit、resize 未触发 NodeExpand。
8. 回答初 / 中 / 高级 CNI / CSI 面试题，能把接口语义、生命周期与生产排障讲清楚。

## CNI / CSI 与其他主题的关系

| 主题 | 解决的核心问题 | 与 CNI / CSI 的关系 |
|---|---|---|
| [Foundation](/01-foundation/) | Linux / 网络 / 存储 / GPU 硬件基础 | CNI 调用 Linux netns / veth / bridge / route / iptables / eBPF；CSI 调用块 / 文件 / 对象存储语义 |
| [Linux 系统与性能调优](/01-foundation/linux-systems/) | 进程调度、内存管理、I/O、网络、cgroup/namespace | netns / veth / bridge 是 CNI 的底层机制；I/O 栈与文件系统决定 CSI 性能 |
| [计算机网络](/01-foundation/computer-networks/) | 网络协议、拓扑、RDMA/RoCE/IB、CNI/LB/DNS | CNI 是计算机网络在容器场景的实现层；VXLAN / BGP / eBPF / RDMA 都在本主题落地 |
| [存储系统](/01-foundation/storage-systems/) | 块/文件/对象语义、一致性、并行文件系统 | CSI 是存储系统接入 K8s 的标准接口；PV/PVC/StorageClass 是语义抽象 |
| [Kubernetes](/02-cloud-native/kubernetes/) | 声明式编排、调度 | K8s 通过 CNI / CSI 接口把网络 / 存储外包给插件；本主题是 K8s 架构的两大扩展点 |
| [容器运行时](/02-cloud-native/container-runtime/) | 镜像管理 + 容器生命周期 | CRI 创建 netns 后触发 CNI；容器 rootfs 准备好后触发 CSI NodePublish |
| **CNI / CSI 深度** | 网络与存储插件接口、生命周期、生产实践 | 本主题 |
| [Ray](/03-ai-platform/ray/) | 分布式 Python 计算 | Ray on K8s 依赖 CNI 做 worker 间通信，依赖 CSI 做数据集 / checkpoint 持久化 |
| [vLLM](/04-llmops/vllm/) / [Triton](/04-llmops/triton/) | 推理引擎 | 推理 Pod 的 Service 负载均衡依赖 CNI；模型权重加载依赖 CSI 或本地缓存 |
| [AI SRE](/07-ai-sre/) | 可观测、SLO | CNI / CSI 的延迟 / 吞吐 / 错误指标是 AI 平台可观测性的重要组成 |
| [安全](/08-security/) | IAM、Secrets、Zero Trust | NetworkPolicy 由 CNI 实现；Secret 卷由 CSI 或 kubelet 挂载 |

## 本章结构

1. [背景](01-background) — 从 K8s in-tree 插件的痛楚到 CNI / CSI 的诞生，AI 视角看网络与存储需求。
2. [核心思想](02-core-ideas) — CNI 与 CSI 的接口哲学、生命周期、幂等性、与 K8s 其他组件的边界。
3. [架构设计](03-architecture) — CNI 部署模型与插件链；CSI Controller / Node 分离；K8s 触发路径；多网卡与 RDMA 拓扑。
4. [Runtime 工作流程](04-runtime-workflow) — 一个 Pod 从调度到 Running 的 CNI ADD 全链路；一个 PVC 从声明到挂载的 CSI 全链路；排障入口。
5. [核心模块](05-core-modules) — CNI 参考插件与主流实现对比；NetworkPolicy 数据面；CSI sidecars 与存储语义；AI 场景存储选型。
6. [源码分析](06-source-analysis) — CNI bridge / host-local IPAM；CSI spec protobuf；external-provisioner 调用链；AWS EBS / hostpath Node 操作。
7. [工程实践](07-mini-demo) — 纯 Python 可运行的 CNI / CSI 概念模拟器（后续补充）。
8. [企业生产实践](08-production-practice) — AI 集群 CNI / CSI 选型、典型故障、性能调优、多租户隔离。
9. [最佳实践](09-best-practices) — CNI / CSI 检查清单、AI 负载特化、YAML 模板。
10. [面试题](10-interview-questions) — 初 / 中 / 高级面试题。
11. [延伸阅读](11-further-reading) — 官方文档、规范、源码、论文与学习路径。

## 一句话总结

CNI 与 CSI 的精髓在于**"标准接口 + 插件生态 + 声明式生命周期"**：Kubernetes 只负责"在正确的时间调用正确的二进制 / gRPC"，把网络拓扑、IPAM、路由、存储协议、快照、扩容这些高度异构的实现细节交给社区与云厂商；对 AI 平台而言，选对 CNI 就是选对通信效率（eBPF / RDMA / 多网卡），选对 CSI 就是选对数据吞吐与可靠性（本地 SSD / 并行文件系统 / 对象存储）——二者都不是"配置一下就行"，而是需要理解接口语义才能在生产里排障和调优。

# 11. 延伸阅读与学习路径

> 一句话理解：**CNI / CSI 是接口标准，真正的深度来自读规范、读参考实现、读 sidecar 源码、读生产案例**——本章把官方文档、规范、源码仓库、经典演讲整理成一张循序渐进的地图。

## 11.1 官方文档（按优先级）

### CNI

| 优先级 | 文档 | 读什么 |
|---|---|---|
| **P0** | [CNI Specification](https://www.cni.dev/docs/spec/) | ADD/DEL/CHECK/GC/STATUS 语义、result JSON、plugin chaining |
| **P0** | [CNI Configuration](https://www.cni.dev/docs/conventions/) | 配置文件格式、conflist、capabilities |
| **P1** | [containernetworking/plugins 文档](https://www.cni.dev/plugins/current/) | bridge、host-local、bandwidth、firewall 等参考插件用法 |
| **P2** | [Multus 文档](https://github.com/k8snetworkplumbingwg/multus-cni) | 多网卡、NetworkAttachmentDefinition |
| **P2** | [SR-IOV CNI 文档](https://github.com/k8snetworkplumbingwg/sriov-cni) | VF 直通、RDMA 网络配置 |

### CSI

| 优先级 | 文档 | 读什么 |
|---|---|---|
| **P0** | [Kubernetes CSI Docs](https://kubernetes-csi.github.io/docs/) | 整体架构、sidecar 说明、部署指南 |
| **P0** | [CSI Specification](https://github.com/container-storage-interface/spec/blob/master/spec.md) | Identity/Controller/Node 接口、幂等性、错误码 |
| **P1** | [CSI Driver Development Guide](https://kubernetes-csi.github.io/docs/developing.html) | 从零写驱动、sidecar 集成 |
| **P1** | [Volume Snapshots](https://kubernetes.io/docs/concepts/storage/volume-snapshots/) / [Volume Expansion](https://kubernetes.io/docs/concepts/storage/persistent-volumes/#expanding-persistent-volumes-claims) | 快照与扩容语义 |
| **P2** | [Kubernetes Storage SIG 文档](https://github.com/kubernetes/community/tree/master/sig-storage) | KEP、会议记录、路线图 |

## 11.2 规范与源码仓库

### CNI 参考实现

| 仓库 | 读什么 |
|---|---|
| [containernetworking/cni](https://github.com/containernetworking/cni) | libcni、spec、cnitool |
| [containernetworking/plugins](https://github.com/containernetworking/plugins) | bridge、host-local、bandwidth、firewall、portmap 源码 |
| [cilium/cilium](https://github.com/cilium/cilium) | eBPF 数据面、NetworkPolicy、Hubble 可观测 |
| [projectcalico/calico](https://github.com/projectcalico/calico) | BGP、Felix、BIRD、Calico IPAM |
| [flannel-io/flannel](https://github.com/flannel-io/flannel) | VXLAN / host-gw 简单实现 |
| [k8snetworkplumbingwg/multus-cni](https://github.com/k8snetworkplumbingwg/multus-cni) | meta-CNI、多网卡调度 |
| [k8snetworkplumbingwg/sriov-cni](https://github.com/k8snetworkplumbingwg/sriov-cni) | SR-IOV VF 直通 |

### CSI 驱动与 sidecars

| 仓库 | 读什么 |
|---|---|
| [container-storage-interface/spec](https://github.com/container-storage-interface/spec) | protobuf / spec 原文 |
| [kubernetes-csi/external-provisioner](https://github.com/kubernetes-csi/external-provisioner) | PVC → CreateVolume 适配 |
| [kubernetes-csi/external-attacher](https://github.com/kubernetes-csi/external-attacher) | VolumeAttachment 处理 |
| [kubernetes-csi/external-resizer](https://github.com/kubernetes-csi/external-resizer) | 扩容流程 |
| [kubernetes-csi/external-snapshotter](https://github.com/kubernetes-csi/external-snapshotter) | 快照 CRD 与 sidecar |
| [kubernetes-csi/csi-driver-host-path](https://github.com/kubernetes-csi/csi-driver-host-path) | 最小完整 CSI 驱动 |
| [kubernetes-sigs/aws-ebs-csi-driver](https://github.com/kubernetes-sigs/aws-ebs-csi-driver) | 云厂商块存储驱动参考 |
| [ceph/ceph-csi](https://github.com/ceph/ceph-csi) | Ceph RBD/RGW/FS 统一驱动 |
| [kubernetes-sigs/vsphere-csi-driver](https://github.com/kubernetes-sigs/vsphere-csi-driver) | 企业存储 CSI 参考 |

## 11.3 经典演讲与论文

| 资源 | 为什么读 |
|---|---|
| [CNI: the Container Network Interface（CoreOS, 2015）](https://github.com/containernetworking/cni) | 理解 CNI 诞生的动机与最小设计 |
| [Kubernetes Storage: From in-tree to CSI（KubeCon 演讲）](https://www.youtube.com/c/kubecon) | 理解 CSI 迁移历程 |
| [Cilium: eBPF-based Networking, Observability, Security](https://cilium.io/) | 理解 eBPF 如何替代 iptables 做网络数据面 |
| [Calico eBPF Data Plane Deep Dive](https://docs.tigera.io/calico/latest/about/) | 理解 BGP 与 eBPF 两种模式 |
| [NVIDIA GPUDirect RDMA 文档](https://docs.nvidia.com/cuda/gpudirect-rdma/) | RDMA 与 GPU Direct 硬件基础 |
| [NCCL 调优文档](https://docs.nvidia.com/deeplearning/nccl/) | 训练通信参数与网络配置对应关系 |

## 11.4 生产实践与案例

| 资源 | 读什么 |
|---|---|
| [AWS EBS CSI Driver 最佳实践](https://docs.aws.amazon.com/eks/latest/userguide/ebs-csi.html) | IAM、topology、加密、扩容 |
| [GCP PD CSI Driver 文档](https://cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/gce-pd-csi-driver) | 区域磁盘、topology |
| [Ceph CSI 架构文档](https://ceph.io/en/news/) | RBD / CephFS / RGW 在 K8s 的落地 |
| [Lustre / WEKA 在 AI 集群的部署白皮书](https://www.weka.io/resources/) | 并行文件系统与 GPU 训练 |
| [Kubernetes NetworkPolicy Recipes](https://github.com/ahmetb/kubernetes-network-policy-recipes) | 常见 NetworkPolicy 模式 |

## 11.5 与本手册其他主题的交叉引用

| 主题 | 与本主题的衔接 | 阅读建议 |
|---|---|---|
| [Kubernetes](/02-cloud-native/kubernetes/) | CNI / CSI 是 K8s 的两大扩展接口 | 先理解 K8s 控制循环与 kubelet，再读本主题 |
| [容器运行时](/02-cloud-native/container-runtime/) | CRI 创建 netns 后触发 CNI，容器启动前触发 CSI NodePublish | 读容器运行时有助于理解 `ContainerCreating` 全链路 |
| [计算机网络](/01-foundation/computer-networks/) | VXLAN / BGP / RDMA / eBPF 原理 | 本主题讲"怎么用"，计算机网络讲"为什么" |
| [存储系统](/01-foundation/storage-systems/) | 块 / 文件 / 对象语义、并行文件系统 | 本主题讲"怎么挂到 K8s"，存储系统讲"后端特性" |
| [Linux 系统与性能调优](/01-foundation/linux-systems/) | netns / veth / bridge / route / cgroup | 读 Linux 系统理解 CNI 脚下原语 |
| [GPU 架构与 CUDA 基础](/01-foundation/gpu-cuda/) | GPU Direct RDMA、NCCL | RDMA CNI 方案需要 GPU 与网络协同 |
| [Ray](/03-ai-platform/ray/) | Ray on K8s 依赖 CNI / CSI | 训练任务网络与数据持久化是本主题的直接应用 |
| [AI SRE](/07-ai-sre/) | CNI / CSI 可观测性 | Hubble、CSI 驱动 metrics、kubelet volume manager 指标 |
| [安全](/08-security/) | NetworkPolicy、加密存储 | 本主题的 NetworkPolicy / StorageClass encryption 是执行点 |

## 11.6 推荐学习路径

### 路径 A：网络优先

```text
1. 读 CNI Specification（P0）
2. 动手跑 containernetworking/plugins 的 bridge + host-local
3. 用 kind 部署 Flannel / Calico / Cilium，对比 VXLAN / BGP / eBPF
4. 配置 NetworkPolicy default-deny + allow DNS
5. 读 Cilium eBPF 数据面源码（可选）
6. 用 Multus + SR-IOV CNI 搭建 RDMA 训练网络（生产前实验）
```

### 路径 B：存储优先

```text
1. 读 CSI Specification（P0）
2. 部署 csi-driver-host-path，观察 PVC → PV → mount 全流程
3. 读 external-provisioner 调用链源码
4. 部署 AWS EBS CSI 或 ceph-csi，测试快照与扩容
5. 对比 local PV / EBS / CephFS / Lustre 在训练场景的表现
6. 设计 StorageClass + VolumeSnapshot 策略
```

### 路径 C：AI 平台全栈

```text
1. 先读完 [Kubernetes 主题](/02-cloud-native/kubernetes/) 与 [容器运行时主题](/02-cloud-native/container-runtime/)
2. 读本主题 1-4 章建立 CNI / CSI 全链路认知
3. 跑通本主题 Mini Demo（cni_csi_mini）
4. 在真实集群或云上部署一套训练 Job（Cilium + Multus + SR-IOV + Lustre CSI）
5. 模拟 Pod ContainerCreating 故障并排障
6. 回看源码（bridge、host-local、external-provisioner）加深理解
```

## 11.7 本章小结

| 类型 | 重点资源 |
|---|---|
| 官方文档 | CNI Spec、Kubernetes CSI Docs、K8s Storage 概念 |
| 源码 | containernetworking/plugins、Cilium/Calico、kubernetes-csi sidecars、AWS EBS CSI |
| 演讲论文 | CNI 起源、CSI 迁移、eBPF 数据面、NCCL/GPUDirect |
| 生产实践 | 云厂商 CSI 最佳实践、并行文件系统、NetworkPolicy Recipes |
| 交叉主题 | Kubernetes、容器运行时、计算机网络、存储系统、GPU/CUDA、AI SRE、安全 |

CNI / CSI 主题到此结束。建议结合本主题 Mini Demo 与真实集群实验，把接口语义、生命周期和排障思路内化为肌肉记忆。

# 1. 背景

> 一句话理解：**CNI 与 CSI 是 Kubernetes 为了摆脱"一个集群一种网络 / 存储实现"的 Vendor Lock-in，把网络连接和卷挂载这两件事标准化成插件接口的结果**——从此任何网络方案只要实现 CNI 规范，任何存储方案只要实现 CSI 规范，就能接入 K8s；这也为 AI 平台的高性能 RDMA 网络与异构存储后端打开了生态大门。

## 1.1 从 K8s in-tree 到 out-of-tree 插件

早期的 Kubernetes 像一块"瑞士军刀"：网络、存储、云厂商逻辑都被硬编码在核心仓库里。

```text
早期 K8s 核心
├── pkg/kubelet/network/        <-- 网络实现（dockershim/libnetwork）
├── pkg/volume/                 <-- 存储实现（aws/gce/ceph/nfs/...）
└── pkg/cloudprovider/          <-- 云厂商逻辑
```

这种 in-tree 模式带来三大痛楚：

1. **发布耦合**：每新增一种网络 / 存储 / 云厂商支持，都要改 K8s 核心代码，跟着 K8s 版本一起发版。
2. **测试与稳定性**：核心仓库要兼容几十种驱动，回归测试爆炸；云厂商 credentials 也不能随便放进开源仓库。
3. **创新速度慢**：存储厂商想支持一个新特性（如快照、扩容），必须等 K8s 发版窗口，无法独立迭代。

Docker 时代还有另一个痛点：Docker 自带的 libnetwork 与 K8s 的网络模型并不完全匹配。K8s 要求每个 Pod 有独立 IP、所有 Pod 之间无需 NAT 直接可达、容器看到的自己的 IP 与别的容器看到的一样；而 Docker 默认的 bridge / port-mapping 模型更偏向"单机容器 + NAT"。这迫使社区重新思考：能不能让 K8s 只定义"容器该怎么连网"，把实现交出去？

## 1.2 CNI 的诞生

2015 年，CoreOS 在 DockerCon 上提出 **CNI（Container Network Interface）** 规范，目标是：

- 为 Linux 容器提供**简单、可插拔**的网络配置接口。
- 让 K8s、Mesos、Cloud Foundry 等编排器都能复用同一套网络插件。
- 用 JSON 配置 + 可执行二进制的方式，把网络创建与销毁标准化。

CNI 的核心设计非常轻量：

```text
CNI = 配置文件（/etc/cni/net.d/*.conf）+ 可执行插件（/opt/cni/bin/*）
```

当容器运行时创建好 network namespace 后，调用 CNI 插件并传入 `ADD` / `DEL` / `CHECK` / `GC` / `STATUS` 等命令。插件负责在 netns 里创建 veth、bridge、IP 地址、路由等。

CNI 很快成为容器编排网络的事实标准。Flannel、Calico、Weave、Cilium、Multus 都实现了 CNI。

## 1.3 CSI 的诞生

与网络类似，K8s 早期把所有 volume 驱动放在 `pkg/volume` 里。这被称为 in-tree volume plugins：

```text
kubernetes/pkg/volume/
├── aws_ebs/
├── gce_pd/
├── cinder/
├── cephfs/
├── nfs/
├── rbd/
├── csi/            <-- 后来加的 CSI shim
└── ...
```

KEP（Kubernetes Enhancement Proposal）推动了一次彻底的解耦：

- **KEP-0378：CSI Volume Plugin GA for 1.13** — 把 CSI 作为官方推荐的外置存储接口。
- **KEP-625：In-tree Storage Plugin to CSI Driver Migration** — 逐步把 in-tree 驱动迁移到 CSI，最终 deprecate / 移除 in-tree 代码。
- **KEP-2923：Skip Volume Ownership Change**、**KEP-284：Volume Snapshot**、**KEP-2847：ReadWriteOncePod** 等 — 不断丰富 CSI 语义。

CSI 用 **gRPC + protobuf** 定义了三组接口：

```text
CSI
├── Identity          <-- 驱动身份与能力（GetPluginInfo / GetPluginCapabilities / Probe）
├── Controller        <-- 创建/删除/发布/快照/扩容（CreateVolume / DeleteVolume / ControllerPublish / ...）
└── Node              <-- 节点挂载/卸载（NodeStageVolume / NodePublishVolume / NodeExpandVolume / ...）
```

与 CNI 的"二进制 + JSON"不同，CSI 是"常驻 gRPC 服务 + sidecar 代理"：驱动以 Pod / DaemonSet 形式部署，通过 Unix domain socket 与 K8s sidecars 通信。

## 1.4 AI Infra 视角：为什么 CNI / CSI 格外重要

AI 平台不是普通的微服务负载，它对网络和存储的要求极高。

### 网络侧：分布式训练的通信效率

| AI 场景 | 网络需求 | CNI 相关技术 |
|---|---|---|
| 大模型分布式训练（DDP / FSDP / Megatron / DeepSpeed） | 高带宽、低延迟、无损网络 | RDMA over Converged Ethernet（RoCEv2）、InfiniBand、SR-IOV CNI、Macvlan |
| 多机集合通信（NCCL） | Pod IP 直接可达、不经过 NAT、稳定的 L2/L3 路径 | Calico BGP、Cilium eBPF 原生路由、Flannel host-gw |
| GPU Direct RDMA | 网卡与 GPU 直接 DMA，绕过 CPU 内存 | SR-IOV + Multus 多网卡、专用 RDMA CNI |
| 推理服务 | 低延迟入口、东西向安全隔离 | Cilium eBPF、NetworkPolicy、Ingress / Gateway API |

一个常见故障：训练 Job 在 16 机规模下正常，扩到 128 机就 hang。根因往往不是 PyTorch 代码，而是 CNI 的 VXLAN 封装导致 MTU 不足、conntrack 表满、或者 RDMA 网卡没有以 SR-IOV VF 形式透传到 Pod。

### 存储侧：数据吞吐与 checkpoint 可靠性

| AI 场景 | 存储需求 | CSI 相关技术 |
|---|---|---|
| 大模型 checkpoint（数十 GB~TB 级） | 高顺序写吞吐、低延迟 | 本地 NVMe / TopoLVM、Lustre / WEKA 并行文件系统 |
| 训练数据集共享 | 高并发读、POSIX 语义或对象语义 | CephFS / Lustre / NFS / S3 CSI |
| 模型权重加载 | 大文件只读、快速分发 | S3 CSI、只读 PVC、镜像预拉取 |
| 推理服务有状态化 | 低延迟持久化 | EBS / GCE PD / Ceph RBD 等块存储 |

checkpoint 场景最能体现 CSI 选型的差异：本地 SSD 吞吐最高但节点绑定、无法迁移；并行文件系统可共享但成本高；对象存储便宜但 latency 高、POSIX 语义弱。没有"银弹"，必须理解 CSI 提供的语义才能做 trade-off。

### 生命周期耦合

AI 负载的另一个特点是 Job 生命周期长、Pod 数量多、对失败敏感：

- 训练 Pod 创建时，CNI 必须一次性为每个 Pod 分配 IP 并配置好 RDMA 网卡；
- 训练过程中，CSI 必须保证 checkpoint 写一致、快照可恢复；
- 训练结束后，CNI 要及时回收 IP 和网卡，CSI 要清理 VolumeAttachment，否则节点上残留资源会影响下一轮调度。

理解 CNI / CSI 的幂等性、清理顺序和错误处理，是避免"训练跑一半资源泄漏"的关键。

## 1.5 本章小结

| 阶段 | 问题 | 解决方案 |
|---|---|---|
| Docker 早期 | 单机容器网络 NAT 模型不满足 K8s Pod 模型 | CNI（2015）标准化容器网络接口 |
| K8s 早期 | in-tree volume 插件耦合核心、迭代慢 | CSI（1.9 alpha → 1.13 GA）标准化外置存储接口 |
| AI 平台 | 高性能 RDMA、异构存储、checkpoint | 在 CNI / CSI 接口上选择 / 自研适合 AI 的插件 |

CNI 与 CSI 的诞生，本质上是 **K8s 把"怎么做"（how）从"做什么"（what）中分离**：K8s 负责定义容器需要什么样的网络和存储生命周期，插件厂商负责用最优实现满足这些生命周期。下一章我们将深入这两个接口的核心语义。

## 参考来源

- [CNI Specification v1.0.0](https://www.cni.dev/docs/spec/)
- [Kubernetes CSI Documentation](https://kubernetes-csi.github.io/docs/)
- [KEP-0378: CSI Volume Plugin GA for 1.13](https://github.com/kubernetes/enhancements/blob/master/keps/sig-storage/0378-csi-volume-plugin-ga-for-1-13/)
- [KEP-625: In-tree Storage Plugin to CSI Driver Migration](https://github.com/kubernetes/enhancements/blob/master/keps/sig-storage/625-csi-migration/)
- [CNI: the Container Network Interface (CoreOS, 2015)](https://github.com/containernetworking/cni)

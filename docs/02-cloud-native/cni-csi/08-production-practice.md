# 8. 企业生产实践

> 一句话理解：**生产级 AI 集群的 CNI / CSI 选型，不是看哪个社区最火，而是看负载特征：训练要 RDMA 和低延迟，推理要隔离和弹性，存储要按 checkpoint / 数据集 / 模型权重三种数据形态分层**。

## 8.1 AI 集群 CNI 选型

### 选型矩阵

| 维度 | 训练集群 | 推理集群 | 通用平台 |
|---|---|---|---|
| 首要诉求 | 高带宽、低延迟、RDMA | 安全隔离、低延迟入口 | 稳定、易运维 |
| 推荐 CNI | Cilium + Multus + SR-IOV CNI | Cilium / Calico eBPF | Cilium（云默认）/ Calico |
| 数据面 | eBPF / SR-IOV VF | eBPF | eBPF / BGP |
| NetworkPolicy | 必须，隔离训练租户 | 必须，按模型 / 团队隔离 | 按 namespace 隔离 |
| MTU | 注意 RDMA / RoCEv2 要求 | 常规 | 常规 |

### 一个现实变化：推理集群的南北向入口

2025-2026 年最大的入口层变化是 **ingress-nginx 于 2026-03 停止维护**、Ingress API 冻结。新的默认组合是：

- CNI 用 Cilium 时，直接开 `gatewayAPI.enabled=true`，由 eBPF 数据面承接 HTTPRoute / GRPCRoute，不再单独部署 Ingress Controller。
- 需要独立网关数据面时用 Envoy Gateway；社区提供 ingress2gateway 迁移工具。

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: inference-gateway
spec:
  gatewayClassName: cilium        # 或 envoy-gateway / nginx-gateway-fabric
  listeners:
    - name: https
      protocol: HTTPS
      port: 443
      allowedRoutes:
        namespaces:
          from: Selector
          selector: { team: inference }
```

角色分离（GatewayClass 由平台组管、Gateway 由集群运维管、HTTPRoute 由业务组管）比 Ingress annotation 大杂烩更适合多租户推理平台。

### 为什么训练推荐 Cilium + Multus + SR-IOV

1. **默认网络走 Cilium**：管理面通信、Service 发现、DNS、监控走 eBPF 高性能路径。
2. **RDMA 走 SR-IOV CNI**：把 Mellanox VF 直接放进训练 Pod，NCCL 可以做 GPU Direct RDMA。
3. **存储网络可分离**：如果后端是 Lustre / WEKA，可以用第二个 macvlan/ipvlan CNI 让存储流量独立网卡。

```text
训练 Pod
 ├── eth0 ── Cilium（管理 / Service / 监控）
 ├── net1 ── SR-IOV VF（NCCL RDMA 训练网络）
 └── net2 ── macvlan（Lustre / WEKA 存储网络）   [可选]
```

手动编排这套组合（SR-IOV NetworkNodePolicy、VF 池、RDMA device plugin、Multus NAD）非常繁琐，**NVIDIA Network Operator 已成为事实标准**：一个 Operator 串起 sriov-network-operator（PF/VF 划分与配置）、Multus、whereabouts IPAM、RDMA shared device plugin、DOCA 固件管理，声明式地给训练节点交付 RDMA 网络。RoCE 方案落地时的经验值：裸金属 K8s 上 RoCEv2 可达到 InfiniBand 约 95% 的性能、成本约 30%（BaaZ 裸金属案例，ConnectX-6 Dx + PFC/ECN 无损网络），但代价是要自己调 PFC/ECN，IB 则是开箱即用。别忘了训练镜像里把 NCCL 指到 RDMA 网卡：`NCCL_SOCKET_IFNAME=eth0 NCCL_IB_HCA=mlx5`。

### Calico BGP 大规模场景

当集群节点数达到数千台，VXLAN 的 BUM 流量和封装开销会成为瓶颈。Calico BGP 模式：

- 每个节点作为 BGP peer 与 ToR 交换机或 route reflector 交换 Pod CIDR 路由。
- Pod 包直接以 IP 包形式走底层网络，无需封装。
- 配合 ECMP 可实现多路径负载均衡。

局限：需要底层网络支持 BGP 路由播发，IP 地址规划复杂。

## 8.2 AI 集群 CSI 选型

### 按数据形态分层

```text
AI 平台数据分层
├── 模型权重（大文件、只读、低频次变更）
│      └── S3 CSI ROX / 镜像层 / 本地缓存
├── 数据集（大文件、多读少写、可能共享）
│      └── Lustre / CephFS / NFS / S3 CSI
├── checkpoint（大文件、高频顺序写、节点亲和）
│      └── local NVMe / TopoLVM / Lustre / WEKA
└── 推理状态（小量、低延迟、持久化）
       └── EBS / Ceph RBD / GCE PD
```

### 典型组合

| 场景 | 存储后端 | CSI 驱动 | 卷语义 |
|---|---|---|---|
| 单节点大模型微调 | 本地 NVMe | local-static-provisioner / TopoLVM | RWO Filesystem |
| 多机分布式训练 checkpoint | Lustre / WEKA | lustre-csi / weka-csi | RWX Filesystem |
| 训练数据集 | CephFS / Lustre | ceph-csi / lustre-csi | RWX / ROX Filesystem |
| 模型仓库 | S3 / GCS / MinIO | s3-csi / gcsfuse-csi | ROX Filesystem |
| 推理数据库 / 缓存 | EBS / Ceph RBD | ebs-csi / ceph-csi | RWO Filesystem/Block |

### local PV 的陷阱

本地 SSD 吞吐最高，但有明显限制：

- **节点绑定**：Pod 被驱逐后只能调度到原节点，否则卷不可用。
- **数据可靠性**：节点磁盘故障会丢数据；重要 checkpoint 需要异步复制到对象存储或并行文件系统。
- **调度约束**：需要使用 `nodeAffinity` 或 TopoLVM 的拓扑感知。

### checkpoint 写入：2025 年后的推荐模式

单纯"local PV 直写"或"并行文件系统直写"都不是最优解，当前主流是**分层 + 异步上传**：

```text
GPU 训练进程
   │ ① 秒级写入
   ▼
本地 NVMe（emptyDir / local PV）        ← 保证 GPU 永不等待
   │ ② 后台异步上传（不与训练争吞吐）
   ▼
S3 兼容对象存储 / Lustre / WEKA          ← 保证可靠性与可迁移性
```

配套机制：

- **Just-In-Time checkpoint**：Kubeflow Trainer v2 监听 SIGTERM（Spot 抢占 / 缩容 / 节点维护），在 Pod 被杀前抢写最后一个 checkpoint——弹性训练几乎必备。
- **按峰值规划容量**：DeepSpeed ZeRO-3 合并 checkpoint 可能产生最终体积 42.5 倍的临时写入峰值（研究实测 1.6GB → 68GB），给存储留足余量，否则 checkpoint 窗口会拖垮迭代时间（业界目标是 checkpoint 与计算重叠 <10%）。
- **多卷一致性保护**：一个训练 Job 挂多个 checkpoint 卷时，用 Volume Group Snapshot（v1.36 GA）做崩溃一致快照，而不是逐卷拍（恢复出来可能跨卷不一致）。

## 8.3 典型故障与排查

### CNI 典型故障

| 现象 | 根因 | 排查命令 |
|---|---|---|
| Pod 卡在 `ContainerCreating`，事件报 `FailedCreatePodSandBox` | CNI 插件缺失或配置错误 | `ls /opt/cni/bin` / `cat /etc/cni/net.d/*.conflist` |
| IP 分配失败 | IP 池耗尽或 host-local 记录损坏 | `ls /var/lib/cni/networks/<network>` |
| 跨节点 Pod 不通 | VXLAN 端口被防火墙阻断或 BGP peer 没建立 | `ip route` / `calicoctl node status` |
| NCCL 训练 hang | MTU 不匹配、RoCE PFC 没配、VF 没透传 | `ip addr show eth1` / `ib_write_bw` |
| Service 偶发超时 | conntrack 表满 | `conntrack -L \| wc -l` / `sysctl net.netfilter.nf_conntrack_max` |
| DNS 解析失败 | NetworkPolicy 默认 deny 没放通 CoreDNS | `kubectl get networkpolicy --all-namespaces` |

### CSI 典型故障

| 现象 | 根因 | 排查命令 |
|---|---|---|
| Pod 卡在 `ContainerCreating`，事件报 `Unable to attach or mount volumes` | VolumeAttachment 残留或 attach limit | `kubectl get volumeattachment` |
| `Multi-Attach error` | RWO 卷仍被其他节点占用 | `kubectl describe pv` |
| PVC 扩容成功但文件系统没变大 | NodeExpandVolume 未触发 | `kubectl get pvc` / `df -h` inside Pod |
| 卷创建在错误 AZ | topology 没配 `WaitForFirstConsumer` | `kubectl get sc -o yaml` |
| CSI driver pod OOM | 大卷格式化或快照操作耗内存 | `kubectl top pod -n kube-system` |
| 节点 NotReady 后卷无法迁移 | VolumeAttachment 没自动清理 | 手动删除 VA 并确认后端已 detach |

### 一个真实排障案例：VolumeAttachment 残留

**现象**：节点 `worker-3` 因硬件故障被删除，该节点上的 EBS 卷无法在新节点挂载。

**排查**：

```bash
kubectl get volumeattachment | grep worker-3
# 发现 VA 仍存在，status.attached=true

kubectl describe volumeattachment csi-xxx
# 显示 nodeName: worker-3
```

**根因**：节点异常下线，external-attacher 没收到 Node 删除事件，VolumeAttachment 未清理。

**修复**：

1. 在云控制台确认 EBS 卷已从 `worker-3` detach。
2. 删除 VolumeAttachment：
   ```bash
   kubectl delete volumeattachment csi-xxx
   ```
3. 新 Pod 重新调度后，external-attacher 会创建新的 VA 并 attach。

**预防**：

- 配置 `kubectl drain` + `--ignore-daemonsets` 正常下线节点。
- 使用 CSI driver 的 `attachRequired: true` 并确保 attacher 正常。
- 对长期运行的训练 Job，设置合理的 PodDisruptionBudget 与节点维护窗口。

## 8.4 性能调优

### CNI 调优

| 方向 | 手段 | 效果 |
|---|---|---|
| MTU | Pod 网卡 MTU = 节点物理 MTU - VXLAN overhead（通常 50） | 避免分片，提高吞吐 |
| VXLAN offload | 开启网卡 GSO/GRO/TSO | 降低 CPU 消耗 |
| eBPF | 用 Cilium 替代 iptables | 降低延迟，提高策略规模 |
| RDMA | SR-IOV VF + RoCEv2/IB + PFC/ECN | 训练通信低延迟高带宽 |
| conntrack | 调大 `nf_conntrack_max`，缩短 timeout | 避免连接表满 |
| DNS | NodeLocal DNSCache | 降低 CoreDNS 负载与延迟 |

### CSI 调优

| 方向 | 手段 | 效果 |
|---|---|---|
| attach 并行度 | 调整 external-attacher 的 worker 数 | 加速大规模 Pod 启动 |
| 快照一致性 | 训练前刷盘 / 使用 quiesce | 保证 checkpoint 可恢复 |
| 本地缓存 | 在节点用 local cache 预热模型权重 | 加速推理冷启动 |
| 块设备 fs | 根据场景选 ext4 / xfs；xfs 对大文件更友好 | 提高大模型文件性能 |
| IOPS/吞吐 | EBS gp3/io2 配置 iops/throughput | 匹配训练写入需求 |
| topology | `WaitForFirstConsumer` + 节点亲和 | 避免跨 AZ attach |

## 8.5 多租户与隔离

### 网络隔离

```text
namespace: team-a
  └── NetworkPolicy: default-deny ingress + 允许同 team 标签 Pod

namespace: team-b
  └── NetworkPolicy: default-deny ingress + 允许同 team 标签 Pod

ingress-nginx / Gateway API
  └── 按 host / path 把外部流量路由到不同 namespace 的 Service
```

### 存储隔离

- 每个团队独立 StorageClass，限制后端 pool / QoS。
- 用 ResourceQuota 限制 PVC 总数与容量。
- 敏感数据用 CSI secret + KMS 加密（如 AWS EBS encryption）。

### RDMA 网络隔离

- 用 PFC/ECN / QoS 在物理网络层隔离训练流量。
- 用 Multus 让不同租户的 RDMA 网络使用不同 VLAN / VF 池。
- NCCL 配置 `NCCL_IB_GID_INDEX`、`NCCL_IB_TC` 匹配网络策略。

## 8.6 硬件卸载：DPU / IPU 前沿实践

AI 集群里"基础设施税"越来越不可忽视：VXLAN 封装、conntrack、NetworkPolicy 执行、存储协议栈都在吃训练节点的 CPU。2025-2026 年，DPU/IPU 卸载从实验室走向生产：

| 方案 | 进展 | 对 K8s 的接入方式 |
|---|---|---|
| **NVIDIA BlueField-4** | 2025-10 发布，800Gb/s + 64 核 Arm，2026 年起随 Vera Rubin NVL72 机柜出货 | DOCA / OPI Operator；OVN-Kubernetes 卸载模式 |
| **Microsoft Azure Boost DPU** | 2024-11 发布、2025 年上线，官方口径 4 倍性能 / 3 倍能效 | 云托管，对用户透明 |
| **Intel E2100 IPU** | OPI 生态主推，已示范路由 / 解密 / 访问控制卸载 | OpenShift + OPI Operator |
| **AMD Pensando（Salina/Pollara）** | 400G 线，Cisco Smart Switch 同源 | OPI / 厂商 Operator |

最成熟的 K8s 模式是 **OVN-Kubernetes DPU offload**：主机只跑 OVN 控制面（CNI 逻辑、策略下发），DPU 上跑 OVS 数据面 fast path，主机 CPU 不碰数据包。存储侧的标志性事件是 WEKA NeuralMesh（GTC DC 2025）：存储软件栈直接部署在 BlueField-4 上，不再需要独立的存储 CPU 服务器——"每个计算节点自带存储服务"的超融合形态，对 GPU 集群的 TCO 是结构性改变。选型建议：万卡以下先不用纠结 DPU；但当单节点 CPU 有 20%+ 被网络/存储基础设施消耗、且网卡升级到 400G/800G 时，DPU 卸载应进入评估清单。

## 8.7 本章小结

| 主题 | 生产要点 |
|---|---|
| CNI 选型 | 训练：Cilium + Multus + SR-IOV（用 NVIDIA Network Operator 编排）；推理：Cilium + Gateway API（ingress-nginx 已退休） |
| CSI 选型 | checkpoint 本地优先 + 异步上传；多卷用 Volume Group Snapshot；数据集用 RWX；模型用 ROX |
| 典型故障 | CNI：IP 池 / MTU / conntrack / NetworkPolicy；CSI：VA 残留 / attach limit / resize |
| 性能调优 | MTU、eBPF、RDMA、attach 并行度、topology、快照一致性 |
| 多租户 | NetworkPolicy default-deny、独立 StorageClass、RDMA QoS |
| 硬件卸载 | DPU（BlueField-4 等）卸载网络/存储基础设施开销，规模化集群的 TCO 杠杆 |

下一章我们把生产经验固化成可落地的最佳实践与 YAML 模板。

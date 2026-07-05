# 2. 核心思想

> 一句话理解：**CNI 与 CSI 的核心思想都是"接口契约 + 生命周期回调 + 幂等执行"**——容器运行时按约定调用 CNI 二进制完成网络连接，K8s 存储控制器按约定调用 CSI gRPC 完成卷生命周期；插件实现者只需满足接口语义，就能无缝替换网络或存储后端。

## 2.1 插件接口：CNI = 二进制 + JSON，CSI = gRPC + protobuf

### CNI 接口

CNI 插件是一个**可执行文件**，接收 JSON 配置和标准输入参数，输出 JSON 结果或错误。

```text
调用方（kubelet / CRI）
    │
    ├─ 环境变量：CNI_COMMAND=ADD/DEL/CHECK/GC/STATUS
    │            CNI_CONTAINERID=<pod sandbox id>
    │            CNI_NETNS=/proc/xxx/ns/net
    │            CNI_IFNAME=eth0
    │            CNI_PATH=/opt/cni/bin
    │            CNI_ARGS=<k=v;k=v>
    │
    └─ stdin：CNI 配置文件 JSON
         │
         ▼
    /opt/cni/bin/bridge
         │
    stdout：{
      "cniVersion": "1.0.0",
      "interfaces": [...],
      "ips": [...],
      "routes": [...],
      "dns": {...}
    }
```

CNI 配置放在 `/etc/cni/net.d/` 目录，按字典序选取第一个 `.conf` / `.conflist` 文件。一个 `.conflist` 可以链式调用多个插件：

```json
{
  "cniVersion": "1.0.0",
  "name": "mynet",
  "plugins": [
    { "type": "bridge", "bridge": "cni0", ... },
    { "type": "host-local", "ipam": { ... } },
    { "type": "firewall", ... },
    { "type": "bandwidth", ... }
  ]
}
```

### CSI 接口

CSI 驱动是一个**常驻 gRPC 服务**，通过 Unix domain socket 暴露 Identity / Controller / Node 三面接口。

```text
K8s sidecars                    CSI driver (Pod / DaemonSet)
    │                                │
    ├─ CreateVolume ────────────────▶│ Controller service
    ├─ ControllerPublishVolume ─────▶│
    ├─ CreateSnapshot ──────────────▶│
    │                                │
    ├─ NodeStageVolume ─────────────▶│ Node service
    ├─ NodePublishVolume ───────────▶│
    ├─ NodeExpandVolume ────────────▶│
    │                                │
    ├─ GetPluginInfo ───────────────▶│ Identity service
    └─ Probe ───────────────────────▶│
```

CSI 不直接面向 kubelet，而是通过一组 sidecar 适配 K8s 的存储流程：

- `external-provisioner` 监听 PVC，调用 `CreateVolume` / `DeleteVolume`。
- `external-attacher` 监听 VolumeAttachment，调用 `ControllerPublishVolume` / `ControllerUnpublishVolume`。
- `external-resizer` 监听 PVC 扩容请求，调用 `ControllerExpandVolume` / `NodeExpandVolume`。
- `external-snapshotter` 监听 VolumeSnapshot，调用 `CreateSnapshot` / `DeleteSnapshot`。
- `node-driver-registrar` 把 CSI socket 注册到 kubelet 的插件注册机制。

## 2.2 生命周期与幂等性

### CNI 生命周期

| 命令 | 语义 | 幂等要求 |
|---|---|---|
| **ADD** | 为容器 netns 添加网络接口 | 同一个容器 ID 多次 ADD 应返回相同结果 |
| **DEL** | 删除容器网络接口并回收资源 | 重复 DEL 不应报错（即使资源已回收） |
| **CHECK** | 检查容器网络是否符合配置 | 健康检查用 |
| **GC** | 回收孤儿资源 | 扫描所有已知容器 ID，回收不在列表里的资源 |
| **STATUS** | 查询插件整体健康 | 返回成功 / 失败 / 版本 |

CNI 的幂等性主要由 **container ID + network name + interface name** 三元组保证。IPAM 插件（如 host-local）会用本地磁盘记录已分配的 IP，避免重复分配。

### CSI 生命周期

| 接口 | 语义 | 幂等要求 |
|---|---|---|
| `CreateVolume` | 从 StorageClass 参数创建后端卷 | 同名 + 相同容量 + 相同参数应返回同一卷 |
| `DeleteVolume` | 删除后端卷 | 重复 Delete 应返回成功 |
| `ControllerPublishVolume` | 把卷挂到目标节点（控制器端） | 重复 publish 应返回成功 |
| `ControllerUnpublishVolume` | 从节点卸载卷（控制器端） | 重复 unpublish 应返回成功 |
| `NodeStageVolume` | 在节点上格式化 / 全局挂载（如 mount 到 `/var/lib/kubelet/plugins/...`） | 同节点重复 stage 应返回成功 |
| `NodeUnstageVolume` | 在节点上卸载全局挂载 | 重复 unstage 应返回成功 |
| `NodePublishVolume` | 把 stage 好的卷 bind-mount 到 Pod 目录 | 重复 publish 应返回成功 |
| `NodeUnpublishVolume` | 从 Pod 目录解绑 | 重复 unpublish 应返回成功 |

CSI 幂等性通常用** volume ID + staging target path + target path** 做 key，后端存储也保存元数据。

## 2.3 Netns + Linux 网络原语

CNI 插件能做的事，本质上是对 Linux 网络原语的编排：

```text
Pod netns ── veth0 <──────────> veth1 ── Linux bridge ── 节点网卡 ── 外部网络
              │
              ├─ IP 地址（IPAM 分配）
              ├─ 路由表（默认路由 / 集群网段）
              ├─ DNS（/etc/resolv.conf）
              └─ iptables/nftables / eBPF 规则
```

| 原语 | 作用 | CNI 使用场景 |
|---|---|---|
| **network namespace** | 隔离网络设备、路由、防火墙 | 每个 Pod 一个 netns |
| **veth pair** | 两个虚拟网卡，跨 netns 通信 | Pod netns ↔ 主机网络栈 |
| **Linux bridge** | 二层转发，连接多个 veth / 物理网卡 | bridge 插件把同节点 Pod 连起来 |
| **route** | 三层转发 | 配置 Pod 默认网关、集群 CIDR 路由 |
| **iptables / nftables** | NAT、过滤、标记 | portmap 插件 DNAT、firewall 插件隔离 |
| **eBPF** | 内核可编程数据面 | Cilium 替代 iptables 做高性能转发 |
| **SR-IOV VF** | 物理网卡虚拟功能直通 | SR-IOV CNI 把 VF 放进 Pod netns |

## 2.4 卷抽象：PV / PVC / StorageClass

CSI 之上，K8s 提供了三层抽象：

```text
用户 / 工作负载
     │
     ▼
  PVC（PersistentVolumeClaim）    <-- 我要 100Gi、RWO、SSD
     │
     ▼
  PV（PersistentVolume）          <-- 后端真实卷的 K8s 对象映射
     │
     ▼
StorageClass + CSI driver        <-- 动态创建 / 回收策略
     │
     ▼
  后端存储（EBS / Ceph / NFS / ...）
```

关键字段：

- `volumeMode: Filesystem | Block` — 文件系统卷或裸块设备。
- `accessModes: ReadWriteOnce | ReadOnlyMany | ReadWriteMany | ReadWriteOncePod` — 并发挂载语义。
- `storageClassName` — 指定由哪个 StorageClass / CSI driver 处理。
- `reclaimPolicy: Retain | Delete` — PV 释放后是保留还是删除。

## 2.5 声明式 + 最终一致性

CNI 与 CSI 都服从 K8s 的声明式模型：

- **CNI**：Pod `spec` 声明了"这个 Pod 需要 eth0 连入 default 网络"，kubelet 在创建 sandbox 时调用 CNI ADD 把现实收敛到声明；Pod 删除时调用 DEL 清理。
- **CSI**：PVC `spec` 声明了"我需要 100Gi 的 RWO 文件系统卷"，external-provisioner 观察到未绑定的 PVC，调用 `CreateVolume` 创建 PV 并绑定；Pod 调度后，external-attacher 与 kubelet 协同把卷挂载。

两个接口都强调**最终一致性**：插件可以失败、重试、重启，只要接口语义正确，系统最终会到达目标状态。

## 2.6 CNI vs CSI 对比

| 维度 | CNI | CSI |
|---|---|---|
| 解决的问题 | 容器网络连接 | 持久化存储挂载 |
| 接口形式 | 可执行二进制 + JSON stdin/stdout | 常驻 gRPC 服务 + protobuf |
| 触发时机 | Pod sandbox 创建 / 销毁 | PVC 创建 / Pod 调度 / 扩容 / 快照 |
| 生命周期命令 | ADD / DEL / CHECK / GC / STATUS | Create/Delete、Publish/Unpublish、Stage/Unstage、Expand/Snapshot |
| 部署形态 | `/opt/cni/bin` 二进制 + `/etc/cni/net.d` 配置 | Controller Deployment + Node DaemonSet + sidecars |
| 与 kubelet 关系 | kubelet / CRI 直接执行 | 通过 sidecar + 插件注册机制间接调用 |
| 代表实现 | Flannel、Calico、Cilium、Multus、SR-IOV CNI | EBS CSI、Ceph CSI、NFS CSI、S3 CSI、Lustre CSI |
| AI 场景关注点 | RDMA、多网卡、VXLAN vs 路由、eBPF | checkpoint 吞吐、RWO/RWX、快照、拓扑 |

## 2.7 与 K8s 其他组件的边界

```text
K8s 生态
├── CRI（容器运行时接口）
│      └── 创建/销毁 netns、启动容器
├── CNI（容器网络接口）
│      └── 在 netns 里创建 veth/IP/路由
├── Service / kube-proxy / Ingress / Gateway API
│      └── 在 CNI 之上做负载均衡与七层路由
├── NetworkPolicy
│      └── 由 CNI 实现的数据面隔离
├── CSI（容器存储接口）
│      └── 把后端卷挂到 Pod
├── PV / PVC / StorageClass
│      └── K8s 的卷声明与动态供应抽象
└── 并行文件系统 / 对象存储
       └── CSI 驱动的真实后端
```

关键边界：

- **CNI ≠ Service**：CNI 解决"Pod 有没有 IP、能不能通"；Service 解决"Pod IP 会变，如何提供稳定 VIP + DNS"。
- **CNI ≠ NetworkPolicy**：NetworkPolicy 是 K8s API，CNI 是执行者；没有实现 NetworkPolicy 的 CNI（如早期 Flannel）无法生效。
- **CSI ≠ 存储后端**：CSI 是接口，后端是 EBS / Ceph / Lustre / S3；选型时二者要一起考虑。
- **CSI ≠ PV/PVC**：PV/PVC 是 K8s 的对象抽象，CSI 是把这些抽象翻译成后端存储操作的协议。

## 2.8 本章小结

| 概念 | 一句话 |
|---|---|
| CNI | 用"二进制 + JSON"把容器网络连接标准化 |
| CSI | 用"gRPC + sidecar"把卷生命周期标准化 |
| 幂等性 | 同一操作重复执行结果不变，是插件容错的基础 |
| netns / veth / bridge / route | CNI 脚下的 Linux 网络原语 |
| PV/PVC/StorageClass | CSI 之上的 K8s 卷抽象 |
| 边界 | CNI 不做负载均衡，CSI 不做后端存储协议 |

理解了接口、生命周期和边界，下一章我们把它们放到 K8s 集群里，看 CNI / CSI 是怎么部署和触发的。

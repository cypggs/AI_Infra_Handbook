# 5. 核心模块

> 一句话理解：**CNI 的核心模块是"参考插件 + 主流数据面实现"，CSI 的核心模块是"sidecar 控制器 + 卷语义 + 后端驱动选型"**——网络侧你要在 bridge / VXLAN / BGP / eBPF / SR-IOV 之间做取舍，存储侧你要在 RWO / RWX / 文件系统 / 块设备 / 快照 / 拓扑之间做语义选择。

## 5.1 CNI 参考插件

`containernetworking/plugins` 仓库提供了一组官方参考实现，很多商业 CNI 都复用或扩展它们。

| 插件 | 作用 | AI 场景注意点 |
|---|---|---|
| **bridge** | 创建 Linux bridge，把 veth 接到 bridge | 同节点 Pod 二层互通，跨节点需 overlay / 路由 |
| **host-local** | 本地文件记录 IP 分配 | 节点级地址池，不适合大规模；重启后记录可能丢失 |
| **static** | 分配固定 IP | 需要上层指定 |
| **loopback** | 配置 lo 接口 | 每个 netns 必备 |
| **route** | 添加额外路由 | 多网段场景 |
| **bandwidth** | 用 tc 做 ingress/egress 限速 | 训练 Pod  QoS |
| **portmap** | DNAT 端口映射 | 类似 `hostPort` |
| **firewall** | iptables/nftables 防火墙规则 | 与 NetworkPolicy 互补 |
| **vlan / macvlan / ipvlan** | 二层/三层直连 | 需要底层网络配合 |

bridge + host-local 的最小工作配置：

```json
{
  "cniVersion": "1.0.0",
  "name": "demo-net",
  "plugins": [
    {
      "type": "bridge",
      "bridge": "cni0",
      "isGateway": true,
      "ipMasq": true,
      "hairpinMode": true,
      "ipam": {
        "type": "host-local",
        "subnet": "10.244.1.0/24",
        "routes": [{ "dst": "0.0.0.0/0" }]
      }
    },
    {
      "type": "firewall"
    }
  ]
}
```

## 5.2 主流 CNI 实现对比

| CNI | 数据面 | 跨节点模型 | NetworkPolicy | 性能 | 适合 AI 场景 |
|---|---|---|---|---|---|
| **Flannel** | VXLAN / host-gw / UDP | Overlay | ❌ | 中 | 小集群、测试 |
| **Calico** | BGP / VXLAN / eBPF | 路由 / Overlay | ✅（iptables/eBPF） | 高 | 大规模、BGP 网络 |
| **Cilium** | eBPF | 路由 / Overlay | ✅（eBPF） | 很高 | 高性能、可观测、RDMA aware |
| **Weave** | VXLAN | Overlay | ✅ | 中 | 早期流行，现已少用 |
| **Multus** | meta-CNI | 依赖子插件 | 依赖子插件 | - | 多网卡分离（管理/存储/RDMA） |
| **SR-IOV CNI** | SR-IOV VF 直通 | Underlay | - | 最高 | RDMA / GPU Direct |
| **Antrea** | OVS | Overlay | ✅ | 高 | VMware 生态 |

### 选型建议（AI 场景）

| 场景 | 推荐 CNI | 理由 |
|---|---|---|
| 通用推理 / 微服务 | Cilium / Calico | eBPF / BGP 性能好、NetworkPolicy 成熟 |
| 大模型分布式训练 | Cilium + Multus + SR-IOV CNI | 默认网络走 Cilium，RDMA 走 SR-IOV VF |
| 需要 Pod IP 与物理网络同网段 | Calico BGP / Macvlan | 路由可达，便于外部防火墙集成 |
| 快速 POC / 测试 | Flannel host-gw | 简单，但性能和功能弱 |

## 5.3 NetworkPolicy 数据面

NetworkPolicy 是 K8s API，但**真正干活的是 CNI 数据面**。实现方式有三种：

```text
Pod 流量
   │
   ├─ 方式 A：iptables / nftables 规则链
   │          按 namespace / label / CIDR 匹配，ACCEPT / DROP
   │
   ├─ 方式 B：eBPF 程序 hook cgroup/netdev
   │          Cilium 在 tc/xdp 入口做策略判决
   │
   └─ 方式 C：OVS flow
              Antrea/Weave 用 Open vSwitch flow 匹配
```

### 三种实现对比

| 实现 | 延迟 | 大规模策略数 | 可观测性 | 代表 CNI |
|---|---|---|---|---|
| iptables | 中 | 策略多时长连接建立慢 | 一般 | Calico（传统模式） |
| nftables | 中 | 优于 iptables | 一般 | Calico（新 nftables 后端） |
| eBPF | 低 | 高 | 强（Cilium Hubble） | Cilium |
| OVS | 中 | 高 | 中 | Antrea |

AI 平台通常策略复杂（多租户、训练/推理隔离），Cilium 的 eBPF 方案在大规模下更有优势。

## 5.4 CSI sidecars

`kubernetes-csi` 组织维护了一组 sidecar，把 K8s 存储语义翻译成 CSI gRPC。

| sidecar | 监听对象 | 调用 CSI | 作用 |
|---|---|---|---|
| **external-provisioner** | PVC / StorageClass | CreateVolume / DeleteVolume | 动态创建 / 删除卷 |
| **external-attacher** | VolumeAttachment | ControllerPublishVolume / ControllerUnpublishVolume | 控制器端挂载 / 卸载 |
| **external-resizer** | PVC（扩容请求） | ControllerExpandVolume | 后端卷扩容 |
| **external-snapshotter** | VolumeSnapshot | CreateSnapshot / DeleteSnapshot | 卷快照 |
| **node-driver-registrar** | 无 | 注册 socket | 让 kubelet 发现 Node 服务 |
| **livenessprobe** | CSI driver | Probe | 健康检查 |
| **csi-attacher-health-monitor** | VolumeAttachment | ControllerGetVolume | 检测异常 attach |

### 部署示例

```yaml
# Controller Deployment 片段
containers:
  - name: csi-driver
    image: my-csi-driver:v1.2.3
    volumeMounts:
      - name: socket-dir
        mountPath: /csi
  - name: external-provisioner
    image: registry.k8s.io/sig-storage/csi-provisioner:v5.0.0
    args:
      - --csi-address=/csi/csi.sock
      - --feature-gates=Topology=true
    volumeMounts:
      - name: socket-dir
        mountPath: /csi
  - name: external-attacher
    image: registry.k8s.io/sig-storage/csi-attacher:v4.7.0
    args:
      - --csi-address=/csi/csi.sock
    volumeMounts:
      - name: socket-dir
        mountPath: /csi

# Node DaemonSet 片段
containers:
  - name: csi-driver
    image: my-csi-driver:v1.2.3
    securityContext:
      privileged: true
    volumeMounts:
      - name: plugin-dir
        mountPath: /csi
      - name: mountpoint-dir
        mountPath: /var/lib/kubelet/pods
        mountPropagation: Bidirectional
      - name: device-dir
        mountPath: /dev
  - name: node-driver-registrar
    image: registry.k8s.io/sig-storage/csi-node-driver-registrar:v2.11.0
    args:
      - --csi-address=/csi/csi.sock
      - --kubelet-registration-path=/var/lib/kubelet/plugins/my.driver/csi.sock
    volumeMounts:
      - name: plugin-dir
        mountPath: /csi
      - name: registration-dir
        mountPath: /registration
```

## 5.5 CSI 卷语义

### accessModes

| 模式 | 缩写 | 含义 | 典型后端 |
|---|---|---|---|
| ReadWriteOnce | RWO | 单节点读写 | EBS / GCE PD / Ceph RBD |
| ReadOnlyMany | ROX | 多节点只读 | NFS / CephFS / 对象存储 |
| ReadWriteMany | RWX | 多节点读写 | NFS / CephFS / Lustre / WEKA |
| ReadWriteOncePod | RWOP | 单 Pod 读写（v1.27 beta） | 避免同节点多 Pod 竞争 |

AI 场景：

- 训练 checkpoint → 通常 RWO（本地 SSD / 块存储）或 RWX（并行文件系统）。
- 共享数据集 → RWX 或 ROX（NFS / Lustre / S3 CSI 只读）。
- 模型权重加载 → ROX（多 Pod 只读挂载）。

### volumeMode

| 模式 | 说明 | 用途 |
|---|---|---|
| Filesystem | 默认；CSI 驱动格式化并 mount | 大多数 AI 场景 |
| Block | 裸块设备；Pod 看到 `/dev/xvdba` | 数据库、需要自定义文件系统、性能敏感 |

### topology

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: zonal-ssd
provisioner: ebs.csi.aws.com
volumeBindingMode: WaitForFirstConsumer
allowedTopologies:
  - matchLabelExpressions:
      - key: topology.ebs.csi.aws.com/zone
        values: ["us-east-1a", "us-east-1b"]
parameters:
  type: gp3
  iops: "16000"
```

`volumeBindingMode: WaitForFirstConsumer` 是 AI 训练的关键：先调度 Pod，再在 Pod 所在可用区创建卷，避免跨 AZ attach 失败。

### snapshot / clone

```yaml
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: checkpoint-snap
spec:
  volumeSnapshotClassName: csi-snapclass
  source:
    persistentVolumeClaimName: training-data
```

快照用途：

- 训练 checkpoint 保护
- 数据集版本化（ROX PVC 从 snapshot 恢复）
- 快速克隆环境做推理微调

## 5.6 AI 存储 CSI 选型

| 后端 | 语义 | 吞吐 / IOPS | 共享 | 适合场景 |
|---|---|---|---|---|
| **local PV / TopoLVM** | 块 / 文件系统 | 极高（本地 NVMe） | 否（RWO） | checkpoint、单节点训练 |
| **EBS / GCE PD / Azure Disk** | 块 / 文件系统 | 高 | 否（RWO） | 通用有状态推理、数据库 |
| **Ceph RBD** | 块 / 文件系统 | 中高 | 否（RWO） | 私有云统一块存储 |
| **CephFS** | 文件系统 | 中 | 是（RWX） | 共享数据集、多 Pod 读 |
| **Lustre** | 并行文件系统 | 极高 | 是（RWX） | 大规模训练 checkpoint + 数据集 |
| **WEKA** | 并行文件系统 | 极高 | 是（RWX） | AI/ML 特化，低 latency |
| **NFS CSI** | 文件系统 | 中 | 是（RWX/ROX） | 简单共享、数据集 |
| **S3 CSI** | 对象存储 | 高吞吐、高延迟 | 是（ROX） | 模型仓库、数据集、只读加载 |

### 训练 vs 推理的 CSI 选择

| 阶段 | 推荐 CSI | 理由 |
|---|---|---|
| 训练 checkpoint 写入 | local PV / Lustre / WEKA | 高顺序写吞吐，避免网络存储瓶颈 |
| 训练数据集读取 | Lustre / CephFS / NFS / S3 CSI ROX | 多 worker 共享或并行读取 |
| 模型权重分发 | S3 CSI ROX / 镜像层 / local cache | 大文件只读，成本低 |
| 推理有状态化 | EBS / Ceph RBD | RWO，持久化日志 / 状态 |

## 5.7 本章小结

| 领域 | 关键选择 |
|---|---|
| CNI 数据面 | Flannel 简单、Calico 大规模 BGP、Cilium 高性能 eBPF、Multus 多网卡、SR-IOV RDMA |
| NetworkPolicy | iptables / eBPF / OVS；大规模 AI 推荐 eBPF |
| CSI sidecars | provisioner / attacher / resizer / snapshotter / registrar |
| 卷语义 | RWO/RWX/ROX、Filesystem/Block、topology、snapshot |
| AI 存储 | 训练 local/并行文件系统、推理块存储/只读对象、数据集共享 RWX |

下一章我们进入源码，看这些模块是怎么实现的。

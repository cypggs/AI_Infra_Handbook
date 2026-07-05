# 6. 源码分析

> 一句话理解：**读 CNI / CSI 源码的关键不是记住每一行，而是抓住"接口契约在哪里定义、生命周期函数如何被调用、幂等性如何实现"这三条主线**——CNI 看 `containernetworking/plugins` 的 JSON 输入输出与 netlink 调用，CSI 看 `container-storage-interface/spec` 的 protobuf 与 kubernetes-csi sidecars 的 watch → gRPC 链。

## 6.1 CNI 源码：containernetworking/plugins

### 仓库结构

```text
containernetworking/plugins/
├── pkg/
│   ├── ip/              <-- IP 地址、路由、AM 工具
│   ├── ipam/            <-- IPAM 接口与实现
│   ├── ns/              <-- netns 操作
│   ├── utils/           <-- 通用工具
│   └── ...
├── plugins/
│   ├── main/
│   │   ├── bridge/      <-- bridge 插件
│   │   ├── host-local/  <-- host-local IPAM
│   │   ├── loopback/    <-- loopback 插件
│   │   └── ...
│   └── meta/
│       ├── bandwidth/   <-- tc 限速
│       ├── firewall/    <-- iptables
│       └── portmap/     <-- DNAT
```

### bridge 插件入口

`plugins/main/bridge/bridge.go` 的核心流程（伪代码）：

```go
func cmdAdd(args *skel.CmdArgs) error {
    // 1. 解析 stdin JSON
    n, _, err := loadNetConf(args.StdinData)

    // 2. 进入容器 netns
    netns, err := ns.GetNS(args.Netns)
    defer netns.Close()

    // 3. 在 host 上创建或复用 bridge（如 cni0）
    br, err := bridgeSetup(n.BrName, n.MTU, n.IsGW, n.IPMasq, n.HairpinMode)

    // 4. 创建 veth pair
    hostVeth, containerVeth, err := ip.SetupVeth(
        args.IfName, n.MTU, n.HairpinMode, br, netns,
    )

    // 5. 调用 IPAM 分配 IP
    result, err := ipam.ExecAdd(n.IPAM.Type, args.StdinData)

    // 6. 在容器 netns 里配置 IP、路由、DNS
    err = netns.Do(func(hostNS ns.NetNS) error {
        // 给容器接口配 IP
        // 加默认路由 / 集群路由
        // 设置 DNS
    })

    // 7. 在 host 上配置路由 / iptables MASQ / hairpin
    // 8. 返回 result
    return types.PrintResult(result, n.CNIVersion)
}
```

关键 netlink 调用：

- `netlink.LinkAdd(&netlink.Veth{...})` 创建 veth pair。
- `netlink.LinkSetMaster(hostVeth, bridge)` 把 host 端接到 bridge。
- `netlink.AddrAdd(containerVeth, addr)` 给容器接口配 IP。
- `netlink.RouteAdd(&route)` 添加路由。

### host-local IPAM 分配与释放

`plugins/ipam/host-local/` 用本地文件记录 IP 分配：

```text
/var/lib/cni/networks/<network-name>/
├── last_reserved_ip.0      <-- 上次分配的 IP，用于顺序分配
├── 10.244.1.2              <-- 每个已分配 IP 一个文件，内容是 container ID
├── 10.244.1.3
└── ...
```

分配逻辑（伪代码）：

```go
func (a *IPAllocator) Get(id string) (*current.IPConfig, error) {
    a.store.Lock()
    defer a.store.Unlock()

    // 1. 先看该 id 是否已分配过（幂等）
    if reservedIP := a.store.GetByID(id); reservedIP != nil {
        return reservedIP, nil
    }

    // 2. 遍历 subnet，找第一个未被占用的 IP
    for ip := range a.subnet {
        if !a.store.Reserve(ip, id) {
            continue
        }
        return ip, nil
    }
    return nil, errors.New("no available IP")
}
```

释放逻辑：

```go
func (a *IPAllocator) Release(id string) error {
    // 删除该 container ID 对应的所有 IP 文件
    return a.store.ReleaseByID(id)
}
```

**生产注意**：host-local 的分配记录是节点本地文件，节点重建后记录丢失，可能造成 IP 冲突；大规模生产通常用 Calico IPAM / Cilium IPAM 等分布式方案。

### Cilium eBPF 数据面入口（可选）

Cilium 的核心在 `cilium/cilium` 仓库：

```text
cilium/
├── bpf/                 <-- eBPF 程序（C）
├── pkg/
│   ├── datapath/        <-- 数据面配置与加载
│   ├── maps/            <-- eBPF map 定义
│   ├── endpoint/        <-- Endpoint（Pod）状态
│   └── policy/          <-- NetworkPolicy 转 eBPF
└── daemon/              <-- agent 主入口
```

关键流程：

1. `daemon/cmd/daemon.go` 启动 agent，加载 eBPF 程序到 tc/xdp hook。
2. `pkg/policy` 把 K8s NetworkPolicy 编译成 eBPF map 条目。
3. 数据包到达 Pod 网卡时，eBPF 程序查 map 决定 pass / drop / redirect。

## 6.2 CSI 源码：container-storage-interface/spec

### protobuf 定义

CSI spec 定义在 `spec.md` / `csi.proto`：

```protobuf
service Identity {
  rpc GetPluginInfo(GetPluginInfoRequest)
      returns (GetPluginInfoResponse);
  rpc GetPluginCapabilities(GetPluginCapabilitiesRequest)
      returns (GetPluginCapabilitiesResponse);
  rpc Probe(ProbeRequest) returns (ProbeResponse);
}

service Controller {
  rpc CreateVolume(CreateVolumeRequest)
      returns (CreateVolumeResponse);
  rpc DeleteVolume(DeleteVolumeRequest)
      returns (DeleteVolumeResponse);
  rpc ControllerPublishVolume(ControllerPublishVolumeRequest)
      returns (ControllerPublishVolumeResponse);
  rpc ControllerUnpublishVolume(...);
  rpc ControllerExpandVolume(...);
  rpc CreateSnapshot(...);
  rpc DeleteSnapshot(...);
  rpc ListVolumes(...);
  rpc ControllerGetVolume(...);
}

service Node {
  rpc NodeStageVolume(NodeStageVolumeRequest)
      returns (NodeStageVolumeResponse);
  rpc NodeUnstageVolume(...);
  rpc NodePublishVolume(NodePublishVolumeRequest)
      returns (NodePublishVolumeResponse);
  rpc NodeUnpublishVolume(...);
  rpc NodeExpandVolume(...);
  rpc NodeGetInfo(...);
  rpc NodeGetCapabilities(...);
  rpc NodeGetVolumeStats(...);
}
```

### CreateVolume 幂等性

spec 要求 `CreateVolume` 幂等：

```protobuf
message CreateVolumeRequest {
  string name = 1;                    // K8s 保证唯一
  CapacityRange capacity_range = 2;
  repeated VolumeCapability volume_capabilities = 3;
  map<string, string> parameters = 4;  // StorageClass 参数
  map<string, string> secrets = 5;
  VolumeContentSource volume_content_source = 6;  // 从 snapshot/clone 创建
}
```

驱动实现通常：

1. 用 `name` 查后端，如果卷已存在且容量 / 参数匹配，直接返回。
2. 否则创建新卷。
3.  never 用同一个 `name` 创建两个不同卷。

## 6.3 kubernetes-csi/external-provisioner 调用链

`external-provisioner` 是 K8s 与 CSI 之间最重要的适配器。

### 入口

```text
cmd/csi-provisioner/csi-provisioner.go
    │
    ▼
pkg/controller/controller.go
    │
    ▼
provisionClaimOperation / deleteVolumeOperation
```

### 创建卷流程（伪代码）

```go
func (p *csiProvisioner) Provision(ctx context.Context, options controller.ProvisionOptions) (*v1.PersistentVolume, error) {
    // 1. 构造 CreateVolumeRequest
    req := csi.CreateVolumeRequest{
        Name:               pvName,
        CapacityRange:      &csi.CapacityRange{RequiredBytes: requestedBytes},
        VolumeCapabilities: volumeCaps,
        Parameters:         storageClassParams,
    }

    // 2. 处理 topology
    if options.SelectedNode != nil {
        req.AccessibilityRequirements = getAccessibilityRequirements(options.SelectedNode)
    }

    // 3. 调用 CSI Controller
    rep, err := p.csiClient.CreateVolume(ctx, req)

    // 4. 构造 PV 对象
    pv := &v1.PersistentVolume{
        Spec: v1.PersistentVolumeSpec{
            Capacity:    v1.ResourceList{v1.ResourceStorage: requestedQty},
            AccessModes: claimAccessModes,
            CSI: &v1.CSIPersistentVolumeSource{
                Driver:       p.driverName,
                VolumeHandle: rep.Volume.VolumeId,
                FSType:       fsType,
            },
            StorageClassName: options.StorageClass.Name,
        },
    }
    return pv, nil
}
```

关键点：

- `volumeBindingMode: WaitForFirstConsumer` 时，`SelectedNode` 会传入，provisioner 据此加 topology 要求。
- `volume_capabilities` 来自 PVC 的 `accessModes` + `volumeMode`。

## 6.4 AWS EBS CSI / hostpath 驱动 NodeStage / NodePublish

### AWS EBS CSI driver

仓库：`kubernetes-sigs/aws-ebs-csi-driver`

```text
pkg/
├── driver/
│   ├── driver.go        <-- gRPC server 入口
│   ├── controller.go    <-- Controller service
│   └── node.go          <-- Node service
└── cloud/
    └── devicemanager.go  <-- /dev 设备路径管理
```

`NodeStageVolume` 关键步骤：

```go
func (d *nodeService) NodeStageVolume(ctx context.Context, req *csi.NodeStageVolumeRequest) (*csi.NodeStageVolumeResponse, error) {
    devicePath := req.PublishContext["devicePath"]
    stagingTargetPath := req.GetStagingTargetPath()

    // 1. 检查块设备是否存在
    if !d.mounter.ExistsPath(devicePath) { ... }

    // 2. 如果需要，格式化文件系统
    fsType := req.GetVolumeCapability().GetMount().GetFsType()
    if err := d.mounter.FormatAndMount(devicePath, stagingTargetPath, fsType, mountOptions); err != nil { ... }

    return &csi.NodeStageVolumeResponse{}, nil
}
```

`NodePublishVolume` 关键步骤：

```go
func (d *nodeService) NodePublishVolume(ctx context.Context, req *csi.NodePublishVolumeRequest) (*csi.NodePublishVolumeResponse, error) {
    source := req.GetStagingTargetPath()
    target := req.GetTargetPath()

    // bind-mount staging path 到 pod 目录
    if err := d.mounter.Mount(source, target, "", []string{"bind"}); err != nil { ... }
    return &csi.NodePublishVolumeResponse{}, nil
}
```

### hostpath CSI driver（学习用）

仓库：`kubernetes-csi/csi-driver-host-path`

hostpath 是最简单的 CSI 参考实现，用本地目录模拟后端存储：

```go
func (hp *hostPath) createHostPathVolume(volID, name string, capRange *csi.CapacityRange, volAccessType state.AccessType) (*state.Volume, error) {
    path := hp.getVolumePath(volID)
    // 在节点本地创建目录或 sparse file
    if err := os.MkdirAll(path, 0750); err != nil { ... }
    // 记录到内存 / 状态文件
    return &state.Volume{...}, nil
}
```

适合本地学习 CSI 接口，不建议生产使用。

## 6.5 源码阅读地图

| 目标 | 仓库 | 入口文件 | 看什么 |
|---|---|---|---|
| CNI 规范 | containernetworking/cni | SPEC.md | ADD/DEL/CHECK/GC/STATUS 语义、result JSON |
| bridge 插件 | containernetworking/plugins | plugins/main/bridge/bridge.go | veth / bridge / route 创建 |
| host-local IPAM | containernetworking/plugins | plugins/ipam/host-local/main.go | IP 分配、本地文件存储 |
| Cilium eBPF | cilium/cilium | bpf/ + pkg/datapath/ | eBPF 程序、策略 map、负载均衡 |
| CSI 规范 | container-storage-interface/spec | spec.md / csi.proto | Identity/Controller/Node 接口 |
| external-provisioner | kubernetes-csi/external-provisioner | pkg/controller/controller.go | PVC → CreateVolume → PV |
| external-attacher | kubernetes-csi/external-attacher | pkg/controller/ | VolumeAttachment → ControllerPublish |
| AWS EBS CSI | kubernetes-sigs/aws-ebs-csi-driver | pkg/driver/node.go | NodeStage / NodePublish |
| hostpath CSI | kubernetes-csi/csi-driver-host-path | pkg/hostpath/ | 最小完整 CSI 实现 |

## 6.6 源码阅读建议

1. **先读 spec 再读实现**：CNI / CSI 的 spec 很短，但每一句话都是设计契约；带着契约去读代码，容易抓住主线。
2. **从入口顺着生命周期走**：CNI 从 `cmdAdd` / `cmdDel` 开始，CSI 从 `CreateVolume` / `NodePublishVolume` 开始。
3. **关注幂等性实现**：这是生产稳定性的关键，也是面试高频点。
4. **用 Mini Demo 验证**：后面章节的 `cni_csi_mini` 会用纯 Python 模拟 CNI ADD/DEL 与 CSI CreateVolume/NodePublish，对照源码理解事半功倍。

## 6.7 本章小结

| 接口 | 源码重点 |
|---|---|
| CNI | JSON 输入输出、netlink 创建 veth/bridge/route、host-local IPAM 文件 |
| CSI spec | Identity / Controller / Node protobuf、幂等性要求 |
| external-provisioner | PVC watch → CreateVolume → PV 构造 |
| AWS EBS / hostpath | NodeStage 格式化全局挂载、NodePublish bind-mount |

源码读到这里，已经能回答"CNI 是怎么给 Pod 插上网线的"和"CSI 是怎么把云盘塞进容器的"。下一章我们把这些知识用到生产实践中。

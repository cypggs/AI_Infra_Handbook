# cni-csi-mini —— 纯 Python 从零实现的 Kubernetes CNI/CSI 教学模拟器

一个**零第三方依赖**的教学模拟器，把容器网络接口（CNI）与容器存储接口（CSI）的核心机制在一个 Python 进程里重建出来：

- **CNI**：bridge 插件、host-local IPAM、同节点/跨节点路由、NetworkPolicy 默认拒绝/显式放行
- **CSI**：Controller Service（provision/attach/snapshot/expand）、Node Service（stage/publish/unpublish/unstage）、VolumeAttachment 一致性
- **Kubelet**：Pod 生命周期触发 CNI ADD/DEL 与 CSI stage/publish/unpublish/unstage，带乐观锁重试

> **它不是玩具**：IPAM 分配与回收、CNI ADD 幂等、跨节点 host-gw 路由、NetworkPolicy ingress/egress、
> CSI CreateVolume 幂等、RWO 单节点 attach、ROX 多节点只读、stage→publish 顺序约束、snapshot 还原、
> controller+node expand、VolumeAttachment 一致性——全部真实可运行，有 30+ 测试守护。
> 用 `FakeClock` 替代真实时间，于是第 7 章描述的 "Pod 创建 → CNI ADD → CSI publish → 删除逆序卸载"
> 时间线可以**精确复现**。

## 快速开始

```bash
cd docs/02-cloud-native/cni-csi/mini-demo
pip install -e ".[dev]"          # 仅依赖 pytest，包本体零依赖
pytest tests/ -v                 # 30+ 测试全绿
python -m cni_csi_mini.demo      # 跑六个端到端场景
```

## 六个场景

| 场景 | 演示的核心机制 |
|---|---|
| **1. CNI ADD + IPAM** | 单节点 Pod 创建，bridge + IPAM 分配 10.244.x.y |
| **2. 多节点 Pod 连通性** | 两个节点注册路由，host-gw 下一跳实现跨节点可达 |
| **3. NetworkPolicy** | 默认拒绝 db 入站，只允许 app=web 访问 3306 |
| **4. CSI volume 生命周期** | PVC → 动态 provision → attach → stage → publish → 删除后逆序卸载 |
| **5. CSI snapshot 和 expand** | 创建 snapshot、controller expand 扩容、从 snapshot restore 新 volume |
| **6. 端到端 Pod + 网络 + 存储** | 一个 Pod 同时拥有 PodIP 和已挂载 PVC |

## 目录结构

```
cni_csi_mini/
├── __init__.py        # 包说明 + 模块→真实组件对照表
├── clock.py           # Clock / FakeClock / RealClock
├── model.py           # Pod / Node / PVC / PV / Volume / VolumeAttachment / NetworkAttachment
├── apiserver.py       # FakeApiServer：resourceVersion、generation、/status、watch 事件流
├── cni.py             # CNI 插件接口、BridgePlugin、IPAM、RouteManager、NetworkPolicyManager
├── csi.py             # CSI Controller/Node Service、VolumeStore、NodeVolumeStore
├── kubelet.py         # kubelet：syncPod / deletePod、CNI + CSI 触发、乐观锁重试
└── demo.py            # 装配 + 六个场景
tests/                 # 30+ 测试：clock / apiserver / cni / csi / kubelet / demo
```

## 与真实 CNI/CSI/K8s 的对照

| 本模拟器 | 真实组件 | 是否简化 |
|---|---|---|
| `FakeApiServer`（内存 dict + 事件流） | kube-apiserver + etcd | 是：无 HTTP/gRPC、无鉴权、单进程 |
| resourceVersion 乐观并发 | 完全一致 | 否 |
| generation（spec 变 +1，status 不变） | 完全一致 | 否 |
| `BridgePlugin` | bridge / host-local / flannel / calico | 是：无真实 netlink/veth |
| `IPAM` | host-local / whereabouts | 是：仅顺序分配 + 回收 |
| `RouteManager` | Linux 路由表 + Calico BGP / Flannel VXLAN | 是：仅检查可达性与下一跳 |
| `NetworkPolicyManager` | kube-proxy + iptables/nftables / Cilium eBPF | 是：仅支持 podSelector + 端口 |
| `ControllerServer` | CSI Controller Service + external-provisioner/attacher/snapshotter | 是：无 gRPC，内存状态 |
| `NodeServer` | CSI Node Service | 是：无真实 mount/nsenter |
| `VolumeStore` | CSI driver 内部状态 + etcd PV/VolumeAttachment | 是：单节点内存 |
| `NodeVolumeStore` | `/var/lib/kubelet/plugins/kubernetes.io/csi/` | 是：仅记录 stage/publish 路径 |
| `Kubelet.syncPod` | kubelet 的 syncPod 循环 | 是：单线程、无 PLEG/goroutine |

**简化的原则**：保留所有"网络/存储插件语义"（这是 CNI/CSI 模式的本质），简化所有"分布式系统工程"
（netlink、veth、iptables、eBPF、gRPC、并发）——因为后者是 K8s 与驱动实现自己的事，与理解 CNI/CSI 无关。

## 测试覆盖要点

- **clock**：FakeClock 步进、RealClock 单调性。
- **apiserver**：resourceVersion 分配、乐观锁冲突、generation 语义、/status 独立 rv、watch 事件流、注入冲突钩子。
- **CNI**：IPAM 顺序分配与回收、IPAM 耗尽、bridge ADD 幂等、DEL 回收 IP、同节点连通性、跨节点 host-gw 路由、
  NetworkPolicy 默认放行/默认拒绝/按端口允许/egress 控制、插件链顺序。
- **CSI**：CreateVolume 幂等、DeleteVolume 回收、RWO 单 attach、ROX 多节点只读、ROX 拒绝读写挂载、
  stage→publish 顺序、unpublish→unstage 顺序、snapshot 还原、controller expand、node expand 前置检查、
  VolumeAttachment 一致性、带 attach 时禁止删除。
- **kubelet**：Pod 创建获得 IP 与 volume 挂载、删除后网络与存储全清理、watch 事件流驱动同步、
  乐观锁冲突重试、只读挂载被传递到 CSI。
- **demo**：六个端到端场景全部通过。

## 诚实的边界

本模拟器故意只保留教学所需的最小语义，以下真实系统的复杂度被省略：

1. **没有真实网络**：不产生 veth pair，不调用 netlink，不发送/接收真实数据包；"连通性"只是路由表查询。
2. **没有真实存储**：不创建块设备、不格式化文件系统、不 bind mount；"挂载"只是内存中的 stage/publish 记录。
3. **没有真实进程**：Pod 只是 dict，容器没有真实 PID；sandbox_id 是确定性字符串。
4. **没有并发**：单线程、顺序执行；所有"并发"通过 apiserver 的乐观锁 + kubelet 重试来体现。
5. **没有 gRPC/HTTP**：CSI 调用是本地 Python 方法调用，CNI 调用是本地对象方法。
6. **NetworkPolicy 大幅简化**：只支持 `podSelector` + 端口，不支持 CIDR、except、egress 到集群外等高级语义。
7. **IPAM 简单**：顺序分配，不支持保留段、双栈、IPv6。
8. **CSI 驱动能力固定**：所有 volume 都支持 attach、stage、snapshot、expand；真实驱动会声明能力位。

这些省略不会妨碍理解 CNI/CSI 的核心概念与数据流；在真实集群里，这些语义被相同的 API 调用序列执行。

## 进一步阅读

- 机制基础见手册 [CNI/CSI 第 7 章：Mini-Demo](../07-mini-demo)。
- 机制基础见 [第 2 章 核心思想](../02-core-ideas)、[第 3 章 架构](../03-architecture)、[第 4 章 Runtime 工作流程](../04-runtime-workflow)。
- 真实实现对照见 [第 6 章 源码分析](../06-source-analysis)（Cilium、Calico、CNI 规范、CSI 规范）。

# 7. 工程实践：cni-csi-mini

> 一句话理解：**用纯 Python 标准库把 Kubernetes 的 CNI（容器网络接口）与 CSI（容器存储接口）的核心语义跑在一个进程里**，让你能逐步看到 Pod 创建时如何分配 IP、跨节点如何路由、NetworkPolicy 如何放行/拒绝、PVC 如何动态 provision、Volume 如何 attach/stage/publish、删除时又如何逆序卸载——全部可测试、可复现。

## 7.1 为什么需要这个 Mini Demo

真实的 CNI / CSI 链路涉及太多“非接口”细节：

- CNI 要调 netlink 创建 veth、bridge、路由、iptables/eBPF；
- CSI 要调 gRPC、块设备、文件系统、mount namespace；
- kubelet 是多线程、有 PLEG、device manager、volume manager。

这些细节对理解 **CNI / CSI 接口本身** 并不是必需的，反而会把初学者淹没。`cni-csi-mini` 的做法是：

> **保留接口语义与生命周期，省略分布式/内核/硬件实现。**

于是你可以在一个 Python 进程里，用 46 个测试守护以下不变量：

- CNI ADD 幂等、IPAM 顺序分配与回收、同节点/跨节点路由、NetworkPolicy 默认拒绝 + 显式放行；
- CSI CreateVolume 幂等、RWO 单节点 attach、ROX 多节点只读、stage→publish 顺序、snapshot 还原、controller + node expand；
- kubelet 在 Pod 创建时触发 CNI + CSI，删除时按 publish→stage→attach→IP 的逆序清理。

## 7.2 目录与运行方式

代码位于 `docs/02-cloud-native/cni-csi/mini-demo/`：

```text
mini-demo/
├── pyproject.toml              # 仅 pytest 为可选开发依赖，包本体零依赖
├── README.md
├── cni_csi_mini/
│   ├── __init__.py             # 模块导出与真实组件对照表
│   ├── clock.py                # FakeClock / RealClock
│   ├── model.py                # Pod / Node / PVC / PV / VolumeAttachment / NetworkAttachment
│   ├── apiserver.py            # FakeApiServer：rv、generation、watch 事件流、乐观锁冲突
│   ├── cni.py                  # CNIPlugin / BridgePlugin / IPAM / RouteManager / NetworkPolicyManager
│   ├── csi.py                  # CSI Controller / Node Service、VolumeStore、NodeVolumeStore
│   ├── kubelet.py              # 模拟 kubelet：syncPod / deletePod
│   └── demo.py                 # 六个端到端场景
└── tests/
    ├── test_clock.py
    ├── test_apiserver.py
    ├── test_cni.py
    ├── test_csi.py
    ├── test_kubelet.py
    └── test_demo.py
```

快速开始：

```bash
cd docs/02-cloud-native/cni-csi/mini-demo
pip install -e ".[dev]"      # 只装 pytest，包本体仍是标准库
pytest tests/ -v             # 46 passed
python -m cni_csi_mini.demo  # 跑六个场景
```

## 7.3 设计要点

### 7.3.1 资源模型：metadata / spec / status 三段式

`model.py` 用普通 dict 表达 K8s 资源，保留 `metadata`、`spec`、`status` 三段式，以及 `resourceVersion`、`generation` 等关键字段：

```python
# model.py
POD_KIND = "Pod"
NODE_KIND = "Node"
PVC_KIND = "PersistentVolumeClaim"
PV_KIND = "PersistentVolume"
VOLUME_ATTACHMENT_KIND = "VolumeAttachment"
NETWORK_ATTACHMENT_KIND = "NetworkAttachment"
VOLUME_KIND = "Volume"

def _meta(name, namespace="default", **extra):
    return {
        "name": name,
        "namespace": namespace,
        "resourceVersion": "0",
        "generation": 1,
        "labels": {},
        "annotations": {},
        "deletionTimestamp": None,
    }

def make_node(name, *, cidr="10.244.0.0/24", labels=None):
    return {
        "apiVersion": "v1",
        "kind": NODE_KIND,
        "metadata": _meta(name, labels=labels or {}),
        "spec": {"podCIDR": cidr},
        "status": {"addresses": [{"type": "InternalIP", "address": f"192.168.0.{name[-1]}"}]},
    }
```

这里一个关键约定是：**集群级资源（Node / PV / VolumeAttachment）使用空 namespace**，与真实 Kubernetes 一致；Namespace 级资源（Pod / PVC / NetworkAttachment）使用 `default`。

### 7.3.2 FakeApiServer：把乐观并发变成可测试的

`apiserver.py` 模拟 kube-apiserver + etcd 的核心语义：

- 每次写操作递增 `resourceVersion`；
- `update` 时检查客户端带来的 `resourceVersion` 是否仍然最新，否则抛 `Conflict`；
- `/status` 子资源有独立的 `resourceVersion`；
- `generation` 只在 spec 变化时 +1；
- 支持 `events_since(index)` 模拟 watch 事件流。

这让我们可以在 `kubelet.py` 里写出带乐观锁重试的 status 更新：

```python
# kubelet.py
class Kubelet:
    def _update_status(self, pod, mutate_fn):
        for _ in range(self.max_retries):
            cur = self.api.get(model.POD_KIND, pod["metadata"]["namespace"],
                               pod["metadata"]["name"])
            updated = copy.deepcopy(cur)
            mutate_fn(updated)
            try:
                return self.api.update_status(updated)
            except Conflict:
                continue
        raise Conflict(f"failed to update status after {self.max_retries} retries")
```

### 7.3.3 CNI：bridge + host-local IPAM + 路由 + NetworkPolicy

`cni.py` 把 CNI 插件链抽象成对象方法：

- `IPAM` 按节点 `podCIDR` 顺序分配 IP，DEL 时回收；
- `BridgePlugin.add()` 给 Pod 分配 sandbox_id、调用 IPAM、记录路由；
- `RouteManager` 维护每个节点的路由表，同节点直连、跨节点通过下一跳 InternalIP 可达；
- `NetworkPolicyManager` 支持 `podSelector` + ingress/egress 端口规则，默认无策略时全放行，有策略时按 selector 匹配。

```python
# cni.py（IPAM 核心）
class IPAM:
    def allocate(self, sandbox_id):
        if sandbox_id in self._sandbox_to_ip:
            return self._sandbox_to_ip[sandbox_id]
        for ip in self._hosts[1:]:
            sip = str(ip)
            if sip not in self._allocated:
                self._allocated[sip] = sandbox_id
                self._sandbox_to_ip[sandbox_id] = sip
                return sip
        raise RuntimeError("IPAM exhausted")

    def release(self, sandbox_id):
        ip = self._sandbox_to_ip.pop(sandbox_id, None)
        if ip is not None:
            self._allocated.pop(ip, None)
```

### 7.3.4 CSI：Controller / Node 分离 + VolumeAttachment

`csi.py` 模拟 CSI 的三面接口中的两面：

- `ControllerServer`：CreateVolume、DeleteVolume、ControllerPublish/Unpublish、CreateSnapshot、ControllerExpand；
- `NodeServer`：NodeStageVolume、NodePublishVolume、NodeUnpublishVolume、NodeUnstageVolume、NodeExpandVolume；
- `VolumeStore`：保存 volume、snapshot、attachment 的全局状态；
- `NodeVolumeStore`：每个 kubelet 一个，记录本节点上的 stage/publish 路径。

RWO / ROX 的 attach 语义在这里被严格检查：

```python
# csi.py
class ControllerServer:
    def controller_publish_volume(self, volume_id, node_name, *, read_only=False):
        vol = self.store.get_volume(volume_id)
        attachments = self.store.attachments_for(volume_id)
        # RWO：已经 attach 到别的节点就拒绝
        if vol["spec"]["accessModes"] == ["ReadWriteOnce"]:
            for other in attachments:
                if other["node_name"] != node_name:
                    raise FailedPrecondition(
                        f"RWO volume {volume_id} already attached to {other['node_name']}"
                    )
        # ROX：只允许 read_only attach
        if "ReadOnlyMany" in vol["spec"]["accessModes"] and not read_only:
            raise FailedPrecondition(f"ROX volume {volume_id} must be attached read-only")
        return self.store.attach(volume_id, node_name, read_only=read_only)
```

### 7.3.5 kubelet：把 CNI 与 CSI 串到 Pod 生命周期

`kubelet.py` 的 `sync_pod` 与 `delete_pod` 是理解本章的重点：

- `sync_pod`：先 `_ensure_network`（CNI ADD），再 `_ensure_volumes`（动态 provision → ControllerPublish → NodeStage → NodePublish），最后更新 Pod status；
- `delete_pod`：先 `_teardown_volumes`（NodeUnpublish → NodeUnstage → ControllerUnpublish），再 `_teardown_network`（CNI DEL），体现“先挂载的后卸载”。

```python
# kubelet.py
class Kubelet:
    def sync_pod(self, pod):
        self._ensure_network(pod)
        self._ensure_volumes(pod)

    def delete_pod(self, pod):
        self._teardown_volumes(pod)
        self._teardown_network(pod)
```

## 7.4 六个端到端场景

`demo.py` 提供六个可独立运行的场景，下面是一次真实运行的输出。

### 场景 1：CNI ADD + IPAM

```text
场景 1：CNI ADD + IPAM（单节点分配 Pod IP）
Pod IP: 10.244.1.2
Gateway: 10.244.1.1
Phase: Running
```

说明：Pod `web` 调度到 `node-1`，`podCIDR=10.244.1.0/24`，IPAM 跳过网关 `.1`，分配 `.2`。

### 场景 2：多节点 Pod 连通性

```text
场景 2：多节点 Pod 连通性（host-gw 路由）
app-a on node-1: 10.244.1.2
app-b on node-2: 10.244.2.2
node-1 -> app-b reachable: True
next hop: 192.168.0.2
```

说明：`RouteManager` 在节点注册时互相学习 Pod CIDR，下一跳用节点 InternalIP，模拟 Calico BGP / Flannel host-gw 模式。

### 场景 3：NetworkPolicy

```text
场景 3：NetworkPolicy（默认拒绝 + 显式 allow ingress）
web -> db:3306 allowed: True
web -> db:8080 denied: False
db -> db:3306 denied: False
```

说明：策略只允许 `app=web` 访问 `app=db` 的 3306/TCP；同 pod 自己访问自己也被拒绝，因为默认拒绝只走显式规则。

### 场景 4：CSI volume 生命周期 + 删除后逆序卸载

```text
场景 4：CSI volume 生命周期（动态 provision → attach → stage → publish）
PVC phase: Bound bound_pv: pv-data
PV phase: Bound handle: vol-data
Volume attached to node-1: True
Node staged: True
Node published to pod: True
Pod phase: Running

场景 4 续：删除 Pod 后逆序卸载
After delete: published: False
After delete: staged: False
After delete: attached: False
```

说明：PVC 未绑定 PV 时，kubelet 调用 `ControllerServer.create_volume` 动态 provision，再 `controller_publish_volume`、`node_stage_volume`、`node_publish_volume`；删除时严格逆序卸载。

### 场景 5：CSI snapshot 和 expand

```text
场景 5：CSI snapshot 与 expand
Original volume size: 10 Gi
Snapshot created: True
Expanded volume size: 20 Gi (controller_expanded=True)
Restored volume size: 10 Gi source=snap-db-v1
```

说明：`create_snapshot` 后原 volume 可以 `controller_expand_volume` 扩容；新 volume 从 snapshot 恢复，source 字段保留原 snapshot 名称。

### 场景 6：端到端 Pod（网络 + 存储同时就绪）

```text
场景 6：端到端 Pod（网络 + 存储同时就绪）
Pod IP: 10.244.1.2
Pod phase: Running
PVC bound: Bound -> pv-shared
```

说明：一个 Pod 同时拥有 `podIP` 和已挂载 PVC，这是 AI 平台最常见的状态（训练/推理 Pod 需要网络通信 + checkpoint 存储）。

## 7.5 与真实组件的对照

| 本模拟器 | 真实组件 | 是否简化 |
|---|---|---|
| `FakeApiServer` | kube-apiserver + etcd | 是：无 HTTP/gRPC、无鉴权、单进程 |
| `resourceVersion` 乐观并发 | 与 K8s 一致 | 否 |
| `generation` 语义 | 与 K8s 一致 | 否 |
| `BridgePlugin` | bridge / host-local / flannel / calico | 是：无真实 netlink/veth |
| `IPAM` | host-local / whereabouts | 是：仅顺序分配 + 回收 |
| `RouteManager` | Linux 路由表 + Calico BGP / Flannel VXLAN | 是：仅检查可达性与下一跳 |
| `NetworkPolicyManager` | kube-proxy + iptables/nftables / Cilium eBPF | 是：仅支持 podSelector + 端口 |
| `ControllerServer` | CSI Controller Service + external-provisioner/attacher/snapshotter | 是：无 gRPC，内存状态 |
| `NodeServer` | CSI Node Service | 是：无真实 mount/nsenter |
| `VolumeStore` | CSI driver 内部状态 + etcd PV/VolumeAttachment | 是：单节点内存 |
| `NodeVolumeStore` | `/var/lib/kubelet/plugins/kubernetes.io/csi/` | 是：仅记录 stage/publish 路径 |
| `Kubelet.syncPod` | kubelet 的 syncPod 循环 | 是：单线程、无 PLEG/goroutine |

**简化原则**：保留所有“网络/存储插件语义”，简化“分布式系统工程细节”。这些省略不会妨碍理解 CNI/CSI 的核心概念与数据流。

## 7.6 测试覆盖

46 个测试覆盖以下关键点：

- **clock**：FakeClock 步进、RealClock 单调性。
- **apiserver**：resourceVersion 分配、乐观锁冲突、generation 语义、status 子资源独立 rv、watch 事件流、注入冲突钩子。
- **CNI**：IPAM 顺序分配与回收、IPAM 耗尽、bridge ADD 幂等、DEL 回收 IP、同节点连通性、跨节点 host-gw 路由、NetworkPolicy 默认放行/默认拒绝/按端口允许/egress 控制、插件链顺序。
- **CSI**：CreateVolume 幂等、DeleteVolume 回收、RWO 单 attach、ROX 多节点只读、ROX 拒绝读写挂载、stage→publish 顺序、unpublish→unstage 顺序、snapshot 还原、controller expand、node expand 前置检查、VolumeAttachment 一致性、带 attach 时禁止删除。
- **kubelet**：Pod 创建获得 IP 与 volume 挂载、删除后网络与存储全清理、watch 事件流驱动同步、乐观锁冲突重试、只读挂载被传递到 CSI。
- **demo**：六个端到端场景全部通过。

## 7.7 诚实的边界

本模拟器故意只保留教学所需的最小语义，以下真实系统的复杂度被省略：

1. **没有真实网络**：不产生 veth pair，不调用 netlink，不发送/接收真实数据包；“连通性”只是路由表查询。
2. **没有真实存储**：不创建块设备、不格式化文件系统、不 bind mount；“挂载”只是内存中的 stage/publish 记录。
3. **没有真实进程**：Pod 只是 dict，容器没有真实 PID；sandbox_id 是确定性字符串。
4. **没有并发**：单线程、顺序执行；所有“并发”通过 apiserver 的乐观锁 + kubelet 重试来体现。
5. **没有 gRPC/HTTP**：CSI 调用是本地 Python 方法调用，CNI 调用是本地对象方法。
6. **NetworkPolicy 大幅简化**：只支持 `podSelector` + 端口，不支持 CIDR、except、egress 到集群外等高级语义。
7. **IPAM 简单**：顺序分配，不支持保留段、双栈、IPv6。
8. **CSI 驱动能力固定**：所有 volume 都支持 attach、stage、snapshot、expand；真实驱动会声明能力位。

## 7.8 下一步

理解了这个 Mini Demo 的数据流后，建议继续阅读：

- [第 8 章 企业生产实践](08-production-practice) — AI 集群 CNI/CSI 选型、典型故障、性能调优、多租户隔离。
- [第 9 章 最佳实践](09-best-practices) — CNI/CSI 检查清单、AI 负载特化建议、YAML 模板。
- [第 10 章 面试题](10-interview-questions) — 用本章的代码实例回答面试中的生命周期与排障问题。

# 4. Runtime 工作流程

> 一句话理解：**CNI 的工作流是"netns 创建后插网卡、配 IP、设路由"，CSI 的工作流是"PVC 创建后造卷、挂节点、塞进 Pod"**——两条线独立触发、独立失败，但都会在 Pod 状态里留下痕迹；理解每一步的输入输出，是排障 `ContainerCreating` 的关键。

## 4.1 CNI 完整流程

### 时序图

```text
用户          kubectl/apiserver   kubelet   containerd/CRI   CNI plugins   IPAM   网络数据面
 │                │                  │            │              │           │        │
 │ apply pod      │                  │            │              │           │        │
 │───────────────▶│                  │            │              │           │        │
 │                │  watch Pod       │            │              │           │        │
 │                │─────────────────▶│            │              │           │        │
 │                │                  │ RunPodSandbox             │           │        │
 │                │                  │──────────────────────────▶│           │        │
 │                │                  │            │ create netns   │           │        │
 │                │                  │            │────────────────▶           │        │
 │                │                  │            │ CNI ADD        │           │        │
 │                │                  │            │───────────────▶│           │        │
 │                │                  │            │                │ allocate IP│        │
 │                │                  │            │                │──────────▶│        │
 │                │                  │            │                │ create veth/bridge/route
 │                │                  │            │                │─────────────────────▶
 │                │                  │            │                │ result    │        │
 │                │                  │            │◀───────────────│           │        │
 │                │                  │            │ start container │           │        │
 │                │                  │            │───────────────────────────────▶      │
 │                │                  │ update status.podIP        │           │        │
 │                │◀─────────────────│            │              │           │        │
```

### 步骤详解

1. **Pod 被调度到节点**

   kubelet 通过 watch 发现本节点需要启动的 Pod，调用 `syncPod`。

2. **CRI 创建 sandbox 容器**

   containerd / CRI-O 创建 pause 容器，主要作用是**持有 network namespace**。pause 容器启动后，netns 路径如 `/proc/<pause-pid>/ns/net` 才存在。

3. **CRI 调用 CNI ADD**

   containerd 的 CNI 模块读取 `/etc/cni/net.d/` 第一个配置，设置环境变量：

   ```bash
   CNI_COMMAND=ADD
   CNI_CONTAINERID=<sandbox-id>
   CNI_NETNS=/proc/xxx/ns/net
   CNI_IFNAME=eth0
   CNI_PATH=/opt/cni/bin
   CNI_ARGS="K8S_POD_NAME=...;K8S_POD_NAMESPACE=..."
   ```

4. **CNI 插件链执行**

   以 `bridge + host-local` 为例：

   ```text
   bridge 插件：
     - 创建/复用 cni0 bridge
     - 创建 veth pair：一端放 netns 命名 eth0，另一端在主机命名 vethxxx
     - 把主机端接到 cni0
     - 调用 IPAM 分配 IP
     - 在 netns 里设 IP、路由、DNS
   ```

5. **返回 prevResult**

   CNI 返回：

   ```json
   {
     "cniVersion": "1.0.0",
     "interfaces": [
       { "name": "eth0", "sandbox": "/proc/xxx/ns/net" }
     ],
     "ips": [
       { "interface": 0, "address": "10.244.1.5/24", "gateway": "10.244.1.1" }
     ],
     "routes": [
       { "dst": "0.0.0.0/0" }
     ],
     "dns": { "nameservers": ["10.96.0.10"] }
   }
   ```

6. **kubelet 更新 Pod 状态**

   拿到 IP 后，kubelet 把 `podIP` / `podIPs` 写回 apiserver。

7. **DEL 反向清理**

   Pod 删除时，CRI 调用 CNI DEL，插件按 container ID 回收 IP、删除 veth、清理路由。IPAM 的磁盘记录被删除，IP 回归地址池。

## 4.2 CSI 完整流程

### 时序图

```text
用户     kubectl    apiserver   external-provisioner   CSI Controller    后端存储
 │          │           │              │                    │              │
 │ apply PVC│           │              │                    │              │
 │─────────▶│           │              │                    │              │
 │          │  create PVC             │                    │              │
 │          │──────────▶│             │                    │              │
 │          │           │  watch PVC  │                    │              │
 │          │           │────────────▶│                    │              │
 │          │           │              │ CreateVolume       │              │
 │          │           │              │───────────────────▶│              │
 │          │           │              │                    │ 创建卷       │
 │          │           │              │                    │─────────────▶│
 │          │           │              │◀───────────────────│              │
 │          │           │  create PV + bind               │              │
 │          │           │◀─────────────│                    │              │

用户 apply Pod（使用该 PVC）
 │          │           │              │                    │              │
 │          │ scheduler bind Pod to node                   │              │
 │          │           │              │                    │              │
 │          │           │  create VolumeAttachment        │              │
 │          │           │─────────────▶ external-attacher  │              │
 │          │           │              │ ControllerPublishVolume           │
 │          │           │              │───────────────────▶│ 挂卷到节点   │
 │          │           │              │                    │─────────────▶│
 │          │           │              │  NodeStageVolume   │              │
 │          │           │              ├────────────────────────────────────▶ kubelet → CSI Node
 │          │           │              │  NodePublishVolume │              │
 │          │           │              ├────────────────────────────────────▶ kubelet → CSI Node
 │          │           │              │  容器启动，看到挂载点                │
```

### 步骤详解

1. **PVC 创建**

   ```yaml
   apiVersion: v1
   kind: PersistentVolumeClaim
   metadata:
     name: training-data
   spec:
     accessModes: ["ReadWriteOnce"]
     resources:
       requests: { storage: 100Gi }
     storageClassName: fast-ssd
   ```

   PVC 创建后处于 `Pending`。

2. **external-provisioner 触发 CreateVolume**

   provisioner 监听未绑定的 PVC，构造 `CreateVolumeRequest`：

   ```protobuf
   name: pvc-xxx-yyyy
   capacity_range: { required_bytes: 107374182400 }
   volume_capabilities: {
     mount: { fs_type: "ext4" }
     access_mode: { mode: SINGLE_NODE_WRITER }
   }
   parameters: { type: "gp3", iops: "16000" }
   ```

   CSI Controller 调用云厂商 API 创建 EBS 卷，返回 `volume_id` 和 `capacity_bytes`。

3. **PV 创建并绑定**

   provisioner 在 K8s 里创建 PV：

   ```yaml
   apiVersion: v1
   kind: PersistentVolume
   metadata:
     name: pvc-xxx-yyyy
   spec:
     capacity: { storage: 100Gi }
     accessModes: ["ReadWriteOnce"]
     csi:
       driver: ebs.csi.aws.com
       volumeHandle: vol-0123456789abcdef0
       fsType: ext4
     storageClassName: fast-ssd
   ```

   K8s 把 PV 绑定到 PVC，PVC 变成 `Bound`。

4. **Pod 调度与 VolumeAttachment**

   Pod 使用该 PVC 后，scheduler 选节点。kubelet 的 `volume manager` 发现 Pod 需要这个卷，触发 reconciler 创建 `VolumeAttachment`：

   ```yaml
   apiVersion: storage.k8s.io/v1
   kind: VolumeAttachment
   metadata:
     name: csi-1234567890abcdef
   spec:
     attacher: ebs.csi.aws.com
     nodeName: worker-2
     source:
       persistentVolumeName: pvc-xxx-yyyy
   ```

5. **ControllerPublishVolume**

   `external-attacher`  watch 到 VolumeAttachment，调用 CSI Controller：

   ```protobuf
   ControllerPublishVolumeRequest {
     volume_id: "vol-0123456789abcdef0"
     node_id: "worker-2"
     volume_capability: { ... }
   }
   ```

   云厂商把 EBS 卷 attach 到 worker-2。VolumeAttachment 的 `status.attached` 变成 `true`。

6. **NodeStageVolume**

   kubelet 通过 plugin socket 调用 CSI Node 的 `NodeStageVolume`：

   - 检查块设备 `/dev/xvdba` 是否存在。
   - 格式化（如果还没格式化）。
   - 全局挂载到 staging path，如 `/var/lib/kubelet/plugins/kubernetes.io/csi/ebs.csi.aws.com/.../globalmount`。

7. **NodePublishVolume**

   kubelet 调用 `NodePublishVolume`：

   - 把 staging path bind-mount 到 Pod 目录：
     `/var/lib/kubelet/pods/<pod-uid>/volumes/kubernetes.io~csi/<pvc-name>/mount`
   - 设置只读或读写。

8. **容器启动**

   容器内看到 `/data` 已经挂载好，可以读写。

9. **卸载与删除**

   Pod 删除时，流程反向：

   ```text
   NodeUnpublishVolume → NodeUnstageVolume
   → VolumeAttachment 删除 → ControllerUnpublishVolume
   → PVC 删除 → DeleteVolume（如果 reclaimPolicy=Delete）
   ```

## 4.3 故障排查：Pod stuck ContainerCreating

### 先定位是 CNI 还是 CSI

```bash
kubectl describe pod <pod> -n <ns>
```

常见事件：

| 事件 | 大概率方向 |
|---|---|
| `FailedCreatePodSandBox` | CNI 或 CRI |
| `network: ...` 错误 | CNI 配置 / IPAM / 插件 |
| `Unable to attach or mount volumes` | CSI attach / stage / publish |
| `Multi-Attach error` | RWO 卷被另一个节点占用 |
| `Volume is already attached to node X` | VolumeAttachment 残留 |

### CNI 排障清单

```bash
# 1. 看 CNI 配置
ls -la /etc/cni/net.d/
cat /etc/cni/net.d/10-*.conflist

# 2. 看 CNI 二进制
ls -la /opt/cni/bin/

# 3. 手动执行 CNI ADD 调试（在节点上）
CNI_COMMAND=ADD CNI_CONTAINERID=test CNI_NETNS=/proc/1/ns/net \
  CNI_IFNAME=eth0 CNI_PATH=/opt/cni/bin \
  /opt/cni/bin/bridge < /etc/cni/net.d/10-test.conf

# 4. 看节点路由与 bridge
ip route
ip link show cni0
brctl show          # 或 bridge link

# 5. 看 IPAM 分配记录（host-local）
cat /var/lib/cni/networks/<network-name>/*

# 6. 看 CNI 日志
journalctl -u kubelet | grep -i cni
```

典型问题：

- **IP 池耗尽**：host-local 的 `subnet` 太小，Pod 数超过容量。
- **CNI 配置冲突**：两个 `.conflist` 竞争，kubelet 选了错误配置。
- **MTU 问题**：VXLAN 封装后，Pod 内实际可用 MTU 比节点网卡小 50；NCCL 大包被分片。
- **conntrack full**：大量短连接训练导致 nf_conntrack 表满。
- **NetworkPolicy 误拦截**：默认 deny 策略没放通 DNS / Service CIDR。

### CSI 排障清单

```bash
# 1. 看 PVC / PV / VolumeAttachment
kubectl get pvc,pv,va -n <ns>
kubectl describe pvc <pvc>
kubectl describe pv <pv>
kubectl describe volumeattachment <va>

# 2. 看 CSI driver pod 日志
kubectl logs -n kube-system deployment/ebs-csi-controller -c ebs-plugin
kubectl logs -n kube-system daemonset/ebs-csi-node -c ebs-plugin

# 3. 看 kubelet volume manager 日志
journalctl -u kubelet | grep -i csi

# 4. 看节点挂载点
findmnt | grep <pvc-name>
mount | grep <pv-name>

# 5. 手动验证 socket
grpcurl -unix -proto csi.proto /var/lib/kubelet/plugins/ebs.csi.aws.com/csi.sock csi.v1.Identity.GetPluginInfo
```

典型问题：

- **VolumeAttachment 残留**：节点异常下线后，VA 没清掉，新 Pod 无法 attach。
- **attach limit**：节点可 attach 的卷数达到上限（AWS 不同类型实例限制不同）。
- **topology 失败**：StorageClass 的 `volumeBindingMode: WaitForFirstConsumer` 没配，卷创建在错误可用区。
- **resize 未触发 NodeExpand**：PVC 改大后，ControllerExpand 成功，但文件系统没扩展；需要 kubelet 触发 NodeExpandVolume。

## 4.4 生命周期对偶表

| 方向 | CNI | CSI |
|---|---|---|
| 创建 | ADD | CreateVolume / ControllerPublish / NodeStage / NodePublish |
| 删除 | DEL | NodeUnpublish / NodeUnstage / ControllerUnpublish / DeleteVolume |
| 检查 | CHECK | ControllerGetVolume / NodeGetVolumeStats |
| 回收孤儿 | GC | ListVolumes / 控制器清理 |
| 健康 | STATUS | Probe |
| 幂等关键 | container ID + network name + ifname | volume ID + node ID + target path |

## 4.5 本章小结

- CNI 流程：**sandbox 创建 → CNI ADD → 插件链 → IPAM → 返回 IP → Pod Running**。
- CSI 流程：**PVC 创建 → CreateVolume → PV 绑定 → Pod 调度 → ControllerPublish → NodeStage → NodePublish → 容器启动**。
- 排障核心：`kubectl describe pod` 看事件；CNI 问题查 `/etc/cni/net.d` 和 `/opt/cni/bin`；CSI 问题查 PVC/PV/VolumeAttachment 和 driver 日志。

下一章我们将拆解 CNI / CSI 的核心模块与主流实现。

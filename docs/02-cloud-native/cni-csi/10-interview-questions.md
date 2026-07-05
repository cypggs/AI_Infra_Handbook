# 10. 面试题

> 一句话理解：**CNI / CSI 面试考的不是背命令，而是"接口语义 + 生命周期 + 排障思路"**——能讲清楚 ADD/DEL 与 Create/Delete/Stage/Publish 的幂等性，能在 Pod 卡住时快速定位是网络还是存储，就已经超过大多数候选人。

## 初级

### Q1. 什么是 CNI？它解决什么问题？

**答**：CNI（Container Network Interface）是容器网络插件标准。它定义了容器运行时在创建/销毁容器 netns 时如何调用插件完成网络配置。K8s 通过 CNI 把网络实现外包给 Flannel、Calico、Cilium 等插件，自己只负责触发接口。

### Q2. 什么是 CSI？它和 in-tree volume 插件有什么区别？

**答**：CSI（Container Storage Interface）是 K8s 外置存储驱动标准，用 gRPC 定义 Identity / Controller / Node 三面接口。in-tree 插件写在 K8s 核心仓库里，迭代耦合、vendor 代码难维护；CSI driver 独立部署、独立迭代，云厂商和存储厂商可以在 K8s 核心外实现自己的驱动。

### Q3. CNI 的 ADD 和 DEL 分别做什么？

**答**：

- ADD：为指定 netns 创建网络接口（如 veth）、分配 IP、配置路由和 DNS。
- DEL：回收 ADD 创建的资源，包括 IP、veth、路由；要求幂等，重复 DEL 不报错。

### Q4. CSI 的 CreateVolume 和 DeleteVolume 是干什么的？

**答**：

- CreateVolume：根据 PVC 要求在后端存储创建卷，返回 volume ID 和容量。
- DeleteVolume：根据 volume ID 删除后端卷。二者都需幂等。

### Q5. 为什么 Pod 会有独立的 network namespace？

**答**：netns 隔离网络设备、路由表、防火墙规则，让每个 Pod 拥有独立的 IP 栈。同一 Pod 内多个容器共享 netns，所以可以用 localhost 通信；不同 Pod 的 netns 隔离，所以 IP 不冲突。

### Q6. 简述 veth pair 和 Linux bridge 在 CNI 中的作用。

**答**：veth pair 是成对虚拟网卡，一端在 Pod netns（eth0），一端在主机网络栈；Linux bridge 把多个 veth 主机端连起来，实现同节点 Pod 的二层互通。跨节点通信需要 overlay 或路由。

### Q7. PVC、PV、StorageClass 三者的关系是什么？

**答**：

- PVC 是用户的存储请求（容量、访问模式、StorageClass）。
- PV 是集群中真实卷的映射。
- StorageClass 描述动态供应模板（provisioner、参数、回收策略）。

未绑定的 PVC 会被 external-provisioner 消费，调用 CSI CreateVolume 创建 PV 并绑定。

## 中级

### Q8. CNI 插件链（plugin chaining）是什么？prevResult 有什么用？

**答**：`.conflist` 文件可以按顺序执行多个插件，前一个插件的返回结果通过 `prevResult` 传给后一个插件。后一个插件可以基于已有接口信息做额外操作，例如 bandwidth 插件读取 IP 后应用 tc 限速，firewall 插件添加 iptables 规则。

### Q9. 解释 CSI 中 ControllerPublishVolume 与 NodePublishVolume 的区别。

**答**：

- ControllerPublishVolume：在存储控制器侧把卷 attach 到目标节点（如云厂商把 EBS 挂到 VM）。
- NodePublishVolume：在目标节点上把已经 stage 好的卷 bind-mount 到 Pod 目录，让容器可见。

### Q10. NodeStageVolume 与 NodePublishVolume 的区别是什么？为什么分两步？

**答**：

- NodeStageVolume：在节点上执行一次性的、可被多个 Pod 复用的全局挂载，如格式化块设备并 mount 到 `/var/lib/kubelet/plugins/.../globalmount`。
- NodePublishVolume：把 stage 路径 bind-mount 到每个 Pod 的私有目录。

分两步的原因：一个卷可能被多个 Pod 使用（ROX / RWX），stage 一次即可，publish 多次；同时解耦"节点级准备"和"Pod 级暴露"。

### Q11. RWO、RWX、ROX 分别是什么意思？AI 场景怎么选？

**答**：

- RWO：单节点读写。
- RWX：多节点读写。
- ROX：多节点只读。

AI 场景：训练 checkpoint 常用 RWO（本地 SSD）或 RWX（并行文件系统）；数据集共享用 RWX 或 ROX；模型权重加载用 ROX。

### Q12. Pod 卡在 ContainerCreating，如何快速判断是 CNI 还是 CSI 问题？

**答**：先 `kubectl describe pod` 看事件：

- `FailedCreatePodSandBox` / `network: ...` → CNI。
- `Unable to attach or mount volumes` / `Multi-Attach error` → CSI。
- 然后分别查 CNI 配置/IPAM/路由，或查 PVC/PV/VolumeAttachment/CSI driver 日志。

### Q13. NetworkPolicy 为什么不生效？

**答**：可能原因：

1. CNI 不支持 NetworkPolicy（如早期 Flannel）。
2. 默认 deny 策略没有放通必要流量（DNS、同 namespace）。
3. 策略 selector 写错，没有匹配到目标 Pod。
4. CNI agent 没有正确同步策略（如 Calico felix / Cilium agent 异常）。

### Q14. 什么是 VolumeAttachment？它什么时候会出现？

**答**：VolumeAttachment 是 K8s 存储对象，表示一个 PV 被 attach 到哪个节点。当 Pod 使用 CSI RWO 卷并被调度到某节点时，external-attacher 会创建它，调用 ControllerPublishVolume；卸载成功后删除。

### Q15. CNI 的 CHECK 和 GC 命令是做什么的？

**答**：

- CHECK：验证容器网络配置是否符合 CNI 配置，用于健康检查。
- GC：扫描所有已知容器 ID，回收不在列表中的孤儿资源，防止 IP / veth 泄漏。

## 高级

### Q16. 设计一个支持 RDMA 的 AI 训练网络方案，你会怎么选 CNI？

**答**：推荐 **Cilium + Multus + SR-IOV CNI**：

- 默认网络走 Cilium eBPF，负责管理面、Service、DNS、监控。
- RDMA 网络用 Multus 调用 SR-IOV CNI，把 Mellanox VF 直通进 Pod netns。
- 需要时再用第三个 CNI（macvlan/ipvlan）分离存储网络。
- 物理网络配置 RoCEv2、PFC/ECN、QoS，NCCL 配置对应 GID / TC。

### Q17. CSI 驱动的幂等性如何实现？如果 CreateVolume 被调用两次会怎样？

**答**：幂等性通常用 `name`（K8s 保证唯一）作为 key：

1. 驱动先查后端是否已存在同名卷。
2. 如果存在且容量 / 参数匹配，直接返回该卷信息。
3. 如果不存在，创建新卷。

所以连续两次 CreateVolume 不会创建两个卷，而是返回同一个 volume ID。

### Q18. 训练集群用 local PV 做 checkpoint 有什么风险？如何缓解？

**答**：风险：

- 节点绑定：Pod 被驱逐后只能回原来节点，否则卷不可用。
- 磁盘故障：本地 SSD 没有后端冗余，可能丢数据。
- 调度复杂：需要 nodeAffinity / topology。

缓解：

- checkpoint 写入 local PV 后，异步复制到对象存储或并行文件系统。
- 使用 TopoLVM 做动态本地卷和拓扑感知。
- 关键训练任务使用支持 RWX 的并行文件系统作为主 checkpoint 后端。

### Q19. 为什么 CSI 扩容时 PVC status 已经变大，但 Pod 里 `df -h` 还是旧的？

**答**：CSI 扩容分两步：

1. ControllerExpandVolume：底层块设备扩容，PVC status 更新。
2. NodeExpandVolume：节点上扩展文件系统，通常需要 Pod 重启或 kubelet 重新扫描。

如果第二步没触发，文件系统仍然保持原大小。解决：确认 CSI driver 支持 expansion，且 kubelet 触发 rescan；必要时重启 Pod。

### Q20. 对比 Flannel、Calico、Cilium 在 AI 训练场景的优劣。

**答**：

| 维度 | Flannel | Calico | Cilium |
|---|---|---|---|
| 数据面 | VXLAN/host-gw | BGP/VXLAN/eBPF | eBPF |
| 跨节点 | Overlay / L2 | 路由 / Overlay | 路由 / Overlay |
| NetworkPolicy | 不支持 | 支持（iptables/eBPF） | 支持（eBPF） |
| 性能 | 中 | 高 | 很高 |
| 可观测 | 弱 | 中 | 强（Hubble） |
| RDMA | 不支持 | 需配合 Multus/SR-IOV | 需配合 Multus/SR-IOV |

AI 训练：Flannel 只适合测试；Calico BGP 适合大规模；Cilium eBPF 适合高性能 + 可观测。

### Q21. 多租户 AI 平台中，如何通过网络和存储隔离保证安全？

**答**：

- 网络：每个租户 namespace 配置 default-deny NetworkPolicy，只允许同租户 / 指定入口流量；用 Gateway API / Ingress 做七层路由。
- 存储：每个租户独立 StorageClass 或后端 pool；用 ResourceQuota 限制 PVC 容量和数量；敏感数据用 encrypted StorageClass + KMS。
- RDMA：物理网络 QoS / PFC / VLAN 隔离；Multus 给不同租户分配不同 VF pool 或 VLAN。

### Q22. 解释 CNI 的 `capabilities` 机制，并举一个例子。

**答**：`capabilities` 允许容器运行时向 CNI 插件传递额外参数。插件在配置中声明自己支持哪些能力，运行时按需传入。

例子：bandwidth 插件声明支持 `bandwidth` 能力，kubelet 在创建 Pod 时根据 annotation `kubernetes.io/ingress-bandwidth` 把限速值传给插件，插件用 tc 配置限速。

```json
{
  "type": "bandwidth",
  "capabilities": { "bandwidth": true }
}
```

## 面试小结

| 级别 | 考察重点 |
|---|---|
| 初级 | 接口定义、基本命令、PVC/PV/StorageClass 关系 |
| 中级 | 生命周期、Stage/Publish 区别、RWO/RWX、NetworkPolicy 排障、VolumeAttachment |
| 高级 | RDMA 方案设计、幂等性实现、local PV 风险、多租户隔离、扩容原理 |

下一章是延伸阅读与学习路径。

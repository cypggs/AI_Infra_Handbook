# 10. 面试题

> 一句话理解：**GPU 调度面试考的不是背命令，而是“Device Plugin 协议、GPU 切分技术差异、拓扑感知实现、Gang 调度原理、生产排障思路”这五个维度能否讲清楚**。

## 初级

### Q1. Kubernetes 中 GPU 是如何被识别和分配的？

**答**：GPU 厂商实现 **Device Plugin**，以 gRPC 方式向 kubelet 注册 `nvidia.com/gpu` 资源并上报设备列表。Pod 在 `resources.limits` 中声明 `nvidia.com/gpu: 1` 后，kubelet 调用 Device Plugin 的 `Allocate` 接口，把对应 GPU 设备文件（如 `/dev/nvidia0`）和库挂载到容器内。

### Q2. Device Plugin 的核心 gRPC 接口有哪些？

**答**：

- `GetDevicePluginOptions`：返回插件选项（如是否需要抢占）。
- `ListAndWatch`：持续向 kubelet 推送设备列表与健康状态。
- `Allocate`：为容器分配指定设备，返回 cgroup 设备白名单、环境变量、挂载点。
- `GetPreferredAllocation`（可选）：让插件参与调度决策，推荐最优设备组合。
- `PreStartContainer`（可选）：容器启动前做初始化。

### Q3. 为什么 Pod 中 GPU 要写在 `limits` 而不是 `requests`？

**答**：Device Plugin 管理的扩展资源目前只在 `limits` 中生效；kube-scheduler 根据 `limits` 做调度，`requests` 通常等于 `limits`。如果把 GPU 只写在 `requests` 里，容器可能不会被分配 GPU 设备。

### Q4. `nvidia-smi` 在节点能看到 GPU，但 Pod 里看不到，可能是什么原因？

**答**：

1. Pod 没有声明 `nvidia.com/gpu` 资源。
2. NVIDIA Container Toolkit 未正确配置，库/设备未挂载。
3. Device Plugin 未运行或健康检查失败。
4. container runtime 不是配置好的 `nvidia-container-runtime`。
5. 驱动未加载或内核模块异常。

### Q5. MIG、MPS、time-slicing 三者有什么区别？

**答**：

- **MIG**：硬件级切分，每张 A100/H100 可分成多个独立实例，有独立显存与计算资源，故障隔离最好。
- **MPS**：多进程共享一张卡，显存隔离弱，适合小任务共享。
- **time-slicing**：内核级分时复用，多个容器轮流使用 GPU，上下文切换有开销，不适合低延迟推理。

### Q6. 为什么训练任务通常用整卡而不是 MIG？

**答**：NCCL 分布式训练需要 GPU 之间高速互联（NVLink/NVSwitch），而 MIG 实例之间通常不能跨实例做 NCCL 通信；同时训练任务需要大显存和稳定 QoS，整卡性能最优、故障域最小。

### Q7. Pod 请求 `nvidia.com/gpu: 1` 却一直 Pending，如何排查？

**答**：

1. `kubectl describe pod` 看事件，确认是 `Insufficient nvidia.com/gpu` 还是其他。
2. `kubectl describe node` 看 `Allocatable` 中 GPU 数量。
3. 检查 Device Plugin Pod 是否 Running。
4. 检查节点是否有污点、Pod 是否有容忍。
5. 检查是否请求了 MIG 资源但节点没有对应 profile。

## 中级

### Q8. 解释 Device Plugin 的 `ListAndWatch` 和 `Allocate` 如何配合。

**答**：

- `ListAndWatch` 是长连接，Device Plugin 把节点上所有 GPU 设备（含健康状态）推送给 kubelet；kubelet 更新到 `node.status.allocatable`。
- kube-scheduler 根据 `allocatable` 调度 Pod。
- Pod 被调度到节点后，kubelet 在创建容器前调用 `Allocate`，传入设备 ID；Device Plugin 返回需要挂载的设备路径、环境变量、挂载卷。

### Q9. MIG 在 Kubernetes 中是如何暴露为调度资源的？

**答**：GPU Operator 的 MIG Manager 按 ConfigMap 把物理 GPU 切分成 MIG 实例后，Device Plugin 会把这些实例作为独立设备上报。节点 `allocatable` 会出现 `nvidia.com/mig-1g.10gb`、`nvidia.com/mig-2g.20gb` 等资源。Pod 按这些资源名请求即可。

### Q10. 什么是拓扑感知调度？在 GPU 场景如何实现？

**答**：拓扑感知调度是指调度器在选择节点和 GPU 时，考虑 CPU/内存/NIC/GPU 之间的 NUMA、PCIe、NVSwitch 等物理拓扑关系，减少跨域访问延迟。

实现方式：

- 用 NFD/GFD 把拓扑信息打成节点标签。
- 使用 scheduler-plugins 的 `NodeResourceTopology` 插件，读取 CRD 中的节点拓扑。
- 在 Pod 中通过 affinity 或 scheduler 配置，让调度器选择同 NUMA / 同 NVSwitch / 同机架的 GPU。

### Q11. Gang 调度解决什么问题？

**答**：分布式训练通常需要多个 Pod 同时启动（如 4 节点 × 8 卡）。如果 scheduler 逐个调度，可能出现部分 Pod 已占用资源、部分 Pod _pending_，导致已调度 Pod 空等甚至训练失败。Gang 调度保证“全部满足或一个不满足”，避免资源死锁。

### Q12. Volcano 与 Kueue 的主要区别是什么？

**答**：

| 维度 | Volcano | Kueue |
|---|---|---|
| 定位 | 面向批处理/AI 的独立调度器 | 原生 K8s 上的工作负载队列系统 |
| Gang 调度 | 原生 PodGroup | 依赖 scheduler-plugins |
| 抽象 | Queue / PodGroup / Job | ClusterQueue / LocalQueue / Workload |
| 与原生 scheduler | 替换默认 scheduler | 共存 |
| 适用 | 训练集群、已用 Volcano 生态 | 多租户 AI 平台 |

### Q13. GPU Operator 包含哪些核心组件？

**答**：NVIDIA Driver DaemonSet、Container Toolkit、Device Plugin、DCGM Exporter、Node Feature Discovery、MIG Manager、GPU Feature Discovery、Validator。详细职责见第 8 章。

### Q14. NCCL timeout 可能由哪些原因导致？

**答**：

1. 网络不通：Pod 之间 IP 不可达、防火墙阻断。
2. MTU 不一致：RDMA 网络 MTU 与预期不符。
3. PFC/ECN 未配置：RoCEv2 拥塞控制未生效。
4. IB 端口 down 或链路质量差。
5. 多租户下 NetworkPolicy 放通不完整。
6. GPU-NIC 拓扑不亲和导致 GPUDirect 失败。

排查：开启 `NCCL_DEBUG=INFO`、用 `ib_write_bw` 测带宽、检查 `nvidia-smi topo -m`。

### Q15. 如何给不同团队分配 GPU 配额并防止互相抢占？

**答**：

- namespace 级 `ResourceQuota` 限制 GPU 总数。
- `LimitRange` 设置默认与最大 GPU 数。
- `PriorityClass` 区分关键训练/普通训练/开发测试。
- Volcano Queue 或 Kueue ClusterQueue 做队列隔离与公平共享。
- 物理节点池按团队/用途划分，避免混部带来的噪声。

## 高级

### Q16. 设计一个千卡训练集群的 GPU 调度方案。

**答**：

1. **节点选型**：DGX/HGX 8 卡节点，NVSwitch 全互联，配置 RoCEv2/InfiniBand + GPUDirect RDMA。
2. **网络**：默认 Pod 网络用 Cilium eBPF；训练 RDMA 网络用 Multus + SR-IOV CNI 透传 VF。
3. **调度**：使用 Volcano 或 Kueue + scheduler-plugins，配置 PodGroup/Workload 做 Gang 调度，配合 `NodeResourceTopology` 做拓扑感知。
4. **切分**：训练用整卡；推理/开发用 MIG 或独立推理节点池。
5. **队列**：按团队设置 Queue/ClusterQueue，权重与 borrow limit 结合，保障关键训练。
6. **可观测**：DCGM + queue metrics + 训练业务指标，Xid 与 NCCL timeout 实时告警。
7. **故障隔离**：节点掉卡自动 cordon，训练任务自动 checkpoint-restart。

### Q17. Device Plugin 的 `GetPreferredAllocation` 有什么用？

**答**：默认 kube-scheduler 只按数量调度 GPU，不知道设备之间的拓扑。`GetPreferredAllocation` 允许 Device Plugin 在 Allocate 之前，根据当前空闲设备和拓扑信息，向 kubelet 推荐一组最优设备 ID。NVIDIA Device Plugin 可用其实现 NUMA 亲和、NVLink 亲和等策略。

### Q18. 为什么 MIG 切分后节点上会出现 `nvidia.com/mig-xxx` 资源而不是 `nvidia.com/gpu`？

**答**：MIG 模式下，物理 GPU 被切分成多个独立实例，每个实例不再是完整 GPU。Device Plugin 把这些实例作为新的扩展资源上报，因此节点 allocatable 不再包含 `nvidia.com/gpu`，而是各个 MIG profile 对应的资源名。请求整卡任务的 Pod 需要调度到未开启 MIG 的节点。

### Q19. GPU 节点出现 Xid 48 / 74 / 95，应该如何处理？

**答**：

- Xid 48（double bit ECC error）、74（NVLink error）、95（uncorrectable ECC）通常意味着硬件需要隔离。
- 立即 cordon 节点，避免新 Pod 调度。
- 驱逐或等待该节点训练任务完成 checkpoint 后重启。
- 如果重启后 Xid 复现，标记该 GPU 不可用在 MIG ConfigMap 中，或更换物理卡。
- 事后复盘：检查散热、电源、PCIe 连接，必要时联系厂商。

### Q20. 在 Kueue 中如何设计 ClusterQueue 才能既公平又保障关键训练？

**答**：

- 按业务线创建 ClusterQueue（如 `cq-train-prod`、`cq-train-dev`、`cq-infer`）。
- 用 `weight` 控制长期公平份额；用 `borrowingLimit` 允许短时借用但要设置上限。
- 为关键训练配置更高 PriorityClass，开启抢占。
- 为推理/开发队列设置 `admissionChecks` 或时间窗口，避免挤占训练资源。
- 监控 queue wait time，动态调整 weight。

### Q21. 多租户平台中，如何防止一个用户的训练任务占满所有 GPU？

**答**：

- ResourceQuota 硬上限。
- Queue weight + borrowingLimit 控制动态占用。
- PriorityClass 抢占：低优先级任务可被高优先级抢占，但不能无限抢占（可配 preemptionPolicy）。
- 最大运行时间限制：结合 Job TTL 或 Kueue 的 maxRuntime。
- 节点池隔离：关键团队/任务使用独立节点池，物理上限天然隔离。

### Q22. 解释 GPU Operator 中 Validator 的作用，以及如果它失败意味着什么。

**答**：Validator 在安装或升级后逐项检查驱动、container toolkit、device plugin、MIG manager 等组件是否正常工作。如果 Validator 失败，说明某一步未通过，常见原因包括：

- 内核版本与驱动不兼容。
- container runtime 未配置 nvidia runtime。
- MIG ConfigMap 格式错误。
- 节点上已有旧版本 NVIDIA 驱动冲突。

排查：查看 `gpu-operator` namespace 下 validator Pod 日志，按失败项逐一修复。

## 面试小结

| 级别 | 考察重点 |
|---|---|
| 初级 | Device Plugin 基本流程、GPU 资源声明、MIG/MPS/time-slicing 区别、Pending 排查 |
| 中级 | ListAndWatch/Allocate、拓扑感知、Gang 调度、Volcano vs Kueue、NCCL 排障 |
| 高级 | 千卡集群设计、GetPreferredAllocation、Xid 硬件隔离、Kueue 公平调度、多租户资源保护 |

下一章是延伸阅读与学习路径。

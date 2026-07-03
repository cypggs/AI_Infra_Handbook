# 10. Kubernetes 面试题精讲（初/中/高级）

> 一句话理解：面试题不是用来背的，而是检验你是否真正理解了机制——每道题都附"考点 + 答题要点 + 常见误区"，帮你把前九章的知识点串成一条能复述的线。

本章按初级（概念）、中级（机制与实现）、高级（设计与排障）三档组织，覆盖 K8s 通用知识 + AI 平台特化考点。每题给出**参考答案要点**和**面试官想听什么**，方便你自检理解深度。

## 10.1 初级：概念与基础

### Q1. 用一句话说清 Kubernetes 解决了什么问题？

**考点**：对 K8s 定位的本质理解。

**答题要点**：Kubernetes 是一个**声明式的容器编排系统**——你告诉它"我要 3 个 vLLM 副本"，它负责让集群的实际状态无限趋近这个期望状态（自动调度、故障重启、滚动升级、扩缩容）。它把"运维操作"变成了"声明期望 + 控制循环收敛"，让大规模部署、自愈、弹性成为平台能力而非每个应用自己实现。

**误区**：只说"管容器的工具"——没点出"声明式 + 控制循环"这一与 systemd/ansible 的本质区别。

### Q2. Pod 和容器的区别？为什么要有 Pod？

**考点**：Pod 作为最小调度单元的设计动机。

**答题要点**：
- **容器是应用进程的隔离单元，Pod 是调度的最小单元**。K8s 不直接调度容器，而是调度 Pod（一个或多个紧密协作的容器）。
- **Pod 提供共享上下文**：同 Pod 的容器共享网络命名空间（同 IP、同端口空间）、共享存储卷、共享 IPC。这适合 sidecar 模式（如主容器 + 日志收集 sidecar + Service Mesh proxy）。
- **为什么不让 K8s 直接调度多容器**：把"一组需共享资源的容器"打包成 Pod，调度器只需关心 Pod 级别的资源/亲和，简化了调度模型。

**加分**：提到 sidecar 容器（KEP-753，v1.33 GA）——init-like 的 sidecar 现在有独立的生命周期保证。

### Q3. Deployment、ReplicaSet、Pod 是什么关系？

**考点**：owner-reference 链与滚动升级机制。

**答题要点**：
- **Pod ← ReplicaSet ← Deployment**（owner-reference 链）。
- **ReplicaSet** 负责维持"某模板的副本数"（当前状态 → 期望状态）。
- **Deployment** 管理**多个 ReplicaSet**，通过创建新 RS、逐步增新 RS 副本、缩旧 RS 副本实现滚动升级（第 4、7 章）。模板一变，Deployment 就创建一个新 RS（用 `pod-template-hash` 区分），旧 RS 缩到 0 但保留（供回滚）。

**加分**：能说出滚动升级的 `maxSurge`/`maxUnavailable` 语义（先增后删、永不低于期望副本数）。

### Q4. Service 和 Ingress 有什么区别？

**考点**：四层 vs 七层流量管理。

**答题要点**：
- **Service** 是**四层（L4）**负载均衡，给一组 Pod 一个稳定的虚拟 IP/DNS 名，靠 kube-proxy（iptables/IPVS）或 EndpointSlice 转发。适合 TCP/UDP 服务。
- **Ingress** 是**七层（L7）**，基于 HTTP host/path 把流量路由到不同 Service，需要 Ingress Controller（nginx/traefik）实现。适合 HTTP 路由、TLS 终结。
- **Gateway API** 是 Ingress 的演进（HTTPRoute/GRPCRoute 等），更通用、角色分离（Infra Provider / Cluster Operator / App Developer），HTTPRoute 已 GA。

**加分**：知道 vLLM/Triton 推理服务既用 Service（稳定端点）又用 Ingress/Gateway（按模型路由、TLS）。

### Q5. HPA、VPA、Cluster Autoscaler 区别？

**考点**：扩缩容层次。

**答题要点**：
- **HPA**（Horizontal）：**扩 Pod 数**（按 CPU/QPS/自定义指标）。推理服务标配。
- **VPA**（Vertical）：**调 Pod 的 requests**（会重启 Pod）。慎用。
- **Cluster Autoscaler / Karpenter**：**扩节点数**（Pod 调不上时加机器）。

三者层次不同：HPA/VPA 管集群内 Pod，CA/Karpenter 管集群规模。生产常组合：HPA 扩 Pod + CA 扩节点。

## 10.2 中级：机制与实现

### Q6. 详细描述一个 Pod 从 `kubectl apply` 到 Running 的全过程。

**考点**：端到端流程（第 4 章核心）。

**答题要点**（顺流程讲）：
1. **kubectl → apiserver**：kubectl 把 YAML 转 JSON，经认证/授权/准入（Mutating → Validating）后写 etcd。
2. **scheduler watch**：kube-scheduler 通过 informer watch 到新 Pod（Pending、未调度），执行调度周期：PreFilter → Filter（NodeResourcesFit/NodeAffinity/TaintToleration）→ Score → Reserve → Bind，把 `nodeName` 写回。
3. **kubelet watch**：目标节点的 kubelet watch 到 `nodeName==self` 的 Pod，PLEG 触发 syncPod：调 CRI 起容器、CNI 配网络、CSI 挂卷、Device Plugin 分配 GPU。
4. **状态上报**：kubelet 周期上报 Pod phase（Pending→Running）、探针状态（ContainersReady/PodReady）到 apiserver。
5. **Service 更新**：Endpointslice controller watch 到带 label 的 Pod 就绪，更新 Endpointslice，kube-proxy 据此更新转发规则，Pod 开始接流量。

**加分**：能说出每一步失败的症状（Pending=调度失败、ContainerCreating=运行时/网络/存储、CrashLoopBackOff=应用崩溃）。

### Q7. 控制循环（control loop）是什么？为什么 K8s 用它？

**考点**：水平触发 vs 边沿触发（第 2、6 章）。

**答题要点**：
- **控制循环**：周期性对比"期望状态 vs 实际状态"，做最小必要动作让实际趋近期望。
- **水平触发**（level-triggered）vs **边沿触发**（edge-triggered）：K8s 控制器是水平触发——不管事件丢失与否，每次循环都重新评估当前状态。这让它**幂等、容错、最终一致**：即使错过某个事件，下次循环仍会纠正。
- **为什么用它**：分布式系统事件不可靠（网络抖动、组件重启），边沿触发会丢事件导致状态漂移；水平触发靠"反复重评估"保证最终收敛。代价是可能有重复操作（所以要幂等）。

**加分**：提到 informer 的 list+watch + resync（定期全量重列）机制——resync 就是水平触发的兜底。

### Q8. kube-scheduler 的调度框架（Scheduling Framework）有哪些扩展点？为什么这么设计？

**考点**：调度框架 12 扩展点（第 5、6 章）。

**答题要点**：
- 调度周期（串行）：`PreEnqueue → QueueSort → PreFilter → Filter → PostFilter → PreScore → Score`。
- 绑定周期（并发）：`Reserve → Permit → PreBind → Bind → PostBind`。
- 共 12 个扩展点（还有 `Unreserve`/`PreBind` 等）。
- **为什么这么设计**：把调度逻辑拆成可插拔的插件，用户能不动 kube-scheduler 源码就定制调度（写 out-of-tree 插件）。这是 K8s 可扩展性的典范—— Gang 调度、拓扑感知、容量调度都通过插件实现。

**加分**：提到 v1.19 GA；提到 scheduler-plugins（Coscheduling/NodeResourceTopology/Capacity）；提到 v1.36 原生 PodGroup（把 Gang 调度从插件升到内置）。

### Q9. 什么是 Gang 调度？为什么分布式训练需要它？

**考点**：AI 场景特化的调度（第 1、7 章）。

**答题要点**：
- **Gang 调度**：一组 Pod（gang）要么全部调度成功，要么一个都不调度（all-or-nothing）。
- **为什么训练需要**：分布式训练（DDP/Megatron）所有 worker 要在 `init_process_group` 会合，少一个都会卡死。不用 Gang 调度会出现死锁——8 个 worker 只调上 5 个，这 5 个等剩 3 个，剩 3 个被别的任务占着资源永远上不来，整个集群训练互相阻塞。
- **实现**：Volcano、scheduler-plugins Coscheduling，或 v1.36 原生 PodGroup。核心机制是 Permit 扩展点 + Reserve/Unreserve 资源回滚（凑不够法定数就释放已预占资源，避免碎片化）。

**加分**：能说出第 7 章模拟器的 `_schedule_gang` 实现（先全部 Reserve，够 min_available 才 Bind，否则 Unreserve 回滚）。

### Q10. Device Plugin 机制如何工作？GPU 怎么被调度？

**考点**：扩展资源与 GPU 调度（第 5、7、8 章）。

**答题要点**：
1. **注册**：Device Plugin（如 NVIDIA 的）通过 gRPC 向 kubelet 注册，`ListAndWatch` 上报设备列表，kubelet 把它转成 `node.status.allocatable["nvidia.com/gpu"]`。
2. **调度**：scheduler 看到 Pod 声明 `limits.nvidia.com/gpu: 1`，用 NodeResourcesFit 插件检查节点 allocatable 是否够，够就调度。
3. **分配**：kubelet syncPod 时调 Device Plugin 的 `Allocate()`，拿到具体设备索引，注入 `NVIDIA_VISIBLE_DEVICES` 环境变量 + `/dev/nvidia*` 挂载到容器。

**加分**：提到 GPU Operator 一键部署这套；提到 MIG/MPS 的隔离级别差异（硬件级 vs 进程级）。

### Q11. K8s 如何实现高可用？

**考点**：控制平面 HA（第 3、8 章）。

**答题要点**：
- **apiserver**：无状态，多副本前置 LB。
- **etcd**：Raft 一致性，3 或 5 节点（奇数），法定数写入。**etcd 是 HA 的命脉**。
- **scheduler / controller-manager**：多副本但选主（leader election），只有一个 active，靠 `--leader-elect`。
- **节点**：工作节点天然分布式，Pod 多副本 + 反亲和保证可用性。

**加分**：提到 etcd 法定数（3 容忍 1 故障、5 容忍 2）；提到 etcd 要独占 SSD、监控 `fsync` 延迟。

## 10.3 高级：设计与排障

### Q12. 设计一个支持分布式训练的 AI 调度系统，你会怎么做？

**考点**：综合设计能力（贯穿全书）。

**答题要点**（分层回答）：
1. **底座**：K8s 集群 + GPU 节点池（污点隔离）+ GPU Operator。
2. **调度**：Volcano 或 v1.36 原生 PodGroup 做 Gang 调度；scheduler-plugins NodeResourceTopology 做拓扑感知（worker 同 NVSwitch 域）；PriorityClass 体系（推理 > 训练 > 实验）。
3. **上层**：Kubeflow Training Operator / Ray Train 封装 PyTorchJob/RayCluster CRD，提供 worker/ps 角色模板。
4. **弹性**：检查点定期保存到 PVC/对象存储；配 `RestartJob` policy，worker 故障整 Job 重启从检查点恢复。
5. **可观测**：DCGM-Exporter + Prometheus 监控 GPU 利用率/显存；Gang 排队深度告警。
6. **多租户**：按团队 namespace + ResourceQuota（GPU 配额）+ Queue（Volcano 公平调度）。

**加分**：能讨论 trade-off——Volcano（成熟但独立调度器）vs 原生 PodGroup（统一但新）；弹性训练（minAvailable < worker）vs 严格 Gang。

### Q13. 一个 GPU Pod 一直 Pending，你怎么排查？

**考点**：排障流程（第 8 章）。

**答题要点**：
1. `kubectl describe pod <pod> | grep -A20 Events` 看调度失败原因。
2. **常见原因与解法**：
   - `insufficient nvidia.com/gpu` → GPU 不够，扩节点或排队。
   - `untolerated taint` → 没加 GPU 污点的 toleration。
   - `didn't match node affinity` → nodeSelector/label 不匹配。
   - `Insufficient memory` → requests 太大。
3. 检查节点：`kubectl describe node <gpu-node>` 看 `Allocatable` 的 GPU 是否被占满（Device Plugin 是否正常上报）。
4. 如果 Gang 调度，检查 PodGroup 状态：`kubectl get podgroup`，看是否在排队（minMember 未满足）。

**加分**：提到 Device Plugin 故障会让节点 GPU 容量"消失"（allocatable 显示 0），需查 GPU Operator pod。

### Q14. 推理服务滚动升级如何做到零中断？

**考点**：滚动 + 探针 + 流量摘除（第 8、9 章）。

**答题要点**：
1. **Deployment 配置**：`maxUnavailable: 0`（永不低于期望副本）+ `maxSurge: 1`。
2. **readinessProbe**：新 Pod 就绪（健康检查通过）才被 Endpointslice 收录、接流量。
3. **优雅关停**：旧 Pod 删除时，`preStop` hook 先主动从 Service 摘流（sleep 等待 kube-proxy 规则更新），应用处理 `SIGTERM` 排空在途请求，`terminationGracePeriodSeconds` 留足时间。
4. **大模型特化**：startupProbe 兜底慢启动；新旧 Pod 共存期间共享模型缓存（避免重复加载权重）。

**误区**：只说"用 RollingUpdate"——零中断的关键是探针 + 摘流 + 优雅关停的配合，不是滚动本身。

### Q15. K8s 是最终一致的吗？这意味着什么？

**考点**：一致性模型的理解。

**答题要点**：
- **是的，K8s 是最终一致的**。多个控制器异步收敛，某时刻不同组件看到的状态可能不同步（如 Pod 已 Running 但 Endpointslice 还没更新，导致短暂流量打到已删 Pod）。
- **意味着**：
  1. 不能假设"apply 后立即生效"——要等控制循环收敛。
  2. 控制器必须**幂等**——可能被多次触发。
  3. 客户端要处理瞬时不一致（重试、read-after-write 容忍）。
  4. 乐观并发：写操作带 `resourceVersion`，冲突时重试（apiserver 保证单对象强一致，跨对象最终一致）。

**加分**：提到 etcd 单对象线性一致 + 多控制器最终一致 = K8s 的混合一致性模型。

### Q16. 如果让你优化一个 GPU 利用率只有 30% 的推理集群，你会怎么做？

**考点**：综合优化（衔接 vLLM/Triton 主题）。

**答题要点**（多管齐下）：
1. **测量**：DCGM-Exporter 确认是利用率低（GPU idle）还是显存低（batch 上不去）。
2. **批处理**：开启 vLLM continuous batching / Triton dynamic batching，把并发请求合并成大 batch 提高 SM 利用率。
3. **切分**：小模型用 MIG 把一张卡切成多实例并发跑，提高利用率。
4. **共享**：同模型多副本改用 MPS 共享 SM（可信租户）。
5. **调度**：binpack 策略把推理 Pod 堆满节点（提高节点级利用率）；Descheduler 重平衡。
6. **弹性**：HPA 按 GPU 利用率/QPS 扩缩，低谷缩容。
7. **模型层**：量化（FP8/INT8）、蒸馏减小模型，降低单请求计算量提高吞吐。

**加分**：强调"先测后优化"——不测量就优化是盲改。

### Q17. etcd 挂了会怎样？怎么恢复？

**考点**：容灾（第 8 章）。

**答题要点**：
- **etcd 挂 = apiserver 无法读写 = 整个集群控制平面停摆**。但**已运行的 Pod/Service 不会立即受影响**（kubelet/kube-proxy 是本地决策，依赖缓存）。新操作（扩缩、调度新 Pod、升级）全部失败。
- **少数 etcd 挂（如 5 节点挂 2）**：仍有法定数，集群正常。
- **多数 etcd 挂（丧失法定数）**：控制平面停摆。
- **恢复**：从快照恢复——`etcdctl snapshot restore` 到新 etcd 集群，重启 apiserver 指向新 etcd。

**加分**：强调**定期备份 + 恢复演练**的重要性（很多人备份了从没验证恢复）；备份必须存集群外部（对象存储）。

## 本章小结

K8s 面试题的核心是**沿一条主线串联知识**：初级考概念定位（Pod/Deployment/Service 各是什么、为什么这么设计），中级考机制流程（一个 Pod 的完整生命周期、控制循环的水平触发、调度框架的扩展点、Gang 调度与 Device Plugin），高级考设计与排障（AI 调度系统设计、Pending 排障、零中断升级、最终一致性的影响、GPU 利用率优化、etcd 容灾）。答题的关键不是背诵细节，而是展现**对设计动机和 trade-off 的理解**——面试官想听的是"为什么"，而不只是"是什么"。AI 平台方向的候选人，务必把 Gang 调度、Device Plugin、GPU 利用率优化、MIG/MPS 这几个特化考点答深，这是与通用 K8s 候选人拉开差距的地方。

**参考来源**

- 本手册第 1–9 章
- [Kubernetes 官方文档（面试常考点）](https://kubernetes.io/zh-cn/docs/home/)
- [Kubernetes Scheduling Framework](https://kubernetes.io/zh-cn/docs/concepts/scheduling-eviction/scheduling-framework/)
- [NVIDIA GPU Operator](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/overview.html)

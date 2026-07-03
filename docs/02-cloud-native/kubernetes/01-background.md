# 1. 背景

## 1.1 从"一台机器一个应用"到"容器编排"

部署模型的演进可以概括为四个阶段：

```text
物理机 ──► 虚拟机 ──► 容器 ──► 容器编排（Kubernetes）
```

| 阶段 | 隔离粒度 | 典型问题 |
|---|---|---|
| 物理机 | 整机 | 资源利用率低；应用耦合；扩缩容=搬机器 |
| 虚拟机（VMware/KVM） | 虚拟硬件 | 隔离好但启动慢（分钟级）、镜像大（GB）、弹性差 |
| 容器（Docker, 2013） | 进程命名空间 + cgroups | 启动秒级、镜像小、环境一致；但**单机**——多机部署、故障转移、滚动升级仍靠手写脚本 |
| 容器编排（K8s, 2014 开源 / 2015 1.0） | 跨集群的 Pod 集合 | 解决容器的"多机协作"：调度、自愈、扩缩、滚动发布、服务发现 |

容器解决了"一台机器怎么跑多个隔离应用"，但**没有解决"成百上千台机器怎么协作管理这些容器"**。这正是 Kubernetes 出现的动机。

## 1.2 Kubernetes 解决的核心问题

把一个生产级分布式系统需要的能力列出来，K8s 几乎都内置了：

1. **调度（Scheduling）**：给每个 Pod 选一个合适的节点（资源够不够、亲和/反亲和、污点容忍、拓扑域）。
2. **自愈（Self-healing）**：Pod 崩了重启、节点宕了重新调度、副本数低于期望自动补齐。
3. **扩缩容（Scaling）**：手动 `kubectl scale`，或基于 CPU/自定义指标自动扩缩（HPA/VPA）。
4. **滚动发布与回滚（Rollout & Rollback）**：Deployment 控制器逐个替换旧 Pod，出问题可一键回滚到上一个 Revision。
5. **服务发现与负载均衡（Service & DNS）**：Pod IP 会变，Service 提供稳定 VIP + DNS 名，kube-proxy 做 iptables/IPVS 转发。
6. **配置与密钥管理（ConfigMap / Secret）**：把配置和敏感数据与镜像解耦。
7. **存储编排（CSI）**：声明 `PVC`，K8s 自动从 `StorageClass` 申请卷并挂载，Pod 迁移时卷可跟随。
8. **批处理与定时任务（Job / CronJob）**：保证 N 个 Pod 成功完成，失败重试，到点触发。
9. **资源配额与多租户（ResourceQuota / LimitRange / Namespace）**：限制团队/项目能用多少 CPU/内存/GPU。
10. **可扩展性（CRD + Operator + 调度框架 + Admission）**：把任何领域逻辑注入 K8s，而不必改核心代码。

> 对 AI 平台尤其重要的是第 1、2、9、10 条：调度 GPU 与拓扑、训练 Job 的 all-or-nothing（Gang）调度、用 Operator 包装 ML 工作流（如 KubeFlow 的 `TFJob`/`MPIJob`、NVIDIA 的 `GPU Operator`）。

## 1.3 为什么 Kubernetes 赢了

2014–2017 年容器编排领域有三大竞争者：

| 编排器 | 出身 | 设计哲学 | 结局 |
|---|---|---|---|
| **Docker Swarm** | Docker 官方 | 极简、内置于 Docker、上手快 | 功能弱、不支持复杂调度；Docker 公司战略收缩后被边缘化 |
| **Apache Mesos + Marathon** | Berkeley（ Borg 前成员参与） | 两级调度、可跑多种框架（含 Spark/Mesos） | 社区萎缩、Twitter/Mesosphere 商业化失败；Mesos 项目已移入 Attic |
| **Kubernetes** | Google（基于内部 Borg 十年经验）开源 | 声明式 API、可扩展、社区中立（CNCF） | **赢家通吃** |

K8s 胜出的根本原因不是"技术最强"，而是：

1. **Google Borg 的血统**：Borg 在 Google 内部跑了十年、支撑全球规模，K8s 继承了其核心思想（声明式、控制循环、Pod、标签选择器、服务发现）。Borg 团队 2015 年发表的 [Large-scale cluster management at Google with Borg](https://research.google/pubs/large-scale-cluster-management-at-google-with-borg/)（EuroSys'15）和 2016 年的 [Borg, Omega, and Kubernetes](https://research.google/pubs/borg-omega-and-kubernetes/)（ACM Queue）把这些设计公之于众。
2. **社区中立 + CNCF 基金会**：K8s 一开始就捐给 CNCF（Linux Foundation 下），不被任何一家云厂商独占，AWS/GCP/Azure 都必须支持它。这避免了"被锁死"的担忧。
3. **声明式 + 可扩展的 API 模型**：CRD + Operator 让生态可以无限生长——任何新硬件（GPU/FPGA）、新工作负载（训练/推理/数据）都能以"K8s 原生方式"接入。
4. **网络效应**：一旦主流云厂商都提供托管 K8s（EKS/GKE/AKS），工具链（Helm、Istio、Argo、Prometheus）都围绕它构建，新进入者几乎不可能追赶。

## 1.4 与其他编排器/平台的对比

| 维度 | Kubernetes | Docker Swarm | Nomad | Mesos | OpenShift | Ray on K8s（KubeRay） |
|---|---|---|---|---|---|---|
| 出身 | Google Borg | Docker | HashiCorp | Berkeley/Twitter | Red Hat（K8s 发行版） | Anyscale/社区 |
| 调度模型 | 单层、Pod 级、可扩展框架 | 简单 spread | 单二进制、灵活 | 两级（框架向 Mesos master 请求资源） | = K8s | 委托给 K8s 调度 |
| 生态 | 最大（CNCF） | 小 | 中（HashiCorp 栈） | 已萎缩 | 企业 K8s | 复用 K8s 生态 |
| 适合 AI/GPU | ✅ Device Plugin/GPU Operator/Volcano | ❌ | 部分（支持 GPU） | ✅（曾是 Spark 主力） | ✅ | ✅（Ray 负责任务，K8s 负责节点） |

> **一个常见误解**：Ray 和 Kubernetes 是竞争关系。实际上它们是**互补**的：K8s 负责节点生命周期、GPU 调度、部署弹性（KubeRay 把 Ray Cluster 表达为 CRD），Ray 负责集群内的任务/Actor 调度与对象存储。详见 [Ray 主题](/03-ai-platform/ray/)。

## 1.5 Kubernetes 与 AI 平台的特殊契合

K8s 最初是为无状态微服务设计的，但它能成为 AI 平台底座，靠的是三个关键能力被补齐：

1. **GPU 作为一等资源**：通过 Device Plugin 框架，节点上的 NVIDIA GPU 被抽象为 `nvidia.com/gpu` 这类扩展资源，可以像 CPU 一样被声明、调度、配额。NVIDIA 的 **GPU Operator** 把驱动、Container Toolkit、Device Plugin、DCGM 监控全部自动化，解决了"在 K8s 上装 GPU 节点极其繁琐"的痛点。
2. **Operator 模式包裹复杂工作流**：分布式训练（MPIJob/PyTorchJob via Training Operator）、推理服务（KServe）、批调度（Volcano）都用 CRD + Operator 实现，平台团队可以像用内置资源一样用它们。
3. **调度框架（Scheduling Framework）的插件化**：AI 训练需要的 Gang Scheduling（all-or-nothing）、拓扑感知（NUMA/PCIe/GPU 分组）、负载感知，都能通过调度插件实现，而不必 fork kube-scheduler。

> **里程碑**：自 **Kubernetes v1.36.0**（2026 年）起，调度框架**原生支持 PodGroup 调度**（KEP-4671 gang scheduling、KEP-5598 opportunistic batching），引入 `PodGroupPostFilterPlugin` 与协同放置（Placement）插件。这意味着 Gang Scheduling 正从 out-of-tree（Volcano / scheduler-plugins coscheduling）走向 in-tree 原生支持——这是 AI 训练负载调度的关键演进。详见 [第 5 章](05-core-modules) 与 [第 8 章](08-production-practice)。

## 1.6 本主题的视角与边界

本主题**不是** K8s 入门教程（官方文档已经做得很好），而是面向**已经会 `kubectl` 但想理解底层机制、并在 AI 平台场景下做设计与调优**的工程师。重点放在：

- **机制**：声明式 + 控制循环如何工作；调度框架如何决策；kubelet 如何把 Pod 真正跑起来。
- **源码视角**：关键组件的代码组织与调用链，让你能定位问题、阅读源码。
- **AI 场景**：GPU 调度、Gang Scheduling、拓扑感知、训练/推理 Operator 的工程实践。
- **取舍**：自建 vs 托管、网络/存储选型、调度策略选择背后的工程判断。

边界：

- **Docker / 容器运行时基础**：假设你了解容器镜像、`docker run`。运行时细节（containerd、OCI）会在 CRI 一节点到为止。
- **Helm / Operator 框架开发**：本主题讲 Operator **模式**，Helm/Operator SDK 的具体用法在生产实践章简述。
- **Service Mesh / GitOps**：只在相关处提及，不展开。

## 本章小结

Kubernetes 之所以成为 AI 平台底座，不是因为它是为 AI 设计的，而是因为它用**声明式 API + 控制循环 + 可扩展性**这套通用模型，把"调度、自愈、扩缩、滚动发布、服务发现、存储编排、资源治理"这七件生产级分布式系统必做的事收敛成了一套统一抽象；GPU、训练 Operator、Gang 调度都是在这套抽象上的"插件"。理解了 K8s 的核心思想，就理解了为什么整个 AI 基础设施生态都长在它之上。

**参考来源**

- [Kubernetes Components — 官方文档](https://kubernetes.io/docs/concepts/overview/components/)
- [Large-scale cluster management at Google with Borg (EuroSys'15)](https://research.google/pubs/large-scale-cluster-management-at-google-with-borg/)
- [Borg, Omega, and Kubernetes (ACM Queue, 2016)](https://research.google/pubs/borg-omega-and-kubernetes/)
- [Kubernetes 调度框架文档](https://kubernetes.io/docs/concepts/scheduling-eviction/scheduling-framework/)
- [NVIDIA GPU Operator 文档](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/index.html)

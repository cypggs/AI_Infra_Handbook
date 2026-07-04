# 11. Kubernetes 延伸阅读与学习路径

> 一句话理解：本章是 Kubernetes 主题的"出口"——把官方文档、经典论文/演讲、源码入口、社区项目整理成一张可循序的阅读地图，并标出它与本手册其他主题（Ray、vLLM、Triton、KServe）的衔接点。

Kubernetes 太大，一本手册不可能穷尽。本章的目标是给你一张**从入门到精通、从通用到 AI 特化**的阅读路线图：先官方文档打地基，再论文/演讲理解设计哲学，最后源码与社区项目深入实现。每条都标注了**为什么读、读什么**。

## 11.1 官方文档（按优先级）

官方文档是最权威、最及时的来源，但体量巨大。建议按这个顺序读：

| 优先级 | 文档 | 读什么 |
|---|---|---|
| **P0** | [Kubernetes 概念（Concepts）](https://kubernetes.io/zh-cn/docs/concepts/) | Pod/Service/Workload/Storage/调度的权威定义，每个概念配 YAML 示例 |
| **P0** | [kubectl 命令参考](https://kubernetes.io/docs/reference/kubectl/) | 日常操作必备，`kubectl explain`、`kubectl describe` |
| **P0** | [调度与驱逐](https://kubernetes.io/zh-cn/docs/concepts/scheduling-eviction/) | 调度框架、亲和/反亲和、污点/容忍、抢占——AI 平台核心 |
| **P1** | [任务（Workloads）：Job/CronJob](https://kubernetes.io/zh-cn/docs/concepts/workloads/controllers/job/) | 训练任务的基础工作负载 |
| **P1** | [设备插件](https://kubernetes.io/zh-cn/docs/concepts/extend-kubernetes/compute-storage-net/device-plugins/) | GPU 等 extended resource 的上报机制 |
| **P1** | [安全（RBAC/NetworkPolicy）](https://kubernetes.io/zh-cn/docs/concepts/security/) | 多租户必备 |
| **P2** | [API 约定（spec/status）](https://github.com/kubernetes/community/blob/master/contributors/devel/sig-architecture/api-conventions.md) | 写 Operator/CRD 必读 |
| **P2** | [控制器模式](https://kubernetes.io/zh-cn/docs/concepts/overview/components/) | 控制平面组件职责 |

**阅读技巧**：官方文档适合"带着问题查"而非"从头通读"。把概念部分当字典，遇到不懂的对象就去翻对应章节。

## 11.2 经典论文与演讲（理解设计哲学）

K8s 的很多设计只有回到源头论文/演讲才能真正理解"为什么这么设计"。

### Borg —— Kubernetes 的直系祖先

- **《Large-scale cluster management at Google with Borg》**（EuroSys'15 / Verma 等）—— K8s 控制平面、调度、PriorityClass 的思想源头。读这篇能理解 K8s 为什么是"声明式 + 控制循环 + Priority + Preemption"。本手册 Meta/Google 主题的 Borg 案例研究有详解。

### Omega —— 声明式 API 的理论奠基

- **《Omega: flexible, scalable schedulers for large compute clusters》**（Malawski 等，EuroSys'15 / Google）—— 提出用"共享状态 + 乐观并发"替代 Borg 的中心调度，是 K8s 多控制器并发 + `resourceVersion` 乐观锁的理论基础。

### Kubernetes 设计演讲

- **《Kubernetes: the surprisingly boring platform》**（Kelsey Hightower 等演讲）—— 理解 K8s "boring（可预测、可依赖）" 的设计哲学。
- **Kubernetes SIG 演讲（KubeCon）**—— KubeCon 每届都有 scheduling/sig-scheduling 的深入分享，是追踪 Gang 调度、拓扑感知、弹性等前沿的最佳途径。可在 CNCF YouTube 频道找。

## 11.3 调度与 Gang 调度专题（AI 重点）

AI 平台工程师必须深读的子领域：

| 资源 | 读什么 |
|---|---|
| [KEP-624 Scheduling Framework](https://github.com/kubernetes/enhancements/blob/master/keps/sig-scheduling/624-scheduling-framework/) | 12 扩展点的设计动机与 API |
| [KEP-4671 Gang Scheduling / PodGroup](https://github.com/kubernetes/enhancements/tree/master/keps/sig-scheduling/4671-foo) | v1.36 原生 Gang 调度的提案 |
| [kubernetes-sigs/scheduler-plugins 文档](https://scheduler-plugins.sigs.k8s.io/) | Coscheduling/NodeResourceTopology/Capacity/Trimaran 插件用法 |
| [Volcano 文档](https://volcano.sh/en/docs/) | 生产级 Gang 调度器，国内广泛使用 |
| [《Borg, Omega, and Kubernetes》](https://research.google/pubs/pub49374/)（Burns 等，ACM Queue 2016） | Google 内部三代调度系统的演进，理解 K8s 在历史中的位置 |

**为何重要**：分布式训练的 all-or-nothing、拓扑感知、公平调度是 K8s 在 AI 场景最大的扩展点，理解这些提案的演进（外挂调度器 → 插件 → 原生）能帮你在选型时做对决策。

## 11.4 GPU 与设备管理专题

| 资源 | 读什么 |
|---|---|
| [NVIDIA GPU Operator](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/overview.html) | 一键部署 GPU 栈（驱动/runtime/DevicePlugin/DCGM） |
| [NVIDIA Device Plugin 源码](https://github.com/NVIDIA/k8s-device-plugin) | Device Plugin gRPC 协议的参考实现 |
| [DCGM-Exporter](https://github.com/NVIDIA/dcgm-exporter) | GPU Prometheus 指标导出 |
| [MIG 支持文档](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/mig.html) | A100/H100 的 MIG 切分配置 |
| [Run:AI / Volcano 的 GPU 共享方案](https://volcano.sh/en/docs/v1.9.0/) | GPU 共享调度的工程实践 |

## 11.5 源码阅读入口

想深入实现的，从这些入口开始（第 6 章有详解）：

| 入口 | 路径 | 看什么 |
|---|---|---|
| 仓库 | [kubernetes/kubernetes](https://github.com/kubernetes/kubernetes) | 主仓库 |
| 调度器 | `pkg/scheduler/` | `scheduleOne`、`framework/`（12 扩展点接口） |
| kubelet | `pkg/kubelet/` | `PLEG`、`syncPod`、`device-manager` |
| controller-runtime | [kubernetes-sigs/controller-runtime](https://github.com/kubernetes-sigs/controller-runtime) | 写 Operator 的标准库，informer/reconcile 模板 |
| client-go | `k8s.io/client-go/tools/cache` | Informer / Delta FIFO / WorkQueue |
| scheduler-plugins | [kubernetes-sigs/scheduler-plugins](https://github.com/kubernetes-sigs/scheduler-plugins) | 自定义插件的样例（Coscheduling） |

**源码阅读建议**（第 6 章详述）：
1. 从 `cmd/` 入口顺着 `Run` 往下读，建立全局观。
2. 抓住 `wait.Until`/`Run` 这类周期循环——它们标记控制循环边界。
3. 读 Informer 理解"为什么控制器不压垮 apiserver"。
4. 改插件时 clone `scheduler-plugins`，按 `pkg/coscheduling` 读最快。

## 11.6 工具与生态（动手必备）

| 工具 | 用途 |
|---|---|
| **kind / minikube** | 本地起测试集群（学习必备） |
| **k9s** | 终端 TUI，比 `kubectl` 高效十倍 |
| **kubectx / kubens** | 快速切集群/namespace |
| **Helm** | 包管理，部署复杂应用（[Helm 主题](../helm/)） |
| **Operator 模式** | CRD + 控制循环，把领域运维知识编码成自愈系统（[Operator 主题](../operator/)） |
| **ArgoCD / Flux** | GitOps 持续部署 |
| **kubectl-neat / kubent** | 清理冗余字段 / 查弃用 API |
| **Prometheus + Grafana** | 监控标配 |
| **Lens / k9s** | GUI/TUI 集群管理 |

**学习建议**：本地装 kind + k9s，把本手册第 7 章的演示场景在真实集群复现一遍（写 Deployment/PyTorchJob/GPU Pod），对照 `kubectl describe` 与模拟器输出，理解会立体很多。

## 11.7 与本手册其他主题的交叉引用

Kubernetes 是 AI 基础设施的底座，几乎所有上层主题都建立在它之上：

| 主题 | 与 K8s 的衔接 | 阅读建议 |
|---|---|---|
| **[容器运行时](/02-cloud-native/container-runtime/)** | K8s 不启动容器，通过 CRI 把运行委托给 containerd/CRI-O；运行时是 K8s 之下的执行层 | 先读本主题的调度（第 5、7 章），再读容器运行时的 CRI/dockershim 与镜像优化 |
| **[GPU 架构与 CUDA 基础](/01-foundation/gpu-cuda/)** | K8s 负责把 GPU 资源分配给 Pod，GPU/CUDA 主题解释 GPU 内部执行模型、Tensor Core、NCCL、MIG/MPS/DCGM | 两主题互补：K8s 讲“怎么调度 GPU”，GPU/CUDA 讲“GPU 被调度后内部发生什么” |
| **[Linux 系统与性能调优](/01-foundation/linux-systems/)** | K8s 的 CPU/memory 限制、QoS、Device Plugin 最终通过 Linux cgroup 生效；本主题是 K8s 资源管理的内核视角 | 读 Linux 系统调优理解 kubelet 写完 `cpu.cfs_quota_us` 后内核发生了什么 |
| **[Ray / KubeRay](/03-ai-platform/ray/)** | RayCluster CRD 把 Ray 集群跑在 K8s 上，Ray 自带 actor 级调度与 K8s Pod 调度协作 | 先读本主题的调度（第 5、7 章），再读 Ray 的 autoscaler |
| **[vLLM](/04-llmops/vllm/)** | vLLM 作为 Deployment/Service 跑在 K8s，靠 K8s 的探针/滚动/扩缩管理生命周期 | vLLM 的 continuous batching 提 GPU 利用率，K8s 负责编排 |
| **Triton** | 多 backend 推理服务，Instance Group 对应 K8s 调度 | 见 [Triton](/04-llmops/triton/) |
| **KServe** | 基于 Knative 的 Serverless 推理，深度依赖 K8s CRD + 自动扩缩 | LLMOps 篇（待补充） |
| **[LLM Gateway](/04-llmops/)** | 用 K8s Ingress/Gateway API 做七层路由 | Gateway API 是 Ingress 演进 |
| **[案例研究：Meta / Google](/09-case-study/)** | Borg 是 K8s 祖先；Meta 的 cluster management 与 K8s 对照 | 读 Borg 论文理解 K8s 设计根源 |
| **[AI SRE / 可观测性](/07-ai-sre/)** | K8s 监控（Prometheus/DCGM）是 AI 平台 SRE 的核心 | 本主题第 8 章可观测性是衔接点 |

## 11.8 推荐学习路径

根据你的背景，推荐两条路径：

### 路径 A：AI 工程师补 K8s（已有 ML 背景）

1. 本主题第 1–4 章（背景 → 核心思想 → 架构 → 运行流程）—— 建立 K8s 心智模型。
2. 第 7 章 Mini-Demo —— 动手跑通调度/GPU/Gang。
3. 第 8 章生产实践 + 第 9 章最佳实践 —— 知道怎么在 K8s 上跑 AI 工作负载。
4. 跳到 [Ray / KubeRay](/03-ai-platform/ray/)、[vLLM](/04-llmops/vllm/) —— 看上层如何用 K8s。
5. 需要时回查第 5 章（模块）、第 10 章（面试）。

### 路径 B：平台/SRE 工程师深入 K8s

1. 本主题第 1–6 章（含源码分析）—— 打深基础。
2. 第 8 章生产 + [AI SRE](/07-ai-sre/) 主题 —— 生产运维。
3. 官方文档概念 + KEP-624/4671 + scheduler-plugins 源码 —— 调度专精。
4. Borg/Omega 论文 + Meta/Google 案例研究 —— 设计哲学。
5. 自研 Operator（controller-runtime）实践。

### 路径 C：快速入门（只想用起来）

1. 本主题 index + 第 2 章（核心思想）+ 第 4 章（运行流程）。
2. 本地装 kind，跟着第 7 章跑 mini-demo，再在 kind 上复现。
3. 第 8 章 8.1–8.3 节（集群底座 + GPU + 训练）够用起步。

## 本章小结

Kubernetes 的学习是一场马拉松，本主题为你打了地基（动机→架构→源码→实践→生产），但要精通还需持续深入：官方文档当字典查、Borg/Omega 论文理解设计哲学、KEP 与 scheduler-plugins 追踪调度前沿、controller-runtime 让你能写 Operator。对 AI 方向的读者，重点是**调度（Gang/拓扑/公平）+ 设备管理（Device Plugin/MIG/MPS）**这两个特化方向，并顺着本手册的 [Helm](../helm/)、Ray、vLLM、Triton、KServe 主题看 K8s 如何被上层使用。最重要的是**动手**——本地装 kind，把本主题的每个概念都跑一遍，远比读十遍文档有效。Kubernetes 是 AI 基础设施的通用语言，掌握它，你就拥有了理解和构建任何 AI 平台的能力。

**参考来源**

- [Kubernetes 官方文档](https://kubernetes.io/zh-cn/docs/home/)
- [Borg 论文（EuroSys'15）](https://research.google/pubs/pub43438/)
- [《Borg, Omega, and Kubernetes》（ACM Queue 2016）](https://research.google/pubs/pub49374/)
- [KEP-624 Scheduling Framework](https://github.com/kubernetes/enhancements/blob/master/keps/sig-scheduling/624-scheduling-framework/)
- [kubernetes-sigs/scheduler-plugins](https://scheduler-plugins.sigs.k8s.io/)
- [Volcano](https://volcano.sh/en/docs/)
- [NVIDIA GPU Operator](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/overview.html)
- [kubernetes/kubernetes 源码](https://github.com/kubernetes/kubernetes)
- [kubernetes-sigs/controller-runtime](https://github.com/kubernetes-sigs/controller-runtime)

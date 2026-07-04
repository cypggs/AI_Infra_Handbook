# Kubernetes 总览

> 一句话理解：**Kubernetes 是一个声明式、控制循环驱动的容器编排系统**——你告诉它"我想要 3 个副本的推理服务运行在带 GPU 的节点上"，它通过 apiserver / etcd / scheduler / controller / kubelet 一组解耦的组件，持续把"期望状态"收敛为"观测状态"，并在硬件、网络、存储、GPU 等异构资源上做调度与生命周期管理。

## 为什么 AI 平台工程师必须懂 Kubernetes

今天几乎所有的 AI 平台（Kubeflow、KServe、Ray on K8s / KubeRay、vLLM/Triton 的生产部署、Training Operator、Volcano、各云的 MLOps 平台）都构建在 Kubernetes 之上。原因不是"K8s 适合跑 AI"，而是：

1. **统一的资源抽象**：CPU/GPU/内存/存储/网络都被抽象成可声明、可调度、可配额的资源。
2. **声明式 + 自愈**：节点宕机、Pod 崩溃、镜像拉取失败，控制器会自动把系统拉回期望状态——这对长时间运行的训练 Job 和推理服务至关重要。
3. **可扩展性**：CRD + Operator + 调度框架让平台团队可以把领域逻辑（如"分布式训练的 all-or-nothing 调度"）注入 K8s，而不必 fork 核心。
4. **生态事实标准**：监控（Prometheus）、日志（Loki/Fluentd）、CI/CD（ArgoCD）、服务网格（Istio）、GitOps 都默认以 K8s 为集成目标。

不懂 K8s 的 AI 平台工程师，会被限制在"用别人的平台"的层面，无法设计、调优、排障底层调度与资源治理。

## 学习目标

阅读完本主题后，你应该能够：

1. 解释 Kubernetes 的核心抽象：声明式 API、控制循环、Pod、Controller、Operator。
2. 画出控制平面（apiserver / etcd / scheduler / controller-manager）与节点（kubelet / kube-proxy / CRI）的完整架构，并描述一个 Pod 从 `kubectl apply` 到 Running 的全链路。
3. 说清楚 kube-scheduler 的**调度框架（Scheduling Framework）**：调度周期 vs 绑定周期、12 个扩展点、Filter/Score/PostFilter 插件如何决定 Pod 落在哪个节点。
4. 理解 CRI / CNI / CSI 三大接口边界，以及为什么"没有 CNI 集群就起不来"。
5. 在 K8s 上调度 GPU：Device Plugin、GPU Operator、MIG/MPS、拓扑感知调度、Gang Scheduling（Volcano / scheduler-plugins / v1.36 原生 PodGroup）。
6. 用 Controller / Operator 模式（CRD + reconcile loop）实现自定义自动化，理解它与"写脚本"的本质区别。
7. 跑通并扩展本主题的 Mini Demo——一个纯 Python、无需真实集群的微型 kube-scheduler + Deployment 控制器 + GPU 调度模拟器。
8. 回答生产部署、etcd 容量、网络/存储选型、多租户隔离、AI 负载调度相关的面试问题。

## Kubernetes 与其他主题的关系

| 主题 | 解决的核心问题 | 与 Kubernetes 的关系 |
|---|---|---|
| [Foundation](/01-foundation/) | Linux / 网络 / 存储 / GPU 硬件基础 | K8s 运行在这些基础之上；GPU/NVLink/RDMA 都通过 Device Plugin + CNI 暴露给 Pod |
| [GPU 架构与 CUDA 基础](/01-foundation/gpu-cuda/) | GPU 硬件架构、CUDA 编程模型、NVIDIA 软件栈 | K8s 调度 GPU Pod 后，任务在 GPU 内部按 SIMT/Warp/SM 执行；MIG/MPS/DCGM 等概念是两主题的交叉点 |
| [容器运行时](/02-cloud-native/container-runtime/) | 镜像管理 + 容器生命周期（namespace/cgroup/overlayfs、OCI、containerd/runc） | K8s 通过 CRI 调用容器运行时；运行时是 K8s 之下的执行层，本主题的"CRI 一节"与运行时主题互补 |
| **Kubernetes** | 声明式编排、调度、生命周期、资源治理 | 本主题，AI 平台的底座 |
| [Ray](/03-ai-platform/ray/) | 分布式 Python 计算 | KubeRay 把 Ray Cluster 作为 CRD 跑在 K8s 上；Ray Serve/Train 依赖 K8s 做部署与弹性 |
| [vLLM](/04-llmops/vllm/) / [Triton](/04-llmops/triton/) | 单实例推理引擎 | 生产部署在 K8s 上，通过 Deployment/StatefulSet + GPU 资源声明 + HPA 扩缩 |
| [LLM Gateway](/04-llmops/llm-gateway/) | 多模型统一接入 | Gateway 通常以 Ingress / Gateway API / Service Mesh 形式接入 K8s |
| [AI SRE](/07-ai-sre/) | 可观测、SLO、事故响应 | K8s 的 Prometheus / kube-state-metrics / OpenTelemetry 是 AI SRE 的数据源 |
| [安全](/08-security/) | IAM、Secrets、Zero Trust | K8s 的 RBAC、NetworkPolicy、Pod Security Admission、Secret/Sealed-Secrets 是执行点 |
| [Meta](/09-case-study/meta/) / [Google](/09-case-study/google/) | 超大规模训练基础设施 | 它们的内部编排（Twine/Borg）思想与 K8s 同源，但规模与硬件协同设计远超开源 K8s |

## 本章结构

1. [背景](01-background) — 从物理机/VM 到容器编排的演进，为什么 K8s 赢，它解决的核心问题。
2. [核心思想](02-core-ideas) — 声明式 API、控制循环、最终一致性、Pod、Controller、Operator、扩展性（CRD/CNI/CSI/CRI）。
3. [架构设计](03-architecture) — 控制平面 vs 节点，组件解耦，一个 Pod 的完整生命周期。
4. [Runtime 工作流程](04-runtime-workflow) — `kubectl apply` → apiserver → etcd → scheduler → kubelet → CRI/CNI/CSI 全链路。
5. [核心模块](05-core-modules) — apiserver、etcd、scheduler（调度框架）、controller-manager、kubelet、kube-proxy、CRI、CNI、CSI、DNS、Ingress/Gateway API、HPA/VPA、RBAC、Admission。
6. [源码分析](06-source-analysis) — `kubernetes/kubernetes` 仓库结构、调度框架源码、Controller 模式源码、kubelet PLEG/syncPod。
7. [工程实践](07-mini-demo) — 纯 Python 可运行的微型 K8s 调度器 + 控制器 + GPU 调度 Mini Demo。
8. [企业生产实践](08-production-practice) — 自建 vs 托管 vs Serverless、控制平面高可用、etcd 调优、网络/存储选型、GPU 调度、多租户、Volcano/Training Operator。
9. [最佳实践](09-best-practices) — 资源声明、调度策略、镜像、安全、可观测、AI 负载调优。
10. [面试题](10-interview-questions) — 初/中/高级面试题。
11. [延伸阅读](11-further-reading) — 官方文档、KEP、论文、源码、生产实践。

## 一句话总结

Kubernetes 不是"容器运行时"，而是**把"期望状态"持续收敛为"实际状态"的控制平面**——它的每一个组件（apiserver 是入口、etcd 是真相、scheduler 是决策、controller 是闭环、kubelet 是执行）都在为"声明式 + 最终一致性"这一核心思想服务；理解了这一点，调度 GPU、写 Operator、排障 Pod 卡在 Pending 都只是同一套模型的不同投影。

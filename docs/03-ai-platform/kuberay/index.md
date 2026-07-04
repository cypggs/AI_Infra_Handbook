# KubeRay

> 一句话理解：**KubeRay 是 Ray 在 Kubernetes 上的官方 Operator**，它把 Ray 集群的创建、扩缩容、作业提交、Serve 部署和故障恢复翻译成 K8s 的声明式资源（CRD）与控制器循环。

## 学习目标

读完本主题后，你应该能够：

1. 解释为什么要在 K8s 上运行 Ray，以及 KubeRay 解决了哪些手工部署痛点。
2. 掌握 `RayCluster`、`RayJob`、`RayService` 三个核心 CRD 的语义与关键字段。
3. 描述 KubeRay Operator 的架构：controller-runtime、Reconciler、Informer、Workqueue。
4. 理解 RayCluster 创建、Worker 扩缩容、RayJob 提交、RayService 升级的完整生命周期。
5. 熟悉源码主入口与关键调用链。
6. 具备在 K8s 上部署和运维 KubeRay 生产环境的能力：GCS FT、自动扩缩、GPU/TPU、监控、多租户。
7. 通过 Mini Demo 在本地模拟 KubeRay 控制平面的核心行为。

## 与相邻主题的关系

| 主题 | 关系 |
|---|---|
| [Ray](../ray/) | KubeRay 是 Ray 在 Kubernetes 上的部署形态，Ray 的核心概念（GCS、Raylet、Autoscaler、Placement Group）先在 Ray 主题中讲解。 |
| [Kubernetes](../../02-cloud-native/kubernetes/) | KubeRay 基于 K8s 的 CRD、Controller、Scheduler、Service、RBAC 构建。 |
| [Operator 模式](../../02-cloud-native/operator/) | KubeRay 本身就是一个典型 Operator：声明式 API + 调和循环。 |
| [KServe](../kserve/) | KServe 可加载 Ray Serve 端点；RayService 可与 KServe InferenceGraph 组合。 |
| [MLflow](../mlflow/) | 训练实验可在 KubeRay 集群上运行，模型注册到 MLflow 后再由 Ray Serve 或 KServe 加载。 |
| [AI SRE](../../07-ai-sre/) | KubeRay 生产环境需要 Prometheus/Grafana、SLO 与告警。 |

## 本章结构

1. [背景](01-background) — 从裸机 Ray 到 K8s 上 Ray 的演进，KubeRay 的定位与价值。
2. [核心思想](02-core-ideas) — CRD 抽象、Head/Worker 映射、自动扩缩、GCS 容错、声明式升级。
3. [架构设计](03-architecture) — Operator 分层、controller-runtime 组件、与 K8s API Server 交互。
4. [Runtime 工作流程](04-runtime-workflow) — RayCluster、RayJob、RayService 生命周期与状态机。
5. [核心模块](05-core-modules) — CRD、Reconciler、Common 构建包、Batch Scheduler、Autoscaler、APIServer。
6. [源码分析](06-source-analysis) — 仓库结构、main.go、三大 Reconciler 调用链、关键源码文件。
7. [Mini Demo](07-mini-demo) — 本地模拟 KubeRay 控制平面：创建集群、扩缩容、提交作业。
8. [企业生产实践](08-production-practice) — Helm 部署、GCS FT、GPU/TPU、资源隔离、安全、监控。
9. [最佳实践](09-best-practices) — Head 不跑任务、Worker Group 设计、镜像、扩缩容、Job 打包、升级。
10. [面试题](10-interview-questions) — 初/中/高级 KubeRay 面试题。
11. [延伸阅读](11-further-reading) — 官方文档、源码、论文、相关主题交叉引用。

## 一句话总结

**KubeRay 让 Ray 集群变成 Kubernetes 里的一份 YAML**：你描述 desired state，Operator 负责把 Head、Worker、Service、Autoscaler、Job、Serve 全部调和到现实状态，并在异常时自动恢复。

**参考来源**

- [KubeRay Docs — Welcome](https://ray-project.github.io/kuberay/)
- [Ray Docs — Ray on Kubernetes](https://docs.ray.io/en/latest/cluster/kubernetes/index.html)
- [KubeRay GitHub](https://github.com/ray-project/kuberay)

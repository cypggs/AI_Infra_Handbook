# Kubeflow：Kubernetes 上的机器学习平台

> 一句话理解：**Kubeflow 是把 Jupyter 开发、Pipeline 编排、超参搜索、分布式训练、模型服务串成一条生产级 ML 流水线的 K8s 原生平台**——它本身不是单一软件，而是一组 Operator 和 Web UI 的集合，目标让机器学习工作负载像 `Deployment` 一样在 Kubernetes 上声明式运行。

## 学习目标

读完本主题，你应该能：

1. 解释为什么需要 Kubeflow（裸跑 ML 工作负载的痛点）。
2. 说清 Kubeflow 的核心组件：Notebooks、Pipelines、Katib、Training Operator、KServe、Central Dashboard、Profiles。
3. 理解 Kubeflow Pipelines v2 的 DSL → Compiler → IR YAML → Run 的完整链路。
4. 理解 Katib 的 Experiment/Trial/Suggestion/Early Stopping 机制。
5. 理解 Training Operator 如何管理 TFJob/PyTorchJob/MPIJob/XGBoostJob。
6. 理解多租户模型：Profile、Namespace、KFAM、Istio 认证。
7. 了解 Kubeflow 源码主结构和关键控制器调用链。
8. 动手跑一个纯 Python mini-demo，模拟 Pipeline DAG、Katib 实验、TrainingJob、Profile。
9. 知道生产落地要点：安装方式选择、多租户、存储、artifact、升级、成本。

## 与相邻主题的关系

| 主题 | 关系 | 链接 |
|---|---|---|
| **Kubernetes** | Kubeflow 的底座：namespace、CRD、调度、存储、网络 | [Kubernetes](../../02-cloud-native/kubernetes/) |
| **Operator 模式** | Kubeflow 每个组件都是 Operator（Pipeline、Katib、Training Operator 等） | [Operator 模式](../../02-cloud-native/operator/) |
| **Helm** | 安装 Kubeflow 或其组件时可选用 Helm / Kustomize | [Helm](../../02-cloud-native/helm/) |
| **KServe** | Kubeflow 的模型服务组件 | [KServe](../kserve/) |
| **存储系统** | Pipeline artifact、Notebook PVC、训练 Job checkpoint 都依赖 K8s 存储选型 | [存储系统](../../01-foundation/storage-systems/) |
| **Ray** | 分布式训练/推理的补充，可与 Training Operator / KubeRay 组合 | [Ray](../ray/) |
| **MLflow** | 实验追踪与模型注册，常与 Kubeflow Pipelines 集成 | 计划中 |
| **AI SRE** | Kubeflow 生产环境的可观测、SLO、成本治理 | [AI SRE](../../07-ai-sre/) |

## 本章结构

| 章节 | 标题 | 内容 |
|---|---|---|
| 1 | [背景](01-background) | ML 工作负载的痛点、Kubeflow 诞生、与 Airflow/MLflow/KServe/Ray 的对比 |
| 2 | [核心思想](02-core-ideas) | Notebooks、Pipelines、Katib、Training Operator、KServe、Central Dashboard、Profiles |
| 3 | [架构设计](03-architecture) | 控制平面、组件交互、多租户与认证、存储与网络 |
| 4 | [Runtime 工作流程](04-runtime-workflow) | 从 Notebook 开发到 Pipeline Run → Katib 调参 → TrainingJob → KServe 部署 |
| 5 | [核心模块](05-core-modules) | Central Dashboard、Notebook Controller、Profile/KFAM、Pipelines 后端、Katib、Training Operator |
| 6 | [源码分析](06-source-analysis) | kubeflow/pipelines、training-operator、katib、manifests 关键源码与调用链 |
| 7 | [Mini Demo](07-mini-demo) | 纯 Python 模拟 Pipeline DAG、Katib Experiment、TrainingJob、Profile |
| 8 | [企业生产实践](08-production-practice) | 安装方式、多租户、认证、存储、artifact、监控、升级 |
| 9 | [最佳实践](09-best-practices) | Pipeline 版本、缓存、可复现、资源配额、安全、成本 |
| 10 | [面试题](10-interview-questions) | 初/中/高级 Kubeflow 高频题 |
| 11 | [延伸阅读](11-further-reading) | 官方文档、论文/博客、生态工具、学习路径 |

## 一句话总结

**Kubeflow = Kubernetes 上的 ML 生命周期操作系统**：Notebook 做开发、Pipelines 做编排、Katib 做搜索、Training Operator 做分布式训练、KServe 做服务、Central Dashboard 做入口——全部通过 CRD 和 Operator 跑在 K8s 上。

## 参考来源

- [Kubeflow 官网](https://www.kubeflow.org/)
- [Kubeflow GitHub](https://github.com/kubeflow/kubeflow)
- [Kubeflow Pipelines GitHub](https://github.com/kubeflow/pipelines)
- [Kubeflow Katib GitHub](https://github.com/kubeflow/katib)
- [Kubeflow Training Operator GitHub](https://github.com/kubeflow/training-operator)
- 本手册 [Operator 模式](../../02-cloud-native/operator/)、[KServe](../kserve/)、[Ray](../ray/)、[Kubernetes](../../02-cloud-native/kubernetes/)

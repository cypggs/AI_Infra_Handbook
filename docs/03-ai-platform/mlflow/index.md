# MLflow：机器学习生命周期管理平台

> 一句话理解：**MLflow 是 ML 世界的“版本控制系统”——它不负责训练或推理的执行，而是把实验、参数、指标、模型 artifact、版本和部署链路统一记录起来，让模型从实验室到生产线可追踪、可复现、可回滚**。

## 学习目标

读完本主题，你应该能：

1. 解释为什么需要 MLflow（实验不可复现、模型版本混乱、部署链路断裂）。
2. 说清 MLflow 四大核心组件：Tracking、Projects、Models、Model Registry。
3. 理解 Tracking 的核心概念：Experiment、Run、Metric、Parameter、Artifact、Tag。
4. 理解 Model Registry 的核心概念：Registered Model、Model Version、Stage、Alias、Tag。
5. 理解 MLflow Model 的 flavor、signature、input example、conda/env 依赖封装。
6. 理解 Tracking Server / Backend Store / Artifact Store 三层架构。
7. 了解 MLflow 源码主结构和关键调用链。
8. 动手跑一个本地 MLflow Mini Demo：训练 sklearn 模型、记录实验、注册模型、加载预测、切换版本。
9. 知道生产落地要点：部署形态、数据库选择、artifact 存储、认证、与 Kubeflow/KServe 集成。

## 与相邻主题的关系

| 主题 | 关系 | 链接 |
|---|---|---|
| **Kubeflow** | Kubeflow 编排训练/推理工作负载，MLflow 追踪实验与注册模型，两者常互补集成 | [Kubeflow](../kubeflow/) |
| **KServe** | KServe 可加载 `models:/name/version` 格式的 MLflow 模型作为在线服务 | [KServe](../kserve/) |
| **Ray** | Ray Train/Tune 可把实验记录到 MLflow | [Ray](../ray/) |
| **Kubernetes** | 生产部署 MLflow Tracking Server 常跑在 K8s 上 | [Kubernetes](../../02-cloud-native/kubernetes/) |
| **存储系统** | Artifact Store 的底层是对象存储/文件系统；模型版本依赖持久化存储 | [存储系统](../../01-foundation/storage-systems/) |
| **AI SRE** | MLflow 生产环境的监控、SLO、成本治理 | [AI SRE](../../07-ai-sre/) |

## 本章结构

| 章节 | 标题 | 内容 |
|---|---|---|
| 1 | [背景](01-background) | ML 生命周期管理痛点、MLflow 诞生、与 Kubeflow/W&B/Neptune 的对比 |
| 2 | [核心思想](02-core-ideas) | Tracking、Projects、Models、Model Registry 四大组件与核心概念 |
| 3 | [架构设计](03-architecture) | Tracking Server、Backend Store、Artifact Store、REST API、UI |
| 4 | [Runtime 工作流程](04-runtime-workflow) | 一次完整实验 → 注册 → 部署的链路 |
| 5 | [核心模块](05-core-modules) | Fluent API、MlflowClient、Tracking Service、Model Registry Service、Artifact Repository、Model Flavors、PyFunc |
| 6 | [源码分析](06-source-analysis) | mlflow/tracking、mlflow/models、mlflow/store、mlflow/server 关键源码与调用链 |
| 7 | [Mini Demo](07-mini-demo) | 本地 SQLite + 文件 artifact，训练、记录、注册、加载、预测 |
| 8 | [企业生产实践](08-production-practice) | 部署形态、数据库、artifact 存储、认证、高可用、备份 |
| 9 | [最佳实践](09-best-practices) | 实验命名、参数/指标规范、模型签名、版本管理、与 CI/CD 集成 |
| 10 | [面试题](10-interview-questions) | 初/中/高级 MLflow 高频题 |
| 11 | [延伸阅读](11-further-reading) | 官方文档、论文/博客、生态工具、学习路径 |

## 一句话总结

**MLflow = 机器学习生命周期的事实记录层**：Tracking 记录每次实验，Models 封装模型与依赖，Model Registry 管理版本与阶段，Projects 保证代码可复现——它们共同让模型从“黑盒脚本”变成可追溯、可部署的资产。

## 参考来源

- [MLflow 官方文档](https://mlflow.org/docs/latest/index.html)
- [MLflow GitHub](https://github.com/mlflow/mlflow)
- [MLflow — What is MLflow?](https://mlflow.org/docs/latest/what-is-mlflow.html)
- 本手册 [Kubeflow](../kubeflow/)、[KServe](../kserve/)

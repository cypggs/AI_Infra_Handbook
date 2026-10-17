# Airflow：工作流编排平台

> 一句话理解：**Airflow 是数据与 ML 流水线的“调度指挥中心”——它用 Python 把任务写成 DAG，由 Scheduler 决定何时执行、由 Executor 决定在哪执行、由 Metadata Database 记录完整状态，让复杂的依赖、重试、回刷、监控变得可编排、可观测、可审计**。

## 学习目标

读完本主题，你应该能：

1. 解释为什么需要 Airflow（定时任务依赖复杂、失败重试不可控、脚本散落、可观测性差）。
2. 说清 Airflow 3 核心组件：API Server（FastAPI）、Scheduler、DAG Processor、Executor、Worker、Metadata Database、Triggerer。
3. 理解 DAG、Operator、Task、TaskInstance、DAG Run 的关系与生命周期。
4. 理解 Executor 的选型差异：Sequential、Local、Celery、Kubernetes、Edge（3.x），以及多 Executor。
5. 理解 XCom 的作用、默认限制与自定义后端。
6. 理解 Deferrable Operator / Triggerer 如何释放 worker 槽位。
7. 了解 Airflow 3 的关键演进：Task SDK + Task Execution API（AIP-72）、Edge Executor（AIP-69）、Asset/分区调度、HITL（3.1）、状态存储（3.3），3.4 预览（Task Loops AIP-111、Dag Importer AIP-85），以及 2→3 迁移要点。
8. 动手跑一个本地 Airflow Mini Demo：定义 DAG、调度执行、状态流转、XCom、defer 触发器。
9. 知道生产落地要点：数据库、Executor、监控、高可用、托管服务、与 Kubeflow/MLflow 集成。

## 与相邻主题的关系

| 主题 | 关系 | 链接 |
|---|---|---|
| **Kubeflow** | Kubeflow Pipelines 负责 ML 工作流；可与 Airflow 互补或替代 | [Kubeflow](../kubeflow/) |
| **MLflow** | Airflow 编排训练/数据处理，MLflow 记录实验与注册模型 | [MLflow](../mlflow/) |
| **KubeRay** | Ray 作业可作为 Airflow 任务执行 | [KubeRay](../kuberay/) |
| **KServe** | Airflow 编排模型部署流水线，KServe 负责服务 | [KServe](../kserve/) |
| **Kubernetes** | KubernetesExecutor / CeleryExecutor on K8s 的常见底座 | [Kubernetes](../../02-cloud-native/kubernetes/) |
| **存储系统** | XCom 与 Dataset/Asset 调度依赖持久化存储；大任务结果常外置到对象存储 | [存储系统](../../01-foundation/storage-systems/) |
| **AI SRE** | Airflow 生产环境的监控、告警、SLO | [AI SRE](../../07-ai-sre/) |

## 本章结构

| 章节 | 标题 | 内容 |
|---|---|---|
| 1 | [背景](01-background) | 数据/ML 流水线痛点、Airflow 诞生、与 Cron/Kubeflow/Prefect/Dagster 的对比 |
| 2 | [核心思想](02-core-ideas) | DAG、Operator、Task、TaskInstance、DAG Run、Executor、XCom、Deferrable Operator、Dataset |
| 3 | [架构设计](03-architecture) | Airflow 3 服务化架构：API Server（FastAPI + React UI）、DAG Processor、Scheduler、Executor、Worker、Metadata DB、Triggerer、Task Execution API |
| 4 | [调度工作流程](04-scheduling-workflow) | DAG 文件 → 序列化 → Scheduler → DAG Run → Task Instance → Executor → 状态流转、重试、回刷、Asset 事件驱动 |
| 5 | [核心模块](05-core-modules) | DAG Processor、Scheduler、Executor、Task Runner、XCom、Triggerer、Plugins、Connections |
| 6 | [源码分析](06-source-analysis) | airflow-core / task-sdk / providers monorepo、Execution API、关键调用链 |
| 7 | [Mini Demo](07-mini-demo) | 本地 SQLite + Python 模拟 Scheduler/Executor/XCom/Triggerer，跑通 DAG 生命周期 |
| 8 | [企业生产实践](08-production-practice) | Metadata DB、Executor 选型、K8s/Edge 部署、认证（JWT/API token）、监控、高可用、托管服务、2→3 迁移 |
| 9 | [最佳实践](09-best-practices) | DAG 设计、依赖管理、Asset 触发、HITL、状态存储、测试、迁移检查 |
| 10 | [面试题](10-interview-questions) | 初/中/高级 Airflow 高频题（含 Airflow 3 架构与迁移） |
| 11 | [延伸阅读](11-further-reading) | 官方文档、论文/博客、生态工具、学习路径 |

## 一句话总结

**Airflow = Python 定义 + 数据库存储 + 调度器驱动 + 执行器分发的工作流编排平台**：DAG 描述任务依赖，Scheduler 决定何时运行，Executor 决定在哪运行，Metadata Database 记录所有状态，XCom 传递任务数据，Triggerer 让异步等待不浪费 worker 资源。

## 参考来源

- [Apache Airflow 官方文档](https://airflow.apache.org/docs/apache-airflow/stable/index.html)
- [Apache Airflow GitHub](https://github.com/apache/airflow)
- [Astronomer — Airflow Components](https://www.astronomer.io/docs/learn/airflow-components)
- 本手册 [Kubeflow](../kubeflow/)、[MLflow](../mlflow/)

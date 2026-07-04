# Airflow：工作流编排平台

> 一句话理解：**Airflow 是数据与 ML 流水线的“调度指挥中心”——它用 Python 把任务写成 DAG，由 Scheduler 决定何时执行、由 Executor 决定在哪执行、由 Metadata Database 记录完整状态，让复杂的依赖、重试、回刷、监控变得可编排、可观测、可审计**。

## 学习目标

读完本主题，你应该能：

1. 解释为什么需要 Airflow（定时任务依赖复杂、失败重试不可控、脚本散落、可观测性差）。
2. 说清 Airflow 核心组件：Webserver/API Server、Scheduler、Executor、Worker、Metadata Database、Triggerer、DAG Processor。
3. 理解 DAG、Operator、Task、TaskInstance、DAG Run 的关系与生命周期。
4. 理解 Executor 的选型差异：Sequential、Local、Celery、Kubernetes、Dask，以及 Airflow 2.10+ 的多 Executor。
5. 理解 XCom 的作用、默认限制与自定义后端。
6. 理解 Deferrable Operator / Triggerer 如何释放 worker 槽位。
7. 了解 Dataset/Asset 调度与 Airflow 3 Execution API / JWT 的变化方向。
8. 动手跑一个本地 Airflow Mini Demo：定义 DAG、调度执行、状态流转、XCom、defer 触发器。
9. 知道生产落地要点：数据库、Executor、监控、高可用、与 Kubeflow/MLflow 集成。

## 与相邻主题的关系

| 主题 | 关系 | 链接 |
|---|---|---|
| **Kubeflow** | Kubeflow Pipelines 负责 ML 工作流；可与 Airflow 互补或替代 | [Kubeflow](../kubeflow/) |
| **MLflow** | Airflow 编排训练/数据处理，MLflow 记录实验与注册模型 | [MLflow](../mlflow/) |
| **KubeRay** | Ray 作业可作为 Airflow 任务执行 | [KubeRay](../kuberay/) |
| **KServe** | Airflow 编排模型部署流水线，KServe 负责服务 | [KServe](../kserve/) |
| **Kubernetes** | KubernetesExecutor / CeleryExecutor on K8s 的常见底座 | [Kubernetes](../../02-cloud-native/kubernetes/) |
| **AI SRE** | Airflow 生产环境的监控、告警、SLO | [AI SRE](../../07-ai-sre/) |

## 本章结构

| 章节 | 标题 | 内容 |
|---|---|---|
| 1 | [背景](01-background) | 数据/ML 流水线痛点、Airflow 诞生、与 Cron/Kubeflow/Prefect/Dagster 的对比 |
| 2 | [核心思想](02-core-ideas) | DAG、Operator、Task、TaskInstance、DAG Run、Executor、XCom、Deferrable Operator、Dataset |
| 3 | [架构设计](03-architecture) | Webserver/API Server、Scheduler、Executor、Worker、Metadata DB、Triggerer、DAG Processor |
| 4 | [调度工作流程](04-scheduling-workflow) | DAG 文件 → DAG Bag → 序列化 → Scheduler → DAG Run → Task Instance → Executor → 状态流转 |
| 5 | [核心模块](05-core-modules) | DAG Processor、Scheduler、Executor、Task Runner、XCom、Triggerer、Plugins、Connections |
| 6 | [源码分析](06-source-analysis) | airflow/models、airflow/jobs/scheduler_job.py、airflow/executors、airflow/providers 关键源码与调用链 |
| 7 | [Mini Demo](07-mini-demo) | 本地 SQLite + Python 模拟 Scheduler/Executor/XCom/Triggerer，跑通 DAG 生命周期 |
| 8 | [企业生产实践](08-production-practice) | Metadata DB、Executor 选型、K8s 部署、监控、高可用、安全 |
| 9 | [最佳实践](09-best-practices) | DAG 设计、依赖管理、回填、传感器、资源隔离、测试、版本升级 |
| 10 | [面试题](10-interview-questions) | 初/中/高级 Airflow 高频题 |
| 11 | [延伸阅读](11-further-reading) | 官方文档、论文/博客、生态工具、学习路径 |

## 一句话总结

**Airflow = Python 定义 + 数据库存储 + 调度器驱动 + 执行器分发的工作流编排平台**：DAG 描述任务依赖，Scheduler 决定何时运行，Executor 决定在哪运行，Metadata Database 记录所有状态，XCom 传递任务数据，Triggerer 让异步等待不浪费 worker 资源。

## 参考来源

- [Apache Airflow 官方文档](https://airflow.apache.org/docs/apache-airflow/stable/index.html)
- [Apache Airflow GitHub](https://github.com/apache/airflow)
- [Astronomer — Airflow Components](https://www.astronomer.io/docs/learn/airflow-components)
- 本手册 [Kubeflow](../kubeflow/)、[MLflow](../mlflow/)

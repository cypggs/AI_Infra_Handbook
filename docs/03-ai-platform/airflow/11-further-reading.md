# 11. 延伸阅读与总结

> 一句话理解：Airflow 不是孤立工具，它与 **Kubeflow、MLflow、KServe、dbt、Spark、Kubernetes** 等共同构成 AI 平台与数据工程工具链；学完本章后，建议沿着“单机使用 → 生产部署 → 生态集成”的路线继续深入。

## 11.1 核心官方资源

| 资源 | 说明 |
|---|---|
| [Apache Airflow 官方文档](https://airflow.apache.org/docs/apache-airflow/stable/index.html) | 最权威、最及时的参考 |
| [Apache Airflow GitHub](https://github.com/apache/airflow) | 源码、issue、release note |
| [Airflow Quickstart](https://airflow.apache.org/docs/apache-airflow/stable/start.html) | 本地快速上手 |
| [Airflow Providers](https://airflow.apache.org/docs/apache-airflow-providers/) | 官方 provider 包文档 |
| [Astronomer 文档](https://www.astronomer.io/docs/) | 商业化托管与最佳实践 |

## 11.2 关键概念文档

| 资源 | 说明 |
|---|---|
| [DAGs](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dags.html) | DAG 定义、调度、依赖、Task Group |
| [Operators](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/operators.html) | Operator 概念与自定义 |
| [Tasks](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/tasks.html) | Task 与 TaskInstance |
| [DAG Runs](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dag-run.html) | DAG Run 与 execution date |
| [Executors](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/executor/index.html) | 各种 Executor 对比 |
| [XComs](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/xcoms.html) | 任务间数据交换 |
| [Scheduler](https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/scheduler.html) | Scheduler 工作原理与调优 |
| [DAG File Processing](https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/dag-file-processing.html) | DAG Processor 解析流程 |
| [DAG Serialization](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dags.html#dag-serialization) | DAG 序列化机制 |
| [Deferrable Operators](https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/deferring.html) | Defer 与 Triggerer |
| [Datasets](https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/datasets.html) | 数据驱动调度 |
| [Database Setup](https://airflow.apache.org/docs/apache-airflow/stable/howto/set-up-database.html) | Metadata DB 配置 |

## 11.3 相邻主题交叉引用

| 主题 | 关系 | 链接 |
|---|---|---|
| Kubeflow | ML 工作流编排，可与 Airflow 互补或替代 | [Kubeflow 总览](../kubeflow/index.md) |
| MLflow | Airflow 编排训练，MLflow 记录实验/注册模型 | [MLflow 总览](../mlflow/index.md) |
| KubeRay | Ray 作业可作为 Airflow 任务执行 | [KubeRay 总览](../kuberay/index.md) |
| KServe | Airflow 编排模型部署，KServe 负责服务 | [KServe 总览](../kserve/index.md) |
| Kubernetes | KubernetesExecutor / Celery on K8s 底座 | [Kubernetes 总览](../../02-cloud-native/kubernetes/index.md) |
| Operator 模式 | Airflow 自身也依赖 K8s Operator 部署 | [Operator 模式总览](../../02-cloud-native/operator/index.md) |
| AI SRE | Airflow 生产监控、告警、SLO | [AI SRE 总览](../../07-ai-sre/index.md) |

## 11.4 进阶论文、博客与演讲

| 类型 | 资源 | 看点 |
|---|---|---|
| 论文 | [Airbnb 博客 — Airflow 起源](https://medium.com/airbnb-engineering/airflow-a-workflow-management-platform-46318b977fd8) | Airflow 最初设计动机 |
| 实践 | [Astronomer — Airflow Best Practices](https://www.astronomer.io/docs/learn/airflow-best-practices/) | 企业级最佳实践 |
| 对比 | [Prefect vs Airflow](https://www.prefect.io/guide/blog/prefect-vs-airflow/) | 现代编排工具对比 |
| 对比 | [Dagster vs Airflow](https://dagster.io/blog/dagster-vs-airflow) | 数据资产视角对比 |
| 工程 | [Spotify 数据平台实践](https://engineering.atspotify.com/) | 大规模 Airflow 使用经验 |
| 工程 | [Netflix 数据流水线](https://netflixtechblog.com/) | 高可用编排实践 |

## 11.5 推荐学习路径

1. **第 1 周**：精读本主题 01-05 章，运行 Mini Demo。
2. **第 2 周**：读 06 源码分析 + 07-09 生产与最佳实践；尝试用 LocalExecutor + PostgreSQL 本地部署 Airflow。
3. **第 3 周**：写一个自己的 DAG，接入 MLflow/KServe 或 dbt/Spark；尝试 KubernetesExecutor。
4. **第 4 周**：读官方 release note，关注 Airflow 3 的 Execution API、JWT、Asset 演进。

## 11.6 一句话总结

Airflow 是数据与 ML 流水线的“调度指挥中心”：

- **DAG** 用 Python 描述任务依赖；
- **Scheduler** 决定何时运行；
- **Executor** 决定在哪运行；
- **Metadata Database** 记录所有状态；
- **XCom** 传递任务数据；
- **Triggerer** 让异步等待不浪费资源。

它与 Kubeflow、MLflow、KServe、Kubernetes 等工具组合，构成从数据摄取到模型部署的完整 AI 基础设施链路。

## 本章小结

- 官方文档和 GitHub 是最权威的学习来源。
- Airflow 与 Kubeflow、MLflow、KServe、Kubernetes、AI SRE 等主题紧密相连。
- 学习路径遵循：本地 Demo → 自定义 DAG → 生产部署 → 生态集成 → 关注 Airflow 3 演进。

**参考来源**

- [Apache Airflow 官方文档](https://airflow.apache.org/docs/apache-airflow/stable/index.html)
- [Apache Airflow GitHub](https://github.com/apache/airflow)
- [Astronomer — Airflow Components](https://www.astronomer.io/docs/learn/airflow-components)
- 本手册相关主题总览

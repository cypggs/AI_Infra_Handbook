# 1. 背景：为什么需要 Airflow

> 一句话理解：当企业从“几个定时脚本”发展到“上百个相互依赖的数据清洗、训练、部署任务”时，**Cron 的线性调度能力会迅速崩溃**——Airflow 用 DAG 把依赖、重试、监控、回刷统一编排起来。

## 1.1 裸跑定时任务的痛苦

假设你负责一个推荐系统，每天需要：

1. 从 Kafka 拉取日志并写入数据湖。
2. 清洗、聚合、生成特征表。
3. 用特征表训练模型。
4. 评估模型，AUC 达标则注册到 MLflow。
5. 把模型部署到 KServe。
6. 发送完成通知。

用 Cron 或 Jenkins 拼接这些步骤时，常见痛点：

| 阶段 | 裸跑方式 | 痛点 |
|---|---|---|
| 依赖管理 | 每个任务写死前置任务的完成时间 | 上游延迟导致下游空跑或数据错误 |
| 失败处理 | 脚本失败发邮件，人工重跑 | 半夜告警、手动修复、错过 SLA |
| 重试策略 | 自己写 `for` 循环 + sleep | 重试次数、退避策略不一致 |
| 回刷/补数 | 手动修改日期参数逐个执行 | 容易遗漏、状态不可见 |
| 可观测性 | 分散的日志文件 | 无法一眼看清整条链路状态 |
| 扩展性 | 单台机器运行 | 任务多了资源争抢、无法水平扩展 |
| 协作 | 每人写自己的脚本 | 风格不一、难以维护 |

## 1.2 Airflow 是什么

Apache Airflow 是一个**开源的工作流编排平台**，最初由 Airbnb 在 2014 年开发，2016 年捐给 Apache 基金会。它的核心定位：

> **用 Python 代码定义任务依赖（DAG），由 Scheduler 自动调度、由 Executor 分发执行、由 Metadata Database 持久化状态，并提供 Web UI 做监控与运维**。

Airflow 的几个核心设计哲学：

- **Pipeline as Code**：DAG 是 Python 代码，可版本控制、可单元测试、可复用。
- **显式依赖**：任务之间的依赖关系在代码里清晰可见。
- **可观测性优先**：每个 DAG Run、每个 Task Instance 的状态、日志、时长都在 UI 上可见。
- **可扩展**：通过 Operator、Hook、Sensor、Executor 插件化扩展。

## 1.3 Airflow 与相邻工具的对比

| 工具 | 定位 | 与 Airflow 的关系 |
|---|---|---|
| **Cron** | 单机定时任务 | Airflow 替代 Cron 的复杂场景，提供更强大的依赖、重试、监控 |
| **Kubeflow Pipelines** | K8s 原生 ML 工作流 | 与 Airflow 功能重叠，KFP 更偏 ML/K8s，Airflow 更通用、生态更广 |
| **Prefect** | 现代 Python 工作流编排 | Prefect 2/3 更强调动态、云原生、去中心化；Airflow 更成熟、生态更丰富 |
| **Dagster** | 数据资产感知的编排 | Dagster 强调数据资产（asset）与数据质量；Airflow 2.4+ 也引入 Dataset/Asset 调度 |
| **Temporal / Cadence** | 微服务工作流引擎 | 更偏应用级长事务，Airflow 更偏数据/ETL/ML 批处理 |
| **Argo Workflows** | K8s 原生工作流 | 容器级工作流，与 Airflow 互补：Airflow 编排业务逻辑，Argo 执行容器任务 |
| **MLflow** | ML 生命周期管理 | Airflow 编排训练流程，MLflow 记录实验与注册模型 |
| **dbt** | 数据转换 | 常与 Airflow 集成：Airflow 调度 dbt 任务 |

**关键区分**：

- **Airflow vs Kubeflow Pipelines**：Airflow 通用，社区大、Operator 多；KFP 更适合完全 K8s 原生的 ML Pipeline。
- **Airflow vs Prefect**：Prefect 更现代、动态；Airflow 更成熟、企业采用率高。
- **Airflow vs Dagster**：Dagster 从数据资产视角设计；Airflow 从任务调度视角设计，近年也在补齐 asset 能力。

## 1.4 Airflow 解决了什么（和不解决什么）

**Airflow 解决**：

- ✅ 复杂任务依赖的显式表达与自动调度。
- ✅ 失败重试、告警、SLA 监控。
- ✅ 历史运行状态、日志、审计的可视化。
- ✅ 数据回刷（backfill）与补数。
- ✅ 水平扩展：通过 Celery/Kubernetes Executor 把任务分发到多台机器。
- ✅ 丰富的生态：AWS、GCP、Azure、Spark、Snowflake、dbt、MLflow 等官方 provider。

**Airflow 不解决**：

- ❌ 实时/流处理（需 Kafka/Flink/Spark Streaming）。
- ❌ 训练作业的 GPU 调度细节（需 K8s / Ray / Slurm）。
- ❌ 模型 serving 的自动扩缩（需 KServe/Triton）。
- ❌ 数据血缘与数据质量治理（需 OpenLineage / Great Expectations / dbt tests）。

## 1.5 AI 平台为什么需要 Airflow

一个成熟 AI 平台的编排层通常长这样：

```
数据源（Kafka / DB / 对象存储）
        │
        ▼
[数据摄取：Spark / Flink / 自定义脚本]
        │
        ▼
[特征工程：Spark SQL / dbt / Python]
        │
        ▼
[训练编排：Airflow / Kubeflow Pipelines]
        │  ├─ 调用 MLflow 记录实验
        │  ├─ 调用 Ray / KubeRay 分布式训练
        │  └─ 调用 Katib 超参搜索
        │
        ▼
[模型评估与注册：MLflow Model Registry]
        │
        ▼
[模型部署：KServe / Triton / 自研服务]
        │
        ▼
[监控与反馈：Prometheus / Grafana / A/B 测试]
```

Airflow 在这个链路里负责**把多个异构步骤按依赖关系串起来**：

- 对**数据工程师**：编排 ETL、dbt、Spark 任务。
- 对**ML 工程师**：编排训练、评估、注册、部署。
- 对**平台/SRE**：提供统一监控、告警、资源隔离、审计。

## 本章小结

- **痛点**：复杂依赖、失败处理、重试、回刷、可观测性是 Cron/脚本方案的瓶颈。
- **定位**：Airflow 是用 Python 代码定义 DAG 的开源工作流编排平台。
- **对比**：比 Cron 强大；比 Kubeflow Pipelines 更通用；比 Prefect/Dagster 更成熟、生态更广。
- **价值**：把散落脚本变成可编排、可观测、可扩展、可审计的流水线。

**参考来源**

- [Apache Airflow — What is Airflow?](https://airflow.apache.org/docs/apache-airflow/stable/index.html)
- [Apache Airflow — History](https://airflow.apache.org/docs/apache-airflow/stable/project.html)
- [Astronomer — Airflow Components](https://www.astronomer.io/docs/learn/airflow-components)
- 本手册 [Kubeflow](../kubeflow/)、[MLflow](../mlflow/)

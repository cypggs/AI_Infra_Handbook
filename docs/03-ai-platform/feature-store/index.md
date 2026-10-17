# 特征平台与训练数据基础设施

> 一句话理解：**特征平台（Feature Store）是 ML 特征从原始数据到在线服务的“唯一可信管道”——同一份特征逻辑只写一次，训练时用 point-in-time join 取历史值（不泄漏未来），服务时用低延迟 KV 取最新值（不读错数），从而系统性消灭训练/服务偏斜**。
>
> 2024-2026 年，随着 LLM 与 Agent 应用爆发，特征平台的定位正在从“ML 的基础设施”扩展为“**实时上下文引擎（real-time context engine）**”：embedding 成为一等公民特征，流式特征以亚秒级新鲜度喂给在线推理与 Agent 决策。标志性事件是 **2025 年 8 月 Databricks 宣布收购 Tecton**（Tecton 由 Uber Michelangelo 团队创立，上一轮融资估值约 9 亿美元），将其实时特征服务并入 Agent Bricks，为个性化 AI Agent 供给实时上下文。

## 学习目标

读完本主题，你应该能：

1. 解释为什么需要特征平台：特征逻辑重复实现、训练/服务偏斜（skew）、数据泄漏、离线/在线语义不一致。
2. 说清三大核心问题：point-in-time correctness、离线/在线存储分离、特征复用与治理。
3. 理解 Lambda / Kappa 架构在特征生产上的取舍，以及批流一体（如 Tecton RIFT）的演进。
4. 掌握 point-in-time join 的语义：event_timestamp、as-of 取值、max_age / TTL。
5. 理解特征平台的架构分层：特征定义层、离线存储、在线存储、物化同步、特征服务 API。
6. 了解主流系统：Feast（开源事实标准）、Hopsworks（RonDB）、Tecton、Databricks、SageMaker、Vertex AI 的架构差异。
7. 了解 2025-2026 新趋势：embedding 特征、实时上下文工程、Lakehouse 化离线底座、Context Lake。
8. 动手跑一个本地 Mini Demo：事件流 → PIT 训练集 → 在线同步与 TTL → 偏斜检测。
9. 知道生产落地要点：物化调度、在线存储选型、特征监控（漂移/偏斜）、延迟预算。

## 与相邻主题的关系

| 主题 | 关系 | 链接 |
|---|---|---|
| **Kubeflow** | 训练流水线编排；PIT 训练集构建常是流水线中的一个 step | [Kubeflow](../kubeflow/) |
| **MLflow** | 模型/实验生命周期管理；特征平台管数据，MLflow 管模型，两者共同覆盖 MLOps | [MLflow](../mlflow/) |
| **Ray** | 特征计算的分布式执行引擎（Ray Datasets / Ray Serve 特征服务） | [Ray](../ray/) |
| **向量数据库** | embedding 作为一等特征后，向量库与特征平台深度交汇 | [向量数据库与 Embedding 基础设施](../../06-rag/vector-db/) |
| **存储系统** | 离线底座（列式/湖格式）与在线底座（LSM/KV）的存储原理 | [存储系统](../../01-foundation/storage-systems/) |
| **分布式系统** | 一致性、分区、延迟权衡贯穿在线特征服务 | [分布式系统](../../01-foundation/distributed-systems/) |
| **Airflow** | 离线特征批处理作业的调度编排 | [Airflow](../airflow/) |

## 本章结构

| 章节 | 标题 | 内容 |
|---|---|---|
| 1 | [背景](01-background) | ML 特征工程痛点、训练/服务偏斜、Uber Michelangelo 的诞生、特征平台发展史 |
| 2 | [核心思想](02-core-ideas) | 特征即资产、单逻辑单实现、PIT correctness、离线/在线分离、Lambda vs Kappa |
| 3 | [架构设计](03-architecture) | 特征平台四层架构、离线/在线存储选型、物化同步、特征服务、端到端时序图 |
| 4 | [工作流程](04-runtime-workflow) | 特征生产全链路：定义 → 回填 → PIT 训练集 → 物化 → 在线服务 → 监控 |
| 5 | [核心模块](05-core-modules) | Entity / Feature View / 注册中心 / 离线存储 / 在线存储 / PIT join 引擎 / 监控 |
| 6 | [生态与源码分析](06-source-analysis) | Feast 架构与源码走读、Hopsworks、Tecton、云厂商方案对比 |
| 7 | [Mini Demo](07-mini-demo) | 纯 Python 特征存储：PIT join、在线 TTL、偏斜检测，50 个 pytest 用例 |
| 8 | [企业生产实践](08-production-practice) | 物化调度、在线存储选型、延迟预算、特征漂移监控、大厂案例 |
| 9 | [最佳实践](09-best-practices) | 特征命名、时间语义规范、TTL 策略、偏斜防控、治理与成本 |
| 10 | [面试题](10-interview-questions) | 初/中/高级特征平台高频题 |
| 11 | [延伸阅读](11-further-reading) | 官方文档、论文/博客、生态工具、学习路径与手册内回链 |

## 一句话总结

**特征平台 = 训练数据的一致性强约束**：它把“每个特征怎么算”定义为唯一资产，用 point-in-time join 保证训练不偷看未来，用在线/离线双存储保证服务与训练同源，用物化与监控保证新鲜度和无偏斜——在 LLM/Agent 时代，这套能力正以“实时上下文引擎”的名字重新成为 AI 基础设施的核心层。

## 参考来源

- [Feast 官方文档](https://docs.feast.dev/)
- [Feast GitHub](https://github.com/feast-dev/feast)
- [Hopsworks Feature Store](https://www.hopsworks.ai/feature-store)
- [Amazon SageMaker Feature Store](https://docs.aws.amazon.com/sagemaker/latest/dg/feature-store.html)
- [Databricks Feature Engineering in Unity Catalog](https://docs.databricks.com/en/machine-learning/feature-store/index.html)
- [Tecton 官方博客](https://www.tecton.ai/whats-new/)

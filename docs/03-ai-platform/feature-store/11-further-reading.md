# 11. 延伸阅读与总结

> 一句话理解：特征平台是“数据 → 模型”的咬合层，学完后建议沿“**PIT 正确性 → 批流生产 → 在线服务与监控 → 云/开源选型**”四条线继续深入，并与 Kubeflow/MLflow/向量数据库等主题串成完整 MLOps 图景。

## 11.1 核心官方资源

| 资源 | 说明 |
|---|---|
| [Feast 官方文档](https://docs.feast.dev/) | 开源事实标准：概念、存储矩阵、教程 |
| [Feast GitHub](https://github.com/feast-dev/feast) | 源码与 release note（0.67.x，活跃迭代） |
| [Feast 欺诈检测教程](https://docs.feast.dev/tutorials/tutorials-overview/fraud-detection) | 回填 → PIT 训练集 → 在线预测三段式 |
| [Hopsworks Feature Store](https://www.hopsworks.ai/feature-store) | RonDB 在线库、ArrowFlight 取数、开源一体化 |
| [SageMaker Feature Store 文档](https://docs.aws.amazon.com/sagemaker/latest/dg/feature-store.html) | 托管在线/离线模型、PutRecord/DeleteRecord 语义 |
| [Databricks Feature Engineering](https://docs.databricks.com/en/machine-learning/feature-store/index.html) | Unity Catalog 特征工程、托管管道、on-demand 特征 |
| [Vertex AI Feature Store](https://docs.cloud.google.com/vertex-ai/docs/featurestore/overview) | Google 托管路线（Legacy 版 2027-02 停服） |
| [Tecton 官方博客](https://www.tecton.ai/whats-new/) | RIFT 引擎、1.0 实时上下文能力（团队已并入 Databricks） |

## 11.2 相邻主题交叉引用

| 主题 | 关系 | 链接 |
|---|---|---|
| Kubeflow | 训练流水线编排；PIT 训练集构建常作为 pipeline step | [Kubeflow 总览](../kubeflow/index.md) |
| MLflow | 模型/实验生命周期；特征平台管数据、MLflow 管模型 | [MLflow 总览](../mlflow/index.md) |
| Ray | 特征计算的分布式执行（Ray Datasets / Ray Serve） | [Ray 总览](../ray/index.md) |
| KServe | 推理服务；Transformer 前置步骤可封装特征获取 | [KServe 总览](../kserve/index.md) |
| Airflow | 离线特征批处理作业的调度 | [Airflow 总览](../airflow/index.md) |
| KubeRay | 大规模回填作业可跑在 KubeRay 集群 | [KubeRay 总览](../kuberay/index.md) |
| 向量数据库与 Embedding 基础设施 | embedding 作为一等特征，与特征平台深度交汇 | [向量数据库总览](../../06-rag/vector-db/index.md) |
| 存储系统 | 离线列式底座与在线 KV 的存储原理 | [存储系统总览](../../01-foundation/storage-systems/index.md) |
| 分布式系统 | 一致性、分区与延迟权衡贯穿在线特征服务 | [分布式系统总览](../../01-foundation/distributed-systems/index.md) |

## 11.3 进阶论文与文章

| 类型 | 资源 | 看点 |
|---|---|---|
| 论文 | [Hidden Technical Debt in ML Systems (Sculley et al., NIPS 2015)](https://papers.nips.cc/paper/5656-hidden-technical-debt-in-machine-learning-systems.pdf) | 数据依赖债务、“管道丛林”问题的开山之作 |
| 论文 | [Michelangelo: Uber's Machine Learning Platform (2017)](https://www.uber.com/blog/michelangelo-machine-learning-platform/) | 第一个工业级特征平台的设计与教训 |
| 论文 | [The ML Test Score (Breck et al., 2017)](https://research.google/pubs/the-ml-test-score-a-rubric-for-ml-production-readiness-and-technical-debt-reduction/) | 把偏斜/泄漏检查纳入上线门禁的评分卡 |
| 行业 | [Databricks 收购 Tecton（PYMNTS, 2025-08）](https://www.pymnts.com/acquisitions/2025/databricks-to-purchase-tecton-to-boost-ai-agent-offerings/) | 特征平台 = Agent 实时上下文的标志性事件 |
| 行业 | [Tecton 1.0 发布](https://www.tecton.ai/whats-new/introducing-tecton-1-0/) | embedding 生成、Feature Retrieval API、Prompt 管理 |
| 行业 | [RisingWave：2026 实时特征平台观察](https://risingwave.com/blog/real-time-feature-store-2026/) | 流式 SQL 取代专用特征平台的论点 |
| 实践 | [Databricks：What is a Feature Store?](https://www.databricks.com/blog/what-feature-store-complete-guide-ml-feature-engineering) | 概念全景 + PSI 等监控口径 |
| 实践 | [Tecton 实时上下文访谈（Cerebral Valley）](https://cerebralvalley.ai/blog/building-context-rich-applications-with-tecton-125ItJUvGdlBoo52YilajW) | Coinbase 风控 <100ms 的落地细节 |

## 11.4 推荐学习路径

1. **第 1 周**：精读 01-03 章 + 跑通 Mini Demo（50 个测试），动手改窗口大小/TTL 观察 PIT 与偏斜行为变化。
2. **第 2 周**：读 04-06 章，用 Feast local 模式（DuckDB + SQLite）复刻 Demo 的六个场景，对照官方 fraud-detection 教程。
3. **第 3 周**：读 07-09 章，选定一个云账号（或 Databricks 社区版）体验托管特征工程 + 在线服务 + 监控告警的完整闭环。
4. **第 4 周**：跟进 2025-2026 动态——Databricks/Tecton 整合进展、Feast release note、流式 SQL 路线演进，并结合向量数据库主题思考 embedding 特征的接入设计。

## 11.5 一句话总结

特征平台用三根支柱撑起训练数据的一致性：**定义中心化**消灭双实现，**point-in-time join** 杜绝未来泄漏，**离线/在线双存储 + 物化 + TTL** 保证同源与新鲜；当 LLM/Agent 需要毫秒级实时上下文时，这套沉淀十年的能力正以“实时上下文引擎”之名成为 AI 基础设施的必选项。

## 本章小结

- 官方文档（Feast/云厂商）+ 三篇奠基论文（Sculley/Michelangelo/ML Test Score）是最核心的延伸阅读。
- 与 Kubeflow、MLflow、向量数据库等主题联动，构成完整 MLOps 与 LLMOps 图景。
- 学习路径：本地 Demo → Feast 复刻 → 云端闭环 → 跟进整合期动态。

**参考来源**

- [Feast 官方文档](https://docs.feast.dev/)
- [Hopsworks Feature Store](https://www.hopsworks.ai/feature-store)
- [SageMaker Feature Store](https://docs.aws.amazon.com/sagemaker/latest/dg/feature-store.html)
- 本手册相关主题总览

# 10. 面试题精选

> 一句话理解：MLflow 面试主要考察 **Tracking、Models、Model Registry 三者的概念、API、部署架构，以及如何在真实生产环境中落地**。

## 10.1 初级

### Q1. MLflow 的四大核心组件是什么？

**答**：Tracking、Projects、Models、Model Registry。

- Tracking：记录参数、指标、artifact。
- Projects：打包可复现训练代码。
- Models：标准化模型打包与部署格式。
- Model Registry：模型版本、阶段、别名管理。

### Q2. 什么是 Run？

**答**：Run 是 MLflow Tracking 中的单次执行单元，包含参数、指标、标签、artifact 和模型。Run 属于某个 Experiment。

### Q3. `mlflow.log_metric` 和 `mlflow.log_metrics` 的区别？

**答**：前者一次 log 一个指标值（可带 step），后者一次 log 多个指标值。都可以多次调用追加历史值。

### Q4. Model Registry 里的 Stage 和 Alias 有什么区别？

**答**：

- Stage：模型版本的生命周期标签，如 Staging、Production、Archived。
- Alias：指向某个版本的动态标签，如 champion、challenger，可随时间指向不同版本。

### Q5. 如何加载 Model Registry 中别名为 champion 的模型？

**答**：

```python
model = mlflow.pyfunc.load_model("models:/my-model@champion")
```

## 10.2 中级

### Q6. MLflow Tracking Server 由哪三部分组成？

**答**：Tracking Server、Backend Store、Artifact Store。

- Tracking Server：FastAPI 应用，暴露 REST API。
- Backend Store：保存实验、Run、参数、指标、标签、注册模型等元数据。
- Artifact Store：保存模型文件、图表、日志等二进制文件。

### Q7. 生产环境为什么推荐 PostgreSQL + S3？

**答**：

- SQLite 并发差，不适合多用户。
- PostgreSQL 支持高并发、事务、备份、索引。
- S3 提供高可用、大容量、生命周期管理和跨区域复制。

### Q8. 如何保证模型服务的可复现性？

**答**：

1. 记录训练代码版本（git commit）。
2. 记录所有超参数和数据集版本。
3. 使用 `log_model` 打包模型、signature、依赖、代码路径。
4. 通过 Model Registry 的 alias/stage 控制线上模型版本。

### Q9. `log_model` 生成的 `MLmodel` 文件里有什么？

**答**：包含 flavors（如 sklearn、python_function）、artifact 路径、signature、input example、conda/python 环境等元数据。

### Q10. MLflow 如何实现 A/B 测试？

**答**：

- 把新版本注册为 `challenger` alias，旧版本保持 `champion`。
- 线上服务按流量比例分别加载两个 alias。
- 对比指标后决定是否把 `champion` alias 切换到新版本。

## 10.3 高级

### Q11. MLflow Tracking 的 `log_metric` 调用链是怎样的？

**答**：

1. `mlflow.log_metric` → `MlflowClient.log_metric`
2. → `RestStore.log_metric`（REST）或 `SqlAlchemyStore.log_metric`（本地）
3. → 写入 `metrics` 表。

### Q12. 多副本 Tracking Server 部署时需要注意什么？

**答**：

- Server 本身无状态，可多副本。
- Backend Store 必须共享，且支持并发。
- Artifact Store 必须共享，否则多副本间 artifact 不一致。
- 配置统一的 `default-artifact-root`。
- 启用认证和负载均衡。

### Q13. 如何防止 Model Registry 中的重规划风暴/误操作？

**答**：

- 设置 alias 切换审批流程。
- 使用 tag/stage 约束：只有 Staging 阶段才能提升到 Production。
- 启用 basic auth 或企业 workspace 权限控制。
- 对 Production 变更进行审计和告警。

### Q14. MLflow 与 Kubeflow 如何协同？

**答**：

- Kubeflow Pipelines 负责编排训练/评估/部署流程。
- 每个训练 step 内部调用 MLflow Tracking 记录实验。
- 训练完成后把模型注册到 MLflow Model Registry。
- KServe 从 MLflow Model Registry 加载模型提供服务。

### Q15. 如何设计一个大型企业的 MLflow 多租户方案？

**答**：

- 方案 A：每个团队独立 Tracking Server + DB + Bucket，隔离最强。
- 方案 B：共享 Tracking Server，通过 auth 插件和 experiment/model 命名前缀隔离。
- 根据合规要求选择；关键业务建议方案 A。

## 本章小结

- 初级题聚焦概念和 API。
- 中级题聚焦架构、部署和可复现性。
- 高级题聚焦源码调用链、多副本、多租户、企业治理。

**参考来源**

- [MLflow 官方文档](https://mlflow.org/docs/latest/index.html)
- 本手册 MLflow 各章内容
- 常见 ML 平台面试题整理

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
- 方案 B：共享 Tracking Server，3.13+ 用内置 RBAC 按角色授权，或 3.10+ 用 `--enable-workspaces` 做多工作区；experiment/model 命名带团队前缀。
- 关键业务建议方案 A，并配合 OIDC 代理统一登录；Databricks 环境直接用 Unity Catalog 做模型级治理。

### Q16. MLflow 3.0 相比 2.x 最大的变化是什么？

**答**：

1. **GenAI 能力成为一等公民**：Tracing（基于 OpenTelemetry，autolog 集成 LangChain/LlamaIndex/OpenAI 等 20+ 框架）、Prompt Registry、GenAI Evaluation（LLM-as-a-Judge）、AI Gateway。
2. **LoggedModel 一等实体**：模型拥有独立 `model_id` 和血缘，不再是 Run 下的普通 artifact；Registry 可直接引用 LoggedModel。
3. **治理增强**：3.13 内置 RBAC + Admin UI + Trace 归档 + 官方 Helm Chart；3.15 MCP Registry；3.17 资源级细粒度权限。
4. 破坏性变化：artifact 路径重组、移除 mleap/fastai flavor 与 MLflow Recipes。

### Q17. MLflow Tracing 是如何实现的？对应用性能有什么影响？

**答**：

- 基于 OpenTelemetry：autolog/`@mlflow.trace` 产生 span，经批量缓冲后异步上报到 Tracking Server 的 trace API，写入 SQL（热数据）并可选归档到对象存储。
- 影响：批量异步上报对主路径延迟影响很小；风险在服务端——高 QPS 下 Backend Store 写入压力大，需要配置 Trace Archival 保留策略，多模态附件走 Artifact Store。

### Q18. 如何用 MLflow 管理提示词（Prompt）的版本与上线？

**答**：

- 用 Prompt Registry：`register_prompt()` 提交新版本（带 commit message 和 diff），用 `staging`/`production` 别名管理流量。
- 应用代码 `load_prompt("name@alias")` 只引用别名，实现灰度与秒级回滚。
- prompt 与模型在 Registry 中独立发版；上线前用 `mlflow.genai.evaluate()` + scorer 回归，并用 `@mlflow.test`（3.14+）固化进 CI。

### Q19. MLflow 与 Langfuse 都在做 LLM 观测，怎么选？

**答**：

- Langfuse/LangSmith 更专注 LLM 可观测性，接入轻量、trace 分析体验好。
- MLflow 的优势是**一体化**：Tracing 与实验追踪、模型/Prompt Registry、评估共享同一后端与 UI，且 3.13+ 自带 RBAC、Trace 归档等治理能力。
- 已经重度使用 MLflow 做模型治理、或需要“观测 + 评估 + 权限”一体的团队选 MLflow；只做轻量 LLM 排障的团队可选 Langfuse。

## 本章小结

- 初级题聚焦概念和 API。
- 中级题聚焦架构、部署和可复现性。
- 高级题聚焦源码调用链、多副本、多租户、企业治理。
- 2025-2026 年的新热点：MLflow 3.x 的 GenAI 能力（Tracing / Prompt Registry / Evaluation / AI Gateway）、LoggedModel 一等实体、RBAC 与 Trace 归档。

**参考来源**

- [MLflow 官方文档](https://mlflow.org/docs/latest/index.html)
- [MLflow 3 Release Notes](https://mlflow.org/releases/3/)
- 本手册 MLflow 各章内容
- 常见 ML 平台面试题整理

# 10. 面试题

## 初级

### 1. Kubeflow 是什么？它解决了什么问题？

Kubeflow 是一组在 Kubernetes 上运行 ML 工作负载的组件（Notebook、Pipelines、Katib、Kubeflow Trainer、KServe、Hub 等）。它解决了 ML 生命周期工具割裂、不可复现、难协作的问题。

### 2. Kubeflow 的核心组件有哪些？

- Notebooks：Jupyter 开发环境。
- Pipelines（KFP）：ML 工作流编排。
- Katib：超参搜索 / NAS。
- Kubeflow Trainer：分布式训练与 LLM 微调（V1 框架 CRD / V2 TrainJob）。
- KServe：模型服务（含 LLMInferenceService）。
- Hub：模型/OCI 制品/MCP 目录（原 Model Registry）。
- Spark Operator：数据工程。
- Central Dashboard：统一入口。
- Profiles / KFAM：多租户。

### 3. Kubeflow 多租户的基本单元是什么？

`Profile`。一个 Profile 对应一个 namespace，Profile Controller 会创建 namespace、RBAC、Istio AuthorizationPolicy、ResourceQuota。

### 4. KFP 中的 Experiment、Run、Pipeline 分别指什么？

- Pipeline：DAG 定义（IR YAML）。
- Experiment：一组相关 Run 的逻辑分组。
- Run：一次 Pipeline 执行实例。

### 5. Katib 的 Experiment / Trial / Suggestion 分别是什么？

- Experiment：一次搜索任务，定义目标、搜索空间、算法、Trial 数量。
- Trial：一次具体超参组合的实验运行。
- Suggestion：根据算法生成下一组超参的服务。

## 中级

### 6. KFP v2 的 DSL → Run 链路是怎样的？

```
Python DSL → Compiler → IR YAML (pipeline spec) → API Server → Run → Driver/Launcher/Executor → Pod → Artifact + MLMD
```

Driver 解析参数、Launcher 管理 artifact、Executor 运行业务容器。

### 7. Kubeflow Trainer 如何管理 PyTorch 分布式训练？

V1：用户创建 `PyTorchJob`，指定 `Master` 和 `Worker` 的 replicas。Controller 创建对应 Pod 和 Headless Service，注入 `MASTER_ADDR`、`WORLD_SIZE` 等环境变量。

V2（当前默认）：用户创建 `TrainJob`，通过 `spec.runtimeRef` 引用 `TrainingRuntime`（内置 torch-distributed、torchtune 等），由运行时负责 `torchrun` 启动参数与环境注入，并与 Kueue/Volcano 集成 gang scheduling。

### 8. Kubeflow 为什么默认用 Istio？

- 统一入口 Gateway。
- 认证（OIDC/JWT）。
- namespace 间流量隔离。
- Notebook 路径路由 `/notebook/<ns>/<name>`。

### 9. Katib 如何收集 Trial 的指标？

Trial 训练容器把目标指标写到 `/katib/metrics/metrics.json`，Metrics Collector 读取后上报，Experiment Controller 根据 objective 比较并保留最优 Trial。

### 10. Pipeline 如何实现缓存？

KFP v2 通过计算 step 输入/输出/镜像的指纹，命中缓存时直接复用之前的 output artifact，不再创建 Pod。

## 高级

### 11. Kubeflow Pipelines v1 与 v2 的核心差异是什么？

- v1 后端基于 Argo Workflows；v2 逐步解耦，使用 Driver/Launcher/Executor 模型。
- v2 DSL 更类型化，编译为 Protobuf-based IR YAML。
- v2 原生支持 artifact、lineage、缓存。

### 12. Kubeflow Trainer V1 与 V2 的演进方向是什么？

V1 是各框架独立 CRD（TFJob、PyTorchJob、MPIJob 等），现处维护模式。V2 于 2025-07 GA，引入统一的 `TrainJob` + `TrainingRuntime` 模型，把用户面与平台面解耦；Kubeflow 1.11 起成为默认。v2.2 的破坏性变更：`PodTemplateOverrides` → `RuntimePatches`，移除 `numProcPerNode` 与 `ElasticPolicy`。

### 13. 如何设计一个高可用的 Kubeflow 生产平台？

- 安装方式：根据团队规模选完整发行版（1.11 / 26.03）、独立组件或仅 Python SDK。
- 多租户：Profile + RBAC + Istio AuthorizationPolicy + ResourceQuota；1.11 默认 PSS/NetworkPolicy。
- 存储：S3/GCS/SeaweedFS artifact、MySQL MLMD、Katib DB 均做备份；模型制品走 Hub OCI。
- 可观测：Prometheus/Grafana + ELK/Loki + TensorBoard。
- 升级：分组件灰度升级，KFP 2.15+ 数据库迁移不可回滚须先备份。
- 成本：Notebook 自动休眠、Pipeline cache、KServe 缩容到零。

### 14. Pipeline Run 卡在某个 step，如何排查？

1. 看 KFP UI 中该 step 的日志。
2. `kubectl describe pod <pod-name>` 看事件。
3. 检查 artifact store 连通性。
4. 检查 resource quota / GPU 是否足够。
5. 查看 Driver/Launcher 日志。

### 15. 如何在 Kubeflow 中做模型 A/B 测试？

通过 KServe 的 `canaryTrafficPercent` 或 InferenceGraph 把流量按百分比切到不同版本；Pipeline 部署时输出两个 `InferenceService` 版本。

### 16. Hub 与旧的 Model Registry 有什么区别？

Hub 是 Model Registry 在 2026 年的更名扩围：除模型版本治理外，新增 Model Catalog（基准测试、硬件对比、Hugging Face 拉取）、MCP Catalog（搜索/部署 MCP 服务器），模型存储以 OCI 为标准，并通过 reconciliation controller 记录线上 `InferenceService` 实际运行的版本。

### 17. 在 Kubeflow 上微调一个 LLM 并上线，典型链路是什么？

1. `pip install kubeflow`，用 `BuiltinTrainer` + torchtune 运行时（LoRA/QLoRA/DoRA）配置微调任务，`HuggingFaceModelInitializer` 拉模型。
2. 可选先用 SDK 本地后端（Docker/进程）验证。
3. 提交 `TrainJob`（`runtimeRef` 指向 torchtune 运行时），分布式训练并自动上报指标。
4. 微调产物以 OCI 制品注册到 Hub。
5. KServe 创建 `LLMInferenceService`，经 Custom Storage Initializer 拉取模型，暴露 OpenAI 兼容端点。

## 参考答案速查

| 题号 | 关键词 |
|---|---|
| 1 | K8s-native ML 平台、生命周期统一 |
| 2 | Notebook/Pipeline/Katib/Trainer/KServe/Hub/Spark/Dashboard/Profile |
| 3 | Profile = namespace |
| 4 | Pipeline/Experiment/Run |
| 5 | Experiment/Trial/Suggestion |
| 6 | DSL → Compiler → IR → API Server → Driver/Launcher/Executor |
| 7 | PyTorchJob V1 / TrainJob + TrainingRuntime V2 |
| 8 | 认证、流量隔离、路由 |
| 9 | /katib/metrics/metrics.json 或 push-based |
| 10 | 输入/输出/镜像指纹 |
| 11 | Argo vs Driver/Launcher、IR YAML |
| 12 | TrainJob + TrainingRuntime、2025 GA、RuntimePatches |
| 13 | 安装、多租户、存储、可观测、升级、成本 |
| 14 | UI 日志、Pod 事件、artifact、quota、Driver 日志 |
| 15 | KServe canary / InferenceGraph |
| 16 | Model Catalog + MCP Catalog + OCI |
| 17 | BuiltinTrainer → TrainJob → Hub OCI → LLMInferenceService |

**参考来源**

- [Kubeflow 官方文档](https://www.kubeflow.org/docs/)
- [KFP v2 Documentation](https://www.kubeflow.org/docs/components/pipelines/)
- [Katib Documentation](https://www.kubeflow.org/docs/components/katib/)
- [Kubeflow Trainer Documentation](https://trainer.kubeflow.org/)
- [Kubeflow SDK GitHub](https://github.com/kubeflow/sdk)
- [Kubeflow Community Distribution 26.03 Release](https://blog.kubeflow.org/kubeflow-26.03-release/)
- 本手册 [KServe 面试题](../kserve/10-interview-questions)

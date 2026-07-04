# 10. 面试题

## 初级

### 1. Kubeflow 是什么？它解决了什么问题？

Kubeflow 是一组在 Kubernetes 上运行 ML 工作负载的组件（Notebook、Pipelines、Katib、Training Operator、KServe 等）。它解决了 ML 生命周期工具割裂、不可复现、难协作的问题。

### 2. Kubeflow 的核心组件有哪些？

- Notebooks：Jupyter 开发环境。
- Pipelines：ML 工作流编排。
- Katib：超参搜索 / NAS。
- Training Operator：分布式训练作业。
- KServe：模型服务。
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

### 7. Training Operator 如何管理 PyTorch 分布式训练？

用户创建 `PyTorchJob`，指定 `Master` 和 `Worker` 的 replicas。Training Operator 创建对应 Pod 和 Headless Service，注入 `MASTER_ADDR`、`WORLD_SIZE` 等环境变量。训练框架用这些变量初始化进程组。

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

### 12. Training Operator V1 与 V2 的演进方向是什么？

V1 是各框架独立 CRD（TFJob、PyTorchJob、MPIJob 等）。V2（alpha）引入统一的 `TrainJob` + `TrainingRuntime` 模型，把用户面与平台面解耦。

### 13. 如何设计一个高可用的 Kubeflow 生产平台？

- 安装方式：根据团队规模选完整发行版或独立组件。
- 多租户：Profile + RBAC + Istio AuthorizationPolicy + ResourceQuota。
- 存储：S3/GCS artifact、MySQL MLMD、Katib DB 均做备份。
- 可观测：Prometheus/Grafana + ELK/Loki + TensorBoard。
- 升级：分组件灰度升级，备份数据库。
- 成本：Notebook 自动休眠、Pipeline cache、KServe 缩容到零。

### 14. Pipeline Run 卡在某个 step，如何排查？

1. 看 KFP UI 中该 step 的日志。
2. `kubectl describe pod <pod-name>` 看事件。
3. 检查 artifact store 连通性。
4. 检查 resource quota / GPU 是否足够。
5. 查看 Driver/Launcher 日志。

### 15. 如何在 Kubeflow 中做模型 A/B 测试？

通过 KServe 的 `canaryTrafficPercent` 或 InferenceGraph 把流量按百分比切到不同版本；Pipeline 部署时输出两个 `InferenceService` 版本。

## 参考答案速查

| 题号 | 关键词 |
|---|---|
| 1 | K8s-native ML 平台、生命周期统一 |
| 2 | Notebook/Pipeline/Katib/Training/KServe/Dashboard/Profile |
| 3 | Profile = namespace |
| 4 | Pipeline/Experiment/Run |
| 5 | Experiment/Trial/Suggestion |
| 6 | DSL → Compiler → IR → API Server → Driver/Launcher/Executor |
| 7 | PyTorchJob CRD → Master/Worker Pod + Service + env |
| 8 | 认证、流量隔离、路由 |
| 9 | /katib/metrics/metrics.json |
| 10 | 输入/输出/镜像指纹 |
| 11 | Argo vs Driver/Launcher、IR YAML |
| 12 | TrainJob + TrainingRuntime |
| 13 | 安装、多租户、存储、可观测、升级、成本 |
| 14 | UI 日志、Pod 事件、artifact、quota、Driver 日志 |
| 15 | KServe canary / InferenceGraph |

**参考来源**

- [Kubeflow 官方文档](https://www.kubeflow.org/docs/)
- [KFP v2 Documentation](https://www.kubeflow.org/docs/components/pipelines/)
- [Katib Documentation](https://www.kubeflow.org/docs/components/katib/)
- [Training Operator Documentation](https://www.kubeflow.org/docs/components/training/)
- 本手册 [KServe 面试题](../kserve/10-interview-questions)

# 1. 背景：为什么需要 Kubeflow

> 一句话理解：在 Kubernetes 上跑机器学习工作负载时，**开发、实验、训练、调参、服务每个阶段都要自己拼一套工具**——Kubeflow 把这些阶段统一成一组 K8s-native 组件，让 ML 平台从"脚本作坊"变成"声明式工厂"。

## 1.1 裸跑 ML 工作负载的痛苦

假设你负责一个 AI 平台，团队每天要：

- 用 Jupyter Notebook 做特征工程。
- 用 Airflow / Cron 触发训练脚本。
- 手动调超参，用 Excel 记录结果。
- 用 `torchrun` 或 `mpirun` 起分布式训练，手动管理 Pod。
- 训练完把模型拷到对象存储，再手写 YAML 部署 vLLM/KServe。
- 没有统一的 artifact、 lineage、权限、可观测。

每个环节用不同工具，衔接靠人工：

| 阶段 | 裸跑方式 | 痛点 |
|---|---|---|
| 开发 | 本地 Jupyter / VS Code + 远程 SSH | 环境不一致、GPU 抢不到、数据搬来搬去 |
| 实验 | 脚本 + CSV/Excel | 不可复现、无法追踪、参数散落成文件 |
| 流水线 | Airflow / Argo / shell | 与 K8s 资源割裂、难复用、难缓存 |
| 超参搜索 | for-loop / Optuna 裸跑 | 资源管理难、Trial 失败难恢复、结果不聚合 |
| 分布式训练 | 手动起 TF/PyTorch Job | 网络配置烦、容错差、扩容麻烦 |
| 模型服务 | 手写 Deployment/Ingress | 金丝雀、扩缩、A/B 测试重复造轮子 |
| 协作 | 共享账号 / 手工 namespace | 无隔离、权限混乱 |

裸跑时每新增一个模型或团队，平台工程师就要重新搭一套胶水。

## 1.2 Kubeflow 是什么

Kubeflow 是一个**面向机器学习的 Kubernetes 发行版/平台**，最初由 Google 在 2017 年发布，后来成为开源社区项目。它的核心思路：

> **把 ML 生命周期的每个阶段都做成 K8s CRD + Controller + Web UI**。

典型组件：

- **Notebooks**：Jupyter/Lab/VS Code server，由 Notebook Controller 管理（v2 正在向 CRD 驱动的 Workspaces 架构重构）。
- **Pipelines（KFP）**：ML 工作流编排，用 Python DSL 定义 DAG，编译为 IR YAML。
- **Katib**：AutoML，超参搜索与神经架构搜索；v0.19 起 Trial 可直接以 TrainJob 运行。
- **Kubeflow Trainer**（原 Training Operator）：分布式训练作业。V1 提供 TFJob、PyTorchJob、MPIJob 等框架级 CRD；**V2（2025-07 GA）统一为 `TrainJob` + `TrainingRuntime` 模型**，内置 torchtune LLM 微调运行时（LoRA/QLoRA/DoRA），并已加入 PyTorch 生态。
- **KServe**（原 KFServing）：模型服务；v0.18 起新增 `LLMInferenceService` CRD，把 LLM 服务化提升为一等平台原语。
- **Hub**（原 Model Registry）：模型资产中心，v0.3.9 起扩展出 Model Catalog 与 MCP Catalog，以 OCI 作为模型存储标准。
- **Spark Operator**：2025 年起成为 Kubeflow 核心组件，可用统一 Python SDK 提交 Spark 作业。
- **Central Dashboard**：统一入口（Dashboard v2 已随 26.03 发行版发布）。
- **Profiles / KFAM**：多租户与用户命名空间。

### 2025–2026：GenAI 时代的 Kubeflow

Kubeflow 在 2025–2026 年经历了明显的定位升级，从"传统 MLOps 平台"转向"GenAI 原生平台"：

- **2025-03 Kubeflow 1.10**：Trainer 2.0 引入 JAX 支持；Katib 增加面向 LLM 微调的高级调参 API；KFP 2.4 支持 `ParallelFor` 循环并行度控制；Spark Operator 进入核心组件；oauth2-proxy 取代 OIDC-authservice。
- **2025-07 Kubeflow Trainer 2.0 GA**：统一 `TrainJob` API，废弃"每框架一个 CRD"的旧范式，并加入 PyTorch 生态。
- **2025-12 Kubeflow 1.11**：默认启用 Pod Security Standards（系统 namespace restricted / 用户 namespace baseline）；默认网络策略；"零 Pod 开销"优化面向 1000+ 命名空间规模；对象存储默认切换为 SeaweedFS（MinIO 逐步弃用）。
- **2026-04 Community Distribution 26.03**：社区发行版改用**日历版本号**（Year.Month.Patch，每年两个基线版本），组件矩阵为 KFP 2.16、Trainer 2.2、KServe 0.18、Hub 0.3.9、Spark Operator 2.5，验证 Kubernetes 1.34+；Dashboard v2 与 Notebooks 2.0（alpha）首次发布。
- **2026 Python-first SDK**：`pip install kubeflow` 提供统一的 `TrainerClient` / `SparkClient` / `PipelinesClient` / `ModelRegistryClient`，支持本地（Docker/Podman/进程）开发、集群上规模化运行。
- **2026-07/08 临近 CNCF 毕业**：Kubeflow 进入 CNCF 毕业最后评审阶段（据 InfoQ 2026-08 报道），社区活跃度处于历史高点。

> 本主题内容基于 2026-10 的最新版本状态撰写：Kubeflow 1.11（2025-12）与 Community Distribution 26.03（2026-04）为当前稳定基线，Trainer 2.2 / KServe 0.18 / KFP 2.16 为核心组件版本。

## 1.3 Kubeflow 与相邻工具的对比

| 工具 | 定位 | 与 Kubeflow 的关系 |
|---|---|---|
| **Airflow** | 通用数据/任务编排 | Kubeflow Pipelines 更聚焦 ML：artifact 血缘、缓存、实验管理 |
| **MLflow** | 实验追踪 + 模型注册 | 常与 Kubeflow Pipelines 集成，互补而非替代 |
| **KServe** | 模型服务 | Kubeflow 的 serving 组件，也可独立使用 |
| **Ray** | 分布式计算/训练/推理 | 可与 Kubeflow Trainer（KubeRay）或 KServe 组合 |
| **SageMaker / Vertex** | 托管云 ML 平台 | Kubeflow 是开源自托管替代，更灵活但运维更重 |
| **Argo Workflows** | 通用 K8s 工作流 | KFP v1 后端基于 Argo；KFP v2 仍以 Argo 作为执行引擎之一，但 DSL/IR 层已完全解耦，并支持本地运行（Local Runner） |

**关键区分**：

- **Kubeflow vs MLflow**：MLflow 管"实验和模型资产"，Kubeflow 管"ML 工作负载在 K8s 上的全生命周期"；2026 年 Kubeflow SDK 路线图已计划原生 MLflow tracking 集成。
- **Kubeflow vs Airflow**：Airflow 是时间/依赖驱动的任务调度；Kubeflow Pipelines 是数据/artifact 驱动的 ML DAG。
- **Kubeflow vs Ray**：Ray 是运行时；Kubeflow 是平台层，可编排 Ray 集群（KubeRay）。

## 1.4 Kubeflow 解决了什么（和不解决什么）

**Kubeflow 解决**：

- ✅ 统一的 K8s-native ML 工作台（Notebook + Dashboard）。
- ✅ 可复现的 pipeline（版本化、缓存、artifact 血缘）。
- ✅ 自动化超参搜索与 NAS。
- ✅ 声明式分布式训练（一行 YAML 或一段 Python 跑 `torchrun`/MPI/HPC 作业）。
- ✅ LLM 微调与服务：torchtune 运行时（LoRA/QLoRA/DoRA）+ KServe `LLMInferenceService`。
- ✅ 模型与 Agent 资产治理：Hub 统一管理模型目录、OCI 制品与 MCP 服务器目录。
- ✅ 多租户隔离（Profile + namespace + Istio auth）。

**Kubeflow 不解决**：

- ❌ 数据标注、数据仓库、特征平台（需 Feast/自定义）。
- ❌ 通用 ETL（需 Airflow/Spark/Flink）。
- ❌ 商业化的模型市场、自动扩缩到零的极致优化（KServe 可部分解决）。
- ❌ 零运维：Kubeflow 本身也需要升级、监控、调优。

## 1.5 AI 平台为什么需要 Kubeflow

一个成熟 AI 平台最终会长成这样：

```
算法工程师 / 数据科学家
        │
        ▼
[Central Dashboard] / [Kubeflow SDK] — 统一入口（Web 或 Python）
        │
        ├─ Notebooks — 开发/实验
        ├─ Pipelines — 编排训练/数据流程
        ├─ Katib — 超参搜索（Trial 可直接跑 TrainJob）
        ├─ Trainer — 分布式训练与 LLM 微调（TrainJob + TrainingRuntime）
        ├─ KServe — 模型服务（含 LLMInferenceService）
        ├─ Hub — 模型目录 / OCI 制品 / MCP Catalog
        ├─ Spark Operator — 数据工程
        └─ Model Registry / MLflow — 模型/实验资产
        │
        ▼
    Kubernetes
        │
        ▼
    GPU / CPU 节点池
```

Kubeflow 是这一层里**把 ML 各阶段标准化到 K8s** 的关键：

- 对**数据科学家**：在 Notebook 里写代码，一键提交 Pipeline / Katib / Training Job。
- 对**平台工程师**：用 CRD 扩展新能力，用 Kustomize/Helm 管理发行版。
- 对**SRE**：统一在 K8s 上做可观测、资源配额、多租户、升级。

## 本章小结

- **痛点**：裸跑 ML 各阶段工具割裂，重复工程、不可复现、难协作。
- **定位**：Kubeflow 是 K8s 原生 ML 平台，把 Notebook、Pipeline、Katib、Trainer、KServe、Hub 统一起来。
- **演进**：2025–2026 年从"每框架一个 CRD"转向统一的 `TrainJob` 模型，Python-first SDK（`pip install kubeflow`），对象存储默认切到 SeaweedFS，并发力 CNCF 毕业。
- **对比**：比 Airflow 更 ML 专用；比 MLflow 更偏工作负载编排；不替代 KServe/Ray，而是集成它们。
- **价值**：把 ML 生命周期从脚本集合变成声明式、可复现、可协作的平台。

**参考来源**

- [Kubeflow — What is Kubeflow?](https://www.kubeflow.org/docs/started/introduction/)
- [Kubeflow GitHub](https://github.com/kubeflow/kubeflow)
- [Kubeflow 1.10 Release Announcement](https://blog.kubeflow.org/kubeflow-1.10-release/)
- [Kubeflow 1.11 Release Announcement](https://blog.kubeflow.org/kubeflow-1.11-release/)
- [Kubeflow Community Distribution 26.03 Release Announcement](https://blog.kubeflow.org/kubeflow-26.03-release/)
- [Kubeflow Trainer v2.2 Release](https://blog.kubeflow.org/kubeflow-trainer-v2.2-release/)
- [InfoQ — Kubeflow Expands AI Capabilities as CNCF Graduation Nears](https://www.infoq.com/news/2026/08/kubeflow/)
- 本手册 [KServe](../kserve/)、[Ray](../ray/)、[Operator 模式](../../02-cloud-native/operator/)

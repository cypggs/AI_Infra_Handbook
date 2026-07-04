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

- **Notebooks**：Jupyter/Lab/VS Code server，由 Notebook Controller 管理。
- **Pipelines**：ML 工作流编排，用 Python DSL 定义 DAG。
- **Katib**：AutoML，超参搜索与神经架构搜索。
- **Training Operator**：分布式训练作业（TFJob、PyTorchJob、MPIJob、XGBoostJob、PaddleJob、MXNetJob）。
- **KServe**（原 KFServing）：模型服务。
- **Central Dashboard**：统一入口。
- **Profiles / KFAM**：多租户与用户命名空间。

## 1.3 Kubeflow 与相邻工具的对比

| 工具 | 定位 | 与 Kubeflow 的关系 |
|---|---|---|
| **Airflow** | 通用数据/任务编排 | Kubeflow Pipelines 更聚焦 ML：artifact 血缘、缓存、实验管理 |
| **MLflow** | 实验追踪 + 模型注册 | 常与 Kubeflow Pipelines 集成，互补而非替代 |
| **KServe** | 模型服务 | Kubeflow 的 serving 组件，也可独立使用 |
| **Ray** | 分布式计算/训练/推理 | 可与 Training Operator（KubeRay）或 KServe 组合 |
| **SageMaker / Vertex** | 托管云 ML 平台 | Kubeflow 是开源自托管替代，更灵活但运维更重 |
| **Argo Workflows** | 通用 K8s 工作流 | KFP v1 后端基于 Argo；KFP v2 逐步解耦 |

**关键区分**：

- **Kubeflow vs MLflow**：MLflow 管“实验和模型资产”，Kubeflow 管“ML 工作负载在 K8s 上的全生命周期”。
- **Kubeflow vs Airflow**：Airflow 是时间/依赖驱动的任务调度；Kubeflow Pipelines 是数据/artifact 驱动的 ML DAG。
- **Kubeflow vs Ray**：Ray 是运行时；Kubeflow 是平台层，可编排 Ray 集群（KubeRay）。

## 1.4 Kubeflow 解决了什么（和不解决什么）

**Kubeflow 解决**：

- ✅ 统一的 K8s-native ML 工作台（Notebook + Dashboard）。
- ✅ 可复现的 pipeline（版本化、缓存、artifact 血缘）。
- ✅ 自动化超参搜索与 NAS。
- ✅ 声明式分布式训练（一行 YAML 跑 `torchrun`/`horovodrun`）。
- ✅ 模型服务与流量治理（通过 KServe）。
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
[Central Dashboard] — 统一入口
        │
        ├─ Notebooks — 开发/实验
        ├─ Pipelines — 编排训练/数据流程
        ├─ Katib — 超参搜索
        ├─ Training Operator — 分布式训练
        ├─ KServe — 模型服务
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
- **定位**：Kubeflow 是 K8s 原生 ML 平台，把 Notebook、Pipeline、Katib、Training、Serving 统一起来。
- **对比**：比 Airflow 更 ML 专用；比 MLflow 更偏工作负载编排；不替代 KServe/Ray，而是集成它们。
- **价值**：把 ML 生命周期从脚本集合变成声明式、可复现、可协作的平台。

**参考来源**

- [Kubeflow — What is Kubeflow?](https://www.kubeflow.org/docs/started/introduction/)
- [Kubeflow GitHub](https://github.com/kubeflow/kubeflow)
- [Kubeflow 1.11 Release](https://github.com/kubeflow/website/blob/master/content/en/docs/kubeflow-distribution/releases/kubeflow-1.11.md)
- 本手册 [KServe](../kserve/)、[Ray](../ray/)、[Operator 模式](../../02-cloud-native/operator/)

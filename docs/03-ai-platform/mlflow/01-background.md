# 1. 背景：为什么需要 MLflow

> 一句话理解：当团队从“一个人跑 Jupyter”变成“多人迭代几十个模型”时，**实验参数、指标、模型文件和部署链路会迅速失控**——MLflow 就是为这种失控提供统一记录和版本管理的平台。

## 1.1 裸跑 ML 的痛苦

假设你所在的 AI 团队有 5 名数据科学家，大家都在各自的 Notebook 里训练模型：

- 每个人用不同的随机种子、超参、数据版本。
- 训练结果散落在本地 CSV、TensorBoard log、Google Sheet 里。
- 模型文件用 `model_v1.pkl`、`model_v1_final.pkl`、`model_v1_final_2.pkl` 命名。
- 上线时不知道某个模型是用哪份代码、哪个数据集、什么依赖训练出来的。
- 模型效果下降时，无法快速回滚到上一个稳定版本。

典型场景：

| 阶段 | 裸跑方式 | 痛点 |
|---|---|---|
| 实验记录 | Excel / Sheet / 聊天记录 | 不可搜索、字段不统一、容易丢失 |
| 超参 | 代码里硬编码或随机 | 无法对比、无法复现 |
| 指标 | print / tensorboard 本地 | 没有和参数/代码绑定 |
| 模型文件 | 本地磁盘 / 网盘 | 版本混乱、依赖缺失 |
| 部署 | 手写 Dockerfile + 拷贝权重 | 环境不一致、上线慢 |
| 协作 | 口头同步 | 重复实验、知识孤岛 |

## 1.2 MLflow 是什么

MLflow 是一个**开源的机器学习与 GenAI 应用生命周期管理平台**，最初由 Databricks 在 2018 年开源。它的核心定位：

> **把 ML 实验、模型、依赖和部署元数据统一记录成可查询、可版本化、可复现的资产**。

MLflow 由四大经典组件组成：

- **MLflow Tracking**：记录实验（Run）的参数、指标、artifact。
- **MLflow Projects**：把代码、依赖、入口封装成可复现的项目。
- **MLflow Models**：把模型打包成标准格式，支持多种 flavor 和部署目标。
- **MLflow Model Registry**：集中管理模型版本、阶段、别名、标签。

2025 年 6 月发布的 **MLflow 3.0** 把这四大组件扩展到了 GenAI/Agent 时代，新增了一等公民能力（详见第 2 章）：

- **MLflow Tracing**：基于 OpenTelemetry 的 LLM/Agent 全链路追踪（自动集成 LangChain、LlamaIndex、OpenAI、Anthropic 等 20+ 框架）。
- **Prompt Registry**：提示词模板的 Git 式版本管理（提交、对比、别名）。
- **GenAI Evaluation**：LLM-as-a-Judge 评估器（相关性、忠实度、安全性等）与评估数据集管理。
- **AI Gateway**：统一的 LLM API 网关（路由、预算、Guardrails、MCP Registry）。
- **LoggedModel 一等实体**：模型不再只是 Run 下的 artifact，而是拥有独立 ID、血缘和生命周期的对象。

从版本演进看（截至 2026-10，最新为 3.17.x）：MLflow 2.x（2022-2025）聚焦传统 ML 实验追踪与模型注册；MLflow 3.0（2025-06）完成 GenAI 转型；3.9-3.17（2026 年）则持续强化企业治理能力——内置 RBAC 与 Admin UI（3.13）、Trace 自动归档（3.13）、官方 Helm Chart（3.13）、`mlflow agent setup` 一键接入编码 Agent（3.14）、MCP Registry（3.15）、可定制 Trace 视图与 Span Links（3.16）、细粒度权限与 Trace 分析加速（3.17）。

## 1.3 MLflow 与相邻工具的对比

| 工具 | 定位 | 与 MLflow 的关系 |
|---|---|---|
| **Kubeflow** | K8s 原生 ML 工作负载编排 | 常与 MLflow 集成：Kubeflow Pipeline 训练，MLflow 记录实验/注册模型 |
| **Weights & Biases (W&B)** | 实验追踪 + 可视化（含 Weave LLM 观测） | 功能与 MLflow Tracking/Tracing 重叠，但 MLflow 更偏开源/自托管和模型注册 |
| **Neptune** | 实验管理 | 与 W&B 类似，MLflow 提供更完整的模型注册与部署封装 |
| **Langfuse / LangSmith** | LLM/Agent 可观测性 | 与 MLflow Tracing 直接竞争；Langfuse 开源轻量，LangSmith 绑定 LangChain 生态，MLflow 优势在于与模型注册/评估一体化 |
| **DVC** | 数据与模型版本化（Git 大文件） | 可与 MLflow 互补：DVC 管数据版本，MLflow 管实验元数据和模型注册 |
| **TensorBoard** | 训练可视化 | MLflow UI 也支持 metric 图表；TensorBoard 更偏深度学习训练过程 |
| **OpenLLMetry / Phoenix (Arize)** | OTel 系 LLM 观测 | 与 MLflow Tracing 同为 OTel 生态；MLflow 额外提供评估、Prompt 与模型治理闭环 |
| **KServe** | 模型服务 | 可直接加载 MLflow Model Registry 中的模型为在线服务 |
| **Git** | 代码版本 | MLflow 记录代码 commit，但不替代 Git |

**关键区分**：

- **MLflow vs Kubeflow**：MLflow 管“实验和模型资产”，Kubeflow 管“ML 工作负载在 K8s 上的执行”。
- **MLflow vs W&B**：W&B 是 SaaS，协作和可视化强；MLflow 是自托管开源，模型注册和部署链路更完整。
- **MLflow vs Langfuse/LangSmith**：Langfuse/LangSmith 专注 LLM 可观测性；MLflow Tracing 与实验追踪、模型注册、评估共享同一套后端与 UI，适合想把“观测 + 评估 + 治理”放在一起的团队。
- **MLflow vs DVC**：DVC 用 Git 追踪数据/模型文件；MLflow 用数据库和 artifact store 追踪元数据与模型全生命周期。

## 1.4 MLflow 解决了什么（和不解决什么）

**MLflow 解决**：

- ✅ 实验参数、指标、artifact 的统一记录与查询。
- ✅ 模型版本化与生命周期管理（Staging / Production / Archived）。
- ✅ 模型打包标准化（flavor、signature、conda env）。
- ✅ 多种部署目标（REST、Docker、SageMaker、Azure ML、KServe 等）。
- ✅ 代码可复现（MLflow Projects）。
- ✅ GenAI/Agent 全链路观测（Tracing）、提示词版本管理（Prompt Registry）与 LLM 质量评估（GenAI Evaluation）。
- ✅ 开源、可自托管、可扩展。

**MLflow 不解决**：

- ❌ 训练执行调度（需 Kubeflow/Airflow/Spark）。
- ❌ 数据仓库/特征平台（需 Feast/DVC）。
- ❌ 模型服务的自动扩缩、A/B 测试（需 KServe/Seldon）。
- ❌ 自动化超参搜索（需 Optuna/Ray Tune/Katib，但 MLflow 可记录结果）。
- ❌ 通用可观测平台的全部能力（Tracing 聚焦 LLM/Agent 语义，基础设施监控仍需 Prometheus/Grafana）。

## 1.5 AI 平台为什么需要 MLflow

一个成熟 AI 平台的资产层通常长这样：

```
数据科学家 / 算法工程师
        │
        ▼
[开发环境：Jupyter / Notebook / IDE]
        │
        ▼
[训练编排：Kubeflow / Airflow / Ray]
        │
        ▼
[实验与模型资产层：MLflow]
        │  ├─ Tracking：Run / params / metrics / artifacts
        │  ├─ Model Registry：versions / stages / aliases
        │  └─ Models：packaging / flavors / signatures
        │
        ▼
[模型服务：KServe / Seldon / Triton / 自研]
        │
        ▼
[监控与反馈：Prometheus / Grafana / A/B 测试]
```

MLflow 是这一层里**把实验和模型变成可管理资产**的关键：

- 对**数据科学家**：一行代码记录实验，UI 上对比不同 Run。
- 对**ML 工程师**：通过 Model Registry 拿到带版本和签名的模型，部署到 KServe。
- 对**SRE/平台工程师**：统一 backend store 和 artifact store，做备份、权限、审计。

## 本章小结

- **痛点**：实验不可复现、模型版本混乱、部署链路断裂；GenAI 时代又增加了“提示词无版本、LLM 调用黑盒、质量无法量化”的新痛点。
- **定位**：MLflow 是开源 ML/GenAI 生命周期管理平台，聚焦实验追踪、模型打包、模型注册，并在 3.x 加入 Tracing、Prompt Registry 与 GenAI Evaluation。
- **对比**：比 Kubeflow 更偏资产层；比 W&B/Neptune 更偏自托管和部署链路；与 Langfuse/LangSmith 在 LLM 观测上竞争但胜在与评估/治理一体化；与 DVC 互补。
- **价值**：把模型从脚本集合变成可追溯、可版本化、可部署的资产。

**参考来源**

- [MLflow — What is MLflow?](https://mlflow.org/docs/latest/what-is-mlflow.html)
- [MLflow — Getting Started](https://mlflow.org/docs/latest/getting-started/index.html)
- [MLflow 3 Release Notes](https://mlflow.org/releases/3/)
- [MLflow GenAI 文档](https://mlflow.org/docs/latest/genai/)
- [MLflow GitHub](https://github.com/mlflow/mlflow)
- 本手册 [Kubeflow](../kubeflow/)、[KServe](../kserve/)

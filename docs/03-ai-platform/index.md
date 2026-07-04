# AI 平台篇

本章节覆盖把模型训练、推理、数据流水线与实验管理串成完整生产链路的 AI 平台组件。

## 已上线主题

- **[Ray](/03-ai-platform/ray/)** — 统一分布式 Python 计算框架：tasks + actors + Plasma 对象存储，支撑训练、推理、数据、RL、超参搜索。
- **[KServe](/03-ai-platform/kserve/)** — Kubernetes 上的标准化模型服务平台：InferenceService + ServingRuntime + InferenceGraph，统一协议、扩缩、金丝雀与多 runtime 编排。
- **[Kubeflow](/03-ai-platform/kubeflow/)** — Kubernetes 上的 ML 平台：Notebook + Pipelines + Katib + Training Operator + KServe + Central Dashboard，覆盖 ML 全生命周期。
- **[MLflow](/03-ai-platform/mlflow/)** — 开源 ML 生命周期平台：Tracking + Models + Model Registry，实验追踪、模型打包、版本治理与生产部署。

## 计划中主题

- Airflow
- Feast
- KubeRay

> AI 平台负责把模型训练、实验管理、模型服务、特征工程和数据流水线串成完整的生产链路。

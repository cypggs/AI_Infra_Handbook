# 11. 延伸阅读

## 官方文档

- [Kubeflow 官网](https://www.kubeflow.org/)
- [Kubeflow 官方 GitHub](https://github.com/kubeflow/kubeflow)
- [Kubeflow Pipelines GitHub](https://github.com/kubeflow/pipelines)
- [Kubeflow Pipelines AGENTS.md](https://github.com/kubeflow/pipelines/blob/master/AGENTS.md)
- [Kubeflow Katib GitHub](https://github.com/kubeflow/katib)
- [Kubeflow Trainer GitHub](https://github.com/kubeflow/trainer)
- [Kubeflow SDK GitHub](https://github.com/kubeflow/sdk)
- [Kubeflow Manifests GitHub](https://github.com/kubeflow/manifests)
- [Kubeflow KServe GitHub](https://github.com/kubeflow/kserve)

## 核心论文与博客

- [Kubeflow 1.10 Release Announcement（2025-03）](https://blog.kubeflow.org/kubeflow-1.10-release/)
- [Kubeflow 1.11 Release Announcement（2025-12）](https://blog.kubeflow.org/kubeflow-1.11-release/)
- [Kubeflow Community Distribution 26.03 Release（2026-04）](https://blog.kubeflow.org/kubeflow-26.03-release/)
- [Kubeflow Manifests Releases（当前稳定版 26.03.1，2026-06）](https://github.com/kubeflow/manifests/releases)
- [Kubeflow Graduation 博客（2026-08）](https://blog.kubeflow.org/graduation/)
- [CNCF 宣布 Kubeflow 毕业（2026-08-17）](https://www.cncf.io/announcements/2026/08/17/cncf-announces-kubeflows-graduation-solidifying-the-standard-for-cloud-native-ai-operations/)
- [Kubeflow Trainer v2.2 Release（2026-03）](https://blog.kubeflow.org/kubeflow-trainer-v2.2-release/)
- [Kubeflow Trainer v2.3.0 Release Notes（2026-08）](https://github.com/kubeflow/trainer/releases/tag/v2.3.0)
- [Kubeflow SDK 0.5.0 Release Notes（2026-08）](https://github.com/kubeflow/sdk/releases/tag/0.5.0)
- [CNCF 博客 — Kubeflow SDK Evolution: One Million Downloads and Counting（2026-08）](https://www.cncf.io/blog/2026/08/03/kubeflow-sdk-evolution-one-million-downloads-and-counting/)
- [KServe v0.21.0 Release Notes（2026-09）](https://github.com/kserve/kserve/releases/tag/v0.21.0)

## 关键工程文章

- [Kubeflow Trainer V2 迁移指南](https://trainer.kubeflow.org/en/latest/operator-guides/migration.html)
- [KFP v2 核心函数文档](https://www.kubeflow.org/docs/components/pipelines/user-guides/core-functions/)
- [Katib 超参搜索算法对比](https://www.kubeflow.org/docs/components/katib/user-guides/hyperparameter-tuning/)
- [Kubeflow SDK 官方文档](https://sdk.kubeflow.org/)

## 本手册相关主题

| 主题 | 关系 | 链接 |
|---|---|---|
| Kubernetes | Kubeflow 底座 | [Kubernetes](../../02-cloud-native/kubernetes/) |
| Operator 模式 | Kubeflow 每个组件都是 Operator | [Operator 模式](../../02-cloud-native/operator/) |
| Helm | 安装辅助 | [Helm](../../02-cloud-native/helm/) |
| KServe | Kubeflow 的模型服务组件 | [KServe](../kserve/) |
| Ray | 分布式训练/推理补充 | [Ray](../ray/) |
| MLflow | 实验追踪与模型注册，可与 Kubeflow Pipelines 集成 | [MLflow](../mlflow/) |
| KubeRay | Ray 在 K8s 上的 Operator，可与 Kubeflow 互补 | [KubeRay](../kuberay/) |
| Airflow | 工作流编排；可与 Kubeflow Pipelines 互补 | [Airflow](../airflow/) |
| 特征平台与训练数据基础设施 | 特征生产/消费与流水线偏斜治理，Kubeflow Pipelines 的上游数据源 | [特征平台](../feature-store/) |
| AI SRE | 生产可观测与成本治理 | [AI SRE](../../07-ai-sre/) |

## 推荐学习路径

1. **先修**：Kubernetes、Operator 模式、容器基础。
2. **入门**：本地 kind 安装 Kubeflow（或 `pip install kubeflow` 只装 SDK），跑官方 [MNIST Pipeline 示例](https://github.com/kubeflow/pipelines/tree/master/samples)。
3. **进阶**：写一个自己的 @dsl.component，接入 S3 artifact；用 Katib 调参（Trial 跑 TrainJob）；用 torchtune 运行时做一次 LoRA 微调。
4. **生产**：独立组件安装、Istio 认证、多租户 ResourceQuota、SeaweedFS/PSS 基线、Prometheus 监控、升级演练。
5. **源码**：阅读 `kubeflow/pipelines/backend`、`kubeflow/trainer/pkg/controller`（V2）、`kubeflow/katib/pkg/controller.v1beta1`、`kubeflow/sdk`。

## 社区与生态

- [Kubeflow Slack](https://www.kubeflow.org/docs/about/community/#kubeflow-slack)
- [Kubeflow 社区会议](https://www.kubeflow.org/docs/about/community/)
- [Kubeflow Community Showcase 2026（CNCF 虚拟活动）](https://community2.cncf.io/events/details/cncf-virtual-project-events-hosted-by-cncf-presents-kubeflow-community-showcase-2026-genai-and-mlops-in-action/)
- [CNCF Kubeflow 项目页（已毕业）](https://www.cncf.io/projects/kubeflow/)
- [KubeCon NA 2026 — A Decade of AI on Kubernetes: Kubeflow's Journey to CNCF Graduation（2026-11，Salt Lake City）](https://events.linuxfoundation.org/kubecon-cloudnativecon-north-america/)

**本章小结**

- 官方文档和 GitHub 是持续学习的核心来源；版本发布博客（1.10/1.11/26.03/Trainer v2.2/v2.3）与 2026-08 的 CNCF 毕业公告是跟进演进的最好材料。
- Kubeflow 与 Kubernetes、Operator、KServe、Ray、MLflow、KubeRay、AI SRE 等主题紧密相连。
- 学习路径遵循：本地体验 → 自定义 Pipeline → LLM 微调 → 生产部署 → 源码阅读。

# 11. 延伸阅读

## 官方文档

- [Kubeflow 官网](https://www.kubeflow.org/)
- [Kubeflow 官方 GitHub](https://github.com/kubeflow/kubeflow)
- [Kubeflow Pipelines GitHub](https://github.com/kubeflow/pipelines)
- [Kubeflow Pipelines AGENTS.md](https://github.com/kubeflow/pipelines/blob/master/AGENTS.md)
- [Kubeflow Katib GitHub](https://github.com/kubeflow/katib)
- [Kubeflow Training Operator GitHub](https://github.com/kubeflow/training-operator)
- [Kubeflow Manifests GitHub](https://github.com/kubeflow/manifests)
- [Kubeflow KServe GitHub](https://github.com/kubeflow/kserve)

## 核心论文与博客

- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629) — 与本主题无直接关联，但涉及 Agent 规划，可参考本手册 Agent 篇。
- Kubeflow 最初由 Google 发布，相关早期论文可参考 [Kubeflow: Machine Learning on Kubernetes](https://arxiv.org/abs/2406.00xx)（如存在）。

## 关键工程文章

- [Kubeflow 1.9/1.11 Release Notes](https://github.com/kubeflow/website/blob/master/content/en/docs/kubeflow-distribution/releases/)
- [KFP v2 迁移指南](https://www.kubeflow.org/docs/components/pipelines/user-guides/core-functions/)
- [Katib 超参搜索算法对比](https://www.kubeflow.org/docs/components/katib/user-guides/hyperparameter-tuning/)
- [Training Operator 弹性训练](https://www.kubeflow.org/docs/components/training/user-guides/)

## 本手册相关主题

| 主题 | 关系 | 链接 |
|---|---|---|
| Kubernetes | Kubeflow 底座 | [Kubernetes](../../02-cloud-native/kubernetes/) |
| Operator 模式 | Kubeflow 每个组件都是 Operator | [Operator 模式](../../02-cloud-native/operator/) |
| Helm | 安装辅助 | [Helm](../../02-cloud-native/helm/) |
| KServe | Kubeflow 的模型服务组件 | [KServe](../kserve/) |
| Ray | 分布式训练/推理补充 | [Ray](../ray/) |
| MLflow | 实验追踪与模型注册，可与 Kubeflow Pipelines 集成 | [MLflow](../mlflow/) |
| AI SRE | 生产可观测与成本治理 | [AI SRE](../../07-ai-sre/) |

## 推荐学习路径

1. **先修**：Kubernetes、Operator 模式、容器基础。
2. **入门**：本地 kind 安装 Kubeflow，跑官方 [MNIST Pipeline 示例](https://github.com/kubeflow/pipelines/tree/master/samples)。
3. **进阶**：写一个自己的 @dsl.component，接入 S3 artifact；用 Katib 调参；用 PyTorchJob 分布式训练。
4. **生产**：独立组件安装、Istio 认证、多租户 ResourceQuota、Prometheus 监控、升级演练。
5. **源码**：阅读 `kubeflow/pipelines/backend`、`training-operator/pkg/controller.v1`、`katib/pkg/controller.v1beta1`。

## 社区与生态

- [Kubeflow Slack](https://www.kubeflow.org/docs/about/community/#kubeflow-slack)
- [Kubeflow 社区会议](https://www.kubeflow.org/docs/about/community/)
- [KubeCon + AICon Kubeflow 议题](https://www.cncf.io/online-programs/)

**本章小结**

- 官方文档和 GitHub 是持续学习的核心来源。
- Kubeflow 与 Kubernetes、Operator、KServe、Ray、MLflow、AI SRE 等主题紧密相连。
- 学习路径遵循：本地体验 → 自定义 Pipeline → 生产部署 → 源码阅读。

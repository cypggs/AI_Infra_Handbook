# 11. 延伸阅读与总结

> 一句话理解：MLflow 不是孤立的工具，它与 **Kubeflow、KServe、DVC、W&B、Neptune、Delta Lake** 等共同构成 MLOps 工具链；学完本章后，建议沿着“实验追踪 → 模型治理 → 模型服务”的路线继续深入。

## 11.1 核心官方资源

| 资源 | 说明 |
|---|---|
| [MLflow 官方文档](https://mlflow.org/docs/latest/index.html) | 最权威、最及时的参考 |
| [MLflow GitHub](https://github.com/mlflow/mlflow) | 源码、issue、release note |
| [MLflow Quickstart](https://mlflow.org/docs/latest/getting-started/intro-quickstart/index.html) | 30 分钟上手 |
| [MLflow Model Registry](https://mlflow.org/docs/latest/model-registry.html) | 模型治理核心 |
| [MLflow Tracking Server](https://mlflow.org/docs/latest/tracking/server.html) | 生产部署必读 |

## 11.2 相邻主题交叉引用

| 主题 | 关系 | 链接 |
|---|---|---|
| Kubeflow | 编排 + 工作流；训练 step 中调用 MLflow | [Kubeflow 总览](../kubeflow/index.md) |
| KubeRay | 训练作业可跑在 KubeRay 集群上 | [KubeRay 总览](../kuberay/index.md) |
| Airflow | 工作流编排；可编排 MLflow 训练/注册流水线 | [Airflow 总览](../airflow/index.md) |
| KServe | 模型服务；可加载 MLflow 模型 | [KServe 总览](../kserve/index.md) |
| vLLM | 大模型推理；MLflow 可注册 PyTorch 大模型 | [vLLM 总览](../../04-llmops/vllm/index.md) |
| SGLang | 大模型结构化输出；可与 MLflow 模型服务结合 | [SGLang 总览](../../04-llmops/sglang/index.md) |
| TensorRT-LLM | 高性能推理；模型可打包进 MLflow artifact | [TensorRT-LLM 总览](../../04-llmops/tensorrt-llm/index.md) |
| Agent Runtime | Agent 训练实验追踪 | [Agent Runtime 总览](../../05-agent/agent-runtime/index.md) |

## 11.3 进阶论文与文章

| 类型 | 资源 | 看点 |
|---|---|---|
| 实践 | [MLflow at Databricks](https://www.databricks.com/product/machine-learning/mlflow) | 托管版与企业治理 |
| 实践 | [MLOps Community — MLflow Best Practices](https://mlops.community/) | 社区经验 |
| 对比 | [Weights & Biases vs MLflow](https://docs.wandb.ai/guides/integrations/mlflow) | 商业与开源差异 |
| 对比 | [Neptune vs MLflow](https://neptune.ai/blog/mlflow-vs-neptune) | 实验追踪对比 |
| 工具链 | [DVC + MLflow](https://dvc.org/doc/use-cases/versioning-data-and-models) | 数据版本与模型版本结合 |

## 11.4 推荐学习路径

1. **第 1 周**：精读本主题 01-05 章，运行 Mini Demo。
2. **第 2 周**：读 06 源码分析 + 07-09 生产与最佳实践；尝试用 PostgreSQL + S3 部署本地 Tracking Server。
3. **第 3 周**：与 Kubeflow Pipeline 或 KServe 联调一个端到端案例。
4. **第 4 周**：读官方 release note，关注 2.x 新特性（如 tracing、prompt engineering UI、gateway）。

## 11.5 一句话总结

MLflow 是 MLOps 的“实验记录本 + 模型仓库”：

- **Tracking** 让每次训练有迹可循；
- **Models** 让模型可被标准化打包与部署；
- **Model Registry** 让模型版本、阶段、别名成为可被工程化管理的资源。

它与 Kubeflow、KServe、vLLM 等工具组合，构成从实验到生产的完整 AI 基础设施链路。

## 本章小结

- 官方文档和 GitHub 是最权威的学习来源。
- MLflow 与 Kubeflow、KServe、vLLM 等主题形成互补。
- 学习路径建议：先本地 Demo，再生产部署，最后与上下游工具集成。

**参考来源**

- [MLflow 官方文档](https://mlflow.org/docs/latest/index.html)
- [MLflow GitHub](https://github.com/mlflow/mlflow)
- 本手册相关主题总览

# 9. 最佳实践

> 一句话理解：Kubeflow 平台是否好用，80% 取决于**Pipeline 怎么写、artifact 怎么管、资源怎么限、多租户怎么分**。

## 9.1 Pipeline 编写

### 用 Component 封装可复用步骤

```python
@dsl.component(
    base_image="python:3.10",
    packages_to_install=["pandas", "scikit-learn"]
)
def preprocess(input_path: str, output_path: str):
    import pandas as pd
    df = pd.read_csv(input_path)
    # ...
    df.to_csv(output_path, index=False)
```

- 每个 component 只干一件事。
- 明确声明输入/输出类型，便于编译器校验。

### 版本化 Pipeline

```python
compiler.Compiler().compile(train_pipeline, 'train_pipeline-v1.0.0.yaml')
```

- Pipeline YAML 存入 Git / 对象存储，和模型版本一一对应。
- 上传时带上版本标签，方便回滚。

### 利用 Cache

KFP v2 默认会缓存未变更的 step。注意：

- 避免在 component 里写非确定性逻辑（如随机种子未固定）。
- 对“数据预处理”等耗时步骤，缓存收益最大。

### 失败重试

```python
@dsl.pipeline
def my_pipeline():
    train_task = train_model(...)
    train_task.set_retry(
        num_retries=3,
        backoff_duration="30s",
        backoff_factor=2,
    )
```

## 9.2 Artifact 与可复现

- **所有输入/输出走 artifact store**（S3 / GCS / MinIO），不要写本地临时路径。
- **固定随机种子**：在训练 component 里 `torch.manual_seed(42)`、`numpy.random.seed(42)`。
- **记录环境**：把依赖版本、镜像 digest、代码 commit 写入 ML Metadata。
- **数据集版本化**：用 DVC / LakeFS / 对象存储版本控制训练数据。

## 9.3 Katib 调参

- **先粗搜再细搜**：先用 random/grid 确定大致范围，再用 bayesian/tpe 精细搜索。
- **限制 Trial 数量**：设置合理的 `maxTrialCount` 和 `parallelTrialCount`。
- **使用 Early Stopping**：medianstop 可节省大量计算资源。
- **metrics 路径统一**：训练代码把指标写到 `/katib/metrics/metrics.json`。

```python
import json
metrics = {"loss": val_loss, "accuracy": acc}
with open("/katib/metrics/metrics.json", "w") as f:
    json.dump(metrics, f)
```

## 9.4 Training Operator

- **合理设置 replica 数**：先从小规模验证，再扩大 Worker 数。
- **使用 Elastic Training**：PyTorchJob 支持动态扩缩，可配合 Spot 实例。
- **checkpoint 定期保存**：防止训练中断后从头开始。
- **分布式通信**：确保节点间网络带宽足够；MPIJob 需要 RDMA/InfiniBand 时配置 `hostNetwork`。

## 9.5 Notebook 与开发环境

- **镜像标准化**：为团队维护一组基础镜像（CPU / GPU / 特定框架版本）。
- **自动休眠**：非工作时间 scale Notebook StatefulSet 到 0，释放 GPU。
- **PVC 大小规划**：避免用户目录满导致训练失败；使用动态扩容。
- **禁止在 Notebook 里跑生产训练**：Notebook 只做开发/调试，生产训练走 Pipeline / TrainingJob。

## 9.6 多租户与资源配额

- **Profile 命名规范**：与用户邮箱/团队名一致，便于审计。
- **ResourceQuota 按团队分级**：

```yaml
hard:
  requests.cpu: "20"
  requests.memory: 80Gi
  requests.nvidia.com/gpu: "4"
```

- **LimitRange**：防止用户申请过大/过小资源。
- **NetworkPolicy**：默认拒绝跨 namespace 流量，仅放行必要服务。

## 9.7 KServe 部署

- 已在 [KServe 主题](../kserve/09-best-practices) 详述，补充：
  - Pipeline 中部署 InferenceService 时，把模型 URI 作为 artifact 传递。
  - 使用 `canaryTrafficPercent` 做 A/B 测试。
  - 监控 `inference_service_ready` 与请求延迟。

## 9.8 安全

- **镜像扫描**：定期扫描 Notebook / Training 镜像漏洞。
- **最小权限 RBAC**：Central Dashboard 用户只拥有自己 namespace 权限。
- **Secrets 集中管理**：用 External Secrets Operator 把 Vault/AWS Secrets Manager 同步到 K8s Secret。
- **审计日志**：记录谁创建了 Run、Experiment、TrainingJob。

## 9.9 常见反模式

| 反模式 | 问题 | 建议 |
|---|---|---|
| 在 Notebook 里长期跑训练 | 无法复现、占用交互式资源 | 迁移到 Pipeline / TrainingJob |
| Pipeline 里硬编码路径 | 环境迁移困难 | 用参数 + artifact |
| Katib Trial 不写 metrics | 实验无法判断最优 | 统一写到约定路径 |
| 所有用户共用 default namespace | 权限混乱、资源争抢 | 用 Profile 隔离 |
| 不限制 GPU quota | 单用户耗尽集群 | ResourceQuota + LimitRange |
| 忽略 Pipeline cache | 重复执行浪费资源 | 保持 component 确定性 |

## 本章小结

- Pipeline：component 化、版本化、用缓存、加重试。
- Artifact：固定随机种子、版本化数据、记录环境。
- Katib：先粗后细、限制 Trial、用 Early Stopping。
- Training：合理 replica、checkpoint、弹性训练。
- Notebook：标准化镜像、自动休眠、禁止跑生产训练。
- 多租户：Profile + ResourceQuota + NetworkPolicy。
- 安全：最小权限、镜像扫描、Secrets 集中管理。

**参考来源**

- [KFP v2 Best Practices](https://www.kubeflow.org/docs/components/pipelines/user-guides/best-practices/)
- [Katib Hyperparameter Tuning Guide](https://www.kubeflow.org/docs/components/katib/user-guides/hyperparameter-tuning/)
- [Training Operator User Guides](https://www.kubeflow.org/docs/components/training/user-guides/)
- 本手册 [KServe 最佳实践](../kserve/09-best-practices)

# 8. 企业生产实践

> 一句话理解：KServe 落地不只是"把模型跑起来"，而是要在**多 runtime 管理、协议统一、金丝雀、扩缩容、多租户、可观测、成本**七个维度建立工程规范。

## 8.1 多 Runtime 管理与版本策略

### 集中管理 ClusterServingRuntime

生产环境建议：

- 所有 runtime 都通过 `ClusterServingRuntime` 声明，纳入 GitOps。
- 镜像指向公司内部镜像仓库，避免直接拉 Docker Hub。
- 为每个 runtime 设置 `protocolVersions`，防止用户选错协议。

```yaml
apiVersion: serving.kserve.io/v1alpha1
kind: ClusterServingRuntime
metadata:
  name: company-vllm
spec:
  supportedModelFormats:
    - name: huggingface
      version: "1"
      autoSelect: true
      priority: 2
  protocolVersions:
    - openai
  containers:
    - name: kserve-container
      image: registry.company.com/ai/vllm:2026.06.01
      args:
        - --model=/mnt/models
        - --tensor-parallel-size=2
```

### Runtime 命名规范

| 类型 | 命名示例 | 说明 |
|---|---|---|
| 社区版 | `kserve-sklearnserver` | 直接使用上游镜像 |
| 公司定制 | `company-vllm`、`company-triton` | 内部优化版本 |
| 实验版 | `company-vllm-rc` | 给特定团队试用 |

### 模型格式注册

为新框架新增 runtime 时，必须定义：

- `name`：modelFormat 名称（建议全局唯一）。
- `autoSelect`：是否允许自动选择。
- `priority`：多个 runtime 支持同一格式时的优先级。
- `version`：可选，区分同一格式的不同版本。

## 8.2 协议统一：不要三种协议混用

KServe 支持 V1/V2/OpenAI，但生产上最好统一：

- **LLM/Agent 平台**：全部走 OpenAI-compatible，SDK 生态最好。
- **传统 ML 平台**：全部走 V2（Open Inference Protocol），张量定义清晰。
- **遗留系统**：V1 仅作为兼容层。

统一协议的好处：

- 客户端代码可复用。
- 网关层只需一种路由/鉴权逻辑。
- 监控指标口径一致。

如果必须混合，建议在网关层做协议转换，而不是让用户感知差异。

## 8.3 金丝雀与 A/B 测试

### 推荐流程

1. **准备新版本**：用新 `storageUri` 或新 `runtime` 镜像创建 IS 的 canary 部分。
2. **小流量验证**：设置 `canaryTrafficPercent: 5`。
3. **观察指标**：错误率、P99 延迟、GPU 利用率、模型输出一致性。
4. **逐步放大**：5 → 25 → 50 → 100。
5. **回滚**：一旦指标异常，把 canary 比例拉回 0。

### 关键指标

| 指标 | 阈值建议 |
|---|---|
| 错误率 | < 0.1% |
| P99 延迟 | 不超过基线 20% |
| GPU 利用率 | 不骤降（模型是否正常加载） |
| 输出一致性 | 新/老版本同输入输出差异在业务允许范围 |

## 8.4 扩缩容：GPU 场景的生死线

### 不要对 GPU 大模型开 scale-to-zero

- 70B 模型加载可能需要 5-10 分钟。
- 冷启动会导致请求超时、用户体验极差。
- **GPU 生产环境统一用 RawDeployment + minReplicas >= 1**。

### CPU 小模型可开 Serverless

- sklearn/xgboost/lightgbm 模型小、启动快。
- 开发测试环境可用 Knative 缩到零节省成本。

### HPA 参数建议

| 资源 | metric | target | 说明 |
|---|---|---|---|
| CPU | cpu | 60-70% | 常规 |
| GPU | gpu | 70-80% | 需要自定义 metrics adapter |
| LLM | concurrency | 每 Pod 10-50 并发 | 按模型大小调整 |

### KEDA 适用场景

- 异步推理队列（Kafka/SQS）。
- 批处理任务。
- 事件驱动的模型调用。

## 8.5 多租户与隔离

### Namespace 隔离

- 每个团队一个 namespace。
- 用 `ServingRuntime`（namespace 级）覆盖 `ClusterServingRuntime`。
- 用 ResourceQuota 限制团队 GPU/CPU/内存。

### RBAC

- 算法工程师：只给 namespace 内 IS 的 create/get/list 权限。
- 平台工程师：管理 `ClusterServingRuntime`、全局配置。
- SRE：查看所有 namespace status/metrics。

### 网络隔离

- 用 Istio AuthorizationPolicy 限制模型间调用。
- 敏感模型走 mTLS。

## 8.6 可观测性建设

### 必接指标

| 指标 | 来源 | 用途 |
|---|---|---|
| `request_count` | runtime /metrics | QPS |
| `request_latency` | runtime /metrics | P50/P99 |
| `inference_queue_length` | runtime /metrics | 是否拥塞 |
| `gpu_utilization` / `gpu_memory_used` | DCGM / runtime | GPU 健康 |
| IS condition status | controller metrics | 服务健康 |
| reconcile errors | controller metrics | 控制面健康 |

### 必设告警

- IS `Ready=False` 持续 > 5 分钟。
- 错误率 > 0.5%。
- P99 延迟突增 > 2x 基线。
- GPU 利用率骤降（可能模型 crash）。
- reconcile error rate > 0。

### 日志规范

- 统一 JSON 格式。
- 包含 `model_name`、`version`、`runtime`、`request_id`。
- 结构化日志方便 ELK/Loki 查询。

## 8.7 成本控制

### 模型合并与 ModelMesh

- 小模型多、单模型流量低时，用 ModelMesh 共享 runtime Pod。
- 减少 Pod 碎片，提高 GPU/CPU 利用率。

### 动态扩缩

- 低峰期 HPA 缩到 minReplicas。
- 非生产环境用 Serverless 缩到零。

### 模型缓存与 PVC

- 热门模型用 pre-populated PVC，避免每次从对象存储下载。
- storage-initializer 可以配置 `pvc://models-cache/llama-3`。

### 抢占式实例 / Spot

- 离线/异步推理可用 spot GPU 实例，大幅降低成本。
- 在线推理用 on-demand，保证可用性。

## 8.8 典型生产架构

```
┌─────────────────────────────────────────────────────────────┐
│                        外部用户 / API                        │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 LLM Gateway / API Gateway                   │
│           限流、鉴权、多供应商聚合、计费                       │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                         KServe                              │
│  namespace=team-a │ namespace=team-b │ namespace=platform   │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    GPU 节点池 / CPU 节点池                    │
│          vLLM / Triton / HuggingFace / sklearn ...          │
└─────────────────────────────────────────────────────────────┘
```

## 本章小结

- **Runtime 管理**：用 `ClusterServingRuntime` 集中管理，命名规范，版本受控。
- **协议统一**：LLM 走 OpenAI-compatible，传统 ML 走 V2，减少网关复杂度。
- **金丝雀**：小流量 → 观察 → 逐步放大；关注错误率、延迟、GPU、输出一致性。
- **扩缩容**：GPU 不开 scale-to-zero；CPU 小模型可 Serverless；HPA/KEDA 按场景选。
- **多租户**：namespace 隔离 + RBAC + 网络策略。
- **可观测**：runtime metrics、controller metrics、IS conditions、结构化日志。
- **成本**：ModelMesh 合并小模型、动态扩缩、PVC 缓存、spot 实例。

**参考来源**

- [KServe — Production Deployment](https://kserve.github.io/website/docs/admin/serverless/)
- [KServe — Autoscaling](https://kserve.github.io/website/docs/modelserving/autoscaling/)
- [KServe — Observability](https://kserve.github.io/website/docs/modelserving/observability/)
- [NVIDIA Triton Production Deployment Guide](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/deployment.html)

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

### 版本与升级纪律

- runtime 与 KServe 版本**成对升级并先在测试集群验证**：vLLM 升一个大版本常常伴随启动参数、指标名变化。
- **注意 v0.16 → v0.17 的升级断层**：v0.17 把安装拆成 `kserve`/`llmisvc`/`localmodel` 三个组件、Helm chart 重组为约 10 个子 chart，官方明确**不能直接 `helm upgrade`**，必须按升级指南迁移。
- 跟踪 [KServe releases](https://github.com/kserve/kserve/releases) 的安全修复（v0.21 修复了 canary 就绪前放流导致瞬时 503 等问题）。

## 8.2 协议统一：不要三种协议混用

KServe 支持 V1/V2/OpenAI，但生产上最好统一：

- **LLM/Agent 平台**：全部走 OpenAI-compatible（`/v1/chat/completions`；需要工具调用+结构化输出的新客户端用 v0.18 起支持的 `/v1/responses`；Claude 生态客户端用 v0.20 起支持的 `/v1/messages`），SDK 生态最好。
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

> **2026 年的两个改进**：llmisvc 从 v0.21 起原生支持金丝雀流量切分和 `rolloutStrategy` 滚动更新（EPP 按切分流）；传统 IS 的 canary 在 v0.21 修复了就绪前放流问题——新 revision 就绪前流量不会切换，消除了瞬时 503。

### 关键指标

| 指标 | 阈值建议 |
|---|---|
| 错误率 | < 0.1% |
| P99 延迟 | 不超过基线 20% |
| GPU 利用率 | 不骤降（模型是否正常加载） |
| 输出一致性 | 新/老版本同输入输出差异在业务允许范围 |

## 8.4 扩缩容：GPU 场景的生死线

### 不要对 GPU 大模型裸开 scale-to-zero

- 70B 模型从对象存储加载可能需要 15-20 分钟（裸拉权重）。
- 冷启动会导致请求超时、用户体验极差。
- **GPU 生产环境默认用 RawDeployment + minReplicas >= 1**。

### 用 LocalModelCache 把冷启动打下来

- v0.15 起官方口径：LocalModelCache 把大模型加载从 15-20 分钟降到约 1 分钟。
- 对"夜间低流量、白天高峰"的负载，缓存 + KEDA（按 vLLM 请求数或队列指标）可以让 LLM 也做有意义的缩容，甚至对延迟不敏感的场景评估缩到零。
- 注意 `LocalModelNodeGroup` 的 `local.path` 必须与 agent DaemonSet hostPath 一致（Helm `/mnt/models`，Kustomize `/models`），否则重复下载 + 权限报错（[kserve#5156](https://github.com/kserve/kserve/issues/5156)）。

### CPU 小模型可开 Serverless

- sklearn/xgboost/lightgbm 模型小、启动快。
- 开发测试环境可用 Knative 缩到零节省成本。

### HPA / KEDA / WVA 参数建议

| 资源 | 扩缩器 | metric | target | 说明 |
|---|---|---|---|---|
| CPU | HPA | cpu | 60-70% | 常规 |
| GPU | HPA | gpu | 70-80% | 需要自定义 metrics adapter |
| LLM（传统 IS） | KEDA | vLLM 请求数/队列长度 | 按模型大小调 | v0.15 起官方支持 |
| LLM（llmisvc） | WVA（HPA/KEDA 后端） | variant 级配置 | prefill/decode 分开调 | v0.17+；v0.21 起 KEDA 直接扩缩 |

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
| EPP 缓存命中率/打分耗时 | EPP metrics（llmisvc） | 路由质量；命中率骤降说明前缀局部性差或 Pod 频繁重建 |

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

### 模型缓存：LocalModelCache 取代"手工 PVC 预热"

- **首选官方 LocalModelCache**（v0.15+）：节点组级声明式缓存，agent 自动下载/清理，还免除了手工维护 pre-populated PVC 的脏活。
- llmisvc 从 v0.19 起同样支持；这是 2026 年 LLM 降本的第一手段——省的不是存储钱，是"每次扩容等 20 分钟"的 GPU 空转。

### 模型合并与 ModelMesh（历史方案）

- ModelMesh 已于 **2026-04-14 归档**，不要再用于新部署；老用户迁移到 RawDeployment + 多个轻量 IS 共享 runtime 镜像。
- 小模型多、单模型流量低的场景，可以用"同一镜像 + 不同 storageUri 的多个小 IS"近似达到密度效果，同时保留独立扩缩和金丝雀能力。

### 动态扩缩

- 低峰期 HPA/KEDA/WVA 缩到 minReplicas。
- 非生产环境用 Serverless 缩到零。

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
│        LLM Gateway / Envoy AI Gateway / API Gateway         │
│      限流（支持 token 级）、鉴权、多供应商聚合、计费           │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   KServe（v0.17+ 三分组件）                  │
│  kserve：IS / ServingRuntime / InferenceGraph               │
│  llmisvc：LLMInferenceService → InferencePool + EPP          │
│  localmodel：LocalModelCache + node agent                    │
│  namespace=team-a │ namespace=team-b │ namespace=platform   │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│         GPU 节点池（NVMe 本地缓存）/ CPU 节点池               │
│     vLLM（PD 分离/多节点）/ Triton / HuggingFace / sklearn   │
└─────────────────────────────────────────────────────────────┘
```

## 本章小结

- **Runtime 管理**：用 `ClusterServingRuntime` 集中管理，命名规范，版本受控；v0.16→v0.17 升级必须走官方迁移指南。
- **协议统一**：LLM 走 OpenAI-compatible（含 responses/messages），传统 ML 走 V2，减少网关复杂度。
- **金丝雀**：小流量 → 观察 → 逐步放大；llmisvc v0.21 起原生支持，传统 IS 的就绪前放流问题已修复。
- **扩缩容**：GPU 默认不开裸 scale-to-zero，上 LocalModelCache 后再评估激进缩容；llmisvc 用 WVA（HPA/KEDA）。
- **多租户**：namespace 隔离 + RBAC + 网络策略。
- **可观测**：runtime metrics、controller metrics、IS conditions、结构化日志；llmisvc 关注 EPP 指标与全链路 tracing（v0.20+）。
- **成本**：LocalModelCache 取代手工 PVC 预热；ModelMesh 已归档勿用；spot 实例用于离线推理。

**参考来源**

- [KServe — Production Deployment](https://kserve.github.io/website/docs/admin/serverless/)
- [KServe — Autoscaling](https://kserve.github.io/website/docs/modelserving/autoscaling/)
- [KServe — LocalModelCache 文档](https://kserve.github.io/website/docs/0.17/model-serving/generative-inference/modelcache/localmodel)
- [KServe — Observability](https://kserve.github.io/website/docs/modelserving/observability/)
- [KServe v0.17 发布公告（安装拆分与升级注意事项）](https://kserve.github.io/website/blog/kserve-0.17-release)
- [Red Hat — ModelMesh/Serverless 迁移指南](https://access.redhat.com/articles/7134025)
- [NVIDIA Triton Production Deployment Guide](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/deployment.html)

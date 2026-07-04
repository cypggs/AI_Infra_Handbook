# 5. 核心模块

> 一句话理解：KServe 控制面由**Controller、Webhook、Runtime Manager、Ingress/Gateway Manager、Autoscaler 集成、Metrics/Agent** 六大模块组成；它们各司其职，又通过 K8s API Server 和 CRD 协同。

## 5.1 InferenceService Controller

这是 KServe 的"心脏"。它监听 `InferenceService` CRD，把用户意图翻译成底层资源。

### 主要职责

1. **解析 spec**：提取 predictor/transformer/explainer、modelFormat、storageUri、resources、replicas。
2. **选 runtime**：调用 Runtime Manager 匹配 `ServingRuntime`。
3. **构建 PodSpec**：注入 model server container、storage-initializer、transformer/explainer。
4. **创建/更新底层资源**：
   - Serverless：Knative Service。
   - RawDeployment：Deployment、Service、Ingress、HPA。
5. **处理 finalizer**：清理资源时确保优雅删除。
6. **更新 status**：写回 conditions 和 URL。

### 关键代码路径（概念级）

```
Reconcile(ctx, req)
  │
  ├─ isvc := Get(InferenceService, req.Name, req.Namespace)
  │
  ├─ if isvc.DeletionTimestamp != nil
  │     └─ handle finalizer cleanup
  │
  ├─ if !finalizer exists
  │     └─ add finalizer
  │
  ├─ isvc.InitializeConditions()
  │
  ├─ predictorReconciler.Reconcile(isvc)
  │     ├─ runtime := ResolveRuntime(isvc.spec.predictor.model)
  │     ├─ podSpec := BuildPodSpec(runtime, isvc)
  │     ├─ Deploy(podSpec)  // Knative or RawDeployment
  │     └─ UpdateStatus(isvc, predictorStatus)
  │
  ├─ transformerReconciler.Reconcile(isvc)  // 可选
  ├─ explainerReconciler.Reconcile(isvc)    // 可选
  │
  ├─ ingressReconciler.Reconcile(isvc)
  │     └─ CreateOrUpdate(Ingress/VirtualService)
  │
  ├─ autoscalerReconciler.Reconcile(isvc)
  │     └─ CreateOrUpdate(HPA / Knative PA annotations)
  │
  └─ UpdateStatus(isvc)
```

## 5.2 Webhook（Admission Controller）

KServe 的 webhook 在资源进入 etcd 前拦截并处理。

### Defaulting

- 给未填字段补默认值：
  - `runtime`：根据 `modelFormat` 自动选择。
  - `protocolVersion`：默认 v1 或 v2。
  - `containerConcurrency`（Serverless）。
- 设置默认 resources、security context。

### Validating

- 校验 `storageUri` 是否合法（`gs://`、`s3://`、`pvc://`、`http://`）。
- 校验 `canaryTrafficPercent` 在 0-100。
- 校验 `modelFormat` 与 `runtime` 是否兼容。
- 校验 `minReplicas <= maxReplicas`。

### Mutating

- 注入 sidecar（transformer/explainer）。
- 注入 storage-initializer init container。
- 设置 Pod label/annotation 供网关选择。

## 5.3 Runtime Manager（ServingRuntime Controller）

负责维护 runtime 注册表，并供 IS Controller 查询。

### 注册表结构

```python
# 伪代码
registry = {
    "sklearn": [
        Runtime(name="kserve-sklearnserver", autoSelect=True, priority=1),
    ],
    "huggingface": [
        Runtime(name="kserve-huggingfaceserver", autoSelect=True, priority=1),
        Runtime(name="custom-vllm", autoSelect=True, priority=2),
    ],
}
```

### 匹配逻辑

```python
def resolve_runtime(model_format, requested_runtime=None):
    if requested_runtime:
        return registry.get_by_name(requested_runtime)
    candidates = [r for r in registry[model_format] if r.autoSelect]
    return max(candidates, key=lambda r: (r.priority, r.name))
```

### 职责边界

- Runtime Manager 只负责"有哪些 runtime"和"怎么匹配"。
- 具体 Pod 怎么渲染由 IS Controller 完成。
- 平台团队通过新增/修改 `ClusterServingRuntime` 即可扩展 runtime，无需改代码。

## 5.4 Ingress / Gateway Manager

### Serverless 模式

由 Knative Serving 负责。KServe 只创建 Knative Service，网络栈由 Knative 维护：

- Knative Service → Configuration → Revision。
- Knative Route → traffic split。
- Knative Ingress（net-istio/net-kourier）→ Gateway/VirtualService。

### RawDeployment 模式

KServe controller 直接创建：

- K8s `Service`：ClusterIP，供集群内调用。
- `Ingress` / `VirtualService`：暴露外部域名。
- 可选 `Certificate`：自动 TLS。

### 支持的 Ingress 类

| Ingress 类 | 说明 |
|---|---|
| Istio | 最常用，功能最全。 |
| Kourier | 轻量，Knative 默认之一。 |
| Ambassador | 较少用。 |
| NGINX | K8s 原生 Ingress。 |

## 5.5 Autoscaler 集成

### Knative Pod Autoscaler（KPA）

- 基于**并发请求数**缩放。
- 配置项：
  - `autoscaling.knative.dev/target-utilization-percentage`
  - `autoscaling.knative.dev/stable-window`
  - `autoscaling.knative.dev/metric`
- 支持 scale-to-zero。

### Horizontal Pod Autoscaler（HPA）

- 基于 CPU/GPU 利用率或自定义 metrics。
- 配置项：
  - `serving.kserve.io/metric`: cpu / gpu / memory
  - `serving.kserve.io/targetUtilizationPercentage`
  - `serving.kserve.io/minReplicas` / `maxReplicas`

### KEDA

- 基于事件源（Kafka queue、SQS、Prometheus metrics）扩缩。
- 适合异步推理、批处理队列。

### 选型建议

| 场景 | 推荐 |
|---|---|
| CPU 小模型、流量波动大 | KPA（Serverless） |
| GPU/LLM、冷启动不可接受 | HPA（RawDeployment） |
| 异步队列 | KEDA |
| 高并发低延迟 | 预热 + HPA |

## 5.6 Storage Initializer

一个轻量 init container，负责把模型从远端拉到本地。

### 支持的存储后端

| URI 前缀 | 说明 |
|---|---|
| `gs://` | Google Cloud Storage |
| `s3://` | AWS S3 / MinIO / 兼容 S3 |
| `azure://` / `wasb://` | Azure Blob |
| `hdfs://` | HDFS |
| `pvc://` | 已有 PVC |
| `http(s)://` | HTTP 下载 |

### 工作流程

1. 读取 `spec.predictor.model.storageUri`。
2. 根据前缀选择下载器。
3. 下载到 `/mnt/models`。
4. runtime 从该目录加载模型。

### 安全

- 使用 `serviceAccountName` 绑定云厂商 IAM role（如 IRSA、Workload Identity）。
- 避免把 credential 写进 spec。

## 5.7 Agent / Queue-Proxy

### queue-proxy（Serverless）

Knative 注入的 sidecar，职责：

- 队列缓冲 Activator 发来的请求。
- 统计并发并上报 autoscaler。
- 优雅停机（drain）。
- 返回 queue metrics。

### agent（RawDeployment / ModelMesh）

KServe agent 职责视场景而定：

- RawDeployment：可选，辅助 storage/modelmesh。
- ModelMesh：核心组件，负责模型加载调度。

## 5.8 Metrics 与可观测模块

KServe 通过标准化方式暴露可观测数据：

### Runtime 指标

每个 runtime 在 `/metrics` 暴露 Prometheus 指标：

```
request_count
request_latency_bucket
inference_queue_length
nvidia_gpu_memory_used_bytes  # GPU runtime
```

### Controller 指标

KServe controller 暴露：

- reconcile 次数、延迟、错误数。
- Inferenceservice 数量按状态分布。

### Status Conditions

IS status 中的 condition 是 SRE 最关心的"健康信号"：

```yaml
status:
  conditions:
    - type: PredictorReady
      status: "True"
    - type: TransformerReady
      status: "True"
    - type: ExplainerReady
      status: "True"
    - type: IngressReady
      status: "True"
    - type: Ready
      status: "True"
```

### Logging 与 Tracing

- Pod 日志：runtime、storage-initializer、queue-proxy。
- Tracing：通过 Istio / OpenTelemetry 注入 trace header。

## 5.9 模块协作图

```
┌─────────────────────────────────────────────────────────────────┐
│                     KServe 控制平面                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │   Webhook    │  │ IS Controller│  │ Runtime Manager      │  │
│  │ (default/    │──▶│ (reconcile)  │──▶│ (ServingRuntime CRD) │  │
│  │  validate/   │  │              │  │                      │  │
│  │  mutate)     │  │              │◀─│                      │  │
│  └──────────────┘  └──────┬───────┘  └──────────────────────┘  │
│                           │                                     │
│           ┌───────────────┼───────────────┐                    │
│           ▼               ▼               ▼                    │
│    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐             │
│    │   Ingress   │ │  Autoscaler │ │   Storage   │             │
│    │   Manager   │ │   Manager   │ │ Initializer │             │
│    └─────────────┘ └─────────────┘ └─────────────┘             │
│                           │                                     │
│                           ▼                                     │
│                  ┌─────────────────┐                            │
│                  │  K8s API Server │                            │
│                  └─────────────────┘                            │
└─────────────────────────────────────────────────────────────────┘
```

## 本章小结

- **IS Controller**：核心控制器，负责把 IS spec 渲染成底层资源。
- **Webhook**：defaulting/validating/mutating，降低用户配置错误。
- **Runtime Manager**：维护 modelFormat → runtime 映射，支持自定义扩展。
- **Ingress/Gateway Manager**：Serverless 靠 Knative，RawDeployment 靠 KServe 自建。
- **Autoscaler 集成**：KPA（并发、缩零）、HPA（资源）、KEDA（事件）。
- **Storage Initializer**：统一模型下载，支持多协议。
- **Agent/Queue-Proxy**：Serverless 请求缓冲与扩缩信号；RawDeployment/ModelMesh 辅助。
- **Metrics**：runtime `/metrics`、controller metrics、status conditions、logs/traces。

**参考来源**

- [KServe — Controller Architecture](https://kserve.github.io/website/docs/concepts/architecture/)
- [KServe — ServingRuntime](https://kserve.github.io/website/docs/concepts/resources/servingruntime/)
- [KServe — Autoscaling](https://kserve.github.io/website/docs/modelserving/autoscaling/)
- [KServe — Storage URI](https://kserve.github.io/website/docs/modelserving/storage/)

# 3. 架构设计：控制面、数据面与网关层

> 一句话理解：KServe 的架构可以切成三块——**控制面（controller/webhook）负责把 `InferenceService` 渲染成 K8s 资源；数据面（runtime model server + queue-proxy/agent）负责实际推理；网关层（Knative/Raw Ingress）负责把外部请求路由到正确 Pod**。

## 3.1 总体架构图

```
┌──────────────────────────────────────────────────────────────────────┐
│                         外部客户端 / API 网关                          │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        Ingress / Gateway                            │
│   /v1/models/... /v2/models/... /openai/v1/chat/completions         │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
            ┌───────────────────┴───────────────────┐
            │                                       │
   Serverless 模式                              RawDeployment 模式
   (Knative Serving)                            (原生 K8s)
            │                                       │
   Knative Activator                        K8s Service
            │                                       │
            └───────────────────┬───────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         Predictor Pod                               │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Transformer Container (可选)                                   │  │
│  │  Explainer Container (可选)                                     │  │
│  ├───────────────────────────────────────────────────────────────┤  │
│  │  Model Server Runtime Container                                │  │
│  │  (vLLM / Triton / HuggingFace / sklearn / ... )                │  │
│  │  监听 /mnt/models，暴露 8080 推理端口                            │  │
│  ├───────────────────────────────────────────────────────────────┤  │
│  │  queue-proxy (Serverless 模式) / agent (RawDeployment 可选)     │  │
│  └───────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                   KServe 控制平面 (kserve-controller-manager)        │
│   - InferenceService Controller                                      │
│   - ServingRuntime Controller                                        │
│   - InferenceGraph Controller                                        │
│   - Webhook (defaulting / validating / mutating)                     │
│   - ModelMesh Controller (可选)                                      │
└──────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         Kubernetes API Server                        │
│   CRD: InferenceService, ServingRuntime, ClusterServingRuntime, ...  │
└──────────────────────────────────────────────────────────────────────┘
```

## 3.2 控制平面（Control Plane）

### kserve-controller-manager

`kserve-controller-manager` 是一个标准的 K8s Operator，内部有多个 controller：

| Controller | 职责 |
|---|---|
| `InferenceService` Controller | 监听 IS CRD，渲染 Knative Service / K8s Deployment + Service + Ingress + HPA + ConfigMap |
| `ServingRuntime` Controller | 处理 runtime 的可用性、协议版本、模型格式注册 |
| `ClusterServingRuntime` Controller | 处理集群级 runtime |
| `InferenceGraph` Controller | 把 Graph 渲染成 Knative Service / K8s Deployment |
| `TrainedModel` Controller | 在单个 IS 内动态挂载/卸载多个子模型（部分场景） |
| Webhook | defaulting、validating、mutating admission |

Controller 的核心逻辑是：

1. **watch** `InferenceService` 的变化（Informer）。
2. **reconcile**：根据 spec 计算 desired state。
3. **apply** 底层资源（Knative Service / Deployment / Service / Ingress / HPA / ServiceAccount）。
4. **update status**：把 `READY`/`PredictorReady`/`IngressReady` 等 condition 写回 IS。

### Webhook

KServe 的 webhook 做三件事：

- **Defaulting**：给未填字段补默认值（如 `modelFormat`、`runtime`、`protocolVersion`）。
- **Validating**：校验 spec 合法性（如 `canaryTrafficPercent` 范围、`storageUri` 格式）。
- **Mutating**：注入 sidecar、init container、环境变量等。

例如，用户写了 `modelFormat.name: sklearn`，但忘写 runtime，webhook 会默认补成 `kserve-sklearnserver`。

## 3.3 数据面（Data Plane）

### Model Server Runtime

数据面的核心是 runtime container。每个 runtime 通常是一个 HTTP/gRPC server，加载模型后监听固定端口（默认 8080）。KServe 维护的 runtime 包括：

| Runtime | 框架/引擎 | 典型模型 |
|---|---|---|
| `kserve-sklearnserver` | scikit-learn | 表格、分类 |
| `kserve-xgbserver` | XGBoost | 梯度提升 |
| `kserve-lgbserver` | LightGBM | 梯度提升 |
| `kserve-tensorflow` | TensorFlow SavedModel | CNN/NLP |
| `kserve-pytorchserver` | PyTorch TorchScript | CV/NLP |
| `kserve-tritonserver` | Triton | 多 backend |
| `kserve-huggingfaceserver` | HuggingFace + vLLM | LLM |
| `kserve-mlserver` | MLServer | sklearn/xgboost/ONNX |
| `kserve-paddleserver` | PaddlePaddle | 百度飞桨 |
| `kserve-custom` | 自定义 | 任意 |

### Storage Init Container

在 runtime 启动前，KServe 通常会注入一个 `storage-initializer` init container：

```yaml
initContainers:
  - name: storage-initializer
    image: kserve/storage-initializer:latest
    args:
      - s3://models/llama-3/
      - /mnt/models
```

它负责从 `storageUri`（S3/GCS/Azure/HTTPS/PVC）下载模型到 `/mnt/models`。runtime 启动后从这个目录加载模型。

### Queue-Proxy / Agent

**Serverless 模式**：Knative 会在 Pod 里注入 `queue-proxy` sidecar，负责：

- 请求队列缓冲（activator 过来的请求）。
- 并发报告给 Knative autoscaler。
- 健康检查/优雅停机。

**RawDeployment 模式**：无 queue-proxy，请求直接打到 model server。可选 `agent` 做一些辅助工作（如 modelmesh 场景）。

## 3.4 网关层（Ingress / Gateway）

KServe 把外部流量路由到模型 Pod，支持两种入口：

### Knative 入口（Serverless）

Knative 自带 Istio/Contour/Kourier/Ambassador 等 net-* 插件。KServe 创建一个 Knative Service 后，Knative 自动：

- 生成一个可路由的 URL（如 `sklearn-iris.default.example.com`）。
- 把请求路由到 revision。
- 处理金丝雀（通过 traffic split）。

### RawDeployment 入口

KServe controller 自己创建：

- K8s `Service`（ClusterIP 或 LoadBalancer）。
- `Ingress` 资源（Istio VirtualService / Kubernetes Ingress / Gateway API）。
- 可选的 SSL、host、path rewrite。

KServe 支持通过 `ingressGateway` 配置使用 Istio 或 Kourier。

### 流量治理特性

| 特性 | 实现 |
|---|---|
| 金丝雀 | Serverless 用 Knative traffic split；RawDeployment 用 Istio/VirtualService weight。 |
| A/B test | `canaryTrafficPercent` 或 `InferenceGraph` Splitter。 |
| 请求路由 | host/path/model name 路由。 |
| 超时/重试 | 网关层配置。 |
| 认证鉴权 | 与 Istio auth policy / OAuth2 proxy 集成。 |

## 3.5 Runtime 注册表与匹配

KServe 在启动时会加载所有 `ServingRuntime` 和 `ClusterServingRuntime`，形成一个内存注册表。匹配算法：

```
1. 取 IS.spec.predictor.model.modelFormat.name
2. 在注册表中过滤 supportedModelFormats[].name == modelFormat.name 的 runtime
3. 如果用户显式指定 runtime，直接用该 runtime
4. 否则，在 autoSelect=true 的 runtime 中按 priority 排序，选最高的
5. 如果多个 runtime 同 priority，按 name 字典序稳定选择
```

这个注册表让平台团队可以：

- 新增自定义 runtime（比如公司自研推理引擎）。
- 覆盖默认 runtime（比如用自编译的 vLLM 镜像替换社区版）。
- 禁用某些 runtime（删除 CR 即可）。

## 3.6 扩缩容组件

### Serverless（Knative Pod Autoscaler）

- 默认基于**并发请求数**缩放。
- `containerConcurrency` 控制每个 Pod 最大并发。
- 可配置 stable/window/target 等参数。
- 无请求时缩到 0，新请求由 Activator 队列缓冲。

### RawDeployment（HPA / KEDA）

- **HPA**：基于 CPU/GPU 利用率或自定义 metrics。
- **KEDA**：基于队列长度、Kafka lag、Prometheus metrics 等事件驱动扩缩。

KServe 通过 annotations 暴露配置：

```yaml
metadata:
  annotations:
    serving.kserve.io/autoscalerClass: hpa
    serving.kserve.io/metric: cpu
    serving.kserve.io/targetUtilizationPercentage: "60"
    serving.kserve.io/minReplicas: "1"
    serving.kserve.io/maxReplicas: "5"
```

## 3.7 可观测性组件

KServe 通过标准化接口与 Prometheus/Grafana/ELK 集成：

| 观测点 | 内容 |
|---|---|
| `/metrics` | runtime 暴露请求数、延迟、队列长度、GPU 利用率。 |
| IS `status.conditions` | `PredictorReady`、`TransformerReady`、`ExplainerReady`、`IngressReady`、`Ready`。 |
| Knative metrics | activator queue、concurrency、autoscaler 决策。 |
| Pod logs | runtime、queue-proxy、storage-initializer 日志。 |
| Tracing | 与 Jaeger/Zipkin 集成（视网关配置）。 |

## 3.8 ModelMesh（可选扩展）

KServe 还有一个子项目 **ModelMesh**，用于**高密度多模型Serving**：

- 把多个小模型加载到同一个 runtime Pod 池中。
- 根据请求动态加载/卸载模型。
- 适合模型数量很多、单个模型流量不高的场景。

ModelMesh 有独立的 controller 和 etcd-based 模型索引，是 KServe 生态的一部分，但不是默认模式。

## 3.9 模块间调用关系

用一个更紧凑的视图表示：

```
用户 apply InferenceService
   │
   ▼
K8s API Server 写入 etcd
   │
   ▼
KServe Controller（Informer）收到事件 → 加入 workqueue
   │
   ▼
Reconciler 读取 IS spec
   │
   ├─ 选 runtime（ServingRuntime 注册表）
   ├─ 生成 Knative Service / Deployment spec
   ├─ 注入 storage-initializer
   ├─ 配置 transformer/explainer
   ├─ 创建 Service / Ingress
   └─ 创建 HPA / KPA
   │
   ▼
底层 workload 运行
   │
   ▼
Gateway 暴露端点
   │
   ▼
客户端调用 → Ingress → Service → Pod → Model Server 返回结果
```

## 本章小结

- **控制面**：`kserve-controller-manager` 包含 IS/ServingRuntime/InferenceGraph 等 controller 和 webhook，负责把 CRD 渲染成 K8s 资源。
- **数据面**：model server runtime + storage-initializer + queue-proxy/agent，负责模型加载和推理。
- **网关层**：Serverless 用 Knative 自带入口；RawDeployment 用 KServe 创建的 Service/Ingress/Istio。
- **runtime 注册表**：`ServingRuntime`/`ClusterServingRuntime` 让模型格式与容器实现解耦。
- **扩缩容**：Knative KPA（缩到零、按并发） vs HPA/KEDA（生产 GPU、按资源/事件）。
- **可观测性**：`/metrics`、`status.conditions`、Knative metrics、Pod logs。
- **ModelMesh**：可选的高密度多模型扩展。

**参考来源**

- [KServe — Architecture](https://kserve.github.io/website/docs/concepts/architecture/)
- [KServe — InferenceService Status](https://kserve.github.io/website/docs/get_started/first_isvc/#3-check-the-inferenceservice-status)
- [Knative Serving docs](https://knative.dev/docs/serving/)
- [KServe — Autoscaling](https://kserve.github.io/website/docs/modelserving/autoscaling/)
- [KServe — ModelMesh](https://kserve.github.io/website/docs/modelserving/model_mesh/)

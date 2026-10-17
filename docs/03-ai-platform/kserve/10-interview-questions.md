# 10. 面试题

## 初级

### 1. KServe 是什么？解决了什么问题？

**答**：KServe 是 Kubernetes 上的标准化模型服务平台。它解决裸部署 vLLM/Triton 等引擎时重复造轮子的问题：模型下载、runtime 选择、流量接入、扩缩容、金丝雀、协议统一、可观测。

### 2. `InferenceService` 的核心字段有哪些？

**答**：`predictor`（必须）、`transformer`（可选）、`explainer`（可选）、`minReplicas`/`maxReplicas`、`canaryTrafficPercent`、`serviceAccountName`。

### 3. `ServingRuntime` 和 `ClusterServingRuntime` 有什么区别？

**答**：`ServingRuntime` 是 namespace 级，`ClusterServingRuntime` 是集群级。Controller 会同时扫描两者，namespace 级可覆盖集群级。

### 4. KServe 支持哪两种部署模式？

**答**：Serverless（基于 Knative，支持缩到零）和 RawDeployment（原生 K8s + HPA，不支持缩到零但延迟更低）。

### 5. V1、V2、OpenAI-compatible 三种协议分别适合什么场景？

**答**：V1 适合兼容 TF Serving 的遗留系统；V2（Open Inference Protocol）适合多框架统一；OpenAI-compatible 适合 LLM/Agent/Chat。

## 中级

### 6. 描述一个 `InferenceService` 从 `kubectl apply` 到可被调用的完整链路。

**答**：
1. API Server 写入 IS。
2. KServe Controller Informer 收到事件并入队。
3. Reconciler 解析 spec，匹配 ServingRuntime。
4. 渲染 PodSpec（runtime container + storage-initializer + transformer/explainer）。
5. 创建 workload（Knative Service 或 Deployment+Service+Ingress+HPA）。
6. 更新 IS status。
7. Pod 启动、下载模型、runtime 加载、readiness 通过。
8. 外部请求经 Ingress → Service → Pod → runtime 返回。

### 7. KServe 如何实现金丝雀？

**答**：用户设置 `canaryTrafficPercent`，Controller 创建新版本 revision/deployment，并通过 Knative traffic split 或 Istio VirtualService weight 切流。

### 8. 为什么 GPU 大模型生产环境通常不用 Serverless？

**答**：大模型加载时间长（分钟级），Serverless 的 scale-to-zero 会导致冷启动严重超时。生产 GPU 通常用 RawDeployment 保持 minReplicas >= 1。

### 9. 如何为团队新增一个自定义 runtime？

**答**：
1. 构建镜像，实现协议端点。
2. 写 `ClusterServingRuntime` YAML，声明 supportedModelFormats、protocolVersions、containers。
3. apply 到集群。
4. 用户写 `modelFormat.name` 即可自动匹配。

### 10. KServe 的 controller 和 webhook 分别做什么？

**答**：Controller 监听 CRD 变化并调和底层资源；Webhook 做 defaulting（补默认值）、validating（校验）、mutating（注入 sidecar/init container）。

## 高级

### 11. KServe controller 的 reconcile 为什么必须是幂等的？

**答**：Informer 可能因网络抖动、resync、status 更新触发重复事件；幂等保证多次 reconcile 不会导致资源状态漂移或重复创建。

### 12. 如果 IS 一直处于 `Ready=False`，你会怎么排查？

**答**：
1. `kubectl describe isvc` 看 status conditions 和 events。
2. 看 predictor Pod 状态：`ImagePullBackOff`、`CrashLoopBackOff`、storage-initializer 失败。
3. 看 runtime 日志：模型加载失败、端口冲突。
4. 看 Ingress/VirtualService 是否正确创建。
5. 看 HPA/KPA 状态。
6. 看 controller 日志是否有 reconcile error。

### 13. KServe 与自研网关 + 裸 vLLM 相比，优势和劣势是什么？

**答**：优势是 K8s-native、runtime 多、协议统一、生态成熟、标准化扩缩和金丝雀。劣势是学习曲线、Knative 可选依赖、对非 K8s 环境不友好。

### 14. `InferenceGraph` 能解决什么问题？给出具体场景。

**答**：把多个模型组合成推理工作流。例如 RAG：embedding 模型 → retriever → LLM，可用 Sequence 节点串联；或推荐场景用 Ensemble 做多模型投票。

### 15. 设计一个高可用的 KServe 生产集群需要考虑哪些方面？

**答**：
- Controller 多副本 + leader election。
- Webhook 高可用（避免 admission 单点）。
- GPU 节点池独立、预留节点。
- Runtime 镜像多区域缓存。
- 多可用区部署。
- Prometheus + Grafana + Alertmanager。
- 金丝雀 + HPA + PodDisruptionBudget。
- 定期备份 etcd / CRD。

### 16. LLMInferenceService 和普通 InferenceService 的本质区别是什么？

**答**：传统 IS 是"一个模型一个端点"，路由靠 kube-proxy 轮询；llmisvc 面向 LLM，数据面基于 Gateway API Inference Extension：HTTPRoute 后端指向 `InferencePool`，由 EPP（llm-d Endpoint Picker）根据 KV-Cache 前缀命中和负载打分选择 Pod，还支持 prefill/decode 分离（KV-Cache 经 NixlConnector + RoCE 传输）、LoRA 热加载、LeaderWorkerSet 多节点并行和 WVA 扩缩。它 v0.16 以 v1alpha1 引入，v0.17 宣布生产可用。

### 17. EPP 的 KV-Cache 感知路由是怎么工作的？有什么代价？

**答**：vLLM Pod 通过 ZMQ 事件（BlockStored/BlockRemoved）把 KV-Cache 块变化实时推给 EPP，EPP 维护"模型名+前缀哈希→Pod"索引；请求到来时按 scorer 管线打分（prefix-cache 权重 2.0、load-aware 权重 1.0），选最高分 Pod。代价是多一跳调度延迟和 EPP 本身的高可用运维，收益是多轮对话/RAG 场景的 TTFT 显著下降和更好的负载均衡。

### 18. KServe 如何解决大模型冷启动？ModelMesh 现在还能用吗？

**答**：三个手段：LocalModelCache（v0.15，节点本地 NVMe 缓存，加载 15-20 分钟降到约 1 分钟，llmisvc v0.19 起支持）；LMCache / KV-Cache 分层卸载（v0.15/v0.20，降 TTFT）；配合 KEDA/WVA 做有缓存支撑的快速扩容。ModelMesh 已于 2026-04 归档，不能用于新部署，迁移方向是 RawDeployment + LocalModelCache。

## 编码/设计题

### 19. 写一个 `ClusterServingRuntime`，让 KServe 支持一个自定义 Python runtime。

```yaml
apiVersion: serving.kserve.io/v1alpha1
kind: ClusterServingRuntime
metadata:
  name: company-custom-ml
spec:
  supportedModelFormats:
    - name: company-ml
      autoSelect: true
      priority: 1
  protocolVersions:
    - v2
  containers:
    - name: kserve-container
      image: registry.company.com/ai/custom-ml:v1
      args:
        - --model_dir=/mnt/models
        - --port=8080
```

### 20. 写一个 `InferenceService`，用 RawDeployment 部署一个 HuggingFace LLM，HPA 按 CPU 60% 扩缩。

```yaml
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: llama-3
  annotations:
    serving.kserve.io/deploymentMode: RawDeployment
    serving.kserve.io/autoscalerClass: hpa
    serving.kserve.io/metric: cpu
    serving.kserve.io/targetUtilizationPercentage: "60"
    serving.kserve.io/minReplicas: "2"
    serving.kserve.io/maxReplicas: "8"
spec:
  predictor:
    model:
      modelFormat:
        name: huggingface
      runtime: kserve-huggingfaceserver
      storageUri: s3://models/llama-3/
      resources:
        limits:
          nvidia.com/gpu: 2
```

## 本章小结

- 初级题聚焦概念：KServe 是什么、核心 CRD、部署模式、协议。
- 中级题聚焦流程：reconcile 链路、金丝雀、runtime 扩展、controller/webhook。
- 高级题聚焦生产与新架构：排查、HA、trade-off、InferenceGraph、llmisvc/EPP、冷启动与 ModelMesh 归档。
- 编码题考察对 YAML spec 和 runtime 抽象的掌握。

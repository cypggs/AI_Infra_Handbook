# 1. 背景：从"裸推理引擎"到统一推理平台

> 一句话理解：单独部署一个 vLLM/Triton 实例很容易，但当你要管理**几百个模型、多种框架、不同团队、金丝雀升级、自动扩缩、协议统一**时，裸引擎的人力成本会爆炸——KServe 用一层 Operator 把这些重复工程抽象掉，让"模型即服务"像 `Deployment` 一样声明式。

## 1.1 裸推理引擎的痛苦

假设你负责一个 AI 平台的模型服务层，团队里有人用 vLLM 跑 Llama、有人用 Triton 跑 BERT、有人用 TensorFlow Serving 跑推荐模型、还有人用 TorchServe。每个都要自己做这些事：

| 任务 | 裸 vLLM/Triton 时你要自己做 | KServe 接手后 |
|---|---|---|
| 模型下载/挂载 | 写 initContainer 拉 S3/GCS、PVC 挂载 | `storageUri` 声明即可 |
| runtime 选择 | 人记住"这个模型用哪个镜像" | `modelFormat.name` 自动匹配 `ServingRuntime` |
| 流量接入 | 手写 Service/Ingress/Gateway | 自动创建 Knative Service 或 K8s Service+Ingress |
| 扩缩容 | 手写 HPA/KEDA/Knative | `minReplicas`/`maxReplicas` + autoscaler 配置 |
| 缩到零 | 自己搭激活机制 | Knative 模式原生支持 |
| 金丝雀 | 手动切流量 | `canaryTrafficPercent` 声明式 |
| pre/postprocessing | 自己写 sidecar | `transformer` 字段声明 |
| 协议统一 | 每个引擎 API 不同 | V1/V2/OpenAI-compatible 统一入口 |
| 可观测 | 每个 runtime 配 metrics | 统一暴露 /metrics + 标准 condition |
| 多模型/图编排 | 自己写 DAG | `InferenceGraph` 声明式组合 |

裸引擎时每加一个模型就像重新发明一次"模型服务"，而 KServe 让这件事变成：

```yaml
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: llama-3
spec:
  predictor:
    model:
      modelFormat:
        name: huggingface        # KServe 自动选 huggingface runtime（可配 vLLM）
      storageUri: s3://models/llama-3/
      resources:
        limits:
          nvidia.com/gpu: 2
```

## 1.2 KServe 是什么

KServe（原名 KFServing）是一个 Kubernetes 上的**标准化模型服务平台**，CNCF 孵化项目。它的定位可以概括为三层：

1. **控制平面**：`kserve-controller-manager` 运行一组 Operator，管理 `InferenceService`、`ServingRuntime`、`ClusterServingRuntime`、`InferenceGraph` 等 CRD。
2. **数据平面**：一组 model server runtime（vLLM、Triton、TorchServe、TensorFlow Serving、sklearnserver、huggingfaceserver 等）+ KServe 自己的 queue-proxy/agent。
3. **流量/网关层**：把外部请求路由到具体模型 Pod，支持 canary、A/B、ensemble、transformer/explainer 链。

用一个比喻：

> **vLLM/Triton 是"发动机"，KServe 是"整车 + 自动驾驶系统"**——发动机决定跑多快，但开车还需要油门、刹车、导航、巡航、安全气囊。KServe 就是把这些东西标准化了。

## 1.3 KServe 与裸引擎 / 自研网关 / Ray Serve 的对比

| 方案 | 核心模型 | 优点 | 缺点 | 适用场景 |
|---|---|---|---|---|
| **裸 vLLM/Triton** | 手动部署 Pod/Service/Ingress | 简单、可控 | 无统一管理、重复工程 | 单模型 poc |
| **自研网关 + 引擎** | 自己写调度/扩缩/canary | 完全贴合业务 | 维护成本高、易重复造轮子 | 超大规模、有专门 infra 团队 |
| **Ray Serve** | Python-first 部署模型 | 与 Ray 生态无缝、灵活 | 不是 K8s-native，需要 Ray 集群 | 已经在用 Ray 做训练/推理 |
| **KServe** | `InferenceService` CRD + runtime 抽象 | K8s-native、runtime 多、协议统一、生态成熟 | 学习曲线、Knative 可选依赖 | 云原生 AI 平台的标准选择 |

**关键区分**：

- **KServe vs 自研网关**：自研网关通常只解决"路由 + 限流"，而 KServe 解决的是**从 CRD 到 Pod 到流量的全生命周期**。
- **KServe vs Ray Serve**：Ray Serve 是应用层框架，嵌入 Python 代码里；KServe 是 K8s 控制平面，用 YAML 声明。
- **KServe vs 单个 runtime**：KServe 不替代 vLLM/Triton，而是**编排**它们。

## 1.4 KServe 解决了什么（和不解决什么）

**KServe 解决**：

- ✅ **统一入口**：一份 `InferenceService` CRD，服务 TF/PyTorch/sklearn/XGBoost/ONNX/HuggingFace/vLLM/Triton 等任意模型。
- ✅ **runtime 解耦**：`ServingRuntime` 让模型格式和容器实现分离，团队可自研 runtime。
- ✅ **流量治理**：canary、A/B、ensemble、explainer、transformer 链。
- ✅ **弹性**：HPA/KPA/KEDA，支持缩到零（Knative）。
- ✅ **协议统一**：V1、V2（Open Inference Protocol）、OpenAI-compatible。
- ✅ **多模型/图编排**：`InferenceGraph` 把多个 InferenceService 组合成复杂推理 DAG。
- ✅ **可观测**：标准化 `/metrics`、conditions、Prometheus 集成。

**KServe 不解决**：

- ❌ **模型训练**：那是 Training Operator / Ray / Kubeflow 的活。
- ❌ **数据流水线**：那是 Argo Workflow / Spark / Flink 的活。
- ❌ **向量检索/RAG**：KServe 只管模型推理，向量库（Milvus/Pinecone）需另搭。
- ❌ **LLM 网关的多供应商聚合**：KServe 管集群内模型端点，跨云/跨供应商聚合是 LLM Gateway（如 LiteLLM）的活。
- ❌ **替代所有运维**：KServe 本身也要升级、监控、调参。

## 1.5 AI 平台为什么需要 KServe

一个成熟 AI 平台最终都会长成这样：

```
用户 / 业务系统
      │
      ▼
[LLM Gateway / API 网关]  ← 限流、鉴权、多供应商聚合
      │
      ▼
[KServe]                  ← 模型发现、路由、扩缩、金丝雀
      │
      ▼
[vLLM / Triton / HuggingFace / ...]  ← 实际跑推理
      │
      ▼
[GPU / 节点池]
```

KServe 是这一层里承上启下的关键：

- 对**算法工程师**：`kubectl apply` 一个 YAML 就能发布模型。
- 对**平台工程师**：用 runtime 抽象支持新框架，无需改 Controller。
- 对**SRE**：统一 metrics/conditions，标准化扩缩和金丝雀。

更重要的是，它是**K8s-native**的——你已有的 K8s 技能（Operator、CRD、RBAC、Ingress、HPA）全部复用。

## 本章小结

- **痛点**：裸推理引擎在模型增多、团队变多、需要灰度/弹性/协议统一时，重复工程爆炸。
- **定位**：KServe 是 K8s 上的标准化模型服务平台，核心抽象是 `InferenceService` + `ServingRuntime` + `InferenceGraph`。
- **对比**：比裸引擎多一层 Operator；比自研网关标准化；比 Ray Serve 更 K8s-native；不替代 runtime，而是编排 runtime。
- **价值**：把"发布一个模型"从工程任务变成声明式操作，是 AI 平台从 poc 走向生产的关键层。

**参考来源**

- [KServe 官网 — What is KServe?](https://kserve.github.io/website/docs/)
- [KServe GitHub](https://github.com/kserve/kserve)
- [KFServing 改名 KServe 的博客](https://blog.kubeflow.org/kfserving-becomes-kserve/)
- 本手册 [Operator 模式](../../02-cloud-native/operator/)（KServe 就是 Operator）、[vLLM](../../04-llmops/vllm/)、[Triton](../../04-llmops/triton/)。

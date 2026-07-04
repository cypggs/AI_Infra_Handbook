# 2. 核心思想：InferenceService、ServingRuntime 与数据面协议

> 一句话理解：KServe 把"模型服务"拆成三层抽象——**`InferenceService` 描述"要服务什么模型"、`ServingRuntime` 描述"用什么容器跑"、数据面协议描述"客户端怎么调用"**；在这之上再用 `InferenceGraph` 组合多个服务、`Transformer`/`Explainer` 扩展前处理/可解释性。

## 2.1 InferenceService：用户的入口

`InferenceService`（IS）是 KServe 最核心的 CRD。用户只需要声明一次，KServe 就负责剩下的所有生命周期。

```yaml
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: sklearn-iris
spec:
  predictor:
    model:
      modelFormat:
        name: sklearn
      storageUri: gs://kfserving-examples/models/sklearn/1.0/model-1
    minReplicas: 1
    maxReplicas: 5
    canaryTrafficPercent: 20
```

**核心字段**：

| 字段 | 含义 |
|---|---|
| `predictor` | **必须**。真正跑模型推理的 Pod。 |
| `transformer` | 可选。请求/响应预处理或后处理（如 tokenization、detokenization）。 |
| `explainer` | 可选。模型可解释性（如 SHAP、LIME、Anchor）。 |
| `minReplicas`/`maxReplicas` | 扩缩边界。 |
| `canaryTrafficPercent` | 金丝雀切流比例。 |
| `serviceAccountName` | 拉模型所需的权限。 |

`predictor` 有三种写法：

1. **老版框架简写**：`predictor.sklearn`、`predictor.tensorflow`、`predictor.pytorch`……（v1beta1 仍兼容，但推荐 runtime 模式）。
2. **新版 runtime 模式**：`predictor.model.modelFormat.name` + 可选 `runtime`。这是推荐方式，更灵活。
3. **自定义容器**：`predictor.containers` 直接写 container spec。

```yaml
# runtime 模式（推荐）
spec:
  predictor:
    model:
      modelFormat:
        name: huggingface
      runtime: kserve-huggingfaceserver   # 显式指定 runtime
      storageUri: s3://models/llama-3/
```

## 2.2 Predictor / Transformer / Explainer：三段式推理链

一个完整的推理请求链路可能包含：

```
客户端请求
   │
   ▼
[Ingress/Gateway]
   │
   ▼
[Transformer]  ← 前处理（tokenize、resize、特征工程）
   │
   ▼
[Predictor]    ← 模型推理
   │
   ▼
[Transformer]  ← 后处理（detokenize、格式化）
   │
   ▼
客户端响应
```

**Predictor**：核心，必须有。它通过 `ServingRuntime` 确定容器镜像、启动命令、资源。

**Transformer**：可选，用于 pre/postprocessing。典型场景：

- LLM 的 tokenize/detokenize。
- 图像分类前的 resize/normalize。
- 推荐模型前的特征拼接。

KServe 支持两种 transformer：

- **v1**：单独的 transformer Pod，KServe 自动把它串到 predictor 前。
- **v2（colocation）**：transformer 与 predictor 同 Pod，通过 localhost 通信，降低延迟。

**Explainer**：可选，用于模型可解释性。输入同样的请求，返回解释（如 SHAP values）。

## 2.3 ServingRuntime / ClusterServingRuntime：runtime 抽象

这是 KServe 架构中非常巧妙的一层——**把"模型格式"和"容器实现"解耦**。

```yaml
apiVersion: serving.kserve.io/v1alpha1
kind: ClusterServingRuntime
metadata:
  name: kserve-huggingfaceserver
spec:
  supportedModelFormats:
    - name: huggingface
      version: "1"
      autoSelect: true
      priority: 1
  protocolVersions:
    - v1
    - v2
  containers:
    - name: kserve-container
      image: kserve/huggingfaceserver:latest
      args:
        - --model_name={{.Name}}
        - --model_dir=/mnt/models
```

**关键机制**：

- 用户写 `modelFormat.name: huggingface`。
- KServe controller 扫描 namespace 的 `ServingRuntime` 或 cluster 的 `ClusterServingRuntime`。
- 找到 `supportedModelFormats` 匹配且 `autoSelect: true` 的 runtime。
- 用该 runtime 的 `containers` 模板渲染 predictor Pod。

模板变量（如 <code v-pre>{{.Name}}</code>、<code v-pre>{{.StorageURI}}</code>、<code v-pre>{{.Labels.modelName}}</code>）在 reconcile 时被替换成实际值。注意：这些 Go template 占位符只在 YAML 字符串里，不是 VitePress 行内代码，不会触发 Vue mustache 问题。

> **为什么需要这一层**：KServe 出厂支持十几种 runtime（sklearn/xgboost/lightgbm/tensorflow/pytorch/onnx/triton/huggingface/paddle），但团队也可以自定义 runtime。新框架出现时，平台工程师只需新增一个 `ClusterServingRuntime`，无需改 KServe controller 代码——这是**开闭原则**。

## 2.4 InferenceGraph：多模型组合与 DAG

当业务需要把多个模型串起来（如 A 模型 embedding → B 模型 rerank → C 模型生成），可以用 `InferenceGraph`：

```yaml
apiVersion: serving.kserve.io/v1alpha1
kind: InferenceGraph
metadata:
  name: llm-rag-pipeline
spec:
  nodes:
    root:
      routerType: Sequence
      steps:
        - serviceName: embedding-model
        - serviceName: retriever
        - serviceName: llm
```

支持的路由类型：

- **Sequence**：顺序执行。
- **Switch**：按条件路由。
- **Ensemble**：并行多模型，聚合结果（投票/平均）。
- **Splitter**：按比例分流（A/B test）。

`InferenceGraph` 让 KServe 从"单模型服务"升级到"推理工作流编排"。

## 2.5 数据面协议：V1 / V2 / OpenAI-compatible

KServe 的一个强大之处是**协议统一**。客户端调用模型时，不需要关心 backend 是 TensorFlow 还是 vLLM。

### V1 协议（传统 ML）

```bash
POST /v1/models/sklearn-iris:predict
Content-Type: application/json
{"instances": [[1.0, 2.0, 3.0, 4.0]]}
```

类似 TensorFlow Serving，适合表格/图像等传统 ML。

### V2 协议（Open Inference Protocol）

```bash
POST /v2/models/sklearn-iris/infer
Content-Type: application/json
{
  "inputs": [{"name": "input", "shape": [1,4], "datatype": "FP32", "data": [1.0,2.0,3.0,4.0]}]
}
```

标准化输入/输出张量格式，被 Triton、TorchServe、MLServer 等支持。适合多框架统一。

### OpenAI-compatible 协议（LLM）

```bash
POST /openai/v1/chat/completions
Content-Type: application/json
{"model": "llama-3", "messages": [{"role": "user", "content": "hello"}]}
```

HuggingFace runtime（基于 vLLM）和 Triton 都支持，让 LLM 服务可以直接对接 OpenAI SDK、LangChain、Cursor 等生态。

**协议选择建议**：

| 场景 | 推荐协议 |
|---|---|
| 传统 ML / 需要强类型张量 | V2 |
| 已有 TF Serving 客户端 | V1 |
| LLM / Agent / Chat | OpenAI-compatible |
| 多 runtime 混合 | 网关层统一成一种 |

## 2.6 Serverless vs RawDeployment：两种部署模式

KServe 支持两种控制平面部署模式：

### Serverless（Knative）

```yaml
metadata:
  annotations:
    serving.kserve.io/deploymentMode: Serverless
```

- 利用 Knative Serving：每个 IS 是一个 Knative Service。
- **缩到零**：无请求时 Pod 数为 0，请求来时由 Knative Activator 队列缓冲并冷启动。
- 默认 autoscaler 是 Knative Pod Autoscaler（KPA），基于并发请求数。
- 适合：开发测试、负载波动大、能接受冷启动。

### RawDeployment（原生 K8s）

```yaml
metadata:
  annotations:
    serving.kserve.io/deploymentMode: RawDeployment
    serving.kserve.io/autoscalerClass: hpa
    serving.kserve.io/metric: cpu
    serving.kserve.io/targetUtilizationPercentage: "60"
```

- KServe controller 直接创建 K8s `Deployment` + `Service` + `Ingress`。
- 用 HPA/KEDA 扩缩，**不支持缩到零**（`minReplicas >= 1`）。
- 无 Knative queue-proxy，延迟更低。
- 适合：生产推理、GPU 模型（冷启动成本极高）、 latency-sensitive。

**生产常用**：GPU/LLM 推理几乎都用 RawDeployment，因为冷启动（模型加载几分钟）无法忍受；开发环境可用 Serverless 省资源。

## 2.7 KServe 的"心智模型"

把前几节组合起来，一个完整的 KServe 心智模型：

```
用户写 InferenceService
        │
        ▼
KServe Controller (kserve-controller-manager)
        │ 1. 选 runtime（modelFormat → ServingRuntime/ClusterServingRuntime）
        │ 2. 按 deploymentMode 创建 Knative Service 或 K8s Deployment+Service+Ingress
        │ 3. 注入 storage initContainer（storageUri → /mnt/models）
        │ 4. 配置 transformer/explainer sidecar
        │ 5. 设置 HPA/KPA/KEDA
        ▼
运行中的 Predictor (+ Transformer/Explainer)
        │
        ▼
Ingress/Gateway 暴露 /v1、/v2、/openai/v1 端点
        │
        ▼
客户端调用（无需关心 backend runtime）
```

## 本章小结

- **`InferenceService`** 是用户入口，描述 predictor/transformer/explainer 和扩缩/金丝雀策略。
- **`ServingRuntime`/`ClusterServingRuntime`** 把模型格式映射到容器实现，支持自定义 runtime。
- **`InferenceGraph`** 把多个模型组合成 Sequence/Switch/Ensemble/Splitter 工作流。
- **三种数据面协议**：V1（传统）、V2（Open Inference Protocol，张量标准化）、OpenAI-compatible（LLM）。
- **两种部署模式**：Serverless/Knative（缩到零、低利用率场景）和 RawDeployment（生产 GPU、低延迟）。
- 心智模型：IS → controller 选 runtime → 创建 workload → 接入流量 → 客户端按统一协议调用。

**参考来源**

- [KServe — InferenceService API](https://kserve.github.io/website/docs/get_started/first_isvc/)
- [KServe — ServingRuntime](https://kserve.github.io/website/docs/concepts/resources/servingruntime/)
- [KServe — InferenceGraph](https://kserve.github.io/website/docs/concepts/resources/inference_graph/)
- [KServe — Data Plane / V2 Protocol](https://kserve.github.io/website/docs/concepts/data_plane/)
- [Open Inference Protocol](https://github.com/kserve/open-inference-protocol)

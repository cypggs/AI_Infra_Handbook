# 6. 源码分析

> 一句话理解：KServe 的源码是**一个典型的 controller-runtime 大型 Operator**——`cmd` 启动 manager，多个 controller 注册到 manager，每个 controller 的 reconciler 通过调用多个子 reconciler 完成 `InferenceService` 的全生命周期渲染。

## 6.1 仓库结构

```
kserve/kserve
├── cmd/
│   └── manager/                 # kserve-controller-manager 入口
│       └── main.go
├── pkg/
│   ├── apis/
│   │   └── serving/
│   │       ├── v1alpha1/        # ServingRuntime / ClusterServingRuntime / InferenceGraph / TrainedModel
│   │       └── v1beta1/         # InferenceService CRD
│   ├── client/
│   │   └── clientset/           # 自动生成的 typed client
│   ├── constants/
│   │   └── constants.go         # 注解、label、端口、环境变量等常量
│   ├── controller/
│   │   └── v1beta1/
│   │       └── inferenceservice/ # InferenceService Controller
│   ├── webhook/
│   │   └── admission/           # defaulting / validating / mutating webhook
│   ├── modelconfig/             # runtime 配置相关
│   ├── utils/                   # 通用工具
│   └── ...
├── config/                      # Kustomize manifests
│   ├── default/
│   ├── manager/
│   ├── webhook/
│   └── overlays/
├── docs/
└── python/
    └── kserve/                  # KServe Python SDK（runtime 开发包）
```

## 6.2 入口：`cmd/manager/main.go`

主函数做几件标准 controller-runtime 的事：

```go
func main() {
    // 1. 解析 flag：metrics addr、probe addr、leader election、webhook port 等
    // 2. 创建 scheme，注册 v1alpha1/v1beta1 CRD
    // 3. 创建 manager（cache + client + leader election + metrics + health probes）
    // 4. 注册 InferenceService controller
    // 5. 注册 ServingRuntime / ClusterServingRuntime / InferenceGraph controller
    // 6. 如果是 webhook 模式，注册 webhook handler
    // 7. mgr.Start(ctx)
}
```

关键点：

- 同时支持 controller 和 webhook，可通过参数开关。
- 使用 controller-runtime 的 `Manager` 统一管 cache、client、leader election。
- scheme 注册所有 KServe API group。

## 6.3 CRD 定义

### `pkg/apis/serving/v1beta1/inference_service_types.go`

`InferenceServiceSpec` 是用户-facing 的核心结构：

```go
type InferenceServiceSpec struct {
    Predictor   PredictorSpec   `json:"predictor"`
    Transformer *TransformerSpec `json:"transformer,omitempty"`
    Explainer   *ExplainerSpec   `json:"explainer,omitempty"`
}

type PredictorSpec struct {
    ComponentExtensionSpec
    Model *ModelSpec `json:"model,omitempty"`
    // 老版框架字段保留兼容
    SKLearn   *SKLearnSpec   `json:"sklearn,omitempty"`
    XGBoost   *XGBoostSpec   `json:"xgboost,omitempty"`
    Tensorflow *TensorflowSpec `json:"tensorflow,omitempty"`
    PyTorch   *PyTorchSpec   `json:"pytorch,omitempty"`
    Triton    *TritonSpec    `json:"triton,omitempty"`
    ...
}

type ModelSpec struct {
    ModelFormat       *ModelFormatSpec       `json:"modelFormat,omitempty"`
    Runtime           *string                `json:"runtime,omitempty"`
    StorageURI        *string                `json:"storageUri,omitempty"`
    ProtocolVersion   *constants.Protocol    `json:"protocolVersion,omitempty"`
    Resources         v1.ResourceRequirements `json:"resources,omitempty"`
}
```

### `pkg/apis/serving/v1alpha1/serving_runtime_types.go`

`ServingRuntimeSpec` 描述 runtime 元数据：

```go
type ServingRuntimeSpec struct {
    SupportedModelFormats []SupportedModelFormat `json:"supportedModelFormats"`
    ProtocolVersions      []constants.Protocol   `json:"protocolVersions,omitempty"`
    Containers            []Container            `json:"containers"`
    ...
}

type SupportedModelFormat struct {
    Name       string `json:"name"`
    Version    *string `json:"version,omitempty"`
    AutoSelect *bool  `json:"autoSelect,omitempty"`
    Priority   *int32 `json:"priority,omitempty"`
}
```

## 6.4 InferenceService Controller Reconcile 链路

主 reconciler 在 `pkg/controller/v1beta1/inferenceservice/controller.go`：

```go
func (r *InferenceServiceReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
    // 1. 获取 IS
    isvc := &v1beta1.InferenceService{}
    if err := r.Client.Get(ctx, req.NamespacedName, isvc); err != nil {
        return ctrl.Result{}, client.IgnoreNotFound(err)
    }

    // 2. 处理 finalizer
    if isvc.ObjectMeta.DeletionTimestamp.IsZero() {
        if !utils.ContainsString(isvc.ObjectMeta.Finalizers, finalizerName) {
            isvc.ObjectMeta.Finalizers = append(isvc.ObjectMeta.Finalizers, finalizerName)
            return ctrl.Result{}, r.Client.Update(ctx, isvc)
        }
    } else {
        return r.finalize(ctx, isvc)
    }

    // 3. 初始化 status conditions
    isvc.Status.InitializeConditions()

    // 4. 调用各子 reconciler
    reconcileResult, err := r.ReconcileHandler.Reconcile(ctx, log, isvc)

    // 5. 写回 status
    if statusErr := r.Client.Status().Update(ctx, isvc); statusErr != nil {
        return reconcileResult, statusErr
    }
    return reconcileResult, err
}
```

### `ReconcileHandler` 的实现

`pkg/controller/v1beta1/inferenceservice/reconciler.go`：

```go
func (r *Reconciler) Reconcile(ctx context.Context, logger logr.Logger, isvc *v1beta1.InferenceService) (ctrl.Result, error) {
    // 4.1 Predictor
    predictorResult, err := r.predictorReconciler.Reconcile(ctx, isvc)
    isvc.Status.PropagatePredictorStatus(predictorResult, err)

    // 4.2 Transformer
    if isvc.Spec.Transformer != nil {
        transformerResult, err := r.transformerReconciler.Reconcile(ctx, isvc)
        isvc.Status.PropagateTransformerStatus(transformerResult, err)
    }

    // 4.3 Explainer
    if isvc.Spec.Explainer != nil {
        explainerResult, err := r.explainerReconciler.Reconcile(ctx, isvc)
        isvc.Status.PropagateExplainerStatus(explainerResult, err)
    }

    // 4.4 Ingress
    ingressResult, err := r.ingressReconciler.Reconcile(ctx, isvc)
    isvc.Status.PropagateIngressStatus(ingressResult, err)

    // 4.5 Autoscaler
    if _, err := r.autoscalerReconciler.Reconcile(ctx, isvc); err != nil {
        return ctrl.Result{}, err
    }

    return ctrl.Result{}, nil
}
```

每个子 reconciler 内部再调用 creator/reconciler，如 `RawKubeReconciler` 或 `KnativeServiceReconciler`。

## 6.5 Predictor Reconciler：runtime 选择与 Pod 渲染

`pkg/controller/v1beta1/inferenceservice/components/predictor.go`：

```go
func (p *Predictor) Reconcile(ctx context.Context, isvc *v1beta1.InferenceService) (*v1alpha1.ComponentStatusSpec, error) {
    // 1. 解析 deployment mode
    deploymentMode := isvcutils.GetDeploymentMode(isvc.Metadata.Annotations)

    // 2. 选 runtime
    runtime, err := p.runtimeResolver.ResolveRuntime(isvc, isvc.Spec.Predictor.Model, deploymentMode)
    if err != nil {
        return nil, err
    }

    // 3. 渲染 PodSpec
    podSpec, err := p.PodSpecBuilder.BuildPodSpec(runtime, isvc, isvc.Spec.Predictor, constants.InferenceServiceContainerName)
    if err != nil {
        return nil, err
    }

    // 4. 根据 deploymentMode 创建 workload
    if deploymentMode == constants.Serverless {
        return p.knativeServiceReconciler.Reconcile(ctx, isvc, podSpec)
    }
    return p.rawDeploymentReconciler.Reconcile(ctx, isvc, podSpec)
}
```

### Runtime Resolver

`pkg/controller/v1beta1/inferenceservice/utils/utils.go` 或类似位置：

```go
func (r *RuntimeResolver) ResolveRuntime(...) (*v1alpha1.ServingRuntime, error) {
    // 列出所有 ClusterServingRuntime / ServingRuntime
    // 按 modelFormat + autoSelect + priority 排序
    // 返回最佳匹配
}
```

### PodSpecBuilder

`pkg/controller/v1beta1/inferenceservice/reconcilers/knative/ksvc_reconciler.go` / `raw/raw_reconciler.go`：

- 注入 storage-initializer init container。
- 注入 runtime container。
- 设置 volume/volumeMount。
- 设置 readiness probe。
- 设置 resource requests/limits。

## 6.6 Webhook 源码

### Defaulting

`pkg/webhook/admission/inferenceservice/defaulter.go`：

```go
func (m *Defaulter) Default(ctx context.Context, obj runtime.Object) error {
    isvc := obj.(*v1beta1.InferenceService)

    // 给 predictor model 补默认值
    if isvc.Spec.Predictor.Model != nil {
        if isvc.Spec.Predictor.Model.ProtocolVersion == nil {
            // 根据 runtime 默认协议
        }
    }

    // 选默认 runtime
    m.setDefaultRuntime(isvc)
    return nil
}
```

### Validating

`pkg/webhook/admission/inferenceservice/validator.go`：

```go
func (v *Validator) ValidateCreate(ctx context.Context, obj runtime.Object) error {
    isvc := obj.(*v1beta1.InferenceService)
    // 校验 storageUri
    // 校验 canaryTrafficPercent
    // 校验 modelFormat
    return nil
}
```

## 6.7 Ingress Reconciler

`pkg/controller/v1beta1/inferenceservice/reconcilers/ingress/`：

- `ingress_reconciler.go`：根据 deploymentMode 选择 Knative ingress 或 RawDeployment ingress。
- `istio_virtual_service.go`：生成 Istio VirtualService。
- `knative_ingress_reconciler.go`：处理 Knative 域名与 traffic split。

关键逻辑：

```go
func (ir *IngressReconciler) Reconcile(ctx context.Context, isvc *v1beta1.InferenceService) (*v1alpha1.IngressStatus, error) {
    if isvcutils.GetDeploymentMode(isvc.Annotations) == constants.Serverless {
        return ir.knativeIngress.Reconcile(ctx, isvc)
    }
    return ir.rawIngress.Reconcile(ctx, isvc)
}
```

## 6.8 Autoscaler Reconciler

`pkg/controller/v1beta1/inferenceservice/reconcilers/autoscaler/`：

- `autoscaler_reconciler.go`：根据 annotations 决定创建 HPA 还是 Knative PA。
- `hpa.go`：生成 HPA v2。
- `podautoscaler.go`：更新 Knative Service annotations。

## 6.9 关键设计模式

### 1. 子 Reconciler 组合

KServe 没有一个大而全的 reconcile 函数，而是拆成多个子 reconciler：predictor、transformer、explainer、ingress、autoscaler。每个子 reconciler 只负责自己的资源，status 再合并。

### 2. Deployment Mode 抽象

通过 annotations 切换 Serverless/RawDeployment，底层用不同的 reconciler 实现同一接口。这是典型的策略模式。

### 3. Runtime 模板化

`ServingRuntime` 用 Go template 描述容器，controller 在 reconcile 时填充变量。这种"配置即代码"的方式让平台扩展 runtime 不需要改 controller 代码。

### 4. Status 聚合

IS status 不是底层资源 status 的简单复制，而是经过语义聚合：

- `PredictorReady` 来自 Knative Service / Deployment 状态。
- `IngressReady` 来自 VirtualService / Ingress 状态。
- `Ready` 是所有 condition 的 AND。

## 6.10 源码阅读建议

如果你是第一次读 KServe 源码，建议按这个顺序：

1. `pkg/apis/serving/v1beta1/inference_service_types.go` —— 先看数据结构。
2. `cmd/manager/main.go` —— 再看入口和 manager 组装。
3. `pkg/controller/v1beta1/inferenceservice/controller.go` —— 主 reconcile 流程。
4. `pkg/controller/v1beta1/inferenceservice/components/predictor.go` —— runtime 选择与 Pod 渲染。
5. `pkg/controller/v1beta1/inferenceservice/reconcilers/` —— 看各子 reconciler。
6. `pkg/webhook/admission/inferenceservice/` —— webhook 逻辑。
7. `config/manager/` —— Kustomize 部署配置。

## 本章小结

- **仓库结构**：`cmd/manager` 入口、`pkg/apis` CRD、`pkg/controller` 控制器、`pkg/webhook` webhook、`python/kserve` SDK。
- **主 reconcile 链路**：Get IS → finalizer → init conditions → 子 reconciler → update status。
- **子 reconciler**：predictor、transformer、explainer、ingress、autoscaler 各司其职。
- **runtime 选择**：`RuntimeResolver` 扫描 ServingRuntime，按 modelFormat + autoSelect + priority 匹配。
- **Pod 渲染**：`PodSpecBuilder` 注入 runtime container + storage-initializer + sidecar。
- **模式**：子 reconciler 组合、deployment mode 策略、runtime 模板化、status 聚合。

**参考来源**

- [KServe GitHub — kserve/kserve](https://github.com/kserve/kserve)
- [KServe — Python SDK](https://kserve.github.io/website/sdk_docs/sdk_doc/)
- controller-runtime 设计模式（本手册 [Operator 模式](../../02-cloud-native/operator/)）

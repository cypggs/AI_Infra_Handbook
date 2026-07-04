# 7. Mini Demo：用纯 Python 模拟 KServe 控制面

> 一句话理解：这个 Demo 不依赖 K8s、Knative、GPU 或真实模型，而是在纯 Python 里复现 **runtime 选择 → reconcile 渲染 → 网关路由 → 金丝雀切流 → 自动扩缩** 的完整控制面链路。

## 7.1 Demo 设计目标

本 Demo 聚焦 KServe 区别于普通 Operator 的核心能力：

1. **Runtime 注册表**：根据 `modelFormat.name` 自动匹配 `ServingRuntime`。
2. **Reconcile 渲染**：把 `InferenceService` 翻译成 `Deployment` + `Service` + `Ingress` + `HPA`。
3. **数据面模拟**：一个 FakeModelServer 按协议（V1/V2/OpenAI）返回固定结果。
4. **网关与金丝雀**：按 `canaryTrafficPercent` 把流量拆分给新旧 revision。
5. **自动扩缩**：HPA 根据负载调整 replica 数量。

## 7.2 目录结构

```
docs/03-ai-platform/kserve/mini-demo/
├── pyproject.toml
├── README.md
├── kserve_mini/
│   ├── __init__.py
│   ├── model.py          # InferenceService / ServingRuntime / Deployment / Service / Ingress / HPA 数据结构
│   ├── registry.py       # RuntimeRegistry：runtime 匹配
│   ├── controller.py     # KServeController：reconcile 链
│   ├── dataplane.py      # FakeModelServer：模拟 model server
│   ├── gateway.py        # Gateway：请求路由 + canary split
│   ├── autoscaler.py     # HPA：根据负载扩缩
│   └── demo.py           # 入口：run_demo()
└── tests/
    ├── __init__.py
    ├── test_registry.py
    ├── test_controller.py
    ├── test_gateway.py
    ├── test_autoscaler.py
    └── test_demo.py
```

## 7.3 运行方式

```bash
cd docs/03-ai-platform/kserve/mini-demo
pip install -e ".[dev]"
pytest tests/ -v
python -m kserve_mini.demo
```

## 7.4 关键代码片段

### Runtime 匹配

```python
class RuntimeRegistry:
    def __init__(self):
        self.runtimes: list[ServingRuntime] = []

    def register(self, runtime: ServingRuntime):
        self.runtimes.append(runtime)

    def resolve(self, model_format: str, requested: str | None = None) -> ServingRuntime:
        if requested:
            for r in self.runtimes:
                if r.name == requested:
                    return r
            raise RuntimeNotFound(requested)
        candidates = [
            r for r in self.runtimes
            if any(f.name == model_format and f.auto_select for f in r.supported_formats)
        ]
        if not candidates:
            raise RuntimeNotFound(model_format)
        return max(candidates, key=lambda r: r.priority)
```

### Reconciler：IS → 底层资源

```python
class KServeController:
    def reconcile(self, isvc: InferenceService) -> ReconcileResult:
        runtime = self.registry.resolve(
            isvc.predictor.model_format,
            isvc.predictor.runtime,
        )
        deployment = self.build_deployment(isvc, runtime)
        service = self.build_service(isvc)
        ingress = self.build_ingress(isvc)
        hpa = self.build_hpa(isvc)
        return ReconcileResult(
            deployment=deployment,
            service=service,
            ingress=ingress,
            hpa=hpa,
            url=f"http://{isvc.name}.{isvc.namespace}.example.com",
        )
```

### 网关：Canary 切流

```python
class Gateway:
    def __init__(self, backend: FakeModelServer):
        self.backend = backend
        self.versions: dict[str, float] = {}  # version -> weight

    def route(self, request: Request) -> Response:
        version = random.choices(
            population=list(self.versions.keys()),
            weights=list(self.versions.values()),
        )[0]
        return self.backend.predict(version, request)
```

### HPA 扩缩

```python
class HorizontalPodAutoscaler:
    def decide_replicas(self, current: int, load: float) -> int:
        # load: 0.0 ~ 1.0 表示当前利用率
        if load > self.target:
            return min(self.max_replicas, current + 1)
        if load < self.target * 0.8 and current > self.min_replicas:
            return max(self.min_replicas, current - 1)
        return current
```

## 7.5 Demo 场景

`python -m kserve_mini.demo` 会执行：

1. 注册两个 `ServingRuntime`：`kserve-sklearnserver`、`kserve-huggingfaceserver`。
2. 用户 apply 一个 sklearn `InferenceService`。
3. Controller reconcile，生成 Deployment/Service/Ingress/HPA。
4. 模拟请求：1000 次调用，观察 HPA 把 replica 从 1 扩到 5。
5. 用户更新 IS，切换新模型版本并设置 `canaryTrafficPercent: 30`。
6. 模拟请求：70% 到老版本，30% 到新版本。
7. 输出最终状态：URL、replicas、canary 比例。

## 7.6 与真实 KServe 的差异

| 真实 KServe | 本 Demo |
|---|---|
| 运行在真实 K8s + Knative | 纯 Python 内存对象 |
| 真实 runtime 容器 | `FakeModelServer` 固定返回 |
| storage-initializer 下载模型 | 跳过，直接假设模型已挂载 |
| Istio/Contour 网关 | `Gateway` 类做加权随机 |
| GPU 调度/显存 | 不涉及 |
| Knative scale-to-zero | 用 HPA 简化模拟 |

## 7.7 测试覆盖

| 测试文件 | 覆盖点 |
|---|---|
| `test_registry.py` | runtime 自动选择、显式指定、找不到时抛异常 |
| `test_controller.py` | reconcile 输出 Deployment/Service/Ingress/HPA；status URL 正确 |
| `test_gateway.py` | canary 比例符合预期；V1/V2/OpenAI 协议路由 |
| `test_autoscaler.py` | 负载高扩、负载低缩、min/max 边界 |
| `test_demo.py` | 端到端 `run_demo()` 成功，输出包含预期字段 |

## 本章小结

- Mini Demo 用纯 Python 复现 KServe 控制面的核心链路，无需 K8s/Knative/GPU。
- 重点展示：runtime 选择、reconcile 渲染、网关 canary、HPA 扩缩。
- 测试覆盖 registry/controller/gateway/autoscaler/端到端。
- 与真实 KServe 的差异明确说明，帮助读者理解 Demo 只是教学模型。

**下一步**：进入 `docs/03-ai-platform/kserve/mini-demo/` 运行 `pytest tests/ -v` 验证。

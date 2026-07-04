# KServe Mini Demo

一个纯 Python 的 KServe 控制面教学模型，覆盖：

- `ServingRuntime` 注册与自动匹配
- `InferenceService` reconcile 生成 `Deployment`/`Service`/`Ingress`/`HPA`
- 假数据面 `FakeModelServer` 支持 V1/V2/OpenAI 协议
- 网关层 canary 切流
- HPA 自动扩缩

## 运行

```bash
cd docs/03-ai-platform/kserve/mini-demo
pip install -e ".[dev]"
pytest tests/ -v
python -m kserve_mini.demo
```

## 模块说明

| 文件 | 职责 |
|---|---|
| `kserve_mini/model.py` | 内存 CRD 数据结构 |
| `kserve_mini/registry.py` | RuntimeRegistry |
| `kserve_mini/controller.py` | KServeController reconcile |
| `kserve_mini/dataplane.py` | FakeModelServer |
| `kserve_mini/gateway.py` | Gateway 路由与 canary |
| `kserve_mini/autoscaler.py` | HPA 决策 |
| `kserve_mini/demo.py` | 端到端演示 |

> 注意：本 Demo 仅用于教学，**不是**真实 KServe 实现。真实 KServe 运行在 Kubernetes + Knative 上，管理真实容器与网关。

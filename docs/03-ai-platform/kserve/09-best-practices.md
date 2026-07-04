# 9. 最佳实践

> 一句话理解：KServe 的强大来自抽象，但抽象用不好也会藏坑——**从 runtime 选型到请求大小、超时、错误处理、安全**，每一环都有明确的最佳实践。

## 9.1 Runtime 选型

| 模型类型 | 推荐 Runtime | 理由 |
|---|---|---|
| sklearn / xgboost / lightgbm | `kserve-sklearnserver` / `kserve-xgbserver` / `kserve-lgbserver` | 轻量、启动快 |
| TensorFlow SavedModel | `kserve-tensorflow` 或 Triton | TF backend 原生 |
| PyTorch TorchScript | `kserve-pytorchserver` 或 Triton | 灵活 |
| ONNX | Triton / `kserve-mlserver` | ONNX Runtime 优化 |
| 多 backend 混合 | Triton | 一个 runtime 服务多种格式 |
| LLM（通用） | `kserve-huggingfaceserver`（vLLM） | OpenAI-compatible、PagedAttention |
| LLM（NVIDIA 优化） | Triton TensorRT-LLM backend | 极致吞吐 |
| 自定义逻辑 | custom runtime + `kserve` Python SDK | 完全可控 |

### 自定义 runtime  checklist

- [ ] 实现 V1/V2/OpenAI 至少一种协议。
- [ ] 暴露 `/ready` 和 `/metrics`。
- [ ] 支持从 `/mnt/models` 加载模型。
- [ ] 提供 grace shutdown 处理。
- [ ] 镜像打进公司内部仓库。
- [ ] 注册 `ServingRuntime` 并设置 protocolVersions。

## 9.2 协议选择

- **新项目**：优先 V2（Open Inference Protocol），框架无关。
- **LLM/Chat/Agent**：必须 OpenAI-compatible，生态无敌。
- **遗留系统**：V1 兼容过渡，逐步迁移。

### 协议转换

如果多团队协议不一致，在网关层做统一转换，而不是让 runtime 同时暴露多套协议。

## 9.3 请求与响应大小

### 大输入（图像、长文本）

- 避免把 MB 级图片直接放在 JSON body 里。
- 用对象存储 URL 或 base64 分块。
- 网关层配置最大 body size（Istio 默认 1 MB，可调）。

### 大输出（LLM 长生成）

- 开 streaming：OpenAI-compatible `/chat/completions` 支持 SSE stream。
- 设置 `max_tokens` 上限。
- 网关/客户端设置合理的 read timeout。

## 9.4 超时与重试

### 超时

| 层级 | 建议 |
|---|---|
| 客户端 | 按 P99 设置，至少 > 模型推理 P99 |
| 网关 | 略高于客户端，留缓冲 |
| runtime | 内部 queue timeout 与网关对齐 |

### 重试

- 幂等请求（只读推理）可配置 1-2 次重试。
- 非幂等请求（带副作用）不重试。
- 对 503/504 重试，对 400/422 不重试。

## 9.5 错误处理

### Runtime 侧

- 返回标准 HTTP status：
  - `200` 成功
  - `400` 请求格式错误
  - `404` 模型不存在
  - `422` 输入校验失败
  - `500` 内部错误
  - `503` 模型未就绪或过载

- 错误体统一格式：

```json
{
  "error": "Model not ready",
  "code": 503,
  "model": "llama-3"
}
```

### Controller 侧

- IS status conditions 必须明确失败原因：
  - `RuntimeNotFound`
  - `StorageDownloadFailed`
  - `ImagePullBackOff`
  - `IngressNotConfigured`

## 9.6 安全

### 镜像安全

- runtime 镜像只从可信仓库拉取。
- 定期扫描镜像漏洞。
- 使用非 root 用户运行 model server。

### 模型安全

- `storageUri` 中的 credential 不硬编码。
- 用 K8s ServiceAccount + 云 IAM（IRSA / Workload Identity）。
- 敏感模型限制 namespace 内访问。

### 网络安全

- 模型 Pod 不直接暴露公网。
- Ingress 层加 TLS。
- Istio mTLS 保护服务间通信。
- Gateway 层做 rate limiting。

## 9.7 资源请求与限制

### CPU 模型

```yaml
resources:
  requests:
    cpu: "1"
    memory: "2Gi"
  limits:
    cpu: "2"
    memory: "4Gi"
```

### GPU 模型

```yaml
resources:
  limits:
    nvidia.com/gpu: 2
  requests:
    nvidia.com/gpu: 2
```

- GPU 必须 requests == limits，否则调度不稳定。
- 大模型按 tensor-parallel-size 配置 GPU 数。

## 9.8 测试策略

| 测试 | 工具/方法 |
|---|---|
| 单元测试 | 自定义 runtime 内部逻辑 |
| 集成测试 | `kubectl apply` 到测试集群，curl 验证 |
| 协议一致性 | 用 Open Inference Protocol 测试集 |
| 性能测试 | k6 / locust / vegeta |
| 金丝雀测试 | 小流量切流 + 输出 diff |
| 混沌测试 | 随机 kill Pod，验证自动恢复 |

## 9.9 避免过度规划

KServe 能做的事情很多，但不要因为能做得多就全做：

- 单模型 poc 不需要 `InferenceGraph`。
- 小团队不需要自研 runtime。
- 没有多框架需求时不需要 Triton。

**从简单开始，只在痛点出现时引入复杂度。**

## 本章小结

- **Runtime 选型**：按模型类型选，复杂场景用 Triton，LLM 用 vLLM/TRT-LLM。
- **协议统一**：新项目 V2，LLM OpenAI-compatible。
- **请求/响应**：避免超大 body，LLM 用 streaming。
- **超时/重试**：分层设置，幂等才重试。
- **错误处理**：标准 HTTP code + 统一错误体 + 清晰 status condition。
- **安全**：可信镜像、IAM 拉模型、TLS/mTLS、限流。
- **资源**：GPU requests=limits；CPU 合理预留。
- **测试**：单元 + 集成 + 性能 + 金丝雀 + 混沌。
- **原则**：从简单开始，按需引入复杂度。

**参考来源**

- [KServe — Best Practices](https://kserve.github.io/website/docs/modelserving/)
- [Open Inference Protocol](https://github.com/kserve/open-inference-protocol)
- [vLLM Production Tips](https://docs.vllm.ai/en/latest/serving/production.html)

# 源码与生态分析

AI 安全领域涌现了大量开源项目。理解它们的设计取舍，有助于在实际架构中做出正确选择。

## 1. OPA（Open Policy Agent）

- **定位**：通用策略引擎，用 Rego 语言描述策略，以 sidecar 或独立服务方式提供授权决策。
- **核心概念**：Policy、Data、Query。OPA 接收 JSON 输入，返回 allow/deny 决策。
- **AI 场景**：LLM Gateway 中的路由/限流/授权、Agent 工具调用审批、RAG 多租户数据访问。
- **源码入口**：`cmd/run.go` 启动 server，`rego/rego.go` 编译与执行 Rego。
- **优势**：与语言无关、高性能、生态丰富。
- **劣势**：Rego 学习曲线陡峭，复杂关系授权不如 OpenFGA 自然。

```rego
package llm.auth

import future.keywords.if
import future.keywords.in

default allow := false

allow if {
    input.user.role == "developer"
    input.action == "llm:chat"
    input.model in ["gpt-mini", "claude-haiku"]
}
```

## 2. OpenFGA

- **定位**：Google 开源的 Relationship-Based Access Control（ReBAC）引擎。
- **核心概念**：Authorization Model、Tuples、Stores、Check API。
- **AI 场景**：多用户共享项目/文档/RAG 集合、Agent 之间的 capability 委托。
- **源码入口**：`pkg/server` 提供 gRPC/HTTP，`pkg/tuple` 处理关系元组。
- **优势**：天然表达“用户 U 是文档 D 的 editor”这类关系。
- **劣势**：相对年轻，生态不如 OPA 成熟。

```python
# 伪代码：OpenFGA Check
body = {
    "tuple_key": {
        "user": "user:alice",
        "relation": "viewer",
        "object": "document:report-2025",
    }
}
response = openfga_client.check(body)
```

## 3. HashiCorp Vault

- **定位**：密钥与敏感数据管理平台。
- **核心引擎**：KV、PKI、Transit（加密即服务）、AWS/GCP/Azure 动态凭证、Database 动态凭证。
- **AI 场景**：
  - 存储 LLM provider API key，按租户/环境隔离。
  - Transit 引擎加密模型权重或 Embedding。
  - PKI 引擎签发服务间 mTLS 证书。
- **源码入口**：`vault/` 核心逻辑，`builtin/` 各引擎实现。
- **优势**：功能全面、高可用、生态成熟。
- **劣势**：自托管运维复杂，cloud 托管版成本不低。

## 4. SPIFFE / SPIRE

- **定位**：工作负载身份标准（SPIFFE）与实现（SPIRE）。
- **核心概念**：SVID（SPIFFE Verifiable Identity Document）、Trust Domain、Workload Attestation。
- **AI 场景**：为 K8s Pod、VM、容器颁发短期身份，服务间通过 mTLS 互相认证。
- **源码入口**：`pkg/server`、 `pkg/agent`。
- **优势**：与云厂商无关，解决“服务账号泛滥”问题。
- **劣势**：需要改造服务调用方式，落地周期较长。

## 5. Istio / Envoy

- **定位**：Service Mesh，提供服务间 mTLS、授权策略、可观测。
- **核心安全资源**：PeerAuthentication、RequestAuthentication、AuthorizationPolicy。
- **AI 场景**：
  - 推理服务与向量库之间强制 mTLS。
  - 按 namespace/service account 限制访问。
  - egress gateway 控制外部模型 API 访问。
- **源码入口**：Istio `pilot/pkg/security`、Envoy `source/extensions/filters/http`。
- **优势**：无需修改应用代码即可实施零信任网络。
- **劣势**：引入延迟与运维复杂度。

## 6. Microsoft Presidio

- **定位**：PII 识别与脱敏框架，支持文本与图像。
- **核心组件**：Analyzer（NER + 正则）、Anonymizer（替换/遮蔽/哈希/加密）。
- **AI 场景**：训练数据清洗、Prompt/Response 日志脱敏、RAG 片段 PII 处理。
- **源码入口**：`presidio-analyzer`、`presidio-anonymizer`。
- **优势**：可扩展、支持自定义识别器。
- **劣势**：纯本地部署对多语言支持有限，性能不如专用云服务。

```python
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()
results = analyzer.analyze(text="My email is alice@example.com", language="en")
print(anonymizer.anonymize(text="My email is alice@example.com", analyzer_results=results).text)
```

## 7. Llama Guard / NeMo Guardrails

- **Llama Guard**：Meta 发布的输入/输出安全分类模型，基于 LLM 做 fine-grained 有害内容检测。
- **NeMo Guardrails**：NVIDIA 开源的 Guardrails 框架，通过 YAML/Colang 定义对话策略与护栏。
- **AI 场景**：内容安全、话题限制、防止越狱、输出合规。
- **优势**：可本地部署、可针对场景微调。
- **劣势**：增加推理成本与延迟，需持续更新安全类别。

## 8. Sigstore / cosign / SLSA

- **Sigstore**：开源软件签名与透明日志生态。
- **cosign**：容器镜像与 blob 签名工具。
- **SLSA**：供应链安全框架，定义 provenance 与构建等级。
- **AI 场景**：
  - 对训练镜像、模型文件、推理镜像签名。
  - 验证模型来源与构建 provenance。
- **源码入口**：`sigstore/cosign`。
- **优势**：降低密钥管理负担，提供公开可验证性。

## 9. HuggingFace Safetensors

- **定位**：安全的模型权重序列化格式，替代 pickle-based `.bin`。
- **优势**：避免 pickle 反序列化远程代码执行风险，加载更快，支持内存映射。
- **AI 场景**：模型仓库、模型分发、推理服务加载权重。

## 10. 工具对比表

| 项目 | 主要能力 | 最佳场景 | 学习曲线 | 运维复杂度 |
|---|---|---|---|---|
| OPA | 通用策略引擎 | Gateway/Runtime 授权 | 中 | 中 |
| OpenFGA | ReBAC | 文档/项目/集合共享 | 中 | 中 |
| Vault | Secrets/加密/PKI | API Key、模型加密 | 中 | 高 |
| SPIRE | 工作负载身份 | 服务间 mTLS | 高 | 高 |
| Istio/Envoy | 零信任网络 | K8s 微服务安全 | 高 | 高 |
| Presidio | PII 识别/脱敏 | 数据清洗、日志脱敏 | 低 | 低 |
| Llama Guard | 内容安全分类 | 输入/输出过滤 | 中 | 中 |
| NeMo Guardrails | 对话策略 | Agent 行为约束 | 中 | 中 |
| Sigstore/cosign | 签名/溯源 | 镜像/模型签名 | 低 | 低 |
| Safetensors | 安全权重格式 | 模型存储分发 | 低 | 低 |

## 小结

开源生态覆盖了 AI 安全的大部分层面，但**没有单一工具能替代体系设计**。下一章通过 Mini Demo 展示如何把这些控制点串成一个可运行的最小闭环。

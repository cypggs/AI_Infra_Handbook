# 延伸阅读

本章汇总 AI 安全相关的权威论文、法规、官方文档、开源项目与工程文章，并给出与本手册其他主题的交叉引用。

## 权威框架与标准

- [NIST AI Risk Management Framework (AI RMF)](https://www.nist.gov/itl/ai-risk-management-framework) — NIST 发布的 AI 风险管理框架， Govern / Map / Measure / Manage 四个职能。
- [NIST SP 800-207 Zero Trust Architecture](https://csrc.nist.gov/publications/detail/sp/800-207/final) — 零信任架构的官方定义与原则。
- [OWASP Top 10 for Large Language Model Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/) — LLM 应用十大安全风险，必读。
- [OWASP Machine Learning Security Top 10](https://owasp.org/www-project-machine-learning-security-top-10/) — 传统 ML 系统安全威胁。
- [MITRE ATLAS](https://atlas.mitre.org/) — AI 系统威胁矩阵与战术技术。
- [EU AI Act](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai) — 欧盟人工智能法案官方页面。
- [GDPR](https://gdpr-info.eu/) — 欧盟通用数据保护条例。
- [中国《生成式人工智能服务管理暂行办法》](http://www.cac.gov.cn/2023-07/13/c_1690898327029107.htm) — 国内生成式 AI 监管文件。

## 身份与访问

- [Open Policy Agent 官方文档](https://www.openpolicyagent.org/docs/latest/)
- [OpenFGA 官方文档](https://openfga.dev/docs)
- [Cedar 授权语言](https://www.cedarpolicy.com/)
- [SPIFFE / SPIRE](https://spiffe.io/) — 工作负载身份标准。
- [Keycloak 官方文档](https://www.keycloak.org/documentation)
- [Ory Kratos / Hydra](https://www.ory.sh/) — 开源身份与 OAuth 基础设施。

## 密钥与供应链

- [HashiCorp Vault 文档](https://developer.hashicorp.com/vault/docs)
- [Sigstore](https://www.sigstore.dev/) — 开源软件签名生态。
- [cosign 文档](https://docs.sigstore.dev/cosign/overview/)
- [SLSA](https://slsa.dev/) — 供应链安全框架。
- [HuggingFace Safetensors](https://huggingface.co/docs/safetensors/index) — 安全模型权重格式。
- [Kubernetes external-secrets](https://external-secrets.io/latest/)

## 网络与零信任

- [Istio Security 文档](https://istio.io/latest/docs/concepts/security/)
- [Cilium 文档](https://docs.cilium.io/en/stable/)
- [Google BeyondCorp](https://cloud.google.com/beyondcorp)
- [Cloudflare Zero Trust](https://www.cloudflare.com/zero-trust/)
- [Teleport](https://goteleport.com/) — 零信任访问平台。
- [OpenZiti](https://openziti.io/) — 开源零信任网络覆盖层。

## 数据隐私与 Guardrails

- [Microsoft Presidio](https://microsoft.github.io/presidio/)
- [Llama Guard 论文 / HuggingFace](https://ai.meta.com/research/publications/llama-guard-llm-based-input-output-safeguard-for-human-ai-conversations/)
- [NeMo Guardrails](https://github.com/NVIDIA/NeMo-Guardrails)
- [Guardrails AI](https://www.guardrailsai.com/)
- [OpenAI Moderation API](https://platform.openai.com/docs/guides/moderation)
- [Azure AI Content Safety](https://azure.microsoft.com/en-us/products/ai-services/ai-content-safety)

## 红队与评估

- [PyRIT](https://github.com/Azure/PyRIT) — 微软开源的生成式 AI 红队工具。
- [Garak](https://github.com/leondz/garak) — LLM 漏洞扫描工具。
- [Anthropic Responsible Scaling Policy](https://www.anthropic.com/research/responsible-scaling-policy)
- [OpenAI Preparedness Framework](https://openai.com/index/introducing-the-preparedness-framework/)

## 论文

- **ReAct**: *Synergizing Reasoning and Acting in Language Models* — 虽然主题是 Agent，但其中工具调用的安全边界值得参考。
- **Llama Guard**: *Llama Guard: LLM-based Input-Output Safeguard for Human-AI Conversations* — Meta 的内容安全分类模型。
- **Tree of Thoughts** / **Chain-of-Thought** 系列 — 规划与推理中的提示注入风险。
- **Membership Inference Attacks on Machine Learning Models** — 成员推断攻击基础。
- **Model Inversion Attacks** — 模型反演攻击。

## 工程博客与案例

- Google Cloud Blog: *BeyondCorp* 系列
- Netflix Tech Blog: *Zero Trust in the Cloud*
- OpenAI / Anthropic 安全博客：红队、对齐、模型评估
- Cloudflare Blog: AI 安全与零信任实践

## 本手册交叉引用

- [LLM Gateway 详解](/04-llmops/llm-gateway/) — 统一入口、认证、限流、审计。
- [Agent Runtime 详解](/05-agent/agent-runtime/) — Agent 循环与工具权限。
- [Tool Use 详解](/05-agent/tool-use/) — 工具调用的 schema、校验与沙箱。
- [MCP 详解](/05-agent/mcp/) — 工具/资源/提示的 capability 协商。
- [RAG 详解](/06-rag/) — 向量库多租户、PII、权限隔离。
- [AI SRE 详解](/07-ai-sre/) — 安全事件的可观测性、审计、事件响应。
- [OpenAI 案例研究](/09-case-study/openai/) — 大规模 AI 服务的安全对齐、红队、合规与隐私治理实践。
- [Anthropic 案例研究](/09-case-study/anthropic/) — RSP/ASL 安全治理框架、Constitutional AI、可解释性驱动的安全监控。

## 学习路径建议

1. **概念入门**：先读 OWASP LLM Top 10 与 NIST AI RMF。
2. **架构设计**：结合本章 03-architecture 与开源项目文档，画出自己的分层架构图。
3. **动手实践**：跑通 Mini Demo，再尝试集成 OPA 或 Presidio。
4. **生产视角**：阅读 Vault、Istio、SPIRE 官方文档，设计零信任落地路径。
5. **合规治理**：研究 GDPR、AI Act、SOC2 与模型卡片，建立审计与影响评估流程。

## 小结

AI 安全是一个快速发展的交叉领域，法规、攻击技术与防御工具都在快速演进。持续关注 OWASP、NIST、MITRE ATLAS、主流云厂商与 AI 实验室的安全发布，是保持竞争力的必要投入。

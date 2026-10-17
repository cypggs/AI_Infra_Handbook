# 延伸阅读

本章汇总 AI 安全相关的权威论文、法规、官方文档、开源项目与工程文章，并给出与本手册其他主题的交叉引用。

## 权威框架与标准

- [NIST AI Risk Management Framework (AI RMF)](https://www.nist.gov/itl/ai-risk-management-framework) — NIST 发布的 AI 风险管理框架， Govern / Map / Measure / Manage 四个职能。
- [NIST SP 800-207 Zero Trust Architecture](https://csrc.nist.gov/publications/detail/sp/800-207/final) — 零信任架构的官方定义与原则。
- [OWASP Top 10 for Large Language Model Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/) — LLM 应用十大安全风险（2025 版），必读。
- [OWASP Top 10 for Agentic Applications 2026](https://genai.owasp.org/resource/agentic-applications-top-10/) — Agentic 系统十大安全风险（ASI01-ASI10，2025-12 发布）。
- [OWASP Machine Learning Security Top 10](https://owasp.org/www-project-machine-learning-security-top-10/) — 传统 ML 系统安全威胁。
- [MITRE ATLAS](https://atlas.mitre.org/) — AI 系统威胁矩阵与战术技术（2025 年起新增 Agent 专项技术）。
- [EU AI Act](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai) — 欧盟人工智能法案官方页面；[实施时间线](https://artificialintelligenceact.eu/implementation-timeline/)。
- [NIST AI 600-1 Generative AI Profile](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf) — NIST AI RMF 的生成式 AI 配套文件（2024-07）。
- [GDPR](https://gdpr-info.eu/) — 欧盟通用数据保护条例。
- [中国《生成式人工智能服务管理暂行办法》](http://www.cac.gov.cn/2023-07/13/c_1690898327029107.htm) — 国内生成式 AI 监管文件。
- [《人工智能生成合成内容标识办法》](https://www.xinhuanet.com/digital/20250902/d08b592223954340af8c02ac3d7161e1/c.html) — 2025-09-01 起施行，配套强制国标 GB 45438-2025《网络安全技术 人工智能生成合成内容标识方法》。

## 身份与访问

- [Open Policy Agent 官方文档](https://www.openpolicyagent.org/docs/latest/)
- [OpenFGA 官方文档](https://openfga.dev/docs)
- [Cedar 授权语言](https://www.cedarpolicy.com/)
- [SPIFFE / SPIRE](https://spiffe.io/) — 工作负载身份标准。
- [Keycloak 官方文档](https://www.keycloak.org/documentation)
- [Ory Kratos / Hydra](https://www.ory.sh/) — 开源身份与 OAuth 基础设施。
- [RFC 8693: OAuth 2.0 Token Exchange](https://www.rfc-editor.org/rfc/rfc8693.html) — Agent 委托链（`act` 声明）的标准基础。

## 密钥与供应链

- [HashiCorp Vault 文档](https://developer.hashicorp.com/vault/docs)
- [Sigstore](https://www.sigstore.dev/) — 开源软件签名生态。
- [cosign 文档](https://docs.sigstore.dev/cosign/overview/)
- [SLSA](https://slsa.dev/) — 供应链安全框架。
- [HuggingFace Safetensors](https://huggingface.co/docs/safetensors/index) — 安全模型权重格式。
- [Picklescan](https://github.com/mmaitre314/picklescan) / [ModelScan](https://github.com/protectai/modelscan) — 模型文件恶意代码扫描，入库 CI 门禁。
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
- [LlamaFirewall（PurpleLlama）](https://github.com/meta-llama/PurpleLlama/tree/main/LlamaFirewall) — Meta 开源的 Agent 组合护栏（Prompt Guard 2 + AlignmentCheck + CodeShield）。
- [Llama Guard 论文 / HuggingFace](https://ai.meta.com/research/publications/llama-guard-llm-based-input-output-safeguard-for-human-ai-conversations/)
- [NeMo Guardrails](https://github.com/NVIDIA/NeMo-Guardrails)
- [Guardrails AI](https://www.guardrailsai.com/)
- [OpenAI Moderation API](https://platform.openai.com/docs/guides/moderation)
- [Azure AI Content Safety](https://azure.microsoft.com/en-us/products/ai-services/ai-content-safety)
- [Cloudflare Firewall for AI](https://developers.cloudflare.com/cloudflare-one/ai-gateway/) — 边缘 LLM 请求检查。

## 红队与评估

- [PyRIT](https://github.com/Azure/PyRIT) — 微软开源的生成式 AI 红队工具。
- [Garak](https://github.com/leondz/garak) — LLM 漏洞扫描工具。
- [AgentDojo](https://github.com/ethz-spylab/agentdojo) — 工具调用 Agent 的提示注入基准（NeurIPS 2024）。
- [AgentHarm](https://huggingface.co/datasets/IBM/agentharm) — Agent 有害任务顺从度基准（ICLR 2025）。
- [PoisonedRAG](https://arxiv.org/abs/2402.07867) — 知识库投毒攻击（USENIX Security 2025）：5 份恶意文档可达约 90% 攻击成功率。
- [Anthropic Responsible Scaling Policy](https://www.anthropic.com/research/responsible-scaling-policy)
- [OpenAI Preparedness Framework](https://openai.com/index/introducing-the-preparedness-framework/)

## 论文

- **ReAct**: *Synergizing Reasoning and Acting in Language Models* — 虽然主题是 Agent，但其中工具调用的安全边界值得参考。
- **Llama Guard**: *Llama Guard: LLM-based Input-Output Safeguard for Human-AI Conversations* — Meta 的内容安全分类模型。
- **LlamaFirewall**: *LlamaFirewall: An Open Source Guardrail System for Building Secure AI Agents*（2025）— Prompt Guard 2 + AlignmentCheck + CodeShield 的组合式 Agent 防护。
- **PoisonedRAG**（USENIX Security 2025）/ **CorruptRAG** — 知识库投毒攻击与防御的代表工作。
- **MCPTox**（2025）— 真实 MCP Server 上的工具投毒基准。
- **Tree of Thoughts** / **Chain-of-Thought** 系列 — 规划与推理中的提示注入风险。
- **Membership Inference Attacks on Machine Learning Models** — 成员推断攻击基础。
- **Model Inversion Attacks** — 模型反演攻击。
- **SalUn**（ICLR 2024）与 SemEval-2025 LLM Unlearning Challenge — 机器遗忘的代表方法与评测基准。

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
- [Benchmark + Evaluation 详解](/07-ai-sre/benchmark-evaluation/) — 安全评测、red-team 评估与 Guardrails 效果回归检测。
- [Personal AI Agent 详解](/05-agent/personal-agent/) — 个人智能体的权限最小化、数据主权与隐私模型是 Agent 安全的产品化形态。
- [OpenAI 案例研究](/09-case-study/openai/) — 大规模 AI 服务的安全对齐、红队、合规与隐私治理实践。
- [Anthropic 案例研究](/09-case-study/anthropic/) — RSP/ASL 安全治理框架、Constitutional AI、可解释性驱动的安全监控。
- [Meta 案例研究](/09-case-study/meta/) — 开放权重安全治理的代表：Llama Guard 2、Prompt Guard、CyberSecEval 2、Code Shield 全部开源，GOAT 自动化红队。

## 学习路径建议

1. **概念入门**：先读 OWASP LLM Top 10（2025 版）与 OWASP Agentic Top 10，再读 NIST AI RMF / AI 600-1。
2. **架构设计**：结合本章 03-architecture 与开源项目文档，画出自己的分层架构图（含 MCP Gateway 与机密计算节点）。
3. **动手实践**：跑通 Mini Demo，再尝试集成 OPA 或 Presidio。
4. **生产视角**：阅读 Vault、Istio、SPIRE 官方文档，设计零信任与 Agent 身份落地路径。
5. **合规治理**：研究 GDPR、AI Act（含 2026-08 透明度义务）、中国标识办法、SOC2 与模型卡片，建立审计与影响评估流程。

## 小结

AI 安全是一个快速发展的交叉领域，法规、攻击技术与防御工具都在快速演进。持续关注 OWASP、NIST、MITRE ATLAS、主流云厂商与 AI 实验室的安全发布，是保持竞争力的必要投入。
